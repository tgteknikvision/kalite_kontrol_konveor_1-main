"""Masaüstü simgesi / başlatıcı (tools/baslat.sh) + program revizyonu — ekransız test (gerçek config/log/kameraya DOKUNMAZ).

2026-09-28, kullanıcı: "masaüstüne bir simge koy; her revizyon yapıldığında simgeden açılan program
revizyonlu olsun". Simge tools/baslat.sh'ı çalıştırır: proje klasöründeki GÜNCEL main.py'yi açar, zaten
açık program varsa ikinci kopya açmaz (PLC'ye çift yazım yasak), kütüphane eksikse pencereyle söyler,
stdout'u loga yazar. main.py başlıkta ve logda çalışan git revizyonunu gösterir.
"""
import os, sys, subprocess, tempfile, time, yaml
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ); os.chdir(PROJ)

sonuc = []
def check(ad, kosul, ek=""):
    sonuc.append((ad, bool(kosul))); print(("  [OK ] " if kosul else "  [FAIL] ") + ad + (f"  ({ek})" if ek else ""))

tmpdir = tempfile.mkdtemp()
BASLAT = os.path.join(PROJ, "tools", "baslat.sh")
def calistir(env_ek=None, timeout=30):
    env = dict(os.environ); env.update({"KONVEYOR_BASLAT_DENEME": "1", "KONVEYOR_BASLAT_LOG": os.path.join(tmpdir, "stdout.log")})
    env.update(env_ek or {})
    r = subprocess.run(["bash", BASLAT], capture_output=True, text=True, env=env, timeout=timeout)
    return r.returncode, r.stdout + r.stderr

print("\n[program_revision]")
import main
git_hash = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJ).stdout.strip()
rev = main.program_revision()
check("revizyon = git kısa hash + tarih", rev.startswith(git_hash) and len(rev.split()) >= 2, rev)
kirli = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=PROJ).stdout.strip())
rev_s = main.program_revision(with_status=True)
check("with_status: ağaç kirliyse '+yerel değişiklik' eklenir, temizse eklenmez", rev_s.startswith(git_hash) and (("+yerel değişiklik" in rev_s) == kirli), rev_s)
sahte = os.path.join(tmpdir, "sahte_repo"); os.makedirs(os.path.join(sahte, ".git", "refs", "heads"))
open(os.path.join(sahte, ".git", "HEAD"), "w").write("ref: refs/heads/main\n")
open(os.path.join(sahte, ".git", "refs", "heads", "main"), "w").write("0123456789abcdef0123456789abcdef01234567\n")
check("git komutu çalışmayan klasörde .git/HEAD'den kısa hash", main.program_revision(sahte) == "0123456", main.program_revision(sahte))
os.remove(os.path.join(sahte, ".git", "refs", "heads", "main"))
open(os.path.join(sahte, ".git", "packed-refs"), "w").write("# pack-refs\nfedcba9876543210fedcba9876543210fedcba98 refs/heads/main\n")
check("packed-refs'ten de okur", main.program_revision(sahte) == "fedcba9")
check("git yoksa '?'", main.program_revision(tmpdir) == "?")

print("\n[pencere başlığı + log]")
from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
tmp_cfg = os.path.join(tmpdir, "config.yaml")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["plc"]["type"] = "null"; cfg["cameras"] = {"camera1_enabled": True, "camera2_enabled": False}
yaml.safe_dump(cfg, open(tmp_cfg, "w", encoding="utf-8"))
main.CONFIG_PATH = tmp_cfg
main.load_config = lambda path=None: yaml.safe_load(open(tmp_cfg, encoding="utf-8"))
main.MainWindow.LOG_DIR = os.path.join(tmpdir, "loglar")
main.MainWindow.OPERATOR_DIR = os.path.join(tmpdir, "operator_kontrol")   # gerçek proje klasörüne YAZMA
main.MainWindow._start_worker = lambda self: setattr(self, "_plc_timer", None)
w = main.MainWindow(); w.show(); app.processEvents()
check("başlıkta 'sürüm <hash>'", f"sürüm {git_hash}" in w.windowTitle(), w.windowTitle())
check("logda [Sürüm] satırı + klasör yolu", "[Sürüm] Program revizyonu: " + git_hash in w.txt_logs.toPlainText() and PROJ in w.txt_logs.toPlainText())
w.worker = None; w.worker2 = None; w.close()

