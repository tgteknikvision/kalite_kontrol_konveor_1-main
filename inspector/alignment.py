import cv2
import numpy as np


DEFAULT_ALIGNMENT = {
    "mode": "contour",
    "min_area_ratio": 0.02,
    "padding_px": 20,
    "foreground": "bright",
    # Metal izolasyonu (foreground=bright): parca PARLAK + RENKSIZ (gri metal);
    # yesil kilavuz raylar parlak ama RENKLI -> doygunlukla ayirt edilir.
    "metal_v_min": 110,   # parlaklik (V) alt esigi
    "metal_s_max": 85,    # doygunluk (S) ust esigi (ustu = renkli -> ele)
}


def get_alignment_config(config: dict) -> dict:
    alignment = DEFAULT_ALIGNMENT.copy()
    alignment.update((config or {}).get("alignment", {}))
    return alignment


def _to_gray(frame: np.ndarray) -> np.ndarray:
    # Kanal sayisina dayanikli gri donusum (gri/4-kanalli kare cokmesin).
    if frame.ndim == 2:
        return frame
    if frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _pick_box(mask: np.ndarray, w_img: int, h_img: int, min_area: float,
              padding: int, reject_thin: bool = False, union: bool = False):
    """Maskeden urun kutusunu (padding'li) dondurur. RETR_EXTERNAL delikleri
    (ic bolge) gormez -> delik ASLA urun sanilmaz.

    union=True ise: en buyuk konturla YATAY ortusen diger metal parcalari da
    kutuya katar (orn. braketin alt flansi ust bloklardan golge cizgisiyle
    ayrildiginda ikisini tek urun cercevesinde birlestirir). Yatay-ortusme
    sarti, yandaki raylari/lekeleri (farkli x-araligi) disarida tutar."""
    candidates, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = []
    for contour in candidates:
        area = float(cv2.contourArea(contour))
        x, y, w, h = cv2.boundingRect(contour)
        if w >= w_img * 0.98 and h >= h_img * 0.98:
            continue
        # ince-dikey konturlari (yesil ray vb.) reddet; parca genis/kare.
        if reject_thin and w < h * 0.3:
            continue
        valid.append((x, y, w, h, area))

    primary, best_area = None, 0.0
    for v in valid:
        if v[4] >= min_area and v[4] > best_area:
            best_area, primary = v[4], v
    if primary is None:
        return None

    x1, y1 = primary[0], primary[1]
    x2, y2 = primary[0] + primary[2], primary[1] + primary[3]
    if union:
        members = [v for v in valid if v is not primary and v[4] >= min_area * 0.3]
        merged = True
        while merged:
            merged = False
            remaining = []
            for (mx, my, mw, mh, ma) in members:
                overlap = max(0, min(x2, mx + mw) - max(x1, mx))
                if overlap >= 0.3 * min(x2 - x1, mw):
                    x1, y1 = min(x1, mx), min(y1, my)
                    x2, y2 = max(x2, mx + mw), max(y2, my + mh)
                    merged = True
                else:
                    remaining.append((mx, my, mw, mh, ma))
            members = remaining

    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w_img, x2 + padding)
    y2 = min(h_img, y2 + padding)
    return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]


