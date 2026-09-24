"""Paket dolunca KONVEYÖR DUR bayrağı (PLC HR102) — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-24, kullanıcı: "100 adete ulaşınca PLC'yi durdur desin, konveyör dursun". Paket hedefine
ulaşılınca PLC'deki 'dur' register'ına (plc.registers.stop, vars. HR102) 1 yazılır; Sıfırla / Devam et /
parti Sıfırla / paket adedi hedefi aşınca 0. PLC bağlı değilken yazılamazsa _poll_plc bağlantı gelince
yazar; yeniden bağlanınca bayrak yeniden yazılır; açılışta paket doluysa uyarı + bayrak, değilse 0.
Modbus adapter: HR<stop> beyaz listede, başka adres engelli. Ayarlar: kutu + register.
"""
import os, sys, time, tempfile, yaml, json
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
from PyQt5.QtWidgets import QApplication, QMessageBox
import main
from inspector.plc import NullPLCAdapter, ModbusTCPPLCAdapter, ALLOWED_REGISTERS, STOP_REGISTER

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))
def pump(n=6):
    for _ in range(n): app.processEvents()

app = QApplication.instance() or QApplication([])
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["type"] = "null"; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
cfg["inspection"].pop("paket_adedi", None)
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow.OPERATOR_DIR = os.path.join(tmpdir, "operator_kontrol")   # gerçek proje klasörüne YAZMA
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
main.QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
main.QApplication.beep = staticmethod(lambda: None)

class RecPLC(NullPLCAdapter):
    def __init__(self, connected=True): super().__init__(); self.stops = []; self.connected = connected; self.fail = False
    def publish_stop(self, stop):
        if self.fail: return False
        self.stops.append(bool(stop)); return super().publish_stop(stop)
    def is_connected(self): return self.connected

ok_res = {"1": {"ok": True, "msg": "delik VAR", "metrics": {"black_ratio": 25.0, "core_ratio": 8.0}}}

print("\n[sabitler]")
check("STOP_REGISTER 102 ve beyaz listede", STOP_REGISTER == 102 and 102 in ALLOWED_REGISTERS and {100, 101} <= ALLOWED_REGISTERS)

print("\n[açılış: paket dolu değil → bayrak 0'a çekilir]")
w = main.MainWindow(); w.show(); pump()
w.plc = RecPLC(); w._stop_written = None
loglar = []; orig = w._append_log; w._append_log = lambda m: (loglar.append(m), orig(m))
check("başlangıçta istenen bayrak 0 (paket boş)", w._stop_desired is False)
w._poll_plc(); pump()
check("ilk poll: PLC'ye 0 yazıldı (eski takılı bayrak temizliği) + log", w.plc.stops == [False] and w._stop_written is False and any("Konveyör serbest" in l and "HR102=0" in l for l in loglar), str(w.plc.stops))
w._poll_plc(); w._poll_plc()
check("bayrak eşitken tekrar yazılmaz", w.plc.stops == [False])

print("\n[100 OK → DUR]")
for i in range(100): w._record_part(i + 1, True, {1: ok_res}, "plc")
pump()
dlg = w._paket_dlg
check("100. parçada PLC'ye 1 yazıldı (bir kez) + log KONVEYÖR DURDURULDU", w.plc.stops == [False, True] and w._stop_written is True and any("KONVEYÖR DURDURULDU" in l and "HR102=1" in l for l in loglar), str(w.plc.stops))
check("uyarı metni konveyörün durduğunu söylüyor", dlg is not None and "KONVEYÖR DURDURULDU" in dlg.text() and "HR102" in dlg.text())
check("bilgi metni: ikisi de konveyörü çalıştırır", dlg is not None and "konveyörü yeniden çalıştırır" in dlg.informativeText())
check("panel 'PAKET DOLDU: 100 / 100 — konveyör durdu'", w.lbl_paket.text() == "PAKET DOLDU: 100 / 100 — konveyör durdu", w.lbl_paket.text())
w._record_part(101, True, {1: ok_res}, "plc"); pump()
check("pencere açıkken yeni parça: bayrak tekrar yazılmaz", w.plc.stops == [False, True])

