import base64
import cv2
import numpy as np


TEMPLATE_SIZE = (96, 96)
DEFAULT_TOLERANCES = {
    "template_score_max": 22.0,
    "white_ratio_tolerance": 10.0,
    "black_ratio_tolerance": 10.0,
    "gray_mean_tolerance": 25.0,
}


def extract_features(snapshot: np.ndarray, config: dict) -> dict:
    rois = config.get("dynamic_rois", {})
    disabled_rois = set(config.get("disabled_rois", []))
    refs = {}

    for name, roi in rois.items():
        if name in disabled_rois or len(roi) != 4:
            continue
        crop = _crop_roi(snapshot, roi)
        if crop is None or crop.size == 0:
            continue
        norm, edge = _prepare_roi(crop)
        refs[name] = {
            "image": _encode_png(norm),
            "edge": _encode_png(edge),
            "size": [int(crop.shape[1]), int(crop.shape[0])],
            "metrics": _roi_metrics(norm),
        }

    return refs


def update_reference_profile(profile: dict, features: dict) -> dict:
    profile = profile.copy() if profile else {"count": 0, "rois": {}}
    profile["count"] = int(profile.get("count", 0)) + 1
    roi_profiles = profile.setdefault("rois", {})

    for roi_name, roi_ref in features.items():
        roi_profile = roi_profiles.setdefault(roi_name, {"count": 0, "references": []})
        roi_profile["count"] = int(roi_profile.get("count", 0)) + 1
        refs = roi_profile.setdefault("references", [])
        refs.append(roi_ref)
        max_refs = int(profile.get("max_refs_per_roi", 10))
        if len(refs) > max_refs:
            del refs[0:len(refs) - max_refs]

    return profile


def evaluate_with_profile(snapshot: np.ndarray, config: dict) -> tuple:
    # Karar yontemi: 'hole' = dogrudan delik tespiti (yeni, varsayilan),
    # 'template' = eski sablon-benzerligi. config.yaml -> roi.decision_method
    method = str(config.get("roi", {}).get("decision_method", "hole")).lower()
    if method == "hole":
        return _evaluate_holes(snapshot, config)

    profile = config.get("reference_profile", {})
    roi_profiles = profile.get("rois", {})
    tolerances = DEFAULT_TOLERANCES.copy()
    tolerances.update(config.get("reference_tolerances", {}))
    threshold = float(tolerances.get("template_score_max", 22.0))

    current_refs = extract_features(snapshot, config)
    display_img = snapshot.copy()
    results = {}
    global_ok = False
    checked_any_roi = False

    for name, roi in config.get("dynamic_rois", {}).items():
        if name in set(config.get("disabled_rois", [])):
            continue
        checked_any_roi = True
        x1, y1, x2, y2 = _roi_bounds(snapshot, roi)
        current = current_refs.get(name)
        profile_item = roi_profiles.get(name, {})
        references = profile_item.get("references", [])

        if not current or not references:
            ok = False
            msg = "Referans ROI Yok"
        else:
            best_score = _best_template_score(current, references)
            ok = best_score <= threshold
            msg = f"skor {best_score:.1f} <= {threshold:.1f}"

        if not ok:
            global_ok = False
        results[name] = {
            "ok": ok,
            "msg": msg,
            "metrics": current.get("metrics", {}) if current else {},
            "limits": reference_metric_limits(references, tolerances),
        }
        _draw_roi_result(display_img, name, x1, y1, x2, y2, ok, msg)

    if checked_any_roi and all(res["ok"] for res in results.values()):
        global_ok = True

    global_status = "PARCA: OK" if global_ok else "PARCA: NOK (HATALI)"
    g_color = (0, 255, 0) if global_ok else (0, 0, 255)
    cv2.putText(display_img, global_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, g_color, 2, cv2.LINE_AA)
    return global_ok, results, display_img


