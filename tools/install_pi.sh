#!/usr/bin/env bash
# Raspberry Pi'de Konveyor Denetim Sistemi'ni uygulama menusune ve masaustune
# kendi ikonuyla ekler (VSCode/terminal olmadan, cift tikla acilir).
#
# Kullanim (Pi uzerinde, proje klasorunde):
#   bash tools/install_pi.sh
#
# Onkosul: veri_toplama venv'i kurulu olmali (picamera2'ye erisim icin
#          tercihen:  python3 -m venv --system-site-packages veri_toplama)
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$DIR/veri_toplama/bin/python"

if [ ! -x "$PY" ]; then
  echo "HATA: $PY bulunamadi. Once venv kurun:"
  echo "  python3 -m venv --system-site-packages veri_toplama"
  echo "  veri_toplama/bin/pip install -r requirements.txt"
  exit 1
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

# Masaustune de kopyala (varsa)
if [ -d "$HOME/Desktop" ]; then
  cp "$DESKTOP" "$HOME/Desktop/konveyor-denetim.desktop"
  chmod +x "$HOME/Desktop/konveyor-denetim.desktop" || true
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