print("\n[Devam et → çalış]")
[b for b in dlg.buttons() if b.text() == "Devam et"][0].click(); pump()
check("Devam et → PLC'ye 0 + log 'serbest'", w.plc.stops == [False, True, False] and any("Konveyör serbest" in l and "Devam et" in l for l in loglar), str(w.plc.stops))
check("panel 'Paket: 101 / 200'", w.lbl_paket.text() == "Paket: 101 / 200")

print("\n[200 → DUR → Sıfırla → çalış]")
for i in range(99): w._record_part(102 + i, True, {1: ok_res}, "plc")
pump(); dlg2 = w._paket_dlg
check("200'de yine 1", w.plc.stops[-1] is True and dlg2 is not None)
[b for b in dlg2.buttons() if b.text() == "Sıfırla"][0].click(); pump()
check("Sıfırla → 0, paket 0/100", w.plc.stops[-1] is False and w._counters["paket_ok"] == 0 and any("Sıfırla" in l and "HR102=0" in l for l in loglar))

print("\n[X ile kapatma / parti sıfırlama / paket adedi değişimi]")
for i in range(100): w._record_part(300 + i, True, {1: ok_res}, "plc")
pump(); n0 = len(w.plc.stops); check("100'de 1", w.plc.stops[-1] is True)
w._paket_dlg.close(); pump()
check("X ile kapatınca (= Devam et) 0", w.plc.stops[-1] is False and len(w.plc.stops) == n0 + 1)
for i in range(100): w._record_part(400 + i, True, {1: ok_res}, "plc")
pump(); check("200'de 1 (bayrak)", w.plc.stops[-1] is True and w._paket_dlg is not None)
w._reset_counters(); pump()
check("parti Sıfırla → pencere kapandı, 0 yazıldı", w._paket_dlg is None and w.plc.stops[-1] is False and any("parti sıfırlandı" in l and "HR102=0" in l for l in loglar))
for i in range(100): w._record_part(500 + i, True, {1: ok_res}, "plc")
pump(); check("yeni partide 100'de 1", w.plc.stops[-1] is True and w._paket_dlg is not None)
w.spin_paket.setValue(150); pump()
check("paket adedi 150'ye çıkınca (100 < 150): pencere kapandı, 0 yazıldı, hedef 150", w._paket_dlg is None and w.plc.stops[-1] is False and w._counters["paket_esik"] == 150, str((w._counters["paket_esik"], w.plc.stops[-3:])))
w.spin_paket.setValue(100); pump()

print("\n[bağlantı yokken / kopup gelince]")
w2 = main.MainWindow(); w2.show(); pump()
w2.plc = RecPLC(connected=False); w2._stop_written = None
log2 = []; w2._append_log = lambda m: log2.append(m)
for i in range(100): w2._record_part(i + 1, True, {1: ok_res}, "plc")
pump()
check("PLC bağlı değilken: istenen 1 ama yazılmadı, hata sessiz (bağlantı gelince)", w2._stop_desired is True and w2.plc.stops == [] and w2._stop_written is None)
w2.plc.connected = True
w2._last_plc_connected = False; w2._poll_plc(); pump()
check("bağlantı gelince poll 1 yazdı", w2.plc.stops == [True] and w2._stop_written is True, str(w2.plc.stops))
w2._last_plc_connected = False; w2._update_plc_connection_status()   # kopup yeniden bağlandı
check("yeniden bağlanınca bayrak 'bilinmiyor' (yeniden yazılacak)", w2._stop_written is None)
w2._poll_plc(); check("→ tekrar 1 yazıldı", w2.plc.stops == [True, True])
w2.plc.fail = True; w2._stop_written = None; w2._poll_plc()
check("yazım başarısız → log '[PLC HATA] ... tekrar denenecek', bayrak bilinmiyor kalır", w2._stop_written is None and any("[PLC HATA] Konveyör dur bayrağı" in l for l in log2))
w2.plc.fail = False
w2._paket_penceresini_kapat()

