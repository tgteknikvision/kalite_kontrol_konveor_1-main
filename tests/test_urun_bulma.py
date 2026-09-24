"""Ürün bulma eşiği: bant parlaklaşınca çerçeve bantla birleşiyor — ekransız test (gerçek config'e DOKUNMAZ).

2026-09-24 13:06 saha: ürün karenin üstünde, bulunan çerçeve 760x1025 (tam boy). Ölçüm (ekran
görüntüsü): bant V≈100-125, ürün V≈180-240, ray metal kenarı 166-180. Metal maskesi V>=110 olduğu
için aydınlık bant bölgesi de "metal" sayılıp ÜNYON kuralıyla (yatay örtüşen bloblar birleşir)
ürüne eklendi. Çözüm: eşik Ayarlar'dan ayarlanabilir (metal_v_min / metal_s_max), sahada 160.
"""
import os, sys, tempfile, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np, cv2
from PyQt5.QtWidgets import QApplication
import main
from inspector.alignment import find_product_box

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=6):
    for _ in range(n): app.processEvents()

H, W = 1088, 1456
def sahne(bant_ust, bant_alt):
    f = np.zeros((H, W, 3), np.uint8)
    g = np.linspace(bant_ust, bant_alt, H).astype(np.uint8)[:, None].repeat(W, axis=1)
    f[:, :, 0] = g; f[:, :, 1] = g; f[:, :, 2] = g
    f[:, 250:340] = (40, 200, 40); f[:, 1130:1220] = (40, 200, 40)      # yeşil raylar
    f[:, 340:360] = (175, 175, 175); f[:, 1110:1130] = (170, 170, 170)    # ray metal kenarları
    f[120:640, 420:1050] = (235, 235, 235)                                # ürün 630x520 üstte
    cv2.circle(f, (600, 450), 60, (30, 30, 30), -1); cv2.circle(f, (900, 460), 45, (30, 30, 30), -1)
    return f
def cfg_al(v, s=85):
    return {"alignment": {"mode": "contour", "foreground": "bright", "metal_v_min": v, "metal_s_max": s, "min_area_ratio": 0.02, "padding_px": 20}}

print("\n[saf: aydınlık bant + ürün]")
parlak = sahne(70, 125); karanlik = sahne(60, 100)
b110 = find_product_box(parlak, cfg_al(110)); b160 = find_product_box(parlak, cfg_al(160))
check("aydınlık bantta V>=110 → çerçeve bantla birleşir (tam boya yakın)", b110 is not None and b110[3] >= 900, str(b110))
check("V>=160 → yalnız ürün (670x560 ±10)", b160 is not None and abs(b160[2] - 670) <= 10 and abs(b160[3] - 560) <= 10, str(b160))
k110 = find_product_box(karanlik, cfg_al(110))
check("karanlık bantta (dünkü koşul) 110 da 160 da ürünü verir", k110 is not None and abs(k110[3] - 560) <= 10 and find_product_box(karanlik, cfg_al(160))[3] - 560 <= 10, str(k110))
check("ray metal kenarları (V 170-175, ince) 160'ta ürüne katılmaz", b160[0] >= 380 and b160[0] + b160[2] <= 1090, str(b160))
check("varsayılan (anahtar yok) hâlâ 110 → geriye uyum", find_product_box(parlak, {"alignment": {"mode": "contour"}}) == b110)

print("\n[Ayarlar: alan + uygulama + log]")
app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["type"] = "null"; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["alignment"] = {"mode": "contour", "foreground": "bright", "min_area_ratio": 0.02, "padding_px": 20}   # eşik anahtarı YOK
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
w = main.MainWindow(); w.show(); pump()
loglar = []; w._append_log = lambda m: loglar.append(m)
dlg = main.SettingsDialog(w.config, w)
check("Ayarlar'da eşik kutuları: V 110 (varsayılan), S 85", dlg.spin_metal_v.value() == 110 and dlg.spin_metal_s.value() == 85)
v = dlg.values(); check("values() metal_v_min/metal_s_max içeriyor", v["metal_v_min"] == 110 and v["metal_s_max"] == 85)
v2 = dict(v); v2["metal_v_min"] = 160
w._apply_settings(v2); pump()
saved = yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
check("Kaydet → config alignment.metal_v_min=160 + dosya + log", w.config["alignment"]["metal_v_min"] == 160 and saved["alignment"]["metal_v_min"] == 160 and any("Ürün bulma eşikleri" in l and "V≥160" in l for l in loglar))
n = len(loglar); w._apply_settings(v2)
check("aynı değerle tekrar Kaydet → eşik logu tekrarlanmaz", not any("Ürün bulma eşikleri" in l for l in loglar[n:]))
dlg2 = main.SettingsDialog(w.config, w)
check("yeniden açılan Ayarlar 160 gösterir", dlg2.spin_metal_v.value() == 160)

print("\n[Ürün Çerçevesi Bul: eşik logda + restartsız etki]")
class FakeWorker:
    def __init__(self, frame): self.last_raw_frame = frame; self.last_frame_time = __import__("time").time()
    def stop(self): pass
    def wait(self, *a): return True
w.worker = FakeWorker(parlak); w._display_snapshot = lambda img, n=1: None
loglar.clear(); w._capture_product_box_for_roi(1)
check("160 ile 'Ürün Çerçevesi Bul' yalnız ürünü buldu ve eşiği logladı", any("[Ürün Bulma] Çerçeve bulundu" in l and "h=56" in l and "V≥160" in l for l in loglar), str([l for l in loglar if "Ürün Bulma" in l]))
w.config["alignment"]["metal_v_min"] = 110; loglar.clear(); w._capture_product_box_for_roi(1)
check("110 ile aynı kare tam boy çerçeve verir (sorun yeniden üretildi) + öneri metni", any("[Ürün Bulma] Çerçeve bulundu" in l and ("h=10" in l or "h=9") and "metal parlaklık eşiği" in l for l in loglar), str([l for l in loglar if "Ürün Bulma" in l]))

w.worker = None; w.worker2 = None; w.close()
basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
