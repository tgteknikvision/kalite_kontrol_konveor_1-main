"""Ürün var/yok kapısı (yanlış çekim) — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-24, saha: tetik geldi ama ürün karede yoktu; ürün bulucu Otsu yedeğiyle ray kenarına
286x1088 çerçeve çizdi (referans 708x542) → 3 nokta + YÖN NOK → PLC'ye 1. Kullanıcı kararı:
ürün yoksa NOK SAYILMASIN, operatöre "yanlış çekim" densin, PLC'ye yine 1 yazılsın (seçenek 1).
Burada: saf kapı (alignment.product_present), uçtan uca _capture_full_frame yolu (sayaç, CSV,
PLC çağrısı, durum etiketi, panel, uyarı penceresi, son geçerli karelerin korunması), kapı
kapalı/tolerans/referanssız davranış, PDF, kalıcılık, sıfırlama, tetik aralığı logu, iki kamera.
"""
import os, sys, time, tempfile, yaml, csv, json, copy
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
import main
from inspector.alignment import find_product_box, product_present, box_size_deviation
from inspector.plc import NullPLCAdapter, InspectionState

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=6):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])

print("\n[saf kapı: alignment.product_present]")
check("bugünkü boş kare (286x1088 vs 708x542) → ürün YOK", product_present([393, 0, 286, 1088], [708, 542])[0] is False)
ok_boxes = [(679, 534), (681, 540), (678, 534), (682, 540), (679, 529), (678, 536), (671, 526), (681, 550), (679, 540), (652, 506)]
check("bugünkü 10 OK çerçevesi → ürün VAR", all(product_present([0, 0, bw, bh], [708, 542])[0] for bw, bh in ok_boxes))
check("sapma değeri (en -%50, boy 0)", box_size_deviation([0, 0, 354, 542], [708, 542]) == (-0.5, 0.0))
check("referans yok → kapı devre dışı (VAR, None)", product_present([0, 0, 10, 10], None) == (True, None))
check("tolerans 0 → yalnız birebir geçer", product_present([0, 0, 708, 542], [708, 542], 0)[0] and not product_present([0, 0, 709, 542], [708, 542], 0)[0])
check("geniş tolerans (2.0) → boş kare bile geçer", product_present([393, 0, 286, 1088], [708, 542], 2.0)[0])
check("bozuk referans → devre dışı", product_present([0, 0, 10, 10], [0, 0]) == (True, None) and product_present([0, 0, 10, 10], ["a", 1]) == (True, None))

def urun_karesi():
    f = np.zeros((600, 800, 3), np.uint8); f[150:450, 200:600] = 200; return f          # gri metal 400x300
def bos_kare():
    f = np.zeros((600, 800, 3), np.uint8); f[:, 100:160] = 200; f[:, 300:420] = (40, 200, 40); return f   # şerit + yeşil ray
check("sentetik ürün karesi → çerçeve 440x340 (padding dahil)", find_product_box(urun_karesi(), {}) == [180, 130, 440, 340])
kutu_bos = find_product_box(bos_kare(), {})
check("sentetik boş kare → ürün bulucu yine de tam boy kutu çizer (sorunun kaynağı)", kutu_bos is not None and kutu_bos[3] == 600, str(kutu_bos))

print("\n[uygulama: uçtan uca _capture_full_frame]")
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["type"] = "null"
cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["alignment"] = {"mode": "contour", "foreground": "bright", "min_area_ratio": 0.02, "padding_px": 20}
cfg["dynamic_rois"] = {"1": [10, 10, 50, 50]}; cfg["disabled_rois"] = []
cfg["roi"]["roi_types"] = {"1": "hole"}; cfg["roi"]["reference_box"] = [440, 340]; cfg["roi"]["handedness_check"] = False
cfg["inspection"] = {"trigger_delay_ms": 0}
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow.OPERATOR_DIR = os.path.join(tmpdir, "operator_kontrol")   # gerçek proje klasörüne YAZMA
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
main.QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
main.QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.Ok)
main.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
beeps = []; main.QApplication.beep = staticmethod(lambda: beeps.append(1))