def _evaluate_holes(snapshot: np.ndarray, config: dict) -> tuple:
    """Dogrudan delik tespiti: her ROI'de koyu (delik) piksel orani.

    Kubbe isikta delik koyu, metal acik cikar. ROI icinde sabit bir gri
    esigin altindaki piksel orani >= esik ise 'delik VAR' (OK), degilse
    'delik YOK' (NOK). Referans/ogrenme gerektirmez; tek esikle ayarlanir.
    Sablon yontemine gore konum/donme/aydinlatmaya cok daha toleranslidir.
    """
    roi_cfg = config.get("roi", {})
    dark_value = int(roi_cfg.get("hole_dark_value", 70))
    dark_ratio_min = float(roi_cfg.get("hole_dark_ratio_min", 6.0))
    dark_ratio_max = float(roi_cfg.get("hole_dark_ratio_max", 90.0))
    # Sekil dogrulamasi: koyu bolge GERCEK yuvarlak delik mi, yoksa centik/golge mi?
    # (Salt koyu-oran, alt centik/golge gibi delik-olmayan koyu bolgeleri "delik" sanip
    #  yanlis-OK uretebiliyordu; sekil bunu eler.)
    shape_check = bool(roi_cfg.get("hole_shape_check", True))
    min_circ = float(roi_cfg.get("hole_min_circularity", 0.55))
    min_fill = float(roi_cfg.get("hole_min_fill", 0.50))
    min_aspect = float(roi_cfg.get("hole_min_aspect", 0.50))
    max_edge = int(roi_cfg.get("hole_max_edge_touch", 1))
    min_blob = float(roi_cfg.get("hole_min_blob_ratio", 3.0))
    # Delik DERINLIK kapisi (tikanmaya karsi onlem): gercek acik delik cekirdegi
    # SIYAHA YAKINDIR (derin bosluk, isigi geri vermez). Yuvarlak+koyu olsa bile
    # yuzeyde duran bir tikac (koyu pul/kir/talas) bu kadar siyah olmaz. ROI'de
    # 'core_value' altindaki (cok koyu) piksel orani 'core_ratio_min'den azsa
    # delik "tikali/dolu" sayilir -> NOK. core_ratio_min=0 -> kapi kapali.
    core_value = int(roi_cfg.get("hole_core_value", 40))
    core_ratio_min = float(roi_cfg.get("hole_core_ratio_min", 2.0))
    # 'notch' (oluk/centik) tipi ROI: yuvarlak delik DEGIL; koyu bolge VAR mi?
    notch_dark_min = float(roi_cfg.get("notch_dark_min", 15.0))
    notch_dark_max = float(roi_cfg.get("notch_dark_max", 95.0))
    # Centik SEKIL kapisi (yanlis-OK onlemi): salt koyu-oran, DUZ parcadaki dagisik
    # golge/kenari da "oluk VAR" sanip OK verebiliyor (saha: oluksuz parca koyu ~%17,
    # eski esik %10 -> yanlis OK). Gercek oluk: TEK, BUYUK, YATAY-UZUN koyu yarik.
    # En buyuk koyu blob ROI'nin >= notch_min_blob_ratio'su, en/boy >= notch_min_aspect
    # (yatay), genislik ROI'nin >= notch_min_width_ratio'su olmali. Koyu-oran bandi kaba
    # kapi olarak kalir (Oluk Esigi slider'i); sekil kapisi ek guvence (isiga dayanikli).
    notch_shape_check = bool(roi_cfg.get("notch_shape_check", True))
    notch_min_blob = float(roi_cfg.get("notch_min_blob_ratio", 25.0))
    notch_min_aspect = float(roi_cfg.get("notch_min_aspect", 1.2))
    notch_min_width = float(roi_cfg.get("notch_min_width_ratio", 0.30))
    roi_types = roi_cfg.get("roi_types", {}) or {}
    # NOKTA BASINA esik override'lari (Kontrol Noktalari -> noktaya sag tik ->
    # Ayarlar): {ad: {"hole_dark_ratio_min": X}} ya da {ad: {"notch_dark_min": X}}.
    # Ayari olmayan nokta yukaridaki GLOBAL degerleri kullanir.
    point_overrides = roi_cfg.get("point_overrides", {}) or {}

    display_img = snapshot.copy()
    results = {}
    checked_any_roi = False
    sx, sy = _roi_reference_scale(snapshot, config)

    for name, roi in config.get("dynamic_rois", {}).items():
        if name in set(config.get("disabled_rois", [])) or len(roi) != 4:
            continue
        # 'yon' tipi noktalar kusur kontrolu DEGIL; sadece yon tayini olcumune
        # girer (_check_handedness). Delik/centik dongusunden atlanir.
        if _roi_type(name, roi_types) == "yon":
            continue
        checked_any_roi = True
        x1, y1, x2, y2 = _roi_bounds(snapshot, roi, sx, sy)
        crop = snapshot[y1:y2, x1:x2] if (x2 > x1 and y2 > y1) else None

        if crop is None or crop.size == 0:
            ok, msg, metrics = False, "ROI boş", {}
        else:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            dark_ratio = float(np.count_nonzero(gray < dark_value) / gray.size * 100.0)
            # Cekirdek koyulugu: siyaha-yakin (cok koyu) piksel orani (delik derinligi).
            core_ratio = float(np.count_nonzero(gray < core_value) / gray.size * 100.0)
            metrics = {
                "black_ratio": dark_ratio,
                "white_ratio": 100.0 - dark_ratio,
                "gray_mean": float(np.mean(gray)),
                "core_ratio": core_ratio,
            }
            roi_type = _roi_type(name, roi_types)
            # Bu noktanin OZEL esigi varsa onu, yoksa global degeri kullan.
            ov = point_overrides.get(name) or {}
            eff_notch_min = float(ov.get("notch_dark_min", notch_dark_min))
            eff_hole_min = float(ov.get("hole_dark_ratio_min", dark_ratio_min))
            eff_core_min = float(ov.get("hole_core_ratio_min", core_ratio_min))
            if roi_type == "notch":
                # Oluk/centik: yuvarlak delik aranmaz. Once koyu-oran bandi (kaba kapi),
                # sonra SEKIL kapisi: koyu bolge GERCEK oluk mu (tek/buyuk/yatay-uzun
                # blob), yoksa DUZ parcadaki dagisik golge mi? (Salt koyu-oran, oluksuz
                # duz parcayi yanlis "oluk VAR" OK yapabiliyordu; sekil bunu eler.)
                in_band = eff_notch_min <= dark_ratio <= notch_dark_max
                if notch_shape_check:
                    nsh = _notch_shape(gray, dark_value)
                    metrics["notch_blob"] = nsh["blob"]
                    metrics["notch_aspect"] = nsh["aspect"]
                    shape_ok = (nsh["blob"] >= notch_min_blob
                                and nsh["aspect"] >= notch_min_aspect
                                and nsh["width_ratio"] >= notch_min_width)
                    ok = in_band and shape_ok
                    if ok:
                        msg = (f"oluk VAR (koyu %{dark_ratio:.1f}, blob %{nsh['blob']:.1f}, "
                               f"en/boy {nsh['aspect']:.1f})")
                    elif not in_band:
                        msg = (f"oluk YOK (koyu %{dark_ratio:.1f} bant disi "
                               f"%{eff_notch_min:.0f}-%{notch_dark_max:.0f})")
                    else:
                        msg = (f"oluk YOK (sekil yok: blob %{nsh['blob']:.1f}<%{notch_min_blob:.0f}, "
                               f"en/boy {nsh['aspect']:.1f}, genislik {nsh['width_ratio']:.2f})")
                else:
                    ok = in_band
                    msg = (f"oluk {'VAR' if ok else 'YOK'} "
                           f"(koyu %{dark_ratio:.1f}, bant %{eff_notch_min:.0f}-%{notch_dark_max:.0f})")
            # 1) Koyu oran bandi (kaba kapi): cok az koyu -> metal dolu (delik yok);
            #    cok fazla koyu -> ROI komple koyu (arka plan/golge).
            elif dark_ratio < eff_hole_min:
                # ANA KAPI: acik (koyu) alan yetersiz -> delik yok / metal dolu /
                # KISMEN bantli-pullu (bant koyu alani azaltir). Esik kalibrasyonla
                # ayarlanir: tam acik delik yuksek (~%25), kismen kapali dusuk (~%11).
                ok = False
                msg = f"delik YOK (acik %{dark_ratio:.1f} < %{eff_hole_min:.0f}, kapali/eksik/tikali)"
            elif dark_ratio > dark_ratio_max:
                ok = False
                msg = f"delik YOK (koyu %{dark_ratio:.1f} > %{dark_ratio_max:.0f}, arka plan/golge)"
            elif core_ratio < eff_core_min:
                # 2) Derinlik kapisi: yeterince siyaha-yakin (derin) cekirdek yok ->
                #    delik tikali/dolu (yuzeyde koyu pul/kir olabilir) -> NOK.
                #    Bu kapi koyu+yuvarlak ama SIG/yansiyan tikaclari da eler.
                ok = False
                msg = (f"delik YOK (cekirdek %{core_ratio:.1f} < %{eff_core_min:.1f}, "
                       f"tikali/dolu olabilir)")
            elif shape_check:
                # Sekil dogrulamasi: koyu blob GERCEK yuvarlak/dolgun delik mi?
                #    Centik/golge -> dusuk yuvarlaklik; kismen bantli delik -> dusuk
                #    dolgu (fill = blob/cember, hilal olur ~0.5) -> NOK.
                shp = _hole_shape(gray, dark_value)
                ok = (shp["circ"] >= min_circ and shp["fill"] >= min_fill
                      and shp["aspect"] >= min_aspect and shp["edge"] <= max_edge
                      and shp["blob"] >= min_blob)
                metrics["circularity"] = shp["circ"]
                metrics["fill"] = shp["fill"]
                if ok:
                    msg = (f"delik VAR (acik %{dark_ratio:.1f}, yuvarlak {shp['circ']:.2f}, "
                           f"dolgu {shp['fill']:.2f})")
                else:
                    msg = (f"delik YOK (sekil uygun degil: yuvarlak {shp['circ']:.2f}, "
                           f"dolgu {shp['fill']:.2f}, kenar {shp['edge']})")
            else:
                ok = True
                msg = f"delik VAR (acik %{dark_ratio:.1f}, bant %{dark_ratio_min:.0f}-%{dark_ratio_max:.0f})"
        results[name] = {"ok": ok, "msg": msg, "metrics": metrics, "limits": {}}
        _draw_roi_result(display_img, name, x1, y1, x2, y2, ok, msg)

    # YON/EL kontrolu: parca dogru yonde mi yoksa AYNA (simetrik) mi?
    hand_ok, hand_msg = _check_handedness(snapshot, config)
    if hand_msg:
        results["YON"] = {"ok": hand_ok, "msg": hand_msg, "metrics": {}, "limits": {}}

    global_ok = bool(checked_any_roi and hand_ok and all(res["ok"] for res in results.values()))
    if not hand_ok:
        global_status = "PARCA: NOK (AYNA/TERS)"
    else:
        global_status = "PARCA: OK" if global_ok else "PARCA: NOK (EKSIK)"
    g_color = (0, 255, 0) if global_ok else (0, 0, 255)
    cv2.putText(display_img, global_status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, g_color, 2, cv2.LINE_AA)
    if hand_msg:
        hc = (0, 255, 0) if hand_ok else (0, 0, 255)
        cv2.putText(display_img, f"YON: {'DOGRU' if hand_ok else 'AYNA/TERS'}", (10, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, hc, 2, cv2.LINE_AA)
    return global_ok, results, display_img


def roi_point_type(name: str, roi_types: dict) -> str:
    """Kontrol noktasi tipi: 'hole' (yuvarlak delik), 'notch' (oluk/centik = varlik)
    veya 'yon' (yon tayini olcum noktasi; kusur kontrolu DEGIL). Once config
    roi_types[name]; yoksa addaki anahtar kelimeden cikarilir. Varsayilan: hole."""
    if name in roi_types:
        t = str(roi_types[name]).lower()
        return "yon" if t in ("yon", "yön", "direction") else t
    low = str(name).lower()
    if any(k in low for k in ("centik", "çentik", "oluk", "slot", "notch", "kanal")):
        return "notch"
    if any(k in low for k in ("yon", "yön", "direction")):
        return "yon"
    return "hole"


# Geriye uyum: modul ici eski ad.
_roi_type = roi_point_type


def _hole_shape(gray: np.ndarray, dark_value: int) -> dict:
    """ROI icindeki en buyuk KOYU blob'un sekil olculeri.

    Gercek delik: yuvarlak (circ~0.9), dolgun (fill~0.95), ROI kenarina degmez.
    Centik/golge: dusuk yuvarlaklik, uzun (en/boy dusuk), kenara deger.
    KISMEN bantli/pullu delik: parlak bant koyu alanin bir kismini yer -> blob
    hilal olur -> fill (blob/cember) duser (~0.5). 'fill' bunu yakalar.
    """
    dark = (gray < dark_value).astype(np.uint8) * 255
    # Delik merkezi (parlak yansima/kahve goz) acik kalabilir -> kapatip doldur.
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    h, w = gray.shape[:2]
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0.0
    for c in contours:
        area = float(cv2.contourArea(c))
        if area > best_area:
            best_area, best = area, c
    if best is None or best_area <= 0:
        return {"circ": 0.0, "fill": 0.0, "aspect": 0.0, "edge": 0, "blob": 0.0}
    perim = cv2.arcLength(best, True)
    circ = float(4.0 * np.pi * best_area / (perim * perim)) if perim > 0 else 0.0
    (_, _), r = cv2.minEnclosingCircle(best)
    fill = float(best_area / (np.pi * r * r)) if r > 0 else 0.0
    bx, by, bw, bh = cv2.boundingRect(best)
    aspect = float(min(bw, bh) / max(bw, bh)) if max(bw, bh) > 0 else 0.0
    edge = int((bx <= 1) + (by <= 1) + (bx + bw >= w - 1) + (by + bh >= h - 1))
    blob = float(best_area / (h * w) * 100.0)
    return {"circ": circ, "fill": fill, "aspect": aspect, "edge": edge, "blob": blob}


def _notch_shape(gray: np.ndarray, dark_value: int) -> dict:
    """ROI icindeki en buyuk KOYU blob'un OLUK (centik) sekil olculeri.

    Gercek oluk: TEK, BUYUK, YATAY-UZUN koyu yarik -> blob ROI'nin buyuk kismi,
    en/boy > 1 (yatay), genislik ROI genisliginin buyuk kismi.
    DUZ parca (oluk yok): koyu pikseller dagisik/ince golge -> en buyuk blob KUCUK
    ve/veya yatay-uzun degil. 'blob' (en buyuk BAGLI blob alani) ana ayirt edicidir:
    salt koyu-oran, dagisik golgeyi de toplayip yanlis "oluk VAR" verebiliyordu.
    """
    dark = (gray < dark_value).astype(np.uint8) * 255
    k = np.ones((5, 5), np.uint8)
    # OPEN once: dagisik kucuk benek/ince golge cizgilerini SIL (gercek DOLU yarik kalir,
    # dagisik golge yok olur) -> dagisik koyu yanlislikla tek bloba birlesmesin.
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k, iterations=1)
    # CLOSE: gercek yarigin icindeki kucuk acik lekeleri/specular kopuklugu doldur (tek blob).
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, k, iterations=2)
    h, w = gray.shape[:2]
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0.0
    for c in contours:
        area = float(cv2.contourArea(c))
        if area > best_area:
            best_area, best = area, c
    if best is None or best_area <= 0:
        return {"blob": 0.0, "aspect": 0.0, "width_ratio": 0.0}
    _, _, bw, bh = cv2.boundingRect(best)
    blob = float(best_area / (h * w) * 100.0)
    aspect = float(bw / bh) if bh > 0 else 0.0          # >1 = yatay uzun
    width_ratio = float(bw / w) if w > 0 else 0.0
    return {"blob": blob, "aspect": aspect, "width_ratio": width_ratio}


