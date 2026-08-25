#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# venv VARSA onu, YOKSA sistem python'unu kullan.
# NEDEN: sahadaki Pi'de venv hic kurulmadi (picamera2/PyQt5/pymodbus Debian 13'te
# sistemden geliyor) ve bu betik "veri_toplama/bin/python: No such file or directory"
# ile duruyordu. Yeni bir Pi'ye tasirken de ayni tuzak var: kurulum_pi.sh
# calistirilmadan once bu betik calismali.
if [ -x "veri_toplama/bin/python" ]; then
  exec veri_toplama/bin/python main.py
fi

if ! python3 -c "import picamera2, PyQt5, cv2, yaml, pymodbus" 2>/dev/null; then
  echo "HATA: Gerekli kutuphaneler eksik." >&2
  echo "  Kurulum:  bash tools/kurulum_pi.sh" >&2
  echo "  (ya da sistem paketleri: sudo apt install python3-picamera2 python3-pyqt5 python3-opencv python3-yaml python3-pymodbus)" >&2
  exit 1
fi

exec python3 main.py
