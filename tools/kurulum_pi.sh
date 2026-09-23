#!/usr/bin/env bash
# Raspberry Pi 5'te Konveyor Bant Denetim Sistemi'ni bastan kurar:
#   sistem paketleri (picamera2 + Qt/OpenGL) -> venv -> python bagimliliklari -> ikonlu kisayol
#
# Kullanim (Pi uzerinde, proje klasorunde):
#   bash tools/kurulum_pi.sh
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "[1/4] Sistem paketleri kuruluyor (picamera2 + PyQt5 + OpenGL)..."
sudo apt-get update
# picamera2 ve PyQt5 sistemden gelir (Pi'de pip ile sorunlu/yavas olabilir);
# venv --system-site-packages ile bunlari gorur. libgl1: Qt/OpenCV goruntuleme.
# NOT: libatlas-base-dev Debian 13 (trixie)'de yok; numpy kendi BLAS'ini getirir.
sudo apt-get install -y python3-picamera2 python3-pyqt5 libgl1

echo "[2/4] Sanal ortam olusturuluyor (veri_toplama, --system-site-packages)..."
# --system-site-packages: venv'in sistemdeki picamera2'yi gormesini saglar.
if [ ! -x "veri_toplama/bin/python" ]; then
  python3 -m venv --system-site-packages veri_toplama
else
  echo "      venv zaten var, atlaniyor."
fi

echo "[3/4] Python bagimliliklari kuruluyor (Pi OS'ta piwheels ARM tekerlekleri)..."
veri_toplama/bin/python -m pip install --upgrade pip
veri_toplama/bin/pip install -r requirements.txt

echo "[4/4] Uygulama kisayolu olusturuluyor (menu + masaustu, kendi ikonu)..."
bash tools/install_pi.sh

echo
echo "============================================================"
echo " KURULUM TAMAMLANDI"
echo " - Uygulama menusunde 'Konveyör Denetim Sistemi' (kendi ikonu)"
echo " - Komut satirindan:  ./calistir.sh"
echo "============================================================"