def _metal_mask(frame: np.ndarray, v_min: int, s_max: int) -> np.ndarray:
    """Parlak + renksiz (metal) maskesi; yesil raylari (parlak specular dahil) eler."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    metal = ((val >= v_min) & (sat <= s_max)).astype(np.uint8) * 255
    # Yesil rayi (ve uzerindeki parlak yansimanin komsulugunu) acikca cikar.
    green = ((hue >= 35) & (hue <= 90) & (sat >= 60) & (val >= 40)).astype(np.uint8) * 255
    green = cv2.dilate(green, np.ones((25, 25), np.uint8), iterations=1)
    metal[green > 0] = 0
    kernel = np.ones((5, 5), np.uint8)
    metal = cv2.morphologyEx(metal, cv2.MORPH_OPEN, kernel, iterations=1)
    metal = cv2.morphologyEx(metal, cv2.MORPH_CLOSE, kernel, iterations=4)
    return metal


def _otsu_mask(frame: np.ndarray, foreground: str) -> np.ndarray:
    gray = cv2.GaussianBlur(_to_gray(frame), (5, 5), 0)
    # 'bright' -> THRESH_BINARY, 'dark' -> THRESH_BINARY_INV (tek polarite).
    threshold_type = cv2.THRESH_BINARY_INV if foreground == "dark" else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, 0, 255, threshold_type + cv2.THRESH_OTSU)
    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    return binary


def find_product_box(frame: np.ndarray, config: dict = None):
    if frame is None or frame.size == 0:
        return None

    alignment = get_alignment_config(config or {})
    min_area_ratio = float(alignment.get("min_area_ratio", 0.02))
    padding = int(alignment.get("padding_px", 20))
    foreground = str(alignment.get("foreground", "bright")).lower()

    h_img, w_img = frame.shape[:2]
    min_area = w_img * h_img * min_area_ratio

    box = None
    # Parlak metal parca + renkli raylar/arka plan: once HSV metal izolasyonu.
    # (Eski salt-parlaklik Otsu, parlak yesil raylari da urun sanip cerceveyi
    #  tum kareye genisletiyordu; metal izolasyonu rayi renkle eler.)
    if foreground != "dark" and frame.ndim == 3 and frame.shape[2] >= 3:
        v_min = int(alignment.get("metal_v_min", 110))
        s_max = int(alignment.get("metal_s_max", 85))
        box = _pick_box(_metal_mask(frame, v_min, s_max), w_img, h_img,
                        min_area, padding, reject_thin=True, union=True)

    # Yedek: metal bulunamazsa (veya foreground=dark) eski Otsu yontemi.
    if box is None:
        box = _pick_box(_otsu_mask(frame, foreground), w_img, h_img,
                        min_area, padding, reject_thin=False)
    return box


def crop_box(frame: np.ndarray, box: list):
    if frame is None or box is None or len(box) != 4:
        return None
    x, y, w, h = map(int, box)
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(frame.shape[1], x + w)
    y2 = min(frame.shape[0], y + h)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2].copy()


def draw_product_box(frame: np.ndarray, box: list, label: str = "URUN"):
    display = frame.copy()
    if box is None or len(box) != 4:
        return display
    x, y, w, h = map(int, box)
    x2, y2 = x + w, y + h
    cv2.rectangle(display, (x, y), (x2, y2), (0, 255, 255), 3)
    cv2.putText(display, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    return display


def box_size_deviation(box, ref_box):
    """Bulunan urun kutusunun referans kutuya (roi.reference_box) gore EN/BOY sapmasi.
    Doner: (dw, dh) kesir (+0.10 = %10 buyuk, -0.60 = %60 kucuk); referans yoksa None."""
    if not box or len(box) != 4 or not ref_box or len(ref_box) != 2:
        return None
    try:
        rw, rh = float(ref_box[0]), float(ref_box[1])
        bw, bh = float(box[2]), float(box[3])
    except (TypeError, ValueError):
        return None
    if rw <= 0 or rh <= 0:
        return None
    return (bw / rw - 1.0, bh / rh - 1.0)


def product_present(box, ref_box, tolerance=0.25):
    """URUN VAR/YOK KAPISI (2026-09-24, saha: "bazen bos kareyi yakaliyor, hepsi NOK").
    Tetik geldiginde urun karede yoksa find_product_box "yok" DEMEZ: metal maskesi bos
    kalinca Otsu yedegi en parlak bloba (ray kenari / metal serit) kutu cizer (sahada
    286x1088, referans 708x542) -> noktalar boslugu olcer -> hepsi NOK + yon NOK.
    Kutu en/boy'u referansa gore toleranstan fazla sapiyorsa urun YOK sayilir.
    Sahada OK cerceveler referansa +-%8 icinde; bos kare %-60 / %+100 sapiyor.
    Doner: (var_mi, sapma); referans yoksa (True, None) = kapi devre disi."""
    dev = box_size_deviation(box, ref_box)
    if dev is None:
        return True, None
    tol = max(0.0, float(tolerance))
    return (abs(dev[0]) <= tol and abs(dev[1]) <= tol), dev


def metal_threshold_suggestion(frame, s_max=85):
    """metal_v_min icin OTOMATIK ONERI (2026-09-24, saha: bant parlaklasinca urun cercevesi bantla
    birlesti; pozlama degisince esik yeniden ayarlanmali). Renksiz (S<=s_max) ve yesil olmayan
    piksellerin V histogramina Otsu uygulanir: iki grup = zemin/bant (koyu) ve urun (parlak);
    esik ikisinin arasina duser. Bulunan kutuya BAGLI DEGIL (kutu yanlisken de dogru calisir).
    Doner: (oneri, zemin_medyan, urun_medyan) ya da None (yeterli piksel yoksa)."""
    if frame is None or getattr(frame, "ndim", 0) != 3 or frame.shape[2] < 3:
        return None
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    green = (hue >= 35) & (hue <= 90) & (sat >= 60) & (val >= 40)
    secim = (sat <= int(s_max)) & (~green)
    v = val[secim]
    if v.size < 1000:
        return None
    thr, _ = cv2.threshold(v.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = int(round(float(thr)))
    koyu, parlak = v[v < thr], v[v >= thr]
    if koyu.size < 100 or parlak.size < 100:
        return None
    return thr, int(np.median(koyu)), int(np.median(parlak))
