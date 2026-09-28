#!/usr/bin/env bash
# =============================================================================
# MASAÜSTÜ SİMGESİNİN ÇALIŞTIRDIĞI BAŞLATICI (2026-09-28, kullanıcı isteği: "masaüstüne simge koy,
# her revizyon yapıldığında simgeden açılan program revizyonlu program olsun")
#
# Her zaman BU proje klasöründeki GÜNCEL main.py'yi açar (kopya/paket yok) -> kod ne zaman değişirse
# değişsin simge son hâli çalıştırır. Açılan revizyon pencere başlığında ve logda görünür.
# Ek güvenlikler:
#   1) Program ZATEN AÇIKSA ikinci kopya AÇMAZ (iki örnek aynı anda PLC HR100'e yazar — yasak) ve
#      bunu pencereyle söyler.
#   2) Kütüphane eksikse ya da program açılışta çökerse SESSİZCE kaybolmaz: hata penceresi + son log.
#   3) stdout/stderr ~/konveyor_loglari/uygulama-stdout.log'a eklenir (libcamera hataları kaybolmasın).
# Test kancaları (normal kullanımda boş bırak):
#   KONVEYOR_BASLAT_DENEME=1   -> programı AÇMAZ, ne yapacağını yazar (exit 0)
#   KONVEYOR_BASLAT_PY=<yol>   -> python yerine bu komut (kütüphane hatası senaryosu)
#   KONVEYOR_BASLAT_LOG=<yol>  -> stdout log dosyası
# Kurulum: bash tools/install_pi.sh  (menü + masaüstü simgesi bu betiğe bağlanır)
# =============================================================================
set -u
PROJE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJE"
DENEME="${KONVEYOR_BASLAT_DENEME:-0}"
LOG="${KONVEYOR_BASLAT_LOG:-$HOME/konveyor_loglari/uygulama-stdout.log}"

mesaj() {   # $1 = info|error, $2 = metin. GUI varsa pencere, yoksa terminal.
  if [ "$DENEME" = "1" ]; then printf '[DENEME:%s] %b\n' "$1" "$2"; return 0; fi
  if command -v zenity >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    zenity "--$1" --title="Konveyör Denetim Sistemi" --width=480 --text="$2" 2>/dev/null
  else
    printf '%b\n' "$2" >&2
  fi
}

# --- 1) Zaten açık mı? (ikinci kopya YASAK: ikisi de PLC'ye yazar) ------------------
# Eşleşme SIKI: komutun ilk kelimesi python* olmalı ve argümanlardan birinin dosya adı main.py olmalı;
# "python -c ..." (satır içi kod) ve içinde 'main.py' geçen kabuk komutları (bash -c "... main.py")
# SAYILMAZ — aksi halde ajan/terminal komutları "zaten açık" sanılıyordu (testte görüldü).
zaten_acik_pid() {
  local p a ilk t
  for p in $(pgrep -f 'main\.py' 2>/dev/null || true); do
    [ "$p" = "$$" ] && continue
    a="$(ps -o args= -p "$p" 2>/dev/null || true)"
    [ -n "$a" ] || continue
    # shellcheck disable=SC2086
    set -- $a
    [ $# -ge 2 ] || continue
    ilk="$(basename "$1")"; shift
    case "$ilk" in python*) ;; *) continue ;; esac
    case " $* " in *" -c "*) continue ;; esac
    for t in "$@"; do
      if [ "$(basename "$t")" = "main.py" ]; then echo "$p"; return 0; fi
    done
  done
  return 1
}
if ACIK="$(zaten_acik_pid)"; then
  mesaj info "Program ZATEN AÇIK (pid $ACIK).\nİkinci kopya açılmadı — iki kopya aynı anda PLC'ye yazamaz.\nAçık pencereyi kullanın; kapanmıyorsa 3 sn bekleyin ya da Kamera Önizleme simgesinden kapatın."
  exit 0
fi

# --- 2) Python ve kütüphaneler (calistir.sh ile aynı seçim) ---------------------------
if [ -x "$PROJE/veri_toplama/bin/python" ]; then PY="$PROJE/veri_toplama/bin/python"; else PY="$(command -v python3 || true)"; fi
PY="${KONVEYOR_BASLAT_PY:-$PY}"
if [ -z "$PY" ]; then
  mesaj error "python3 bulunamadı; program açılamadı.\nKurulum: bash tools/kurulum_pi.sh"; exit 1
fi
if ! HATA="$("$PY" -c "import picamera2, PyQt5, cv2, yaml, pymodbus" 2>&1 >/dev/null)"; then
  mesaj error "Gerekli kütüphane eksik, program açılamadı:\n$HATA\n\nKurulum: bash tools/kurulum_pi.sh\n(ya da: sudo apt install python3-picamera2 python3-pyqt5 python3-opencv python3-yaml python3-pymodbus)"
  exit 1
fi

# --- 3) Hangi revizyon açılıyor? ------------------------------------------------------
REV="$(git -C "$PROJE" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M' 2>/dev/null || true)"
[ -z "$REV" ] && REV="?"
[ -n "$(git -C "$PROJE" status --porcelain 2>/dev/null)" ] && REV="$REV +yerel değişiklik"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
echo "$(date '+%Y-%m-%d %H:%M:%S') [baslat.sh] Başlatılıyor: $PY main.py (revizyon $REV)" >> "$LOG" 2>/dev/null || true
if [ "$DENEME" = "1" ]; then echo "[DENEME] $PY $PROJE/main.py (revizyon $REV)"; exit 0; fi

# --- 4) Başlat; ilk 30 sn içinde hatayla kapanırsa söyle ------------------------------
BASLA=$(date +%s)
"$PY" main.py >> "$LOG" 2>&1
RC=$?
SURE=$(( $(date +%s) - BASLA ))
if [ "$RC" -ne 0 ] && [ "$SURE" -lt 30 ]; then
  SON="$(tail -n 12 "$LOG" 2>/dev/null | cut -c1-160)"
  mesaj error "Program açılışta hata verdi (çıkış kodu $RC, $SURE sn içinde kapandı).\n\nSon log satırları:\n$SON\n\nTam log: $LOG"
fi
exit $RC
