# Program Kullanım Notları

## Programı Başlatma

Program PLC Modbus bağlantısı için sanal ortam içindeki Python ile çalıştırılmalıdır:

```bash
./calistir.sh
```

Alternatif komut:

```bash
veri_toplama/bin/python main.py
```

`python3 main.py` ile çalıştırılırsa sistem Python ortamında `pymodbus` olmadığı için PLC bağlantısında `No module named 'pymodbus'` hatası alınabilir.

Bu not, Raspberry Pi 5 üzerindeki konveyör denetim programının sahada nasıl kullanılacağını anlatır.

## 1. Başlatma

1. Kamera, PLC ve aydınlatmanın enerjili olduğundan emin olun.
2. Raspberry Pi ile PLC'nin aynı Ethernet ağına bağlı olduğunu kontrol edin.
3. Programı başlatın (doğrudan ROI/Eşik analiz ekranı açılır).
4. Canlı kamera görüntüsü gelene kadar bekleyin.
5. Sistem durumunda `CANLI`, PLC durumunda `READY` görülmelidir.

## 2. Kalibrasyon

Kalibrasyon sadece ürün tipi, kamera konumu, ışık, zoom, çözünürlük, PLC adresi veya ROI alanları değiştiğinde yapılmalıdır.

1. `Kalibrasyon Modunu Aç` düğmesine basın.
2. Kamera çözünürlüğünü seçin.
3. Kamera FPS değerini seçin.
4. Dijital zoom değerini ayarlayın.
5. Gerekirse `Çekim Gecikmesi ms` değerini girin.
6. Işık sabitse ve görüntü kararlı isteniyorsa `Exposure/Gain Kilidi` değerini aktif edin.
7. Manuel exposure aktifse `Exposure us` ve `Analog Gain` değerlerini ayarlayın.
8. `Kalibrasyon Resmi Al` ile örnek görüntü alın.
9. `Ürün Çerçevesi Bul` ile ürün konturunun bulunduğunu doğrulayın.
10. `Ürün İçinde ROI Çiz / Ayarla` ile kontrol edilecek alanları ürün çerçevesinin içinde çizin.
11. Uygun ürün takılıyken `OK Referans Ekle` düğmesine basın.
12. PLC tipi, IP, port, unit id ve poll süresini kontrol edin.
13. `Kaydet ve Kilitle` düğmesine basın.

Kalibrasyon açıkken PLC trigger okumaları durur. Bu sırada üretim sonucu PLC'ye gönderilmez.

Not: ROI'ler artık tam kamera görüntüsüne değil, bulunan ürün çerçevesinin içine göre kaydedilir. Bu yüzden bu özellik aktifken eski tam-resim ROI/referansları yeniden çizilmelidir.

## 3. Çekim Gecikmesi

`Çekim Gecikmesi ms`, PLC sensörden ürün algıladıktan sonra kameranın kaç milisaniye bekleyip resim alacağını belirler.

Bu değer ürün sensörden geçtikten sonra kameranın görüş merkezine gelmesi için kullanılır.

Örnek:

```text
trigger_delay_ms = 120
```

Bu durumda PLC trigger geldikten 120 ms sonra resim alınır.

## 4. Exposure/Gain Kilidi

`Exposure/Gain Kilidi` aktifse kamera otomatik pozlamayı kapatır ve sabit değerlerle çalışır.

Bu ayar üretimde önerilir, çünkü otomatik pozlama ışık değişiminde görüntüyü oynatabilir.

Başlangıç için öneri:

```text
Exposure us: 8000
Analog Gain: 1.0
```

Görüntü karanlıksa exposure veya gain artırılır. Görüntü patlıyorsa exposure veya gain azaltılır.

## 5. Üretim

1. Kalibrasyonun kaydedildiğinden emin olun.
2. Program üretim modundayken ayarlar kilitlidir.
3. PLC sensör ürünü algılayınca `trigger` verir.
4. Program ayarlı gecikme kadar bekler.
5. Resim alınır ve ROI analizi yapılır.
6. Sonuç PLC'ye `OK` veya `NOK` olarak gönderilir.

## 6. Üretim Öncesi Kontrol

Üretime başlamadan önce şu şartlar sağlanmalıdır:

- Canlı kamera görüntüsü akıyor olmalı.
- PLC durumu bağlı görünmeli.
- En az bir aktif ROI olmalı.
- Her aktif ROI için OK referans alınmış olmalı.
- Kamera/ışık/ürün pozisyonu kalibrasyon sırasında olduğu gibi kalmalı.
- `Çekim Gecikmesi ms` sensör ile kamera mesafesine göre ayarlanmış olmalı.

Program bu şartlar yoksa üretimde PLC trigger geldiğinde analiz yapmak yerine hata durumuna geçer.

## 7. Dikkat Edilecekler

- Kamera veya aydınlatma oynarsa yeniden kalibrasyon yapılmalıdır.
- Ürün tipi değişirse yeniden kalibrasyon yapılmalıdır.
- ROI yoksa veya OK referans yoksa üretime geçilmemelidir.
- PLC IP değişirse kalibrasyondan PLC ayarı güncellenip tekrar kilitlenmelidir.
- Exposure/gain kilidi aktifken ışık seviyesi sabit tutulmalıdır.

## 8. ROI Ölçüm Logları

Programın ana OK/NOK kararı `template_score_max` değerine göre yapılır. Bu skor, ROI görüntüsünün OK referansa ne kadar benzediğini gösterir.

Loglarda ayrıca her ROI için yardımcı ölçümler gösterilir:

- `siyah %`: ROI içinde Otsu eşik sonrası siyah kalan alan oranı.
- `beyaz %`: ROI içinde Otsu eşik sonrası beyaz kalan alan oranı.
- `parlaklık`: normalize gri görüntünün ortalama parlaklığı.

`OK bant` satırı, referans resimlerden hesaplanan alt/üst aralığı gösterir. Bu değerler ayar yaparken yol gösterir; kararın ana eşiği yine ROI skorudur.

Pratik kullanım:

1. ROI alanlarını çiz.
2. Sağlam ürünle `OK Referans Ekle` düğmesine bas.
3. Logdaki `referans ölçüm` ve `OK alt/üst bant` satırlarını oku.
4. Ürünü tekrar analiz et.
5. Sağlam ürün NOK çıkıyorsa `template_score_max` veya oran toleranslarını biraz artır.
6. Hatalı ürün OK çıkıyorsa toleransı daralt.
