"""Ekransız regresyon testleri — 2026-09-23 sabah değişiklikleri (gerçek config/kameraya DOKUNMAZ).
worker: picamera2 gölgeleme, OpenCV yedeğinden geri dönüş, yarım nesne close().
main: gecikme kutusu, zamanlama damgası, aç/kapa sırası, Enter koruması, imx477 modları."""
import os, sys, time, types, tempfile, copy
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
import numpy as np, yaml
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QKeyEvent

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul)))
    print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))

# ======================= WORKER =======================
import inspector.worker as wk
gercek_sleep = time.sleep
time.sleep = lambda s: None            # worker'daki 1.5 s beklemeler test'te anlik
try:
    print("\n[worker] gölgeleme düzeltmesi + yedekten geri dönüş")
    class FakeCam:
        instances = 0; fail_first = False
        def __init__(self, idx):
            FakeCam.instances += 1
            if FakeCam.fail_first and FakeCam.instances == 1:
                raise RuntimeError("Camera __init__ sequence did not complete.")
            self.set_calls = []
        def create_video_configuration(self, main=None, controls=None):
            return {"use_case": "video", "main": main, "controls": controls}
        def configure(self, c): self.cfg = c
        def set_controls(self, c): self.set_calls.append(c)
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def capture_array(self): return np.full((480, 640, 3), 120, np.uint8)
        def capture_metadata(self): return {"ExposureTime": 400, "AnalogueGain": 16.0}
    fake_pc = types.ModuleType("picamera2"); fake_pc.Picamera2 = FakeCam
    fake_ctrl = types.ModuleType("picamera2.controls")
    class AwbModeEnum: Indoor = 3
    fake_ctrl.AwbModeEnum = AwbModeEnum; fake_pc.controls = fake_ctrl
    sys.modules["picamera2"] = fake_pc; sys.modules["picamera2.controls"] = fake_ctrl

    cfg = {"camera": {"backend": "picamera2", "fps": 20, "awb_mode": "Indoor",
                      "color_gains": [1.5, 1.2], "manual_exposure_enabled": True,
                      "exposure_us": 400, "analogue_gain": 16.0, "zoom": 1.0},
           "resolution": {"width": 640, "height": 480}}
    logs = []
    w = wk.InspectionWorker(cfg, 0); w.log_message.connect(logs.append)
    ok = w._open_camera()
    calls = w._cap.set_calls
    check("picamera2 açıldı", ok and isinstance(w._cap, FakeCam))
    check("awb_mode config'ten UYGULANDI (gölgeleme düzeltildi)", {"AwbMode": 3} in calls, str(calls))
    check("color_gains config'ten UYGULANDI", any(c.get("ColourGains") == (1.5, 1.2) for c in calls))
    check("_on_fallback False", w._on_fallback is False)
    w._release_camera(); check("release sonrası _cap None", w._cap is None)

    class FakeCap:
        reads = 0; released = False
        def __init__(self, idx): pass
        def set(self, *a): pass
        def isOpened(self): return True
        def read(self):
            FakeCap.reads += 1
            if FakeCap.reads > 3000:          # emniyet: sonsuz döngü olmasın
                w2._running = False
            return False, None
        def release(self): FakeCap.released = True
    gercek_vc = wk.cv2.VideoCapture; wk.cv2.VideoCapture = FakeCap
    FakeCam.instances = 0; FakeCam.fail_first = True
    wk.InspectionWorker.PICAM_RETRY_S = 0.0
    cfg2 = copy.deepcopy(cfg); cfg2["camera"].pop("awb_mode"); cfg2["camera"].pop("color_gains")
    logs2 = []
    w2 = wk.InspectionWorker(cfg2, 0); w2.log_message.connect(logs2.append)
    w2.frame_ready.connect(lambda f: w2.stop())      # ilk gerçek kare gelince dur
    w2.run()                                          # senkron
    wk.cv2.VideoCapture = gercek_vc
    check("ilk açılış OpenCV yedeğine düştü", any("OpenCV açıldı" in l for l in logs2))
    check("100 hatalı okumadan sonra Picamera2 yeniden denendi", any("yeniden deneniyor" in l for l in logs2))
    check("yedek VideoCapture release edildi (cihaz sızmadı)", FakeCap.released)
    # run() cikista kamerayi birakir (_cap None) -> kare geldi mi + 2. Picamera2 ornegi mi diye bakilir
    check("ikinci denemede Picamera2 açıldı ve kare geldi", w2.last_raw_frame is not None and FakeCam.instances == 2 and w2._cap is None, f"instances={FakeCam.instances} reads={FakeCap.reads}")
    check("_on_fallback tekrar False", w2._on_fallback is False)

    # --- start() patlarsa yarım Picamera2 nesnesi close() edilmeli (kamera acquired kalmasın) ---
    class FakeCamStartFail(FakeCam):
        closed = 0
        def start(self): raise RuntimeError("Failed to start camera: Invalid argument")
        def close(self): FakeCamStartFail.closed += 1
    FakeCam.fail_first = False
    fake_pc.Picamera2 = FakeCamStartFail
    wk.cv2.VideoCapture = FakeCap
    w3 = wk.InspectionWorker(cfg2, 0); logs3 = []; w3.log_message.connect(logs3.append)
    ok3 = w3._open_camera()
    wk.cv2.VideoCapture = gercek_vc; fake_pc.Picamera2 = FakeCam
    check("start() patlayınca yarım Picamera2 nesnesi close() edildi", FakeCamStartFail.closed == 1, f"closed={FakeCamStartFail.closed}")
    check("yedeğe düşüldü ve _on_fallback True", ok3 and w3._on_fallback)
