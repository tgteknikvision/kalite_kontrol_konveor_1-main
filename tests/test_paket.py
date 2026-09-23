"""Paket adedi / uyarı — ekransız test (gerçek config/log/kameraya DOKUNMAZ)."""
import os, sys, time, tempfile, yaml, csv
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
from PyQt5.QtWidgets import QApplication, QMessageBox, QAbstractSpinBox
from PyQt5.QtCore import Qt
import main

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=5):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["manual_mode"] = True; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["inspection"].pop("paket_adedi", None)
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
main.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
beeps = []; main.QApplication.beep = staticmethod(lambda: beeps.append(1))

w = main.MainWindow(); w.show(); pump()
loglar = []; orig = w._append_log; w._append_log = lambda m: (loglar.append(m), orig(m))
ok_res = {"1": {"ok": True, "msg": "delik VAR", "metrics": {"black_ratio": 25.0, "core_ratio": 8.0}}}
nok_res = {"1": {"ok": False, "msg": "delik YOK (acik %0.0 < %10, kapali/eksik/tikali)", "metrics": {"black_ratio": 0.0, "core_ratio": 0.0}}}

print("\n[kutu]")
check("paket adedi kutusu var, varsayılan 100, oklu", w.spin_paket.value() == 100 and w.spin_paket.buttonSymbols() == QAbstractSpinBox.UpDownArrows)
check("config'e yazılmamışsa da 100", w._paket_adedi() == 100 and w._counters["paket_esik"] == 100)
check("stylesheet'te ok resmi yolu var ve dosya üretildi", "ok_yukari.png" in w.styleSheet() and os.path.exists(main._arrow_icon_paths()["ok_yukari"]))
check("paket satırı 'Paket: 0 / 100'", w.lbl_paket.text() == "Paket: 0 / 100")

print("\n[100'e ulaşma]")
for i in range(99): w._record_part(i + 1, True, {1: ok_res}, "plc")
w._record_part(50, False, {1: nok_res}, "plc")                       # NOK pakete sayılmaz
check("99 OK + 1 NOK → paket 99, uyarı yok", w._counters["paket_ok"] == 99 and getattr(w, "_paket_dlg", None) is None)
w._record_part(100, True, {1: ok_res}, "plc"); pump()
dlg = getattr(w, "_paket_dlg", None)
check("100. OK parçada uyarı penceresi açıldı", dlg is not None and dlg.isVisible(), str(dlg))
check("pencere MODAL DEĞİL (denetim durmaz)", dlg is not None and dlg.windowModality() == Qt.NonModal)
check("metin '100 adete ulaşıldı'", dlg is not None and "100 adete ulaşıldı" in dlg.text())
check("bip + log", beeps and any("100 adete ulaşıldı" in l for l in loglar))
check("panel 'PAKET DOLDU: 100 / 100'", w.lbl_paket.text() == "PAKET DOLDU: 100 / 100")
w._record_part(101, True, {1: ok_res}, "plc"); pump()
check("pencere açıkken yeni parça ikinci pencere AÇMAZ, sayım sürer", w._paket_dlg is dlg and w._counters["paket_ok"] == 101 and "101" in dlg.text())

print("\n[Devam et]")
devam = [b for b in dlg.buttons() if b.text() == "Devam et"][0]
devam.click(); pump()
check("Devam et → pencere kapandı, hedef 200, paket sayacı korundu (101)", w._paket_dlg is None and w._counters["paket_esik"] == 200 and w._counters["paket_ok"] == 101, str((w._counters["paket_esik"], w._counters["paket_ok"])))
check("panel 'Paket: 101 / 200'", w.lbl_paket.text() == "Paket: 101 / 200", w.lbl_paket.text())
for i in range(99): w._record_part(102 + i, True, {1: ok_res}, "plc")
pump()
dlg2 = getattr(w, "_paket_dlg", None)
check("200'de tekrar uyarı", dlg2 is not None and "200 adete ulaşıldı" in dlg2.text())

print("\n[Sıfırla (paket)]")
sifirla = [b for b in dlg2.buttons() if b.text() == "Sıfırla"][0]
sifirla.click(); pump()
c = w._counters
check("Sıfırla → paket 0 / 100; parti toplamları KORUNDU (OK 200, NOK 1)", c["paket_ok"] == 0 and c["paket_esik"] == 100 and c["ok"] == 200 and c["nok"] == 1 and c["toplam"] == 201, str((c["paket_ok"], c["paket_esik"], c["ok"], c["nok"])))
csv_path = os.path.join(main.MainWindow.LOG_DIR, f"parca-{time.strftime('%Y-%m-%d')}.csv")
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("CSV'de PAKET satırı", rows[-1][3] == "PAKET" and "200 OK" in rows[-1][6], str(rows[-1]))
check("sıfırlama logu", any("Paket sıfırlandı (200 OK" in l for l in loglar))

print("\n[X ile kapatma = Devam et]")
for i in range(100): w._record_part(300 + i, True, {1: ok_res}, "plc")
pump(); dlg3 = w._paket_dlg
check("100'de yine uyarı", dlg3 is not None)
dlg3.close(); pump()
check("X ile kapatınca 'Devam et' sayılır: hedef 200", w._paket_dlg is None and w._counters["paket_esik"] == 200)

print("\n[paket adedi değişimi]")
w.spin_paket.setValue(50); pump()
check("paket adedi 50 → config'e yazıldı, hedef mevcut sayımın (100) üstündeki ilk kat = 150", w.config["inspection"]["paket_adedi"] == 50 and w._counters["paket_esik"] == 150, str(w._counters["paket_esik"]))
saved = yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
check("config dosyasına kaydedildi", saved["inspection"]["paket_adedi"] == 50)

print("\n[parti sıfırlama pencereyi kapatır + kalıcılık]")
for i in range(50): w._record_part(400 + i, True, {1: ok_res}, "plc")
pump(); check("150'de uyarı açık", w._paket_dlg is not None)
w._reset_counters(); pump()
check("parti Sıfırla → pencere kapandı, paket 0/50, hedef 50, toplam 0", w._paket_dlg is None and w._counters["paket_ok"] == 0 and w._counters["paket_esik"] == 50 and w._counters["toplam"] == 0)
for i in range(7): w._record_part(500 + i, True, {1: ok_res}, "plc")
w2 = main.MainWindow(); w2.show(); pump()
check("yeniden açılınca paket sayacı ve hedef korunuyor (7 / 50)", w2._counters["paket_ok"] == 7 and w2._counters["paket_esik"] == 50 and w2.lbl_paket.text() == "Paket: 7 / 50" and w2.spin_paket.value() == 50, w2.lbl_paket.text())

for x in (w, w2):
    x.worker = None; x.worker2 = None; x._paket_penceresini_kapat(); x.close()
basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
