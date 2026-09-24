# Program Kullanım Notları

> 2026-09-23'te güncel arayüze göre yeniden yazıldı (eski "Kalibrasyon Modu / OK Referans Ekle /
> template" akışı programdan kaldırılmıştı). Raspberry Pi 5 üzerindeki konveyör denetim
> programının sahada nasıl kullanılacağını anlatır.

## 1. Başlatma
- Menüdeki **"Konveyör Denetim Sistemi"** ikonu ya da proje klasöründe `./calistir.sh`.
  Betik venv varsa onu, yoksa sistem Python'unu kullanır (bu Pi'de kütüphaneler apt'tan gelir).
- Açılışta doğrudan denetim ekranı gelir (mod seçimi / kalibrasyon kilidi yoktur).
- Sol üstte **Sistem Durumu**: Durum `CANLI` (kamera akıyor), PLC `READY` ve logda `PLC bağlı`.
  **Poz** satırında 🔒 görünmeli; `⚠ OTO` yazıyorsa Ayarlar'dan Exposure/Gain kilidini aç.

## 2. Ekran düzeni
- **Sol panel:** Sistem Durumu (Durum, FPS, Netlik, Poz, PLC) · Sayaç · en altta **⚙ Ayarlar**.
  (Elle Çekim Modu ve Çekim Gecikmesi kutuları 2026-09-24'te sol panelden kaldırıldı; gecikme Ayarlar'da.)
- **Kamera satırı (her açık kamera için bir tane):** solda **Kontrol Merkezi** tablosu + canlı
  görüntü; sağda **Son Alınan Tam Resim** (tıklayınca tam boy) + **Kontrol Noktaları** +
  **Ürün Çerçevesi Bul** butonları.
- **Altta Sistem Logları.** Aynı satırlar `~/konveyor_loglari/denetim-YYYY-AA-GG.log` dosyasına
  da yazılır (uygulama kapansa da kalır).

## 3. Çekim gecikmesi (sensör → kamera zamanlaması)
Sensör ürünü görünce PLC tetik verir; program **Çekim Gecikmesi** kadar bekleyip resmi çeker.
Kamera sensörden ileride duruyorsa ürünün kadraja gelmesi için bu süre gerekir.
1. **⚙ Ayarlar → Çekim Gecikmesi ms** kutusuna bir başlangıç değeri yaz (ör. 100 ms) → Kaydet.
2. Bir ürün geçir. **Son Alınan Tam Resim**'in sol altında `Gecikme 100 ms | kare 23 ms` yazar.
3. Ürün resimde **henüz gelmemişse değeri artır, geçmişse azalt**; tekrar ürün geçir.
4. Log satırı gerçek süreyi gösterir: `gecikme 100 ms, tetikten 112 ms sonra, kare yaşı 23 ms`.
   `kare yaşı` kullanılan karenin eskiliğidir; 20 fps'te 50 ms'ye kadar oynar. Daha kararlı
   zamanlama için Ayarlar'dan FPS'i artır.
- Kontrol noktası çizilmemişken de tetikle gelen kare saklanır ve damgalanır; yani gecikme
  ayarı nokta çizmeden yapılabilir. Değer bir sonraki tetikten itibaren geçerlidir.
- Aydınlatma tetikle yanıp sönüyorsa gecikme, ışığın açık kaldığı süreyi aşmamalı.
- Ayarlar penceresi açıkken PLC tetiği durur; değeri girip **Kaydet** ile kapat, sonra ürün geçir.

## 3b. Kamera Önizleme simgesi (programdan bağımsız canlı görüntü)
Masaüstündeki **"Kamera Önizleme"** simgesine çift tıkla: takılı tüm kameralar bulunur ve her
biri için yan yana bir canlı pencere açılır (pencere başlığında poz/gain/fps). Odak, ışık ve
kablo kontrolü için denetim programını açmaya gerek kalmaz.
- Denetim programı açıksa kamerayı o tuttuğu için önce **"kapatılsın mı?"** diye sorar
  (Evet dersen PLC denetimi durur; bitince programı menüdeki simgeden yeniden aç).
