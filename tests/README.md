# Ekransız testler

Gerçek `config.yaml`, saha logları ve kameraya DOKUNMAZ: her test geçici bir klasörde
kendi config/log'unu kullanır (`main.load_config` ve `MainWindow.LOG_DIR` yamalanır),
kamera worker'ı başlatılmaz, `QMessageBox` susturulur, Qt `offscreen` platformunda koşar.
Uygulama çalışırken de güvenle çalıştırılabilir.

```bash
bash tests/calistir_testler.sh          # hepsi
python3 tests/test_paket.py             # tek dosya
```

| dosya | kapsam |
|---|---|
| `test_gecikme_kamera.py` | worker: picamera2 gölgeleme düzeltmesi, OpenCV yedeğinden geri dönüş, yarım nesne close(); main: çekim gecikmesi kutusu↔config↔Ayarlar, zamanlama damgası, kamera aç/kapa sırası, Enter koruması, imx477 çözünürlükleri |
| `test_closeevent.py` | kapanışta sınırlı bekleme + donmuş worker'da zorla çıkış |
| `test_sayac.py` | sayaç, sebep kategorileri, CSV, kalıcılık, iki kamera etiketi, PDF üretimi, sıfırlama, uçtan uca çekim→sayaç |
| `test_paket.py` | paket adedi kutusu, 100'de uyarı (modal değil), Devam et/Sıfırla/X, adet değişimi, kalıcılık |

NEDEN burada: testler önce `/tmp` altındaki oturum klasöründeydi; Pi yeniden başlayınca
`/tmp` temizlendi ve sabahki takım kayboldu (2026-09-23). Testler artık repoda yaşar.