class FakeWorker:
    def __init__(self, frame): self.last_raw_frame = frame; self.last_frame_time = time.time()
    def stop(self): pass
    def wait(self, *a): return True
class RecPLC(NullPLCAdapter):
    def __init__(self): super().__init__(); self.calls = []
    def publish_result(self, ok): self.calls.append(("result", bool(ok))); return super().publish_result(ok)
    def publish_error(self, message): self.calls.append(("error", str(message))); return super().publish_error(message)

w = main.MainWindow(); w.show(); pump()
w.plc = RecPLC()
shown = []; w._display_snapshot = lambda img, n=1: shown.append((n, tuple(img.shape)))
loglar = []; orig_log = w._append_log; w._append_log = lambda m: (loglar.append(m), orig_log(m))
def cekim(frame):
    w.worker = FakeWorker(frame); w._inspection_state = InspectionState.READY; w._trigger_time = time.time()
    w._capture_full_frame(source="plc"); pump()

cekim(urun_karesi())
c = w._counters
check("ürün varken analiz yolu: NOK (gri üründe delik yok), ürün-yok 0, PLC'ye sonuç", c["nok"] == 1 and c["urun_yok"] == 0 and w.plc.calls[-1] == ("result", False), str(w.plc.calls))
check("son geçerli kare + çerçeve saklandı", w._last_full_snapshot is not None and w._last_product_box == [180, 130, 440, 340])
prev_full, prev_snap, prev_box = w._last_full_snapshot, w._last_snapshot, w._last_product_box

n_calls = len(w.plc.calls); shown.clear()
cekim(bos_kare())
c = w._counters
check("boş kare: yanlış çekim 1, NOK hâlâ 1, sistem hatası 0, toplam 2", c["urun_yok"] == 1 and c["nok"] == 1 and c["hata"] == 0 and c["toplam"] == 2, str({k: c[k] for k in ("urun_yok", "nok", "hata", "toplam")}))
yeni = w.plc.calls[n_calls:]
check("PLC'ye 1 yazıldı (publish_error 'ürün algılanamadı'), publish_result ÇAĞRILMADI", len(yeni) == 1 and yeni[0][0] == "error" and "ürün algılanamadı" in yeni[0][1], str(yeni))
check("durum etiketi 'ÜRÜN YOK' turuncu, durum makinesi ERROR", w.lbl_plc.text() == "ÜRÜN YOK" and "ffb454" in w.lbl_plc.styleSheet() and w._inspection_state == InspectionState.ERROR)
panel = w._cam_widgets(1)["errors"]
check("Kontrol Merkezi başlığı 'ÜRÜN ALGILANAMADI', satır yok", "ÜRÜN ALGILANAMADI" in panel.lbl_header.text() and panel._rows == {})
check("log: [ÜRÜN YOK] + çerçeve/referans/sapma/tolerans", any("[ÜRÜN YOK]" in l and "referans 440x340" in l and "tolerans ±%25" in l for l in loglar))
check("son geçerli kare/çerçeve KORUNDU (boş kare yerine geçmedi)", w._last_full_snapshot is prev_full and w._last_snapshot is prev_snap and w._last_product_box == prev_box)
check("ekranda TAM kare gösterildi (kırpık değil)", shown and shown[-1] == (1, (600, 800, 3)), str(shown))
check("nokta dağılımına girmedi (1 (delik) hâlâ 1), paket sayacı etkilenmedi", sum(c["noktalar"].get("1 (delik)", {}).values()) == 1 and c["paket_ok"] == 0, str(c["noktalar"]))
csv_path = os.path.join(main.MainWindow.LOG_DIR, f"parca-{time.strftime('%Y-%m-%d')}.csv")
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("CSV son satır: sonuc URUN_YOK, hatalı nokta 'ürün algılanamadı'", rows[-1][3] == "URUN_YOK" and rows[-1][5] == "ürün algılanamadı" and "referans 440x340" in rows[-1][6], str(rows[-1]))
dlg = getattr(w, "_urun_yok_dlg", None)
check("operatör uyarısı: açık, MODAL DEĞİL, 'Kontrol ettim' butonu, bip", dlg is not None and dlg.isVisible() and dlg.windowModality() == Qt.NonModal and any(b.text() == "Kontrol ettim" for b in dlg.buttons()) and beeps)
check("uyarı metni: ÜRÜN ALGILANAMADI + NOK SAYILMADI + sayı 1", dlg is not None and "ÜRÜN ALGILANAMADI" in dlg.text() and "NOK SAYILMADI" in dlg.text() and ">1<" in dlg.text())

