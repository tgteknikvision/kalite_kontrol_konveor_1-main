"""closeEvent donma düzeltmesi — ekransız test (gerçek config/kameraya DOKUNMAZ)."""
import os, sys, tempfile, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QCloseEvent
import main

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul)))
    print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))

app = QApplication.instance() or QApplication([])
base_cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
tmpdir = tempfile.mkdtemp(); tmp_cfg = os.path.join(tmpdir, "config.yaml")
base_cfg["plc"]["type"] = "null"
base_cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
yaml.safe_dump(base_cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)

class FakeWorker:
    def __init__(self, wait_ok=True):
        self.stopped = False; self.wait_ok = wait_ok; self.wait_calls = []
    def stop(self): self.stopped = True
    def wait(self, ms=None):
        self.wait_calls.append(ms)
        return self.wait_ok

# --- Senaryo 1: normal kapanış (worker zamanında biter) -> os._exit CAGRILMAMALI ---
w = main.MainWindow(); w.show(); app.processEvents()
w.worker = FakeWorker(wait_ok=True); w.worker2 = None
exit_called = []
orig_exit = os._exit
os._exit = lambda code=0: exit_called.append(code)
try:
    ev = QCloseEvent()
    w.closeEvent(ev)
finally:
    os._exit = orig_exit
check("normal kapanışta worker.stop() çağrıldı", w.worker.stopped)
check("normal kapanışta wait(3000) çağrıldı (sınırlı, süresiz DEĞİL)", w.worker.wait_calls == [3000])
check("normal kapanışta event.accept() edildi", ev.isAccepted())
check("normal kapanışta os._exit ÇAĞRILMADI", exit_called == [])

# --- Senaryo 2: DONMUŞ worker (wait() hep False) -> pencere yine KAPANMALI + os._exit ile zorla sonlanmalı ---
w2 = main.MainWindow(); w2.show(); app.processEvents()
w2.worker = FakeWorker(wait_ok=False); w2.worker2 = None
loglar = []
w2._append_log = lambda msg: loglar.append(msg)
exit_called2 = []
os._exit = lambda code=0: exit_called2.append(code)
try:
    ev2 = QCloseEvent()
    w2.closeEvent(ev2)
finally:
    os._exit = orig_exit
check("DONMUŞ worker'da yine stop() çağrıldı", w2.worker.stopped)
check("DONMUŞ worker'da event.accept() edildi (pencere KAPANIR, asılı kalmaz)", ev2.isAccepted())
check("DONMUŞ worker'da os._exit(1) ile ZORLA sonlandırıldı", exit_called2 == [1])
check("DONMUŞ worker'da uyarı loglandı", any("zorla sonlandırılıyor" in l for l in loglar))

# --- Senaryo 3: iki kamera, biri donmuş biri normal -> ikisine de stop() gider, os._exit yine cagrilir ---
w3 = main.MainWindow(); w3.show(); app.processEvents()
w3.worker = FakeWorker(wait_ok=True); w3.worker2 = FakeWorker(wait_ok=False)
exit_called3 = []
os._exit = lambda code=0: exit_called3.append(code)
try:
    ev3 = QCloseEvent()
    w3.closeEvent(ev3)
finally:
    os._exit = orig_exit
check("iki kamerada da stop() çağrıldı", w3.worker.stopped and w3.worker2.stopped)
check("biri donmuşsa yine de os._exit çağrılır", exit_called3 == [1])

# --- Senaryo 4: worker yok (kamera hiç açılmamış) -> hiç çökmemeli ---
w4 = main.MainWindow(); w4.show(); app.processEvents()
w4.worker = None; w4.worker2 = None
exit_called4 = []
os._exit = lambda code=0: exit_called4.append(code)
try:
    ev4 = QCloseEvent()
    w4.closeEvent(ev4)
finally:
    os._exit = orig_exit
check("worker yokken hata vermeden kapanır", ev4.isAccepted() and exit_called4 == [])

for w in (w, w2, w3, w4):
    w.worker = None; w.worker2 = None  # gercek stop/wait cagrilmasin

basarisiz = [a for a, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
