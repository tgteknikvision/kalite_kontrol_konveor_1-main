#!/usr/bin/env bash
# Tüm ekransız testleri koşar; her dosya için TOPLAM satırını gösterir. Çıkış kodu: hata sayısı.
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen
hata=0
for t in tests/test_*.py; do
  printf '%-32s ' "$t"
  out="$(timeout 300 python3 -u "$t" 2>&1)"; rc=$?
  ozet="$(printf '%s\n' "$out" | grep -E '^TOPLAM' | tail -1)"
  if [ "$rc" -eq 0 ] && [ -n "$ozet" ]; then echo "$ozet"; else echo "BAŞARISIZ (rc=$rc)"; printf '%s\n' "$out" | grep -E 'FAIL|Error|Traceback' | head -5; hata=$((hata+1)); fi
done
exit $hata