cekim(bos_kare())
c = w._counters
check("ikinci yanlış çekim: sayı 2, AYNI pencere, metin güncel", c["urun_yok"] == 2 and w._urun_yok_dlg is dlg and ">2<" in dlg.text())
[b for b in dlg.buttons() if b.text() == "Kontrol ettim"][0].click(); pump()
check("'Kontrol ettim' → pencere kapandı + log", getattr(w, "_urun_yok_dlg", None) is None and any("Kontrol ettim" in l for l in loglar))
check("sayaç paneli: 'Yanlış çekim (ürün yok): 2' turuncu", w.lbl_counter_missing.text() == "Yanlış çekim (ürün yok): 2" and "ffb454" in w.lbl_counter_missing.styleSheet())

cekim(urun_karesi())
c = w._counters
check("ürün gelince analiz devam: NOK 2, başlık 'PARÇA NOK', durum NOK", c["nok"] == 2 and panel.lbl_header.text() == "PARÇA NOK" and w.lbl_plc.text() == "NOK")

print("\n[önizleme / kapı ayarları]")
w._last_full_snapshot = bos_kare(); loglar.clear()
w._on_panel_threshold_changed(1, "1", "hole_dark_ratio_min", 12.0); pump()
check("önizlemede boş kare çökmez, '[Uyarı] Önizleme yenilenemedi ... ürün karede bulunamadı'", any("Önizleme yenilenemedi" in l and "ürün karede bulunamadı" in l for l in loglar))
w.config["inspection"]["product_presence_check"] = False
cekim(bos_kare()); c = w._counters
check("kapı KAPALI (product_presence_check: false) → eski davranış: boş kare NOK sayılır", c["nok"] == 3 and c["urun_yok"] == 2)
w.config["inspection"]["product_presence_check"] = True
w.config["inspection"]["product_box_tolerance"] = 2.0
cekim(bos_kare()); c = w._counters
check("tolerans 2.0 → boş kare kapıdan geçer (NOK 4)", c["nok"] == 4 and c["urun_yok"] == 2)
w.config["inspection"]["product_box_tolerance"] = 0.25
ref_yedek = w.config["roi"].pop("reference_box")
cekim(bos_kare()); c = w._counters
check("referans kutu yoksa kapı devre dışı (NOK 5)", c["nok"] == 5 and c["urun_yok"] == 2)
w.config["roi"]["reference_box"] = ref_yedek
cekim(bos_kare()); c = w._counters
check("referans geri gelince kapı yine çalışır (yanlış çekim 3)", c["nok"] == 5 and c["urun_yok"] == 3)
w._urun_yok_penceresi = None
if getattr(w, "_urun_yok_dlg", None):
    [b for b in w._urun_yok_dlg.buttons() if b.text() == "Kontrol ettim"][0].click(); pump()