print("\n[baslat.sh: deneme modu]")
rc, out = calistir()
check("deneme: exit 0, python + main.py + revizyon yazar", rc == 0 and "[DENEME]" in out and "main.py" in out and "revizyon" in out and git_hash in out, out.strip()[-160:])
check("stdout log dosyasına [baslat.sh] satırı düştü", os.path.exists(os.path.join(tmpdir, "stdout.log")) and "[baslat.sh] Başlatılıyor" in open(os.path.join(tmpdir, "stdout.log"), encoding="utf-8").read())

print("\n[baslat.sh: zaten açık → ikinci kopya yok]")
kukla_dir = os.path.join(tmpdir, "kukla"); os.makedirs(kukla_dir)
open(os.path.join(kukla_dir, "main.py"), "w").write("import time; time.sleep(60)\n")      # 'python3 .../main.py' görünümlü kukla
kukla = subprocess.Popen([sys.executable, os.path.join(kukla_dir, "main.py")])
time.sleep(0.5)
try:
    rc, out = calistir()
    check("açık örnek varken: 'ZATEN AÇIK' bilgi penceresi, exit 0, program açılmaz", rc == 0 and "ZATEN AÇIK" in out and "[DENEME:info]" in out and "[DENEME] " not in out, out.strip()[:160])
finally:
    kukla.kill(); kukla.wait()
kukla2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "main.py"])   # satır içi kod: SAYILMAMALI
time.sleep(0.5)
try:
    rc, out = calistir()
    check("'python -c … main.py' (satır içi kod) ve kabuk komutları 'zaten açık' SAYILMAZ", rc == 0 and "[DENEME] " in out and "ZATEN AÇIK" not in out, out.strip()[:120])
finally:
    kukla2.kill(); kukla2.wait()
rc, out = calistir()
check("kukla kapanınca yine açılır", rc == 0 and "[DENEME] " in out)

print("\n[baslat.sh: kütüphane eksik]")
sahte_py = os.path.join(tmpdir, "sahte_python"); open(sahte_py, "w").write("#!/bin/sh\necho \"ModuleNotFoundError: No module named 'picamera2'\" >&2\nexit 1\n"); os.chmod(sahte_py, 0o755)
rc, out = calistir({"KONVEYOR_BASLAT_PY": sahte_py})
check("eksik kütüphane: hata penceresi (modül adı + kurulum komutu), exit 1", rc == 1 and "[DENEME:error]" in out and "picamera2" in out and "kurulum_pi.sh" in out, out.strip()[:200])

print("\n[install_pi.sh masaüstü girdisi]")
kur = open(os.path.join(PROJ, "tools", "install_pi.sh"), encoding="utf-8").read()
check("install_pi.sh: Exec simgeyi baslat.sh'a bağlar, masaüstüne kopyalar, trusted işaretler",
      "Exec=bash $DIR/tools/baslat.sh" in kur and 'konveyor-denetim.desktop' in kur and "metadata::trusted" in kur)
check("baslat.sh çalıştırılabilir ve LF", os.access(BASLAT, os.X_OK) and b"\r\n" not in open(BASLAT, "rb").read())

basarisiz = [ad for ad, k in sonuc if not k]
print(f"\nTOPLAM {len(sonuc)} test, {len(sonuc) - len(basarisiz)} geçti, {len(basarisiz)} başarısız", basarisiz or "")
sys.exit(1 if basarisiz else 0)
