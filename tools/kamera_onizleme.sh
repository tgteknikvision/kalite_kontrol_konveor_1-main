#!/usr/bin/env bash
# =============================================================================
# KAMERA ÖNİZLEME — denetim programından BAĞIMSIZ canlı kamera görüntüsü
#
# Masaüstündeki "Kamera Önizleme" simgesi (çift tık) bu betiği çalıştırır:
#   - Takılı tüm kameraları bulur (rpicam-hello --list-cameras)
#   - Her kamera için ayrı bir canlı önizleme penceresi açar (yan yana)
#   - config.yaml'daki poz/gain kilidi AÇIKSA aynı poz/gain ile gösterir
#     (odak/ışık ayarı programdaki görüntüyle aynı olsun diye)
#   - Denetim uygulaması açıksa (kamerayı o tutar) sorar ve isteğe bağlı kapatır
#
# Kullanım:  bash tools/kamera_onizleme.sh            # kapatana kadar
#            bash tools/kamera_onizleme.sh 5000       # 5 sn (test)
# Kapatmak:  bu terminal penceresinde Ctrl+C ya da pencereyi kapat.
#
# NEDEN (2026-09-23, kullanıcı isteği): kamera/kablo/odak sorunlarını denetim
# programını açmadan görmek için. libcamera'nın "Camera frontend has timed out /
# check your camera sensor connector" gibi hataları da bu pencerede canlı görünür.
# =============================================================================
set -u
PROJE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJE"
SURE_MS="${1:-0}"                       # 0 = kapatana kadar
# Test kancalari (normal kullanimda bos birak):
#   ONIZLEME_APP_KONTROL=0  -> denetim uygulamasi acik mi diye BAKMA (sorma/kapatma)
#   ONIZLEME_SADECE="1"     -> yalniz bu kamera indeks(ler)ini ac (bosluklu liste)
APP_KONTROL="${ONIZLEME_APP_KONTROL:-1}"
SADECE="${ONIZLEME_SADECE:-}"

msg()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m%s\033[0m\n' "$*"; }
soru() {   # GUI varsa zenity, yoksa terminalden e/H
  if command -v zenity >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    zenity --question --title="Kamera Önizleme" --width=420 --text="$1" 2>/dev/null
  else
    printf '%s [e/H] ' "$1"; read -r c; case "$c" in [eEyY]*) return 0;; *) return 1;; esac
  fi
}

msg "==== KAMERA ÖNİZLEME (denetim programından bağımsız) ===="

# --- 1) Denetim uygulaması açıksa kamerayı o tutar: sor, kapat -----------------
app_pids() {
  for p in $(pgrep -f 'main\.py' 2>/dev/null || true); do
    [ "$p" = "$$" ] && continue
    a="$(ps -o args= -p "$p" 2>/dev/null || true)"
    case "$a" in */python*main.py|python*main.py) echo "$p";; esac
  done
}
PIDS=""
[ "$APP_KONTROL" = "1" ] && PIDS="$(app_pids | tr '\n' ' ')"
if [ -n "${PIDS// /}" ]; then
  warn "Denetim uygulaması açık (pid: $PIDS) ve kamerayı tutuyor."
  if soru "Denetim uygulaması açık ve kamerayı tutuyor.\nÖnizleme için uygulama KAPATILSIN mı?\n(PLC denetimi durur; bitince simgeden yeniden açabilirsin.)"; then
    for p in $PIDS; do kill -TERM "$p" 2>/dev/null; done
    for p in $PIDS; do timeout 5 tail --pid="$p" -f /dev/null; kill -9 "$p" 2>/dev/null || true; done
    msg "Uygulama kapatıldı."
  else
    warn "Uygulama açık kalıyor: onun kullandığı kamera açılamaz, yalnız BOŞ kameralar gösterilecek."
  fi
fi

