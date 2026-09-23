"""Seçenek (işaret) kutuları görünürlüğü — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-23, kullanıcı: "seçeneklerin kutuları gözükmüyor, tüm programda açık renk yap, okların
renginde olabilir". Fusion'ın koyu temada çizdiği kutu zeminle aynı tondaydı (eski stilde
kutu şeridinde ~6 parlak piksel ölçüldü). Yeni stil: 2 px açık çerçeve (#d6dae2, ok rengi),
işaretliyken mavi dolgu + beyaz tik. Uygulamanın GERÇEK kurulumuyla (Fusion + koyu palet)
render edilir; piksel sayımı ile görünürlük doğrulanır.
"""
import os, sys, tempfile, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
from PyQt5.QtWidgets import QApplication, QCheckBox, QGroupBox
import main

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=5):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])
app.setStyle("Fusion"); main.apply_dark_palette(app)          # main() ile birebir aynı kurulum
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["manual_mode"] = True; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)

def piksel_say(pm, x0, y0, w, h, kosul):
    img = pm.toImage(); n = 0
    for y in range(y0, min(y0 + h, img.height())):
        for x in range(x0, min(x0 + w, img.width())):
            if kosul(img.pixelColor(x, y)): n += 1
    return n
parlak = lambda c: (c.red() + c.green() + c.blue()) / 3 > 180
mavi = lambda c: c.blue() > 120 and c.blue() > c.red() + 40
beyaz = lambda c: c.red() > 230 and c.green() > 230 and c.blue() > 230

print("\n[stil metni]")
ss = main.build_stylesheet()
check("stylesheet'te QCheckBox::indicator kuralı var", "QCheckBox::indicator" in ss)
check("stylesheet'te QGroupBox::indicator kuralı var (Ayarlar 'Kamera N (kullan)')", "QGroupBox::indicator" in ss)
check("çerçeve rengi ok rengiyle aynı (#d6dae2)", "border: 2px solid #d6dae2" in ss)
ik = main._arrow_icon_paths()
check("tik resmi üretildi ve yola yazıldı", "tik" in ik and os.path.exists(ik["tik"]) and ik["tik"] in ss and "__TICK__" not in ss)
orig = main._arrow_icon_paths
main._arrow_icon_paths = lambda: {}
ss_yedek = main.build_stylesheet()
main._arrow_icon_paths = orig
check("resim üretilemezse url(__…__) yer tutucusu kalmaz (stil bozulmaz)", "url(__" not in ss_yedek and "url(__" not in ss)

print("\n[ana pencere: Elle Çekim Modu kutusu]")
w = main.MainWindow(); w.show(); pump()
chk = w.chk_manual_mode
chk.setChecked(False); pump()
pm = chk.grab()
bos = piksel_say(pm, 0, 0, 20, pm.height(), parlak)
check("boş kutu görünür: açık renkli çerçeve (eski stilde ~6 piksel)", bos >= 60, f"parlak={bos}")
chk.setChecked(True); pump()
pm = chk.grab()
m = piksel_say(pm, 0, 0, 20, pm.height(), mavi); b = piksel_say(pm, 0, 0, 20, pm.height(), beyaz)
check("işaretli kutu: mavi dolgu", m >= 40, f"mavi={m}")
check("işaretli kutu: beyaz tik", b >= 8, f"beyaz={b}")
chk.setChecked(False); pump()
chk.setEnabled(False); pump()
pm = chk.grab()
pasif = piksel_say(pm, 0, 0, 20, pm.height(), lambda c: (c.red() + c.green() + c.blue()) / 3 > 70)
check("pasif kutu da seçilebilir (soluk ama çizili)", pasif >= 40, f"orta-parlak={pasif}")
chk.setEnabled(True); pump()

print("\n[Ayarlar: kamera grubu başlık kutuları + Exposure/Gain Kilidi]")
dlg = main.SettingsDialog(w.config, w); dlg.show(); pump()
g1 = dlg._cam1_w["group"]; g2 = dlg._cam2_w["group"]
check("Kamera 1 grubu işaretli, Kamera 2 boş (test config'i)", g1.isChecked() and not g2.isChecked())
p1 = g1.grab(); p2 = g2.grab()
check("işaretli grup kutusu görünür (mavi + parlak)", piksel_say(p1, 0, 0, 40, 30, mavi) >= 40 and piksel_say(p1, 0, 0, 40, 30, parlak) >= 40,
      f"mavi={piksel_say(p1, 0, 0, 40, 30, mavi)} parlak={piksel_say(p1, 0, 0, 40, 30, parlak)}")
check("boş grup kutusu görünür (açık çerçeve; eski stilde 0 piksel)", piksel_say(p2, 0, 0, 40, 30, parlak) >= 40, f"parlak={piksel_say(p2, 0, 0, 40, 30, parlak)}")
kilit = dlg._cam1_w["manual_exp"]
check("Exposure/Gain Kilidi kutusu QCheckBox (aynı stil)", isinstance(kilit, QCheckBox))
pk = kilit.grab()
check("kilit kutusu görünür", piksel_say(pk, 0, 0, 20, pk.height(), parlak) >= 60 or piksel_say(pk, 0, 0, 20, pk.height(), mavi) >= 40)
check("tüm programdaki QCheckBox'lar pencere stilini alır (özel stil yok)",
      all(not c.styleSheet() for c in w.findChildren(QCheckBox) + dlg.findChildren(QCheckBox)))
check("işaretlenebilir QGroupBox sayısı 2 (kamera 1 / kamera 2)", sum(1 for g in dlg.findChildren(QGroupBox) if g.isCheckable()) == 2)
dlg.close(); w.close(); pump()

basarisiz = [a for a, ok in sonuc if not ok]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız")
sys.exit(1 if basarisiz else 0)