def _has_circle(gray: np.ndarray) -> bool:
    g = cv2.GaussianBlur(gray, (5, 5), 0)
    h, w = g.shape[:2]
    min_r = max(3, int(min(h, w) * 0.10))
    max_r = max(min_r + 1, int(min(h, w) * 0.60))
    circles = cv2.HoughCircles(
        g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max(h, w),
        param1=120, param2=18, minRadius=min_r, maxRadius=max_r,
    )
    return circles is not None


HANDEDNESS_VERSION = 3   # yontem: tum-parca gri NCC -> IKI DELIK PARLAKLIK ASIMETRISI.
                         # Saha gercegi: tum-parca 96x96 gri NCC ayna parcayi ayiramadi
                         # (gercek aynada bile normal~0.64 / ayna~0.61; iki parca piksel
                         # duzeyinde temiz ayna degil + ayirt edici ozellik tum-parcada
                         # seyreliyor). Yeni sinyal: havsali/kademeli delik kubbe isikta
                         # daha KOYU okur; iki delik ROI'sinin parlaklik farkinin ISARETI
                         # havsali deligin tarafini -> yon/eli verir (ROI basina: konuma
                         # toleransli; goreli: isiga dayanikli; gercek karelerde grup-ici
                         # ±0.1, dogru~-26 / ayna~+56 -> 80+ puan zit-isaretli ayrim).
                         # Eski (v2) NCC referanslari gecersiz -> yeniden "Yon Referansi Al".