print("\n[açılışta paket dolu (sayac.json) → uyarı + bayrak 1]")
path = w._sayac_path(); data = json.load(open(path, encoding="utf-8"))
data["paket_ok"] = 100; data["paket_esik"] = 100; json.dump(data, open(path, "w", encoding="utf-8"))
w3 = main.MainWindow(); w3.show(); pump()
check("açılışta istenen bayrak 1 ve uyarı penceresi açık", w3._stop_desired is True and getattr(w3, "_paket_dlg", None) is not None)
w3.plc = RecPLC(); w3._stop_written = None; w3._poll_plc()
check("poll → PLC'ye 1 yazıldı", w3.plc.stops == [True])
w3._paket_penceresini_kapat()

print("\n[özellik kapalı]")
w.config["plc"]["paket_dolu_durdur"] = False
w._reset_counters(); pump(); n1 = len(w.plc.stops)
for i in range(100): w._record_part(600 + i, True, {1: ok_res}, "plc")
pump()
check("kapalıyken 100'de bayrak yazılmaz, metinde konveyör yok", len(w.plc.stops) == n1 and w._paket_dlg is not None and "KONVEYÖR" not in w._paket_dlg.text() and w.lbl_paket.text() == "PAKET DOLDU: 100 / 100")
w._paket_penceresini_kapat(); w.config["plc"]["paket_dolu_durdur"] = True

print("\n[Ayarlar: kutu + register + uygulama]")
dlg_s = main.SettingsDialog(w.config, w)
check("Ayarlar'da 'Paket dolunca konveyörü durdur' işaretli ve register 102", dlg_s.chk_paket_dur.isChecked() and dlg_s.spin_stop_reg.value() == 102)
v = dlg_s.values()
check("values() yeni anahtarları içeriyor", v.get("plc_paket_dur") is True and v.get("plc_stop_reg") == 102)
w._stop_written = True; w._stop_desired = True; n2 = len(w.plc.stops)
v_off = dict(v); v_off["plc_paket_dur"] = False
w._apply_settings(v_off); pump()
check("özellik kapatılınca PLC bayrağı 0'a çekildi + config false", w.plc.stops[-1] is False and len(w.plc.stops) == n2 + 1 and w.config["plc"]["paket_dolu_durdur"] is False)
v_on = dict(v); v_on["plc_paket_dur"] = True; v_on["plc_stop_reg"] = 110
w._apply_settings(v_on); pump()
check("register 110 → config registers.stop=110, PLC adapter yenilendi (bayrak bilinmiyor)", w.config["plc"]["registers"]["stop"] == 110 and w._stop_register() == 110 and w._stop_written is None and any("PLC ayarları değişti" in l for l in loglar))
w.config["plc"]["registers"]["stop"] = 102

print("\n[Modbus adapter: HR<stop> yazımı + beyaz liste]")
class FakeClient:
    def __init__(self): self.writes = []
    def write_register(self, address=None, value=None, **kw):
        self.writes.append((int(address), int(value))); return type("R", (), {"isError": lambda self: False})()
    def close(self): pass
a = ModbusTCPPLCAdapter({"host": "127.0.0.1", "port": 1, "timeout_s": 0.05, "reconnect_s": 100, "unit_id": 0, "registers": {"stop": 105}})
a._client = FakeClient(); a._connected = True
check("stop_addr config'ten (105); yoksa 102", a.stop_addr == 105 and ModbusTCPPLCAdapter.__init__ and True)
b = ModbusTCPPLCAdapter({"host": "127.0.0.1", "port": 1, "timeout_s": 0.05, "reconnect_s": 100})
check("registers.stop yoksa 102", b.stop_addr == 102)
check("publish_stop(True) → HR105=1, log 'KONVEYÖR DUR'", a.publish_stop(True) and a._client.writes[-1] == (105, 1) and any("HR105 yazıldı: 1" in e and "KONVEYÖR DUR" in e for e in a.drain_debug_events()))
check("publish_stop(False) → HR105=0", a.publish_stop(False) and a._client.writes[-1] == (105, 0))
check("HR100 yazımı hâlâ serbest, HR103 engelli", a._write_holding_register(100, 1) and not a._write_holding_register(103, 1) and "engellendi" in a.last_error)
check("NullPLCAdapter.publish_stop True döner ve bayrağı saklar", NullPLCAdapter().publish_stop(True) is True)

for x in (w, w2, w3):
    x.worker = None; x.worker2 = None; x._paket_penceresini_kapat(); x.close()
basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