finally:
    time.sleep = gercek_sleep

# ======================= MAIN =======================
print("\n[main] gecikme kutusu, damga, aç/kapa sırası, Enter koruması, çözünürlük listesi")
import main
app = QApplication.instance() or QApplication([])
base_cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
base_cfg["plc"]["type"] = "null"           # Null PLC
base_cfg["inspection"]["trigger_delay_ms"] = 1
base_cfg["alignment"]["mode"] = "off"           # ürün çerçevesi aranmasın (sentetik kare)
base_cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
base_cfg["dynamic_rois"] = {}; base_cfg["roi"]["roi_types"] = {}; base_cfg["roi"]["point_overrides"] = {}
yaml.safe_dump(base_cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
def fake_start_worker(self):
    self._plc_timer = QTimer(self); self._plc_timer.timeout.connect(self._poll_plc)
main.MainWindow._start_worker = fake_start_worker
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")   # gerçek saha loguna YAZMA
main.QMessageBox.warning = staticmethod(lambda *a, **k: None)
main.QMessageBox.critical = staticmethod(lambda *a, **k: None)

w = main.MainWindow(); w.show(); app.processEvents()
loglar = []
orig_log = w._append_log
def log_yakala(msg): loglar.append(msg); orig_log(msg)
w._append_log = log_yakala

check("sol panelde gecikme kutusu var, config'i gösteriyor", w.spin_trigger_delay.value() == 1)
w.spin_trigger_delay.setValue(150); app.processEvents()
saved = yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
check("kutu → config + dosya (150 ms)", w.config["inspection"]["trigger_delay_ms"] == 150 and saved["inspection"]["trigger_delay_ms"] == 150)
check("kutu → log [Gecikme]", any(l.startswith("[Gecikme]") for l in loglar))

dlg = main.SettingsDialog(w.config, w)
items = [dlg._cam1_w["res"].itemText(i) for i in range(dlg._cam1_w["res"].count())]
check("Ayarlar çözünürlük listesinde imx477 modları", all(m in items for m in ("4056x3040", "2028x1520", "2028x1080", "1332x990")) and "1456x1088" in items)
v = dlg.values()

calls = []
w._start_camera = lambda n: calls.append(f"start{n}")
w._stop_camera = lambda n: calls.append(f"stop{n}")
w.config["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
v1 = dict(v); v1["camera1_enabled"] = False; v1["camera2_enabled"] = True; v1["trigger_delay_ms"] = 220
n_log = len([l for l in loglar if l.startswith("[Gecikme]")])
w._apply_settings(v1)
check("K1 kapat + K2 aç → ÖNCE stop1 SONRA start2", calls == ["stop1", "start2"], str(calls))
check("Ayarlar'daki gecikme sol kutuya yansıdı (sinyalsiz)", w.spin_trigger_delay.value() == 220 and len([l for l in loglar if l.startswith("[Gecikme]")]) == n_log)
calls.clear()
v2 = dict(v); v2["camera1_enabled"] = True; v2["camera2_enabled"] = False
w._apply_settings(v2)
check("K2 kapat + K1 aç → ÖNCE stop2 SONRA start1 (arıza senaryosu)", calls == ["stop2", "start1"], str(calls))

got = []
w._capture_full_frame = lambda source="plc": got.append(source)
w.config["inspection"]["trigger_delay_ms"] = 60
w._capture_from_plc()
check("tetikten sonra çekim beklemede (_capture_pending) ve tetik zamanı kaydedildi", w._capture_pending and w._trigger_time is not None)
t0 = time.time()
while time.time() - t0 < 0.5 and not got:
    app.processEvents(); gercek_sleep(0.01)
check("gecikme dolunca çekim source='plc' ile çağrıldı", got == ["plc"], str(got))
del w._capture_full_frame

class FakeWorker:
    def __init__(self):
        self.last_raw_frame = np.full((300, 400, 3), 200, np.uint8)
        self.last_frame_time = time.time() - 0.023
    def stop(self): pass
    def wait(self, *a): pass
w.worker = FakeWorker()
shown = []
w._display_snapshot = lambda img, n=1: shown.append(img)
w.config["inspection"]["trigger_delay_ms"] = 150
w._trigger_time = time.time() - 0.161
w._capture_full_frame(source="plc")
note = w._last_capture_note
check("PLC çekimi notu 'Gecikme 150 ms | kare ~23 ms'", note.startswith("Gecikme 150 ms | kare 2"), note)
check("log'da (kurulum karesi) 'tetikten ~161 ms sonra' ölçümü", any("[Kurulum]" in l and "tetikten 16" in l and "kare yaşı 2" in l for l in loglar))
check("saklanan kare TEMİZ (damgasız)", w._last_snapshot is not None and int(w._last_snapshot[290, 10].min()) == 200)
check("ekrana giden karede damga var (sol alt)", shown and int(shown[-1][290, 10].min()) < 200)
img = np.zeros((120, 160, 3), np.uint8); w._last_capture_note = "Gecikme 10 ms | kare 5 ms"
out = w._stamp_capture_note(img)
check("_stamp_capture_note küçük resme de yazıyor", out is img and img[:, :, :].max() > 0)

# ELLE CEKIM KALDIRILDI (2026-09-24, kullanici istegi): Bosluk/Enter ya da canli goruntuye
# tik ASLA cekim yapmamali; kutu ve metotlar programda olmamali.
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtCore import QPointF
cap_calls = []
w._capture_full_frame = lambda *a, **k: cap_calls.append(1)
w.centralWidget().setFocus(); app.processEvents()
for key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
    QApplication.sendEvent(w, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)); app.processEvents()
check("Boşluk/Enter çekim TETİKLEMEZ (elle çekim kaldırıldı)", cap_calls == [])
QApplication.sendEvent(w.video_label, QMouseEvent(QEvent.MouseButtonPress, QPointF(10, 10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)); app.processEvents()
check("canlı görüntüye tık çekim TETİKLEMEZ", cap_calls == [])
check("elle çekim kutusu/metotları programda yok", not hasattr(w, "chk_manual_mode") and "keyPressEvent" not in main.MainWindow.__dict__ and not any(hasattr(main.MainWindow, m) for m in ("_manual_capture", "_on_video_clicked", "_manual_mode_on", "_on_manual_mode_changed")))
check("plc.manual_mode artık adapter seçimini etkilemez (type belirler)", type(main.create_plc_adapter({"plc": {"type": "modbus_tcp", "manual_mode": True, "host": "127.0.0.1", "port": 1, "timeout_s": 0.05, "reconnect_s": 0.05}})).__name__ == "ModbusTCPPLCAdapter")

w.worker = None
w.close()
basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
