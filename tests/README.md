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
| `test_gecikme_kamera.py` | worker: picamera2 gölgeleme düzeltmesi, OpenCV yedeğinden geri dönüş, yarım nesne close(); main: sol panelde gecikme kutusu yok (2026-09-24), Ayarlar gecikmesi→config, zamanlama damgası, kamera aç/kapa sırası, Boşluk/Enter/tık çekim tetiklemez + elle çekim metotları yok (mod 2026-09-24'te kaldırıldı), imx477 çözünürlükleri |
| `test_closeevent.py` | kapanışta sınırlı bekleme + donmuş worker'da zorla çıkış |
| `test_sayac.py` | sayaç, sebep kategorileri, CSV, kalıcılık, iki kamera etiketi, PDF üretimi, sıfırlama, uçtan uca çekim→sayaç |
| `test_paket.py` | paket adedi kutusu, 100'de uyarı (modal değil), Devam et/Sıfırla/X, adet değişimi, kalıcılık |
| `test_stil.py` | seçenek kutuları görünür (Fusion + koyu palet ile render, piksel sayımı): boş/işaretli/pasif, Ayarlar kamera grubu kutuları, tik resmi, resimsiz yedek |
| `test_urun_yok.py` | ürün var/yok kapısı: saf `product_present`, uçtan uca boş kare → URUN_YOK (PLC 1, NOK sayılmaz, panel/durum/uyarı penceresi, son geçerli kare korunur), kapı kapalı/tolerans/referanssız, önizleme, PDF, kalıcılık, sıfırlama, tetik aralığı logu, iki kamera |
| `test_snapshot_olcek.py` | sağdaki 'Son Alınan Tam Resim' paneli pencereye sığar: açık min genişlik (cırcır koruması), büyük resim + pencere küçültme → taşma yok, resim etikete sığar, oran korunur, etiket kendi boyutu değişince yeniden ölçek |
| `test_paket_dur.py` | paket dolunca konveyör dur bayrağı (HR102): açılış temizliği, 100'de 1, Devam et/Sıfırla/X/parti Sıfırla/adet değişimi → 0, bağlantı yok/gelince/yazım hatası, açılışta dolu paket, özellik kapalı, Ayarlar kutusu+register, Modbus sahte istemci + beyaz liste |
| `test_urun_bulma.py` | ürün bulma eşiği: aydınlık bant + ürün sentetik sahnede 110 bantla birleşir / 160 yalnız ürün, karanlık bantta ikisi de ürün, ray kenarı katılmaz, varsayılan 110; Ayarlar kutuları, Kaydet → config + log, 'Ürün Çerçevesi Bul' logu eşiği yazar |
| `test_sekil_esik.py` | delik şekil kapısı eşikleri nokta başına: hilal sentetik ROI → 'sekil uygun degil' + '<' işareti, override → OK, genel eşik → OK, başka nokta etkilemez, kategori; editör alanları (0-1, 2 ondalık); `_open_roi_manager` roi_defaults; panelde delik satırı 2 satır (yuvarlak/dolgu kutuları, konum, oran biçimi, kutu → override) |
| `test_operator.py` | NOK'ta operatör kontrol penceresi: açılış (modal değil, %80, resim, gerekçe), DOĞRU → sayaç/paket/dağılım/NOK listesi düzeltme + CSV, HATALI, açıkken yeni NOK, cevapsız kapatma, OK'ta yok, özellik kapalı, paket uyarısı, PDF, sıfırlama, kalıcılık, Ayarlar |

NEDEN burada: testler önce `/tmp` altındaki oturum klasöründeydi; Pi yeniden başlayınca
`/tmp` temizlendi ve sabahki takım kayboldu (2026-09-23). Testler artık repoda yaşar.
