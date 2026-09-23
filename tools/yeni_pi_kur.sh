#!/usr/bin/env bash
# =============================================================================
# YENİ Pi KURULUM / İKİZLİK DENETİMİ
#
# Yeni bir Raspberry Pi 5'i sahadaki Pi'nin İKİZİ haline getirir. Değerleri
# proje kökündeki `saha_ayarlari.conf` dosyasından okur.
#
#   bash tools/yeni_pi_kur.sh --kontrol   # HİÇBİR ŞEY DEĞİŞTİRMEZ, fark raporu
#   bash tools/yeni_pi_kur.sh             # eksikleri kurar (her adımda onay sorar)
#
# NOT: uygulama ayarları (kontrol noktaları, eşikler, poz/gain, yön referansı)
# `config.yaml` içinde ve git ile zaten geliyor. Bu betik YALNIZCA git'in
# taşıyamadığı makine seviyesi ayarlarla ilgilenir.
#
# Betik kişisel yol GÖMMEZ: $HOME/$USER üzerinden çalışır, bu yüzden farklı
# kullanıcı adına sahip bir Pi'de de doğru çalışır (CLAUDE.md kapsam kuralı).
# =============================================================================
set -u

PROJE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJE"
AYAR="$PROJE/saha_ayarlari.conf"

KONTROL=0
[ "${1:-}" = "--kontrol" ] && KONTROL=1

if [ ! -f "$AYAR" ]; then
  echo "HATA: $AYAR bulunamadi." >&2; exit 1
fi
# shellcheck disable=SC1090
. "$AYAR"

TAMAM=0; EKSIK=0
ok()   { echo "  [✓] $*"; TAMAM=$((TAMAM+1)); }
yok()  { echo "  [✗] $*"; EKSIK=$((EKSIK+1)); }
bilgi(){ echo "      $*"; }

# Degistirici adimlar icin onay. --kontrol modunda HIC calismaz.
onayla() {
  [ "$KONTROL" = "1" ] && return 1
  printf "      -> %s [e/H] " "$1"
  read -r c </dev/tty || return 1
  case "$c" in [eEyY]*) return 0;; *) return 1;; esac
}

echo "============================================================"
echo " YENİ Pi KURULUM / İKİZLİK DENETİMİ"
[ "$KONTROL" = "1" ] && echo " MOD: --kontrol (hiçbir şey değiştirilmez)" \
                     || echo " MOD: kurulum (değişiklikler onayla yapılır)"
echo " Makine: $(hostname)   Kullanıcı: ${USER:-$(id -un)}"
echo "============================================================"

# --- 1) Python bagimliliklari ----------------------------------------------
echo
echo "[1] Python kütüphaneleri"
EKSIK_MODUL=""
for m in picamera2 PyQt5 cv2 numpy yaml pymodbus; do
  python3 -c "import $m" 2>/dev/null || EKSIK_MODUL="$EKSIK_MODUL $m"
done
if [ -z "$EKSIK_MODUL" ]; then
  ok "hepsi kurulu (picamera2, PyQt5, cv2, numpy, yaml, pymodbus)"
else
  yok "eksik:$EKSIK_MODUL"
  if onayla "tools/kurulum_pi.sh çalıştırılsın mı?"; then
    bash tools/kurulum_pi.sh && ok "kurulum tamamlandı" || yok "kurulum başarısız"
  else
    bilgi "elle:  bash tools/kurulum_pi.sh"
  fi
fi

# --- 2) Kameralar -----------------------------------------------------------
echo
echo "[2] Kameralar"
LISTE="$(timeout 30 rpicam-hello --list-cameras 2>/dev/null \
         || timeout 30 libcamera-hello --list-cameras 2>/dev/null || true)"