print("\n[rapor / kalıcılık / sıfırlama / tetik aralığı]")
html = w._build_report_html()
check("PDF HTML: 'Yanlış çekim (ürün yok)' sütunu + açıklama", "Yanlış çekim (ürün yok)" in html and "NOK sayılmaz" in html)
pdf = os.path.join(tmpdir, "rapor.pdf"); w._write_report_pdf(pdf)
check("PDF üretildi", os.path.exists(pdf) and open(pdf, "rb").read(5) == b"%PDF-")
data = json.load(open(w._sayac_path(), encoding="utf-8"))
check("sayac.json'da urun_yok kalıcı", data.get("urun_yok") == 3)
eski = dict(data); eski.pop("urun_yok"); json.dump(eski, open(w._sayac_path(), "w", encoding="utf-8"))
c2 = w._load_counters()
check("eski sayac.json (anahtar yok) → urun_yok 0, diğerleri korunur", c2["urun_yok"] == 0 and c2["nok"] == 5)
w._reset_counters(); pump()
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("sıfırla: urun_yok 0, panel gri, CSV SIFIRLA satırında 'yanlış çekim 3'", w._counters["urun_yok"] == 0 and w.lbl_counter_missing.text().endswith(": 0") and rows[-1][3] == "SIFIRLA" and "yanlış çekim 3" in rows[-1][6], rows[-1][6])
w.worker = FakeWorker(urun_karesi()); w._inspection_state = InspectionState.READY
w._capture_from_plc(); pump()
w._inspection_state = InspectionState.READY; loglar.clear()
w._capture_from_plc(); pump()
check("[Tetik] logunda 'önceki tetikten X s sonra' (çift tetik teşhisi)", any("[Tetik] Tam resim" in l and "önceki tetikten" in l and "s sonra" in l for l in loglar))
w._set_inspection_state(InspectionState.READY)
check("_set_inspection_state geriye uyumlu (etiket READY, yeşil)", w.lbl_plc.text() == "READY" and "62b87d" in w.lbl_plc.styleSheet())

print("\n[iki kamera: kamera 2'de ürün yok]")
cfg2 = copy.deepcopy(cfg)
cfg2["cameras"] = {"camera1_enabled": True, "camera2_enabled": True}
cfg2["dynamic_rois_2"] = {"1": [10, 10, 50, 50]}; cfg2["disabled_rois_2"] = []
cfg2["roi2"] = {"roi_types": {"1": "hole"}, "reference_box": [440, 340], "handedness_check": False}
tmp_cfg2 = os.path.join(tmpdir, "config2.yaml"); yaml.safe_dump(cfg2, open(tmp_cfg2, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg2
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg2, encoding="utf-8"))
w2 = main.MainWindow(); w2.show(); pump()
w2.plc = RecPLC(); w2._display_snapshot = lambda img, n=1: None
log2 = []; w2._append_log = lambda m: log2.append(m)
w2._counters = w2._bos_sayac()                       # ortak sayac.json'dan gelen eski sayilari sifirla
w2.worker = FakeWorker(urun_karesi()); w2.worker2 = FakeWorker(bos_kare()); w2._trigger_time = time.time()
w2._capture_full_frame(source="plc"); pump()
check("kamera 2'de ürün yok → yanlış çekim 1, NOK 0, log '[Kamera 2]', PLC'ye 1",
      w2._counters["urun_yok"] == 1 and w2._counters["nok"] == 0 and any("[ÜRÜN YOK]" in l and ("Kamera 2" in l or "K2" in l) for l in log2) and w2.plc.calls[-1][0] == "error", str(w2.plc.calls))
check("kamera 2 satırının paneli bildirimi gösteriyor", "ÜRÜN ALGILANAMADI" in w2._cam_widgets(2)["errors"].lbl_header.text())
if getattr(w2, "_urun_yok_dlg", None):
    [b for b in w2._urun_yok_dlg.buttons() if b.text() == "Kontrol ettim"][0].click(); pump()

for x in (w, w2):
    x.worker = None; x.worker2 = None; x.close()
basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
