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
from PyQt5.QtGui import QPixmap, QColor, QImage, QCloseEvent, QFont, QFontMetrics
from PyQt5.QtCore import Qt, QEvent
from PyQt5 import sip
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
main.MainWindow.OPERATOR_DIR = os.path.join(tmpdir, "operator_kontrol")   # gerçek proje klasörüne YAZMA
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
check("panel 'Operatör: 1 doğru / 0 hatalı / 0 yanlış çekim'", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 0 hatalı / 0 yanlış çekim", w.lbl_counter_operator.text())
check("PLC'ye ek yazım YOK (hâlâ tek sonuç)", w.plc.results == [False])
import glob
gun = time.strftime("%Y-%m-%d"); kdir = main.MainWindow.OPERATOR_DIR
dosyalar = sorted(glob.glob(os.path.join(kdir, gun, "*_resim0001_DOGRU.jpg")))
check("kayıt: gün klasöründe tarih-saat-resim0001-DOGRU.jpg (JPEG) yazıldı", len(dosyalar) == 1 and os.path.getsize(dosyalar[0]) > 1000 and os.path.basename(dosyalar[0]).startswith(gun + "_"), str(dosyalar))
okay = list(csv.reader(open(os.path.join(kdir, "operator_kayit.csv"), encoding="utf-8"), delimiter=";"))
check("kayıt CSV: başlık + satır (tarih;saat;resim;karar;kamera;gerekce;dosya)", okay[0][:4] == ["tarih", "saat", "resim", "karar"] and okay[-1][0] == gun and okay[-1][2] == "1" and okay[-1][3] == "DOGRU" and "delik YOK" in okay[-1][5] and okay[-1][6].endswith("_DOGRU.jpg"), str(okay[-1]))
check("log: kayıt yazıldı", any("[Operatör] Kayıt yazıldı: DOGRU" in l for l in loglar))
# KARAR BANDI (2026-09-28): kayit resminin ustunde karar + tarih/saat + resim no + kamera + gerekce
def renk_say(img, y0, y1, kosul):
    n = 0
    for y in range(y0, y1, 2):
        for x in range(0, img.width(), 2):
            if kosul(img.pixelColor(x, y)): n += 1
    return n
yesil = lambda c: c.green() > 150 and c.green() > c.red() + 60 and c.green() > c.blue() + 40
kirmizi = lambda c: c.red() > 180 and c.red() > c.green() + 80 and c.red() > c.blue() + 80
turuncu = lambda c: c.red() > 200 and 120 < c.green() < 220 and c.blue() < 130
img = QImage(dosyalar[0]); band_h = img.height() - 300
check("kayıt resmi: üstte karar bandı (genişlik aynı 400, yükseklik 300 + bant)", img.width() == 400 and 40 <= band_h <= 200, f"{img.width()}x{img.height()}")
check("DOĞRU bandı yeşil (şerit + yazı)", renk_say(img, 0, band_h, yesil) >= 30, str(renk_say(img, 0, band_h, yesil)))
orta = img.pixelColor(200, band_h + 150)
check("bandın altında orijinal resim bozulmadan duruyor (#556677)", abs(orta.red() - 0x55) < 14 and abs(orta.green() - 0x66) < 14 and abs(orta.blue() - 0x77) < 14, orta.name())
lines = w._operator_banner_lines(dlg, "DOGRU", "2026-09-28 12:48:23")
check("band satırları: karar (yeşil, kalın) + tarih/resim/kamera + gerekçe", lines[0][0].startswith("OPERATÖR: DOĞRU") and lines[0][1] == "#2ecc71" and lines[0][2] is True and "2026-09-28 12:48:23" in lines[1][0] and "Resim #0001" in lines[1][0] and "Kamera 1" in lines[1][0] and lines[2][0].startswith("Gerekçe: 1: delik YOK"), str(lines))

print("\n[HATALI → NOK kalır]")
cekim(); dlg2 = w._review_dlg
dlg2.btn_nok.click(); pump()
c = w._counters
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("NOK 1 kaldı, operator_hatali 1, CSV OPERATOR_HATALI", c["nok"] == 1 and c["ok"] == 1 and c["operator_hatali"] == 1 and rows[-1][3] == "OPERATOR_HATALI" and c["noktalar"].get("1 (delik)"))
check("panel 'Operatör: 1 doğru / 1 hatalı / 0 yanlış çekim'", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 1 hatalı / 0 yanlış çekim")
check("pencerede 3. buton YANLIŞ ÇEKİM (turuncu vurgu), gerekçe etiketi 3 seçeneği açıklıyor", "YANLIŞ ÇEKİM" in dlg2.btn_yanlis.text() and dlg2.btn_yanlis.property("accent") == "warning")

check("HATALI kaydı: resim0002_HATALI.jpg + CSV", len(glob.glob(os.path.join(kdir, gun, "*_resim0002_HATALI.jpg"))) == 1 and list(csv.reader(open(os.path.join(kdir, "operator_kayit.csv"), encoding="utf-8"), delimiter=";"))[-1][3] == "HATALI")
img2 = QImage(glob.glob(os.path.join(kdir, gun, "*_resim0002_HATALI.jpg"))[0])
check("HATALI bandı kırmızı", img2.height() > 300 and renk_say(img2, 0, img2.height() - 300, kirmizi) >= 30, str(renk_say(img2, 0, img2.height() - 300, kirmizi)))
check("HATALI band metni", w._operator_banner_lines(dlg2, "HATALI", "x")[0][0].startswith("OPERATÖR: HATALI") and "NOK sayıldı" in w._operator_banner_lines(dlg2, "HATALI", "x")[0][0])
print("\n[YANLIŞ ÇEKİM seçeneği (NOK kaydı)]")
cekim(); dlg_y = w._review_dlg; n_nok = w._counters["nok"]; n_uy = w._counters["urun_yok"]
dlg_y.btn_yanlis.click(); pump()
c = w._counters
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("YANLIŞ ÇEKİM: NOK−1, yanlış çekim+1, OK değişmedi, operator_yanlis 1, CSV OPERATOR_YANLIS_CEKIM", c["nok"] == n_nok - 1 and c["urun_yok"] == n_uy + 1 and c["ok"] == 1 and c["operator_yanlis"] == 1 and rows[-1][3] == "OPERATOR_YANLIS_CEKIM", str({k: c[k] for k in ("nok", "urun_yok", "ok", "operator_yanlis")}))
check("nokta dağılımı ve NOK listesi geri alındı (1 (delik) yine 1, son_nok 1)", sum(c["noktalar"].get("1 (delik)", {}).values()) == 1 and len(c["son_nok"]) == 1, str(c["noktalar"]))
check("panel '1 doğru / 1 hatalı / 1 yanlış çekim' + yanlış çekim satırı 1", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 1 hatalı / 1 yanlış çekim" and w.lbl_counter_missing.text().endswith(": 1"))
dy = glob.glob(os.path.join(kdir, gun, "*_resim0003_YANLIS_CEKIM.jpg"))
check("kayıt: resim0003_YANLIS_CEKIM.jpg + turuncu bant + CSV karar YANLIS_CEKIM", len(dy) == 1 and renk_say(QImage(dy[0]), 0, QImage(dy[0]).height() - 300, turuncu) >= 30 and list(csv.reader(open(os.path.join(kdir, "operator_kayit.csv"), encoding="utf-8"), delimiter=";"))[-1][3] == "YANLIS_CEKIM")
check("band metni YANLIŞ ÇEKİM (sayılmadı)", w._operator_banner_lines(dlg_y, "YANLIS_CEKIM", "x")[0][0].startswith("OPERATÖR: YANLIŞ ÇEKİM") and "sayılmadı" in w._operator_banner_lines(dlg_y, "YANLIS_CEKIM", "x")[0][0])
check("PLC'ye ek yazım yok", len(w.plc.results) == 3)

print("\n[açıkken yeni NOK / cevapsız kapatma]")
cekim(); dlg3 = w._review_dlg
cekim(); dlg4 = w._review_dlg
check("yeni NOK gelince eski pencere kapandı/silindi (cevapsız → NOK kaldı), yeni #5", dlg4 is not dlg3 and dlg4.part_id == 5 and (sip.isdeleted(dlg3) or not dlg3.isVisible()) and any("#4 kontrol edilmeden" in l and "NOK olarak kaldı" in l for l in loglar))
dlg4.close(); pump()
c = w._counters
check("X ile kapatma → NOK kaldı, sayaç değişmedi (NOK 3)", w._review_dlg is None and c["nok"] == 3 and any("#5: pencere cevapsız" in l for l in loglar))
check("cevapsız kayıtlar: resim0004 ve resim0005 CEVAPSIZ", len(glob.glob(os.path.join(kdir, gun, "*_resim0004_CEVAPSIZ.jpg"))) == 1 and len(glob.glob(os.path.join(kdir, gun, "*_resim0005_CEVAPSIZ.jpg"))) == 1)
img4 = QImage(glob.glob(os.path.join(kdir, gun, "*_resim0005_CEVAPSIZ.jpg"))[0])
gri_renk = lambda c: abs(c.red() - 176) < 25 and abs(c.green() - 183) < 25 and abs(c.blue() - 195) < 25   # (gri = kare dizisi, karıştırma)
check("CEVAPSIZ bandı gri, metin 'cevaplanmadı'", renk_say(img4, 0, img4.height() - 300, gri_renk) >= 30 and "cevaplanmadı" in w._operator_banner_lines(dlg4, "CEVAPSIZ", "x")[0][0], str(renk_say(img4, 0, img4.height() - 300, gri_renk)))
fm = QFontMetrics(QFont("Arial", 12))
uzun = " ".join(f"kelime{i}" for i in range(80))
sar = w._wrap_text(uzun, fm, 200, 3)
check("uzun gerekçe en fazla 3 satıra sarılır, sonu '…'", len(sar) == 3 and sar[-1].endswith("…") and all(fm.horizontalAdvance(s) <= 200 for s in sar), str(sar))
check("kısa metin tek satır", w._wrap_text("kısa", fm, 200, 3) == ["kısa"])
class _FakeDlg: part_id = 7; cam_no = 2; gerekce = uzun; _pm = pm
buyuk = w._operator_kayit_resmi(pm, "HATALI", _FakeDlg(), "2026-09-28 13:00:00")
kisa = w._operator_kayit_resmi(pm, "HATALI", dlg4, "2026-09-28 13:00:00")
check("uzun gerekçede bant büyür ama sınırlı (≤ 2 ek satır)", buyuk.height() > kisa.height() and buyuk.height() - kisa.height() <= 2 * (QFontMetrics(QFont("Arial")).height() + 14) and buyuk.width() == 400, f"{kisa.height()} → {buyuk.height()}")
app.sendPostedEvents(None, QEvent.DeferredDelete); pump()
check("kapanan pencereler bellekten silindi (deleteLater; her biri tam çözünürlük resim taşıyordu)", sip.isdeleted(dlg3) and sip.isdeleted(dlg4) and not w.findChildren(main.OperatorReviewDialog))

print("\n[OK çekimde pencere yok / özellik kapalı]")
w._handle_snapshot = lambda *a, **k: True
cekim()
check("OK çekimde pencere açılmaz", getattr(w, "_review_dlg", None) is None and w._counters["ok"] == 2)
del w._handle_snapshot
w.config["inspection"]["operator_review"] = False
cekim()
check("özellik kapalıyken NOK'ta pencere yok, NOK sayıldı", getattr(w, "_review_dlg", None) is None and w._counters["nok"] == 4)
w.config["inspection"]["operator_review"] = True

print("\n[kayıt kapalı / eski klasör temizliği]")
w.config["inspection"]["operator_kayit"] = False
n_once = len(glob.glob(os.path.join(kdir, gun, "*.jpg")))
cekim(); w._review_dlg.btn_ok.click(); pump()
check("kayıt kapalıyken dosya yazılmaz", len(glob.glob(os.path.join(kdir, gun, "*.jpg"))) == n_once)
w.config["inspection"]["operator_kayit"] = True
eski = os.path.join(kdir, "2020-01-01"); os.makedirs(eski, exist_ok=True); open(os.path.join(eski, "x.jpg"), "w").close()
yabanci = os.path.join(kdir, "notlar"); os.makedirs(yabanci, exist_ok=True)
cekim(); w._review_dlg.btn_nok.click(); pump()
check("30 günden eski gün klasörü silindi, gün-dışı klasör dokunulmadı", not os.path.exists(eski) and os.path.isdir(yabanci) and any("Eski kayıt klasörü silindi" in l for l in loglar))
w.config["inspection"]["operator_kayit_gun"] = 0
os.makedirs(eski, exist_ok=True); cekim(); w._review_dlg.btn_nok.click(); pump()
check("saklama 0 gün = hiç silme", os.path.isdir(eski))
w.config["inspection"]["operator_kayit_gun"] = 30

print("\n[paket / PDF / sıfırlama / kalıcılık / Ayarlar]")
w._counters["paket_ok"] = 99; w._counters["paket_esik"] = 100
cekim(); w._review_dlg.btn_ok.click(); pump()
check("DOĞRU ile paket 100'e ulaşınca paket uyarısı açıldı", w._counters["paket_ok"] == 100 and getattr(w, "_paket_dlg", None) is not None)
w._paket_penceresini_kapat()
html = w._build_report_html()
check("PDF: operatör satırı (sayaçla uyumlu)", "Operatör kontrolü" in html and f">{w._counters['operator_dogru']}</b> parça DOĞRU" in html and f">{w._counters['operator_hatali']}</b> parça HATALI" in html, html[html.find("Operatör kontrolü"):][:120])
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
check("Ayarlar: kayıt kutusu + gün (30)", dlg_s.chk_operator_kayit.isChecked() and dlg_s.spin_operator_gun.value() == 30 and dlg_s.values().get("operator_kayit") is True and dlg_s.values().get("operator_kayit_gun") == 30)
v = dlg_s.values(); v["operator_review"] = False; w._apply_settings(v); pump()
v["operator_kayit"] = False; v["operator_kayit_gun"] = 7; w._apply_settings(v); pump()
check("Ayarlar → kapalı config'e yazıldı (review, kayıt, gün 7)", w.config["inspection"]["operator_review"] is False and not w._operator_review_on() and w.config["inspection"]["operator_kayit"] is False and w.config["inspection"]["operator_kayit_gun"] == 7)
w.config["inspection"]["operator_kayit"] = True; w.config["inspection"]["operator_kayit_gun"] = 30
w.config["inspection"]["operator_review"] = True
w.plc = RecPLC(); w._counters = w._bos_sayac(); w._last_nok_record = None
w._operator_dogru(999)
check("kayıt yokken DOĞRU sayaç değiştirmez, log uyarır", w._counters["ok"] == 0 and any("#999" in l and "kaydı bulunamadı" in l for l in loglar))

print("\n[ürün yok → aynı pencere, 3 seçenek]")
w.plc = RecPLC(); w._counters = w._bos_sayac(); w._last_nok_record = None; w._trigger_gap_s = None
def urun_yok_olayi():
    w._capture_counter += 1
    exc = main.ProductMissing(1, [0, 0, 100, 100], [400, 300], (-0.75, -0.667), 0.25)
    w._on_product_missing(exc, {1: gri_kare}, "plc"); pump()
gri_kare = gri
urun_yok_olayi(); d = w._review_dlg; c = w._counters
check("ürün yok: eski 'Kontrol ettim' kutusu YOK, operatör penceresi açık (tür urun_yok, başlıkta ÜRÜN YOK)", getattr(w, "_urun_yok_dlg", None) is None and d is not None and d.kind == "urun_yok" and "ÜRÜN YOK" in d.windowTitle() and "BULAMADI" in d.findChildren(main.QLabel)[0].text())
check("sayaç: yanlış çekim 1, NOK 0, OK 0; butonlar 'NOK say' / 'evet, ürün yoktu'", c["urun_yok"] == 1 and c["nok"] == 0 and c["ok"] == 0 and "NOK say" in d.btn_nok.text() and "ürün yoktu" in d.btn_yanlis.text())
check("gerekçe: ÜRÜN ALGILANAMADI + çerçeve/referans", "ÜRÜN ALGILANAMADI" in d.lbl_reasons.text() and "referans 400x300" in d.lbl_reasons.text(), d.lbl_reasons.text()[:120])
d.btn_ok.click(); pump(); c = w._counters
check("ürün yok + DOĞRU → yanlış çekim 0, OK 1, paket 1, operator_dogru 1", c["urun_yok"] == 0 and c["ok"] == 1 and c["paket_ok"] == 1 and c["operator_dogru"] == 1 and c["nok"] == 0)
urun_yok_olayi(); w._review_dlg.btn_nok.click(); pump(); c = w._counters
check("ürün yok + HATALI → yanlış çekim 0, NOK 1, NOK listesinde 'operatör: HATALI'", c["urun_yok"] == 0 and c["nok"] == 1 and c["ok"] == 1 and c["son_nok"] and "operatör: HATALI" in c["son_nok"][-1]["sebep"] and c["operator_hatali"] == 1, str(c["son_nok"][-1:]))
urun_yok_olayi(); pid_y = w._review_dlg.part_id; w._review_dlg.btn_yanlis.click(); pump(); c = w._counters
check("ürün yok + YANLIŞ ÇEKİM → yanlış çekim 1 (değişmez), NOK 1, OK 1, operator_yanlis 1", c["urun_yok"] == 1 and c["nok"] == 1 and c["ok"] == 1 and c["operator_yanlis"] == 1)
fy = glob.glob(os.path.join(kdir, gun, f"*_resim{pid_y:04d}_YANLIS_CEKIM.jpg"))
check("kayıt resmi: band 'Program kararı: ÜRÜN YOK'", len(fy) == 1 and "ÜRÜN YOK" in w._operator_banner_lines(type("D", (), {"part_id": pid_y, "cam_no": 1, "gerekce": "-", "kind": "urun_yok"})(), "YANLIS_CEKIM", "x")[1][0])
urun_yok_olayi(); pid_x = w._review_dlg.part_id; w._review_dlg.close(); pump(); c = w._counters
check("ürün yok + X → CEVAPSIZ, yanlış çekim 2 (kaldı), log 'yanlış çekim olarak kaldı'", c["urun_yok"] == 2 and w._review_dlg is None and len(glob.glob(os.path.join(kdir, gun, f"*_resim{pid_x:04d}_CEVAPSIZ.jpg"))) == 1 and any(f"#{pid_x}: pencere cevapsız" in l and "yanlış çekim olarak kaldı" in l for l in loglar))
check("panel: '1 doğru / 1 hatalı / 1 yanlış çekim', PDF satırında YANLIŞ ÇEKİM", w.lbl_counter_operator.text() == "Operatör: 1 doğru / 1 hatalı / 1 yanlış çekim" and "YANLIŞ ÇEKİM" in w._build_report_html())
w.config["inspection"]["operator_review"] = False
urun_yok_olayi()
check("operatör penceresi kapalıyken eski 'Kontrol ettim' kutusu (geriye uyum)", w._review_dlg is None and getattr(w, "_urun_yok_dlg", None) is not None and w._counters["urun_yok"] == 3)
[b for b in w._urun_yok_dlg.buttons() if b.text() == "Kontrol ettim"][0].click(); pump()
w.config["inspection"]["operator_review"] = True

print("\n[uygulama kapanırken açık pencere]")
w.plc = RecPLC(); cekim(); pid_acik = w._review_dlg.part_id
w.worker = None; w.worker2 = None
ev = QCloseEvent(); w.closeEvent(ev)
check("closeEvent: açık operatör penceresi CEVAPSIZ olarak kaydedildi", ev.isAccepted() and w._review_dlg is None and len(glob.glob(os.path.join(kdir, gun, f"*_resim{pid_acik:04d}_CEVAPSIZ.jpg"))) == 1)
basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