- config.yaml'da poz/gain kilidi AÇIKSA aynı poz/gain ile gösterir (programdaki görüntüyle aynı).
- Kapatmak için açılan terminal penceresinde **Ctrl+C** ya da pencereyi kapat.
- Görüntü bir süre sonra donar ve terminalde `Camera frontend has timed out ... check that your
  camera sensor connector is attached securely` yazarsa sorun yazılım değil, **o kameranın
  kablosu/konnektörüdür** (2026-09-23'te Kamera 1'de görüldü).
- Komut satırından: `bash tools/kamera_onizleme.sh` (test için `bash tools/kamera_onizleme.sh 5000` = 5 sn).

## 3c. Sayaç ve PDF rapor
Sol paneldeki **Sayaç** kutusu parti başlangıcından beri **geçen parça, OK, NOK (yüzde), sistem
hatası** ve **hata dağılımını** (hangi kontrol noktası, hangi sebeple, kaç kez) gösterir. Sayılar
uygulama kapansa da kaybolmaz.
- **Paket adedi:** OK/NOK satırlarının altındaki kutu (varsayılan 100). **Paket** satırı o
  paketteki OK parçaları sayar (NOK parçalar pakete girmez). Sayı hedefe ulaşınca bip sesiyle
  büyük bir uyarı çıkar: **"100 adete ulaşıldı!"** → **Sıfırla** = paketi kapat, sayaç 0'dan
  başlar (günlük toplamlar kalır); **Devam et** = sayım sürer, bir sonraki uyarı 200'de, sonra
  300'de… Uyarı açıkken denetim ve PLC durmaz; pencereyi X ile kapatmak "Devam et" sayılır.
  Kutu değişince hedef, mevcut sayımın üstündeki ilk kata ayarlanır.
