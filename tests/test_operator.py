"""NOK'ta operatör kontrol penceresi (DOĞRU / HATALI) — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-24, kullanıcı: "hata verince konveyör yine dursun ama Pi ekranında %80 resim + 'ürün doğru mu
hatalı mı' sorusu çıksın; doğru derse doğruya saysın, demezse hatalıya". PLC'ye yine 1 gider (değişmedi);
pencere modal değil; DOĞRU → NOK-1/OK+1/paket+1, nokta-sebep dağılımı ve NOK listesi düzeltilir, CSV
OPERATOR_DOGRU; HATALI → NOK kalır, CSV OPERATOR_HATALI; cevapsız kapatma → NOK kalır; açıkken yeni NOK
→ eski cevapsız kapanır; OK çekimde pencere yok; Ayarlar'dan kapatılabilir.
"""
import os, sys, time, tempfile, yaml, csv, json
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtCore import Qt
import main
from inspector.plc import NullPLCAdapter, InspectionState

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=8):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["type"] = "null"; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["alignment"] = {"mode": "off"}
cfg["dynamic_rois"] = {"1": [10, 10, 50, 50]}; cfg["disabled_rois"] = []
cfg["roi"]["roi_types"] = {"1": "hole"}; cfg["roi"]["point_overrides"] = {}; cfg["roi"]["handedness_check"] = False
cfg["roi"].pop("reference_box", None)
cfg["inspection"] = {"trigger_delay_ms": 0, "paket_adedi": 100}
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
main.QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
main.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
main.QApplication.beep = staticmethod(lambda: None)

class FakeWorker:
    def __init__(self, frame): self.last_raw_frame = frame; self.last_frame_time = time.time()
    def stop(self): pass
    def wait(self, *a): return True
class RecPLC(NullPLCAdapter):
    def __init__(self): super().__init__(); self.results = []
    def publish_result(self, ok): self.results.append(bool(ok)); return super().publish_result(ok)

gri = np.full((300, 400, 3), 200, np.uint8)               # düz metal: delik YOK -> NOK
w = main.MainWindow(); w.show(); pump()
w.plc = RecPLC(); w._display_snapshot = lambda img, n=1: None
pm = QPixmap(400, 300); pm.fill(QColor("#556677")); w._snapshot_full_pixmap = pm
loglar = []; orig = w._append_log; w._append_log = lambda m: (loglar.append(m), orig(m))
def cekim():
    w.worker = FakeWorker(gri); w._inspection_state = InspectionState.READY; w._trigger_time = time.time()
    w._capture_full_frame(source="plc"); pump()
csv_path = os.path.join(main.MainWindow.LOG_DIR, f"parca-{time.strftime('%Y-%m-%d')}.csv")

print("\n[NOK → pencere]")
cekim()
dlg = getattr(w, "_review_dlg", None)
c = w._counters
check("NOK sayıldı, PLC'ye NOK gitti", c["nok"] == 1 and c["ok"] == 0 and w.plc.results == [False])
check("operatör penceresi açık, MODAL DEĞİL, Resim #1", dlg is not None and dlg.isVisible() and dlg.windowModality() == Qt.NonModal and dlg.part_id == 1 and "#1" in dlg.windowTitle())
check("pencere ekranın ~%80'i", dlg is not None and dlg.width() >= 600 and dlg.height() >= 400, f"{dlg.width()}x{dlg.height()}" if dlg else "")
check("resim var ve etikete sığıyor", dlg is not None and dlg.lbl_img.pixmap() is not None and not dlg.lbl_img.pixmap().isNull() and dlg.lbl_img.pixmap().width() <= dlg.lbl_img.width())
check("gerekçe metni: 1: delik YOK", dlg is not None and "1: delik YOK" in dlg.lbl_reasons.text(), dlg.lbl_reasons.text()[:80] if dlg else "")
check("butonlar DOĞRU / HATALI", dlg is not None and "DOĞRU" in dlg.btn_ok.text() and "HATALI" in dlg.btn_nok.text())
check("log: pencere açıldı", any("[Operatör] Resim #1 NOK → kontrol penceresi" in l for l in loglar))