def _hole_centers_brightness(snapshot: np.ndarray, config: dict) -> list:
    """Yon/el olcum noktalarinin (x-merkezine gore sirali) gri ortalamalari:
    [(x_merkez, gri_ort, ad), ...].

    ONCELIK: kullanicinin cizdigi 'yon' tipi kontrol noktalari (>=2 taneyse
    onlar kullanilir — evrensel: deliksiz urunde de yon tayini yapilabilir).
    Yoksa geriye-uyum icin HOLE-tipi noktalara duser (eski davranis)."""
    roi_cfg = config.get("roi", {}) or {}
    roi_types = roi_cfg.get("roi_types", {}) or {}
    sx, sy = _roi_reference_scale(snapshot, config)
    disabled = set(config.get("disabled_rois", []))
    yon_pts, hole_pts = [], []
    for name, roi in config.get("dynamic_rois", {}).items():
        if name in disabled or len(roi) != 4:
            continue
        rtype = _roi_type(name, roi_types)
        if rtype == "yon":
            target = yon_pts
        elif rtype == "hole":
            target = hole_pts
        else:
            continue
        x1, y1, x2, y2 = _roi_bounds(snapshot, roi, sx, sy)
        if x2 <= x1 or y2 <= y1:
            continue
        crop = snapshot[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        target.append(((x1 + x2) / 2.0, float(np.mean(gray)), name))
    out = yon_pts if len(yon_pts) >= 2 else hole_pts
    out.sort(key=lambda t: t[0])
    return out


def hole_handedness_diff(snapshot: np.ndarray, config: dict):
    """En SAG ve en SOL yon-olcum noktasinin parlaklik farki: sag_gri - sol_gri.
    Noktalar oncelikle 'yon' tipi kontrol noktalari; yoksa hole tipi (geriye uyum).
    Havsa/kademe olan taraf daha koyu okudugundan farkin ISARETI parcanin
    yon/elini verir. <2 olcum noktasi varsa None."""
    hb = _hole_centers_brightness(snapshot, config)
    if len(hb) < 2:
        return None
    return float(hb[-1][1] - hb[0][1])


def _check_handedness(snapshot: np.ndarray, config: dict) -> tuple:
    """Parca dogru yonde mi yoksa AYNA (simetrik/ters) mi? (ok, msg) doner.

    Yontem: iki delik parlaklik asimetrisi (havsali delik daha koyu). Referansta
    olculen farkin ISARETI saklanir (`handedness_hole_diff`); analizde isaret TERS
    donerse (ve buyukluk anlamliysa) -> AYNA -> NOK. Referans yoksa/kapaliysa ya da
    ESKI surumse atlanir (gecer). Referans asimetrisi zayifsa (esik alti) yanlis-NOK
    olmasin diye gecirir."""
    roi_cfg = config.get("roi", {}) or {}
    if not roi_cfg.get("handedness_check", True):
        return True, ""
    if int(roi_cfg.get("handedness_version", 0)) != HANDEDNESS_VERSION:
        return True, ""   # eski/yok referans -> yeniden "Yon Referansi Al" gerekir
    ref_diff = roi_cfg.get("handedness_hole_diff")
    if ref_diff is None:
        return True, ""
    ref_diff = float(ref_diff)
    cur = hole_handedness_diff(snapshot, config)
    if cur is None:
        return True, ""
    margin = float(roi_cfg.get("handedness_margin_diff", 12.0))
    if abs(ref_diff) < margin:
        return True, f"yon kontrol zayif (ref fark {ref_diff:+.0f}, esik {margin:.0f})"
    if cur * ref_diff < 0 and abs(cur) > margin:
        return False, (f"AYNA/TERS parca (delik parlaklik farki {cur:+.0f}, "
                       f"referans {ref_diff:+.0f} ters)")
    return True, f"yon dogru (delik fark {cur:+.0f}, ref {ref_diff:+.0f})"


def has_reference_profile(config: dict) -> bool:
    return bool(config.get("reference_profile", {}).get("rois"))


def reference_metric_limits(references: list, tolerances: dict = None) -> dict:
    tolerances = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    metrics = [_reference_metrics(ref) for ref in references]
    metrics = [item for item in metrics if item]
    if not metrics:
        return {}

    limits = {}
    tolerance_map = {
        "white_ratio": "white_ratio_tolerance",
        "black_ratio": "black_ratio_tolerance",
        "gray_mean": "gray_mean_tolerance",
    }

    for key, tolerance_key in tolerance_map.items():
        vals = [float(item[key]) for item in metrics if key in item]
        if not vals:
            continue
        avg = float(np.mean(vals))
        spread = float(tolerances.get(tolerance_key, 0.0))
        limits[key] = {
            "ref": avg,
            "min": max(0.0, avg - spread),
            "max": min(100.0 if key != "gray_mean" else 255.0, avg + spread),
            "tol": spread,
        }
    return limits


def format_metrics(metrics: dict) -> str:
    if not metrics:
        return "metrik yok"
    return (
        f"siyah %{metrics.get('black_ratio', 0.0):.1f}, "
        f"beyaz %{metrics.get('white_ratio', 0.0):.1f}, "
        f"parlaklık {metrics.get('gray_mean', 0.0):.1f}"
    )


def format_limits(limits: dict) -> str:
    if not limits:
        return "limit yok"
    labels = {
        "black_ratio": "siyah",
        "white_ratio": "beyaz",
        "gray_mean": "parlaklık",
    }
    parts = []
    for key in ("black_ratio", "white_ratio", "gray_mean"):
        item = limits.get(key)
        if not item:
            continue
        suffix = "%" if key != "gray_mean" else ""
        parts.append(
            f"{labels[key]} {item['min']:.1f}-{item['max']:.1f}{suffix} "
            f"(ref {item['ref']:.1f}{suffix})"
        )
    return "; ".join(parts)


def _prepare_roi(roi_crop: np.ndarray) -> tuple:
    gray = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, TEMPLATE_SIZE, interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(gray)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edge = cv2.Canny(gray, 50, 150)
    return gray, edge


def _roi_metrics(norm: np.ndarray) -> dict:
    otsu_threshold, binary = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    white_ratio = float(np.count_nonzero(binary == 255) / binary.size * 100.0)
    black_ratio = 100.0 - white_ratio
    return {
        "otsu_threshold": float(otsu_threshold),
        "white_ratio": white_ratio,
        "black_ratio": black_ratio,
        "gray_mean": float(np.mean(norm)),
        "gray_std": float(np.std(norm)),
    }


def _reference_metrics(ref: dict) -> dict:
    metrics = ref.get("metrics")
    if metrics:
        return metrics

    ref_img = _decode_png(ref.get("image", ""))
    if ref_img is None:
        return {}
    return _roi_metrics(ref_img)


def _best_template_score(current: dict, references: list) -> float:
    cur_img = _decode_png(current.get("image", ""))
    if cur_img is None:
        return float("inf")
    best = float("inf")

    for ref in references:
        ref_img = _decode_png(ref.get("image", ""))
        if ref_img is None:
            continue
        score = _mean_abs_score(cur_img, ref_img)
        best = min(best, score)

    return best


def _mean_abs_score(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    return float(np.mean(cv2.absdiff(a, b)) / 255.0 * 100.0)


def _encode_png(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _decode_png(data: str) -> np.ndarray:
    if not data:
        return None
    raw = base64.b64decode(data.encode("ascii"))
    arr = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


def _crop_roi(snapshot: np.ndarray, roi: list):
    x1, y1, x2, y2 = _roi_bounds(snapshot, roi)
    if x2 <= x1 or y2 <= y1:
        return None
    return snapshot[y1:y2, x1:x2]


def _roi_reference_scale(snapshot: np.ndarray, config: dict) -> tuple:
    """ROI'ler kalibrasyondaki urun kutusu boyutunda (mutlak piksel) saklanir.
    Analiz aninda urun kutusu boyutu farkliysa (Otsu/isik kaynakli kararsizlik),
    ROI'leri referans kutuya gore olcekleyerek kaymayi azalt. Referans kutu yoksa
    (eski config) 1.0 doner -> eski mutlak-piksel davranisi (geriye-donuk uyumlu)."""
    ref = (config.get("roi", {}) or {}).get("reference_box")
    if not ref or len(ref) != 2:
        return 1.0, 1.0
    try:
        ref_w, ref_h = float(ref[0]), float(ref[1])
    except (TypeError, ValueError):
        return 1.0, 1.0
    if ref_w <= 0 or ref_h <= 0:
        return 1.0, 1.0
    h_img, w_img = snapshot.shape[:2]
    return w_img / ref_w, h_img / ref_h


def _roi_bounds(snapshot: np.ndarray, roi: list, sx: float = 1.0, sy: float = 1.0) -> tuple:
    h_img, w_img = snapshot.shape[:2]
    x, y, w, h = map(int, roi)
    if sx != 1.0 or sy != 1.0:
        x, y = int(round(x * sx)), int(round(y * sy))
        w, h = int(round(w * sx)), int(round(h * sy))
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w_img, x + w), min(h_img, y + h)
    return x1, y1, x2, y2


def _draw_roi_result(img, name, x1, y1, x2, y2, ok, msg):
    """Resmin uzerine ROI kutusu + KISA sonuc etiketi cizer.

    `msg` BILEREK cizilmiyor (2026-08-03, kullanici istegi): eskiden kutunun
    ustunde "1: OK [delik VAR (acik %13.9, yuvarlak 0.88, dolgu 0.96)]" gibi uzun
    bir satir vardi, kutulari ortuyor ve resmi okunmaz yapiyordu. Ayrintilar artik
    "Kontrol Merkezi" tablosunda ve loglarda duruyor; resimde yalnizca hangi
    noktanin gectigi/kaldigi gerekiyor. Numara KORUNDU ki kutu tablodaki satirla
    eslestirilebilsin. (Parametre imzada birakildi: cagiranlar degismesin.)"""
    color = (0, 255, 0) if ok else (0, 0, 255)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    text = f"{name}: {'OK' if ok else 'NOK'}"
    font_scale = 0.8
    thickness = 2
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    cv2.rectangle(img, (x1, y1 - th - 5), (x1 + tw, y1), color, -1)
    cv2.putText(img, text, (x1, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)
