"""Sayaç + CSV + PDF rapor — ekransız test (gerçek config/log/kameraya DOKUNMAZ)."""
import os, sys, time, tempfile, yaml, json, csv
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np
from PyQt5.QtWidgets import QApplication, QMessageBox
import main

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))

app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["manual_mode"] = True; cfg["alignment"]["mode"] = "off"
cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["dynamic_rois"] = {}; cfg["roi"]["roi_types"] = {"1": "hole", "3": "notch"}; cfg["roi"]["point_overrides"] = {}
cfg["inspection"]["trigger_delay_ms"] = 100
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
main.QMessageBox.warning = staticmethod(lambda *a, **k: None)
main.QMessageBox.critical = staticmethod(lambda *a, **k: None)
main.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

w = main.MainWindow(); w.show(); app.processEvents()
print("\n[sayaç] temel sayım")
check("başlangıçta sıfır", w._counters["toplam"] == 0 and w.lbl_counter_total.text() == "Geçen parça: 0")
ok_res = {"1": {"ok": True, "msg": "delik VAR (acik %25.0, yuvarlak 0.9, dolgu 0.95)", "metrics": {"black_ratio": 25.0, "core_ratio": 8.0}},
          "3": {"ok": True, "msg": "oluk VAR (koyu %50, blob %40, en/boy 2.0)", "metrics": {"black_ratio": 50.0, "core_ratio": 10.0}},
          "YON": {"ok": True, "msg": "yon dogru (delik fark -26, ref -26)", "metrics": {}}}
nok_res = {"1": {"ok": False, "msg": "delik YOK (acik %0.0 < %10, kapali/eksik/tikali)", "metrics": {"black_ratio": 0.0, "core_ratio": 0.0}},
           "3": {"ok": False, "msg": "oluk YOK (koyu %20.4 bant disi %40-%95)", "metrics": {"black_ratio": 20.4, "core_ratio": 3.0}},
           "YON": {"ok": True, "msg": "yon dogru", "metrics": {}}}
w._record_part(1, True, {1: ok_res}, "plc")
w._record_part(2, False, {1: nok_res}, "plc")
w._record_part(None, False, {}, "plc", error="Kamera 1: Kamera görüntüsü yok. Lütfen bekleyin")
c = w._counters
check("toplam 3 / OK 1 / NOK 1 / hata 1", (c["toplam"], c["ok"], c["nok"], c["hata"]) == (3, 1, 1, 1), str((c["toplam"], c["ok"], c["nok"], c["hata"])))
check("nokta dağılımı: 1 (delik) kapalı/eksik/tıkalı", c["noktalar"].get("1 (delik)", {}).get("kapalı / eksik / tıkalı") == 1, str(c["noktalar"]))
check("nokta dağılımı: 3 (çentik) oran bant dışı", c["noktalar"].get("3 (çentik)", {}).get("oluk yok (oran bant dışı)") == 1)
check("YÖN OK olduğu için dağılıma girmedi", "YÖN" not in c["noktalar"])
check("sistem hatası sebebi kısaltılıp sayıldı", c["hata_sebepleri"].get("Kamera 1: Kamera görüntüsü yok") == 1, str(c["hata_sebepleri"]))
check("son_nok listesinde 1 kayıt, iki sebep", len(c["son_nok"]) == 1 and "1 (delik) = kapalı" in c["son_nok"][0]["sebep"] and "3 (çentik)" in c["son_nok"][0]["sebep"], str(c["son_nok"]))
check("panel: Geçen parça 3, NOK yüzde", w.lbl_counter_total.text() == "Geçen parça: 3" and "%33.3" in w.lbl_counter_nok.text(), w.lbl_counter_nok.text())
check("panel dağılım metni", "1 (delik): 1" in w.lbl_counter_breakdown.text() and "Sistem:" in w.lbl_counter_breakdown.text(), w.lbl_counter_breakdown.text())

print("\n[CSV + kalıcılık]")
csv_path = os.path.join(main.MainWindow.LOG_DIR, f"parca-{time.strftime('%Y-%m-%d')}.csv")
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("CSV: başlık + 3 satır", len(rows) == 4 and rows[0][0] == "zaman", str(len(rows)))
check("CSV NOK satırı: sonuç/sebep/ölçüm", rows[2][3] == "NOK" and "1 (delik)" in rows[2][5] and "koyu 0.0" in rows[2][7], str(rows[2]))
check("CSV hata satırı: resim '-' ve HATA", rows[3][1] == "-" and rows[3][3] == "HATA")
check("CSV gecikme sütunu 100", rows[1][4] == "100")
check("sayac.json yazıldı", os.path.exists(os.path.join(main.MainWindow.LOG_DIR, "sayac.json")))
w2 = main.MainWindow(); w2.show(); app.processEvents()
check("yeniden açılınca sayılar korunuyor", w2._counters["toplam"] == 3 and w2._counters["nok"] == 1 and w2.lbl_counter_total.text() == "Geçen parça: 3")

