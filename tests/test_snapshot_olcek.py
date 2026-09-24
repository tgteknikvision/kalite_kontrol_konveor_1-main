"""'Son Alınan Tam Resim' paneli pencereye SIĞMALI — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-24, kullanıcı ekran görüntüsüyle: sağdaki resim sağa kayıyor, sayfaya sığmıyor.
Sebep: lbl_snapshot'a yalnız minimumHeight verilmişti; Qt, en küçük GENİŞLİK verilmeyen bir
QLabel'in en küçük genişliğini içindeki pixmap kadar sayar. Resim etiketin o anki boyutuna
ölçeklenince etiket bir daha KÜÇÜLEMEZ (cırcır etkisi); kaydırma alanının yatay çubuğu kapalı
olduğu için panel sağdan taşar. Canlı görüntü (video_label) her iki boyutta da açık minimum
taşıdığı için taşmıyordu. Burada: büyük resim göster → pencereyi küçült → panel taşmamalı,
resim etikete sığmalı; ayrıca etiket kendi boyutu değişince de yeniden ölçeklenmeli.
"""
import os, sys, tempfile, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np
from PyQt5.QtWidgets import QApplication, QScrollArea
import main

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=10):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["manual_mode"] = True; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)

def scroll_of(label):
    p = label
    while p is not None and not isinstance(p, QScrollArea):
        p = p.parentWidget()
    return p

w = main.MainWindow(); w.resize(1920, 1000); w.show(); pump()
lbl = w.lbl_snapshot; sa = scroll_of(lbl)
print("\n[kurulum]")
check("snapshot etiketi bir kaydırma alanının içinde (yatay çubuk kapalı)", sa is not None and sa.horizontalScrollBarPolicy() == 1)  # Qt.ScrollBarAlwaysOff == 1
check("etiketin en küçük GENİŞLİĞİ açıkça verilmiş (cırcır koruması)", lbl.minimumWidth() > 0 and lbl.minimumHeight() > 0, f"min={lbl.minimumWidth()}x{lbl.minimumHeight()}")

print("\n[büyük resim → pencereyi küçült]")
img = np.zeros((1088, 1456, 3), np.uint8); img[:, :, 1] = 90
w._display_snapshot(img, 1); pump()
w1 = lbl.width(); pm1 = lbl.pixmap(); s1 = (pm1.width(), pm1.height())
check("büyük pencerede resim etikete sığıyor", pm1 is not None and pm1.width() <= lbl.width() and pm1.height() <= lbl.height(), f"pixmap {pm1.width()}x{pm1.height()} / etiket {lbl.width()}x{lbl.height()}")
w.resize(1100, 700); pump(); w._rescale_snapshot(); pump()
inner = sa.widget()
check("küçük pencerede sağ panel kaydırma alanına SIĞIYOR (taşma yok)", inner.width() <= sa.viewport().width() + 1, f"panel {inner.width()} / görünür {sa.viewport().width()}")
check("etiket küçüldü (cırcır yok)", lbl.width() < w1, f"{w1} -> {lbl.width()}")
pm2 = lbl.pixmap(); s2 = (pm2.width(), pm2.height())
check("resim yeni etiket boyutuna yeniden ölçeklendi ve sığıyor", pm2 is not None and s2[0] <= lbl.width() and s2[1] <= lbl.height() and s2[0] < s1[0], f"pixmap {s2} / etiket {lbl.width()}x{lbl.height()} (önce {s1})")
check("en/boy oranı korunuyor", abs(pm2.width() / pm2.height() - 1456 / 1088) < 0.02)

print("\n[etiket kendi başına boyut değiştirince]")
w.resize(1700, 950); pump()                    # resizeEvent -> gecikmeli rescale
pump(20)
pm3 = lbl.pixmap(); s3 = (pm3.width(), pm3.height())
check("büyütünce resim tekrar büyüdü ve sığıyor", pm3 is not None and s3[0] > s2[0] and s3[0] <= lbl.width() and s3[1] <= lbl.height(), f"pixmap {s3} / etiket {lbl.width()}x{lbl.height()} (önce {s2})")
# Yalniz etiket kucultulurse (pencere degil): ornegin Ayarlar'da satir gizlenip gosterildiginde
lbl.resize(lbl.width() // 2, lbl.height()); pump(20)
pm4 = lbl.pixmap()
check("yalnız etiket küçülünce de resim yeniden ölçeklendi (pencere resizeEvent'i olmadan)", pm4 is not None and pm4.width() <= lbl.width(), f"pixmap {pm4.width()} / etiket {lbl.width()}")

w.worker = None; w.worker2 = None; w.close()
basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