SAYI="$(printf '%s\n' "$LISTE" | grep -c "$BEKLENEN_KAMERA_SENSORU" || true)"
if [ "${SAYI:-0}" -ge "$BEKLENEN_KAMERA_SAYISI" ]; then
  ok "$SAYI adet $BEKLENEN_KAMERA_SENSORU bulundu (beklenen $BEKLENEN_KAMERA_SAYISI)"
  printf '%s\n' "$LISTE" | grep "$BEKLENEN_KAMERA_SENSORU" | sed 's/^/      /'
  bilgi "⚠ Kablolar AYNI soketlere takılmalı: ters takılırsa Kamera 1 ↔ Kamera 2"
  bilgi "  yer değiştirir ve tüm ROI/eşik/yön referansı yanlış yüze uygulanır."
else
  yok "${SAYI:-0} kamera bulundu, $BEKLENEN_KAMERA_SAYISI bekleniyordu"
  bilgi "kabloları ve CSI soketlerini kontrol et"
fi

# --- 3) Statik IP -----------------------------------------------------------
echo
echo "[3] PLC ağı — $PLC_ARAYUZU statik IP"
MEVCUT="$(ip -4 -o addr show "$PLC_ARAYUZU" 2>/dev/null | awk '{print $4}' | head -1)"
if [ "$MEVCUT" = "$PI_STATIK_IP" ]; then
  ok "$PLC_ARAYUZU = $MEVCUT (hedefle aynı)"
else
  yok "$PLC_ARAYUZU = ${MEVCUT:-yok}  (hedef: $PI_STATIK_IP)"
  PROFIL="$(nmcli -t -f NAME,DEVICE con show 2>/dev/null \
            | awk -F: -v d="$PLC_ARAYUZU" '$2==d{print $1; exit}')"
  if [ -z "$PROFIL" ]; then
    bilgi "$PLC_ARAYUZU için NetworkManager profili bulunamadı"
  else
    bilgi "profil: \"$PROFIL\""
    bilgi "⚠ SSH ile bağlıysan bu değişiklik bağlantını KESEBİLİR."
    if onayla "\"$PROFIL\" profiline $PI_STATIK_IP verilsin mi?"; then
      sudo nmcli con mod "$PROFIL" ipv4.method manual \
           ipv4.addresses "$PI_STATIK_IP" ipv4.gateway "$PLC_ARAYUZU_GATEWAY" \
        && sudo nmcli con up "$PROFIL" >/dev/null \
        && ok "uygulandı" || yok "uygulanamadı"
    else
      bilgi "elle: sudo nmcli con mod \"$PROFIL\" ipv4.method manual ipv4.addresses $PI_STATIK_IP"
      bilgi "      sudo nmcli con up \"$PROFIL\""
    fi
  fi
fi
bilgi "not: $PLC_ARAYUZU'a GATEWAY verilmez (internet wlan0'dan gelir)"

# --- 4) PLC erisimi ---------------------------------------------------------
echo
echo "[4] PLC erişimi"
CFG_IP="$(python3 -c "import yaml;print(yaml.safe_load(open('config.yaml'))['plc']['host'])" 2>/dev/null || echo "?")"
CFG_PORT="$(python3 -c "import yaml;print(yaml.safe_load(open('config.yaml'))['plc']['port'])" 2>/dev/null || echo "?")"
if [ "$CFG_IP" = "$PLC_IP" ] && [ "$CFG_PORT" = "$PLC_PORT" ]; then
  ok "config.yaml ile saha_ayarlari.conf uyumlu ($CFG_IP:$CFG_PORT)"
else
  yok "UYUŞMAZLIK — config.yaml: $CFG_IP:$CFG_PORT / conf: $PLC_IP:$PLC_PORT"
fi
if timeout 5 python3 -c "
import socket,sys
s=socket.socket(); s.settimeout(2)
try: s.connect(('$PLC_IP',$PLC_PORT))
except Exception: sys.exit(1)
finally: s.close()" 2>/dev/null; then
  ok "PLC $PLC_IP:$PLC_PORT erişilebilir"