print("\n[DOĞRU → OK'a sayılır]")
c["paket_esik"] = 100
dlg.btn_ok.click(); pump()
c = w._counters
check("pencere kapandı, cevap dogru", w._review_dlg is None and dlg.answer == "dogru")
check("NOK 0, OK 1, paket 1, toplam 1", c["nok"] == 0 and c["ok"] == 1 and c["paket_ok"] == 1 and c["toplam"] == 1, str({k: c[k] for k in ("nok", "ok", "paket_ok", "toplam")}))
check("nokta/sebep dağılımı ve NOK listesi temizlendi", c["noktalar"] == {} and c["son_nok"] == [], str(c["noktalar"]))
check("operator_dogru 1", c["operator_dogru"] == 1)
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("CSV son satır OPERATOR_DOGRU (resim 1)", rows[-1][3] == "OPERATOR_DOGRU" and rows[-1][1] == "1" and rows[-1][2] == "operator", str(rows[-1]))
check("log DOĞRU → OK sayıldı", any("DOĞRU → OK sayıldı" in l for l in loglar))
check("panel 'Operatör: 1 doğru / 0 hatalı'", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 0 hatalı")
check("PLC'ye ek yazım YOK (hâlâ tek sonuç)", w.plc.results == [False])

print("\n[HATALI → NOK kalır]")
cekim(); dlg2 = w._review_dlg
dlg2.btn_nok.click(); pump()
c = w._counters
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("NOK 1 kaldı, operator_hatali 1, CSV OPERATOR_HATALI", c["nok"] == 1 and c["ok"] == 1 and c["operator_hatali"] == 1 and rows[-1][3] == "OPERATOR_HATALI" and c["noktalar"].get("1 (delik)"))
check("panel 'Operatör: 1 doğru / 1 hatalı'", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 1 hatalı")

print("\n[açıkken yeni NOK / cevapsız kapatma]")
cekim(); dlg3 = w._review_dlg
cekim(); dlg4 = w._review_dlg
check("yeni NOK gelince eski pencere kapandı (cevapsız → NOK kaldı), yeni #4", dlg4 is not dlg3 and dlg4.part_id == 4 and not dlg3.isVisible() and any("#3 kontrol edilmeden" in l for l in loglar))
dlg4.close(); pump()
c = w._counters
check("X ile kapatma → NOK kaldı, sayaç değişmedi (NOK 3)", w._review_dlg is None and c["nok"] == 3 and any("#4: pencere cevapsız" in l for l in loglar))

print("\n[OK çekimde pencere yok / özellik kapalı]")
w._handle_snapshot = lambda *a, **k: True
cekim()
check("OK çekimde pencere açılmaz", getattr(w, "_review_dlg", None) is None and w._counters["ok"] == 2)
del w._handle_snapshot
w.config["inspection"]["operator_review"] = False
cekim()
check("özellik kapalıyken NOK'ta pencere yok, NOK sayıldı", getattr(w, "_review_dlg", None) is None and w._counters["nok"] == 4)
w.config["inspection"]["operator_review"] = True

print("\n[paket / PDF / sıfırlama / kalıcılık / Ayarlar]")
w._counters["paket_ok"] = 99; w._counters["paket_esik"] = 100
cekim(); w._review_dlg.btn_ok.click(); pump()
check("DOĞRU ile paket 100'e ulaşınca paket uyarısı açıldı", w._counters["paket_ok"] == 100 and getattr(w, "_paket_dlg", None) is not None)
w._paket_penceresini_kapat()
html = w._build_report_html()
check("PDF: operatör satırı", "Operatör kontrolü" in html and ">2</b> parça DOĞRU" in html, html[html.find("Operatör kontrolü"):][:120])
cekim(); check("sıfırlama öncesi pencere açık", w._review_dlg is not None)
w._reset_counters(); pump()
check("parti Sıfırla → pencere kapandı, operatör sayaçları 0", w._review_dlg is None and w._counters["operator_dogru"] == 0 and w._counters["operator_hatali"] == 0)
cekim(); w._review_dlg.btn_ok.click(); pump()
data = json.load(open(w._sayac_path(), encoding="utf-8"))
check("sayac.json'da operator_dogru kalıcı", data.get("operator_dogru") == 1)
eski = dict(data); eski.pop("operator_dogru"); eski.pop("operator_hatali"); json.dump(eski, open(w._sayac_path(), "w", encoding="utf-8"))
check("eski sayac.json (anahtar yok) → 0", w._load_counters()["operator_dogru"] == 0)
dlg_s = main.SettingsDialog(w.config, w)
check("Ayarlar: kutu işaretli, values() anahtarı", dlg_s.chk_operator_review.isChecked() and dlg_s.values().get("operator_review") is True)
v = dlg_s.values(); v["operator_review"] = False; w._apply_settings(v); pump()
check("Ayarlar → kapalı config'e yazıldı", w.config["inspection"]["operator_review"] is False and not w._operator_review_on())
w.config["inspection"]["operator_review"] = True
w.plc = RecPLC(); w._counters = w._bos_sayac(); w._last_nok_record = None
w._operator_dogru(999)
check("kayıt yokken DOĞRU sayaç değiştirmez, log uyarır", w._counters["ok"] == 0 and any("#999" in l and "kaydı bulunamadı" in l for l in loglar))

w.worker = None; w.worker2 = None; w._review_penceresini_kapat(); w.close()
basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
