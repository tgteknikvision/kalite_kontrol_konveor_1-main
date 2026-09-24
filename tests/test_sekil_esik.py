"""Delik ŞEKİL kapısı eşikleri nokta başına (yuvarlaklık / dolgu) — ekransız test (gerçek config'e DOKUNMAZ).

2026-09-24 saha: nokta 1 açıklık %9 (≥8) ve derinlik %7.3 (≥6) geçti ama "delik YOK (sekil uygun
degil: yuvarlak 0.48, dolgu 0.49, kenar 0)" → üçüncü kapı (şekil) global config'te, panelde/editörde
ayarlanamıyordu. Artık `hole_min_circularity` / `hole_min_fill` nokta başına override (editör sağ tık
→ Ayarlar), mesaj kalan ölçütü '<' ile işaretler ve eşiğin yerini söyler.
"""
import os, sys, tempfile, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np, cv2
from PyQt5.QtWidgets import QApplication, QDialog
import main
from inspector.features import evaluate_with_profile, _hole_shape
import inspector.roi_editor as re_mod
from inspector.roi_editor import ROIDialog, _spin_decimals

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))

# Sentetik ROI: parlak metal (200) uzerinde HILAL koyu blob (havsa yansimasi / yarim kapali delik)
f = np.full((240, 240, 3), 200, np.uint8)
cv2.circle(f, (120, 130), 45, (20, 20, 20), -1)          # koyu delik
cv2.circle(f, (120, 96), 44, (200, 200, 200), -1)         # ust kismi parlak -> hilal kalir
gray_roi = cv2.cvtColor(f[40:200, 40:200], cv2.COLOR_BGR2GRAY)
shp = _hole_shape(gray_roi, 70)
def cfg(overrides=None, **roi_extra):
    roi = {"decision_method": "hole", "roi_types": {"1": "hole"}, "hole_dark_value": 70,
           "hole_dark_ratio_min": 1.0, "hole_dark_ratio_max": 95.0, "hole_core_value": 40,
           "hole_core_ratio_min": 0.0, "hole_shape_check": True, "hole_min_circularity": 0.55,
           "hole_min_fill": 0.5, "hole_min_aspect": 0.3, "hole_max_edge_touch": 1,
           "hole_min_blob_ratio": 1.0, "handedness_check": False, "point_overrides": overrides or {}}
    roi.update(roi_extra)
    return {"alignment": {"mode": "off"}, "dynamic_rois": {"1": [40, 40, 160, 160]}, "disabled_rois": [], "roi": roi}

print("\n[saf: şekil kapısı nokta başına]")
check("hilal blob şekil ölçütünün altında (yuvarlak ya da dolgu)", shp["circ"] < 0.55 or shp["fill"] < 0.5, f"circ {shp['circ']:.2f} fill {shp['fill']:.2f}")
ok1, res1, _ = evaluate_with_profile(f, cfg())
m1 = res1["1"]["msg"]
check("genel eşiklerle NOK: 'sekil uygun degil' + kalan ölçüt '<' işaretli + eşik yeri", not ok1 and "sekil uygun degil" in m1 and " < " in m1 and "sag tik > Ayarlar" in m1, m1)
check("metrics'te circularity/fill var", "circularity" in res1["1"]["metrics"] and "fill" in res1["1"]["metrics"])
ok2, res2, _ = evaluate_with_profile(f, cfg({"1": {"hole_min_circularity": 0.2, "hole_min_fill": 0.2}}))
check("nokta override (0.2/0.2) → OK 'delik VAR'", ok2 and res2["1"]["msg"].startswith("delik VAR"), res2["1"]["msg"])
ok3, res3, _ = evaluate_with_profile(f, cfg(hole_min_circularity=0.2, hole_min_fill=0.2))
check("genel eşik düşürülünce de OK", ok3)
ok4, res4, _ = evaluate_with_profile(f, cfg({"1": {"hole_min_circularity": 0.2}}))
check("yalnız yuvarlaklık gevşetilince dolgu hâlâ kalabilir → mesaj yalnız dolguyu işaretler ya da OK",
      ok4 or ("dolgu" in res4["1"]["msg"] and "yuvarlak" in res4["1"]["msg"] and res4["1"]["msg"].count(" < ") == 1), res4["1"]["msg"])
ok5, res5, _ = evaluate_with_profile(f, cfg({"2": {"hole_min_circularity": 0.2, "hole_min_fill": 0.2}}))
check("başka noktanın override'ı bu noktayı etkilemez", not ok5)
check("sayaç kategorisi 'şekil uygun değil'", main.MainWindow._nok_reason_category(m1) == "şekil uygun değil")

print("\n[editör: nokta ayarları]")
keys = [k for k, *_ in ROIDialog.POINT_SETTINGS["hole"]]
check("POINT_SETTINGS['hole']: açıklık, derinlik, yuvarlaklık, dolgu", keys == ["hole_dark_ratio_min", "hole_core_ratio_min", "hole_min_circularity", "hole_min_fill"], str(keys))
rng_c = [r for k, _l, r, *_ in ROIDialog.POINT_SETTINGS["hole"] if k == "hole_min_circularity"][0]
check("yuvarlaklık aralığı 0-1, ondalık 2; yüzdeler 1", rng_c == (0.0, 1.0) and _spin_decimals(rng_c) == 2 and _spin_decimals((0.0, 50.0)) == 1)

print("\n[main: editöre genel değerler geçiyor]")
app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
c = yaml.safe_load(open("config.yaml", encoding="utf-8"))
c["plc"]["type"] = "null"; c["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
c["roi"]["hole_min_circularity"] = 0.55; c["roi"]["hole_min_fill"] = 0.5
yaml.safe_dump(c, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
w = main.MainWindow(); w.show(); app.processEvents()
w._last_snapshot = f.copy()
captured = {}
class FakeDlg:
    def __init__(self, *a, **k): captured.update(k)
    def exec_(self): return QDialog.Rejected
orig = re_mod.ROIDialog; re_mod.ROIDialog = FakeDlg
try:
    w._open_roi_manager(1)
finally:
    re_mod.ROIDialog = orig
rd = captured.get("roi_defaults", {})
check("roi_defaults yuvarlaklık 0.55 / dolgu 0.5 içeriyor", rd.get("hole_min_circularity") == 0.55 and rd.get("hole_min_fill") == 0.5, str(rd))
w.worker = None; w.worker2 = None; w.close()

basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