else
  yok "PLC $PLC_IP:$PLC_PORT erişilemiyor"
  bilgi "kablo / IP / PLC açık mı diye bak"
fi

# --- 5) Uygulama ayarlari (git ile gelir) -----------------------------------
echo
echo "[5] Uygulama ayarları (config.yaml — git ile taşınır)"
python3 - <<'PY' 2>/dev/null || echo "  [✗] config.yaml okunamadı"
import yaml
c = yaml.safe_load(open("config.yaml"))
r2 = c.get("roi2", {}) or {}
n1 = len(c.get("dynamic_rois", {}) or {}); n2 = len(c.get("dynamic_rois_2", {}) or {})
print(f"  [✓] kameralar: {c.get('cameras')}")
print(f"  [✓] kontrol noktası: kamera1={n1}  kamera2={n2}")
print(f"  [✓] kamera2 poz/gain: {c.get('camera2',{}).get('exposure_us')} us / "
      f"{c.get('camera2',{}).get('analogue_gain')}  kilit={c.get('camera2',{}).get('manual_exposure_enabled')}")
print(f"  [✓] yön referansı: v{r2.get('handedness_version')} diff={r2.get('handedness_hole_diff')}")
print("      (bunlar git ile geldi; kameralar/optik/ışık aynıysa yeniden kalibrasyon GEREKMEZ)")
PY

# --- 6) Uzaktan kontrol ajani (opsiyonel) -----------------------------------
echo
echo "[6] Uzaktan kontrol ajanı (opsiyonel — ürün için şart değil)"
SERVIS="$HOME/.config/systemd/user/claude-agent-konveor.service"
if systemctl --user is-active claude-agent-konveor.service >/dev/null 2>&1; then
  ok "servis çalışıyor ($AJAN_ADI)"
elif [ -f "$SERVIS" ]; then
  yok "servis kurulu ama çalışmıyor"
  bilgi "systemctl --user start claude-agent-konveor"
else
  yok "kurulu değil"
  if [ ! -x "$HOME/.local/bin/claude" ] && ! command -v claude >/dev/null 2>&1; then
    bilgi "önce Claude Code kurulmalı; ajan olmadan da üretim çalışır"
  elif onayla "ajan servisi kurulsun mu?"; then
    mkdir -p "$(dirname "$SERVIS")"
    CLAUDE_YOL="$HOME/.local/bin/claude"; [ -x "$CLAUDE_YOL" ] || CLAUDE_YOL="$(command -v claude)"
    cat > "$SERVIS" <<UNIT
[Unit]
Description=Claude uzaktan kontrol ajani ($AJAN_ADI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJE
ExecStart=$CLAUDE_YOL remote-control --name $AJAN_ADI --spawn same-dir
Restart=always
RestartSec=10
StartLimitIntervalSec=0

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --now claude-agent-konveor.service >/dev/null 2>&1 \
      && ok "kuruldu ve başlatıldı" || yok "başlatılamadı"
    loginctl enable-linger "${USER:-$(id -un)}" >/dev/null 2>&1 \
      && bilgi "linger açıldı (açılışta kendiliğinden kalkar)"
  fi
fi

# --- Ozet -------------------------------------------------------------------
echo
echo "============================================================"
echo " ÖZET:  $TAMAM tamam / $EKSIK eksik"
if [ "$EKSIK" -eq 0 ]; then
  echo " ✅ Bu Pi sahadakinin İKİZİ — üretime alınabilir."
else
  echo " ⚠  Yukarıdaki [✗] maddeleri giderilmeli."
  [ "$KONTROL" = "1" ] && echo "    (kurmak için --kontrol olmadan çalıştır)"
fi
echo
echo " HATIRLATMA: İKİ Pi AYNI ANDA ÇALIŞMASIN — ikisi de HR100'e yazar,"
echo " PLC çelişkili OK/NOK alır. Yeni Pi'yi açmadan eskisini KAPAT."
echo "============================================================"