# --- 2) Kameraları bul ----------------------------------------------------------
LISTE="$(timeout 20 rpicam-hello --list-cameras 2>/dev/null || true)"
INDEKSLER="$(printf '%s\n' "$LISTE" | grep -E '^[0-9]+ :' | awk '{print $1}')"
if [ -n "$SADECE" ]; then INDEKSLER="$(printf '%s\n' $SADECE)"; fi
if [ -z "$INDEKSLER" ]; then
  err "Hiç kamera bulunamadı! (rpicam-hello --list-cameras boş) Kablo/soketleri kontrol et."
  command -v zenity >/dev/null 2>&1 && zenity --error --title="Kamera Önizleme" \
    --text="Hiç kamera bulunamadı.\nKablo ve CSI soketlerini kontrol et." 2>/dev/null
  exit 2
fi
printf '%s\n' "$LISTE" | grep -E '^[0-9]+ :' | sed 's/^/  bulundu: /'

# --- 3) config.yaml'daki poz/gain/çözünürlük (kilit açıksa aynı ayarlar) --------
# Satır i = kamera i için rpicam-hello argümanları (kamera 2 kamera 1'den devralır,
# worker._cam_cfg ile aynı mantık).
ARGS_LIST="$(python3 - <<'PY' 2>/dev/null
import yaml
c = yaml.safe_load(open("config.yaml")) or {}
base = c.get("camera", {}) or {}; res = c.get("resolution", {}) or {}
for i in (0, 1):
    cam = base if i == 0 else {**base, **(c.get("camera2", {}) or {})}
    r = res if i == 0 else {**res, **(c.get("resolution2", {}) or {})}
    a = [f"--width {int(r.get('width', 1456))}", f"--height {int(r.get('height', 1088))}"]
    if cam.get("manual_exposure_enabled"):
        a += [f"--shutter {int(cam.get('exposure_us', 1000))}",
              f"--gain {float(cam.get('analogue_gain', 1.0)):g}"]
    print(" ".join(a))
PY
)"
mapfile -t ARGS_ARR <<<"$ARGS_LIST"

# --- 4) Pencere yerleşimi: yan yana ------------------------------------------
EKRAN_W=1920; EKRAN_H=1080
if command -v xrandr >/dev/null 2>&1; then
  R="$(timeout 5 xrandr --current 2>/dev/null | grep -m1 '\*' | awk '{print $1}')"
  case "$R" in *x*) EKRAN_W="${R%x*}"; EKRAN_H="${R#*x}";; esac
fi
N=$(printf '%s\n' "$INDEKSLER" | wc -l)
PW=$(( (EKRAN_W - 40 * (N + 1)) / N ))
[ "$PW" -gt 1100 ] && PW=1100
PH=$(( PW * 3 / 4 ))
[ "$PH" -gt $((EKRAN_H - 120)) ] && PH=$((EKRAN_H - 120))

# --- 5) Başlat ------------------------------------------------------------------
PIDS_PREV=""
trap 'echo; msg "Önizleme kapatılıyor..."; for p in $PIDS_PREV; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; exit 0' INT TERM HUP
k=0
for i in $INDEKSLER; do
  X=$(( 40 + k * (PW + 40) ))
  # shellcheck disable=SC2086
  rpicam-hello --camera "$i" -t "$SURE_MS" --preview "$X,60,$PW,$PH" \
    --info-text "Kamera $((i+1)) (cam$i) | poz %exp us | gain %ag | %fps fps" \
    ${ARGS_ARR[$i]:-} &
  PIDS_PREV="$PIDS_PREV $!"
  msg "Kamera $((i+1)) (cam$i) açılıyor: ${ARGS_ARR[$i]:-} -> pencere $X,60 ${PW}x${PH}"
  k=$((k + 1))
done
echo
warn "Kapatmak için: bu pencerede Ctrl+C ya da pencereyi kapat."
warn "Görüntü bir süre sonra DONARSA ve aşağıda 'Camera frontend has timed out' yazarsa"
warn "sorun yazılım değil, o kameranın KABLOSU/KONNEKTÖRÜDÜR (libcamera'nın kendi uyarısı)."
warn "Not: başka bir kamera meşgulse 'Unable to set controls: Device or resource busy' satırı"
warn "görülebilir; libcamera açılışta tüm kameraları sayar, önemsizdir."
echo
wait
echo
msg "Önizleme bitti."