- **Paket dolunca konveyör durur (2026-09-24):** hedefe ulaşılınca program PLC'deki **HR102**
  register'ına 1 yazar ("dur"); **Sıfırla** ya da **Devam et** deyince 0 yazar ("çalış"). Uyarı
  penceresinde "KONVEYÖR DURDURULDU" yazar, sol panelde "PAKET DOLDU … — konveyör durdu". Uygulama
  yeniden açılınca paket hâlâ doluysa uyarı ve dur bayrağı yeniden gelir. **PLC programında HR102
  okunup 1 iken konveyör durdurulmalı** (PLC'ci yapar); HR102 başka işte kullanılıyorsa Ayarlar →
  PLC → "Dur register" değiştirilir. Özellik Ayarlar → "Paket dolunca konveyörü durdur" ile kapatılır.
- **PDF Rapor:** özet, nokta/sebep dağılımı, sistem hataları ve son 300 NOK parçanın listesi
  (zaman, resim no, sebep). Masaüstüne `kalite_raporu_TARİH_SAAT.pdf` olarak kaydeder ve açar.
- **Sıfırla:** yeni parti/vardiya başlatır (onay sorar); önceki değerler loga ve CSV'ye yazılır.
- Her çekim için resimsiz bir satır `~/konveyor_loglari/parca-YYYY-AA-GG.csv` dosyasına eklenir
  (Excel ile açılır, ayırıcı `;`): zaman, resim no, kaynak (plc/elle), sonuç, gecikme, hatalı
  noktalar, sebepler, ölçümler. 16.000 parça yaklaşık 5 MB yer tutar.
- **Sistem hatası** = parça denetlenemedi (kamera görüntüsü yok, kontrol noktası yok, ürün
  çerçevesi bulunamadı); PLC'ye NOK yazılır ve sebebi sayaçta ayrı görünür.
- Sebep adları: "kapalı / eksik / tıkalı" (delikte koyu alan az), "şekil uygun değil" (koyu blob
  yuvarlak değil), "derinlik yetersiz", "oluk yok (oran bant dışı / şekil yok)", "ayna / ters parça".

## 3d. "Ürün algılanamadı" uyarısı (yanlış çekim)
Tetik gelir ama kamera karede ürün bulamazsa (örn. sensör boş banda tetik verdi, parça
kameranın altından geçmişti) program bunu **NOK saymaz**; ekranda **"ÜRÜN ALGILANAMADI"**
penceresi çıkar (bip sesiyle), durum satırı turuncu **ÜRÜN YOK** olur, son resimde bulunan
yanlış çerçeve turuncu gösterilir.
- **PLC'ye yine NOK (1) gider** → hat NOK'taki gibi davranır (durur/ayırır). PLC programı değişmedi.
- **Ne yapmalı:** banda ve parçaya bakın — parça gerçekten geçti mi, sensör boşa mı tetikledi?
  Sonra **"Kontrol ettim"** ile pencereyi kapatın. Pencere açıkken denetim ve PLC durmaz;
  yeni yanlış çekimler aynı pencerede sayılır.
- Sol panelde **"Yanlış çekim (ürün yok): N"** satırı ve PDF raporunda ayrı sütun.
- **Sık oluyorsa:** loglarda `[Tetik] ... önceki tetikten X s sonra` değerine bakın; yanlış çekimler
  hep 1-2 s aralıkla geliyorsa sensör aynı parçaya iki tetik veriyor (PLC'ci ile bakılmalı).
  Çekim gecikmesi de yanlış olabilir (§3).
- Ölçüt: bulunan ürün çerçevesi, kontrol noktaları çizilirken kaydedilen referans kutudan
  en ya da boyda %25'ten fazla sapıyorsa "ürün yok" sayılır (config: `inspection.product_box_tolerance`;
  `inspection.product_presence_check: false` kapatır).

## 3e. NOK'ta operatör kontrolü (DOĞRU / HATALI)
Program bir parçaya NOK deyince PLC'ye NOK gider (konveyör durur) ve ekranda büyük bir pencere açılır:
o anki resim (kontrol noktaları işaretli), altında programın gerekçesi ve iki buton.
- **✔ DOĞRU — parçayı OK say:** parça sağlamsa. NOK sayısı bir azalır, OK ve paket bir artar; hata
  dağılımı düzeltilir; CSV'ye `OPERATOR_DOGRU` satırı düşer.
- **✘ HATALI — NOK kalsın:** NOK onaylanır (`OPERATOR_HATALI`).
- Pencereyi cevapsız kapatırsanız ya da cevaplamadan yeni bir NOK gelirse parça NOK kalır.
- PLC'ye ek bir şey yazılmaz; konveyörü her zamanki gibi siz çalıştırırsınız.
- Sol panelde "Operatör: N doğru / M hatalı" satırı, PDF raporunda özet.
- Eşik ayarı sırasında çok NOK çıkıyorsa Ayarlar → "NOK'ta operatör kontrol penceresi" kutusunu kapatın.

## 4. Ayarlar (⚙)
PLC (tip, IP, port, unit id, poll) · **Kamera 1 / Kamera 2** (grup başlığındaki kutu = kamerayı
kullan) · çözünürlük (imx477 doğal modları: 4056x3040 ağır, 2028x1520, 2028x1080, 1332x990) ·
FPS · dijital zoom (**1.0 bırak**, detay üretmez) · **Exposure/Gain Kilidi** (üretimde AÇIK;
hareketli bantta poz ≤1 ms, imx477'de 400 µs iyi sonuç verdi) · çekim gecikmesi · **ürün bulma
eşikleri** (metal parlaklık V, doygunluk S — bkz. §5 madde 2).
- **Pencere açıkken PLC tetiği işlenmez.** Kaydet ile yalnız değişen taraf uygulanır
  (kamera yeniden başlatma / PLC bağlantısını yenileme).
- Kameraları açıp kapatırken program önce kapatır sonra açar. Yine de kamera gelmezse 10 s içinde
  kendiliğinden yeniden dener; hâlâ gelmiyorsa uygulamayı kapatıp açın.

## 5. Kalibrasyon sırası (ürün, kamera, ışık ya da lens değişince)
1. Ayarlar → poz kilidi + kısa poz; **Netlik** göstergesiyle odak (sayı tepe yaptığı yerde bırak).
2. Çekim gecikmesini §3'teki gibi ayarla (ürün kadrajın ortasında olsun).
3. **Ürün Çerçevesi Bul** → sarı çerçeve tüm braketi sarmalı (ray / arka plan girmemeli).
4. **Kontrol Noktaları** → **＋ Yeni Kontrol Noktası** → Delik (daire) / Çentik (kutu) → resimde
   sürükleyerek çiz. Her nokta otomatik numara alır. Noktaya sağ tık → Ayarlar (eşik) / Sil.
   **Kaydet ve Kapat**. En sağlıklısı, noktaları otomatikte gelen **gerçek üretim karesi**
   üzerinde çizmektir (editör her zaman son tetik karesini kullanır).
5. Eşikler: **Kontrol Merkezi**'ndeki "en az" kutularından canlı ayarlanır; her değişiklikte son
   kare yeniden değerlendirilir (PLC'ye yazılmaz). İyi ve hatalı parça ölçümlerinin ortasına koy.
6. Yön/el: doğru parça görüntüsü açıkken Kontrol Noktaları menüsünden **🧭 Yön Referansı Al**
   (en az 2 delik noktası gerekir) → ters/ayna parça NOK verir.
7. İki kamera açıksa 3-6 adımları her kamera için ayrı yapılır; PLC'ye tek (VE'lenmiş) sonuç yazılır.

- **Çerçeve bantı da kapsıyorsa (tam boy / çok büyük çıkıyorsa):** bant, kamera ya da ışık değişince
  parlaklaşmış ve ürünle birleşmiştir. Ayarlar → **"Ürün bulma: metal parlaklık eşiği (V)"** değerini
  artır (sahada 160; bant ~100-125, ürün ~180-240), Kaydet, tekrar **Ürün Çerçevesi Bul**. Logda
  `[Ürün Bulma] ... (metal eşiği V≥160 ...)` görünür. Sonra kontrol noktalarını yeniden çiz.
- **"Şekil uygun değil" (örn. `yuvarlak 0.48 < 0.55, dolgu 0.49 < 0.50`):** delikteki koyu bölge tam
  daire değil (havşa yansıması ya da kısmen kapalı delik). Parça sağlamsa Kontrol Noktaları → noktaya sağ
  tık → Ayarlar → **Yuvarlaklık Eşiği / Dolgu Eşiği** değerlerini ölçülenin altına çek (ör. 0,40) → Kaydet
  ve Kapat. Mesajda `<` işaretli ölçüt hangisiyse onu düşür. Parça gerçekten kısmen kapalıysa NOK doğrudur.

## 6. Üretim
- PLC bağlı, her açık kamerada en az bir delik/çentik noktası.
- Tetik: HR101 0→1. Sonuç: HR100 = 0 OK, 1 NOK/hata; yaklaşık 1 s sonra 0'a çekilir.
- Konveyör dur: HR102 = 1 (paket dolu) / 0 (çalış) — PLC bu register'ı okumalı (§3c).
- Nokta yoksa, kamera karesi yoksa ya da ürün çerçevesi bulunamazsa PLC'ye hata (1) yazılır ve
  durum ERROR olur; sebep logda yazar.

## 7. Elle test
Elle çekim modu **2026-09-24'te kaldırıldı**: çekimi yalnız PLC tetiği yapar; Boşluk/Enter ya da
canlı görüntüye tıklamak çekim YAPMAZ. Ürün geçirmeden eşik denemek için: Kontrol Noktaları →
Kaydet (son gerçek kare yeniden değerlendirilir) ya da Kontrol Merkezi eşik kutuları.

## 8. Logları okuma
- `[Tetik] … | gecikme 100 ms, tetikten 112 ms sonra, kare yaşı 23 ms` → zamanlama.
- `ürün çerçevesi: x=, y=, w=, h=` → tetikten tetiğe çok oynuyorsa hizalama / ışık sorunu.
- Delik: `acik %X` (koyu oran, "açıklık" eşiği), `cekirdek %` ("derinlik"), `yuvarlak`, `dolgu`.
- Çentik: `koyu %X`, `blob %`, `en/boy`. Yön: `delik fark ±X, ref ±Y`.
- Kamera: `Picamera2 açıldı (cam0)` normaldir; `OpenCV'ye geçiliyor` görülürse kamera bağlantısını
  kontrol et (program 10 s sonra kendiliğinden yeniden dener).

## 9. Dikkat edilecekler
- Ayarlar / Kontrol Noktaları penceresi açıkken otomatik çekim olmaz; pencereyi kapat.
- Zoom 1.0 bırak; çözünürlük ya da zoom değişince noktalar yeniden çizilmeli.
- Fare tekerleği hiçbir ayarı değiştirmez (kazara değişmesin diye); tıklayıp yaz ya da ok tuşları.
- `config.yaml` her ayar değişikliğinde yeniden yazılır; elle düzenlemek için uygulamayı kapat.