print("\n[kategori eşlemesi]")
kat = main.MainWindow._nok_reason_category
check("şekil", kat("delik YOK (sekil uygun degil: yuvarlak 0.26, dolgu 0.13, kenar 3)") == "şekil uygun değil")
check("çekirdek", kat("delik YOK (cekirdek %0.5 < %2.0, tikali/dolu olabilir)") == "derinlik yetersiz")
check("ayna", kat("AYNA/TERS parca (delik parlaklik farki -70, referans +48 ters)") == "ayna / ters parça")
check("oluk şekil", kat("oluk YOK (sekil yok: blob %16.3<%25, en/boy 1.0)") == "oluk yok (şekil yok)")
check("bilinmeyen mesaj → parantez öncesi", kat("bambaska bir sey (x)") == "bambaska bir sey")

print("\n[iki kamera etiketi]")
w2._record_part(5, False, {1: nok_res, 2: ok_res}, "plc")
check("iki kamerada etiket 'K1 1 (delik)'", "K1 1 (delik)" in w2._counters["noktalar"], str(list(w2._counters["noktalar"])))

print("\n[PDF]")
pdf = os.path.join(tmpdir, "rapor.pdf")
html = w2._build_report_html()
check("HTML: başlık + özet + dağılım + NOK listesi", all(x in html for x in ("Konveyör Denetim Raporu", "Geçen parça", "1 (delik)", "NOK parçalar", "Kamera 1: Kamera görüntüsü yok")))
w2._write_report_pdf(pdf)
check("PDF dosyası üretildi (%PDF, >2 KB)", os.path.exists(pdf) and open(pdf, "rb").read(5) == b"%PDF-" and os.path.getsize(pdf) > 2000, f"{os.path.getsize(pdf) if os.path.exists(pdf) else 0} bayt")

print("\n[sıfırla]")
loglar = []; w2._append_log = lambda m: loglar.append(m)
w2._reset_counters()
rows = list(csv.reader(open(csv_path, encoding="utf-8"), delimiter=";"))
check("sıfırlama: sayılar 0, yeni başlangıç, CSV'de SIFIRLA satırı, log", w2._counters["toplam"] == 0 and w2._counters["noktalar"] == {} and rows[-1][3] == "SIFIRLA" and any("[Sayaç] Sıfırlandı" in l for l in loglar) and w2.lbl_counter_total.text() == "Geçen parça: 0")

print("\n[uçtan uca: _capture_full_frame → sayaç]")
class FakeWorker:
    def __init__(self): self.last_raw_frame = np.full((300, 400, 3), 200, np.uint8); self.last_frame_time = time.time()
    def stop(self): pass
    def wait(self, *a): return True
w3 = main.MainWindow(); w3.show(); app.processEvents()
w3.worker = FakeWorker(); w3._display_snapshot = lambda img, n=1: None
w3._trigger_time = time.time()
w3._capture_full_frame(source="plc")                      # nokta yok -> "Üretim hazır değil" -> hata
check("nokta yokken çekim 'sistem hatası' sayıldı", w3._counters["hata"] == 1 and any("Aktif kontrol noktası yok" in k for k in w3._counters["hata_sebepleri"]), str(w3._counters["hata_sebepleri"]))
w3._inspection_state = main.InspectionState.READY
w3.config["dynamic_rois"] = {"1": [10, 10, 50, 50]}; w3.config["roi"]["roi_types"] = {"1": "hole"}
w3._capture_full_frame(source="plc")                      # gri kare -> delik yok -> NOK
check("nokta varken NOK sayıldı ve sebep 'kapalı/eksik/tıkalı'", w3._counters["nok"] == 1 and w3._counters["noktalar"].get("1 (delik)", {}).get("kapalı / eksik / tıkalı") == 1, str(w3._counters["noktalar"]))
check("toplam 2 (1 hata + 1 NOK)", w3._counters["toplam"] == 2)

for x in (w, w2, w3):
    x.worker = None; x.worker2 = None; x.close()
basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
