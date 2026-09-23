#!/usr/bin/env bash
# Raspberry Pi'de Konveyor Denetim Sistemi'ni uygulama menusune ve masaustune
# kendi ikonuyla ekler (VSCode/terminal olmadan, cift tikla acilir).
#
# Kullanim (Pi uzerinde, proje klasorunde):
#   bash tools/install_pi.sh
#
# Onkosul: gerekli kutuphaneler kurulu olmali. venv VARSA venv, YOKSA sistem
# python'u kullanilir (calistir.sh ile ayni mantik) — Debian 13'te picamera2/
# PyQt5/opencv/pymodbus apt'tan geldigi icin venv sart degil.
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"

# venv VARSA onu, YOKSA sistem python'unu kullan.
# NEDEN: sahadaki Pi'lerde venv kurulmuyor (kutuphaneler apt'tan geliyor) ve bu
# betik "veri_toplama/bin/python bulunamadi" ile duruyordu — calistir.sh'ta
# cozulen tuzagin aynisi burada da vardi.
if [ -x "$DIR/veri_toplama/bin/python" ]; then
  PY="$DIR/veri_toplama/bin/python"
else
  PY="$(command -v python3)"
  if [ -z "$PY" ]; then
    echo "HATA: python3 bulunamadi." >&2
    exit 1
  fi
fi

# Kisayol calisir durumda mi: eksik kutuphane varsa ikon SESSIZCE acilmaz,
# o yuzden kurulum aninda uyar (kurulumu engellemez).
if ! "$PY" -c "import picamera2, PyQt5, cv2, yaml, pymodbus" 2>/dev/null; then
  echo "UYARI: $PY ile gerekli kutuphaneler ice aktarilamadi."
  echo "       Ikon kurulacak ama uygulama acilmayabilir."
  echo "       Kurulum:  bash tools/kurulum_pi.sh"
  echo "       (ya da: sudo apt install python3-picamera2 python3-pyqt5 python3-opencv python3-yaml python3-pymodbus)"
fi

APP_DIR="$HOME/.local/share/applications"
DESKTOP="$APP_DIR/konveyor-denetim.desktop"
mkdir -p "$APP_DIR"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Konveyör Denetim Sistemi
Comment=Konveyör Bant Kalite Kontrol Denetim Sistemi
Exec=$PY $DIR/main.py
Path=$DIR
Icon=$DIR/app.png
Terminal=false
Categories=Utility;Engineering;
StartupNotify=true
EOF
chmod +x "$DESKTOP"

# Masaustune de kopyala. Klasor adi yerellestirilmis olabilir ("Masaüstü") —
# once XDG'ye sor, sonra bilinen adlari dene.
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [ -z "$DESKTOP_DIR" ] || [ ! -d "$DESKTOP_DIR" ]; then
  for d in "$HOME/Desktop" "$HOME/Masaüstü"; do
    [ -d "$d" ] && DESKTOP_DIR="$d" && break
  done
fi
if [ -n "$DESKTOP_DIR" ] && [ -d "$DESKTOP_DIR" ]; then
  cp "$DESKTOP" "$DESKTOP_DIR/konveyor-denetim.desktop"
  chmod +x "$DESKTOP_DIR/konveyor-denetim.desktop" || true
  echo "Masaustu   : $DESKTOP_DIR/konveyor-denetim.desktop"
fi

# --- KAMERA ONIZLEME kisayolu (2026-09-23, kullanici istegi): denetim programindan
# BAGIMSIZ canli kamera goruntusu (tools/kamera_onizleme.sh). Terminal=true: libcamera
# hatalari (orn. "Camera frontend has timed out" = kablo) ayni pencerede gorunsun.
KAMERA_DESKTOP="$APP_DIR/kamera-onizleme.desktop"
cat > "$KAMERA_DESKTOP" <<EOF2
[Desktop Entry]
Type=Application
Name=Kamera Önizleme
Comment=Denetim programından bağımsız canlı kamera görüntüsü (odak / ışık / kablo kontrolü)
Exec=bash $DIR/tools/kamera_onizleme.sh
Path=$DIR
Icon=camera-photo
Terminal=true
Categories=Utility;Engineering;
StartupNotify=true
EOF2
chmod +x "$KAMERA_DESKTOP"
if [ -n "$DESKTOP_DIR" ] && [ -d "$DESKTOP_DIR" ]; then
  cp "$KAMERA_DESKTOP" "$DESKTOP_DIR/kamera-onizleme.desktop"
  chmod +x "$DESKTOP_DIR/kamera-onizleme.desktop" || true
  command -v gio >/dev/null 2>&1 && gio set "$DESKTOP_DIR/kamera-onizleme.desktop" metadata::trusted true 2>/dev/null || true
  echo "Masaustu   : $DESKTOP_DIR/kamera-onizleme.desktop"
fi

# Menu onbellegini tazele (varsa)
command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

echo "Kuruldu: $DESKTOP"
echo "Calistirici: $PY $DIR/main.py"
echo "Ikon       : $DIR/app.png"
echo
echo "Not: Masaustundeki ikona ilk tikta 'Allow Launching' / 'Guven' sorulabilir."
echo "     Uygulama menusunde 'Konveyör Denetim Sistemi' olarak gorunur."
