# Saha Durumu — Konveyör Kalite Kontrol

> Bu dosya HEP güncel gerçeği tutar. Durum değişince ilgili satırı **üstüne yaz**.
> Son güncelleme: 2026-09-28 ~12:55 (/kalite tam okuma 467040d + config.yaml'ın gerçek hali)

## Donanım / Makine
- **Raspberry Pi 5**, kullanıcı `tg_pi5_kalite_kontrol_konveor`, makine `tgpi5kalitekontrolkonveor`.
  Debian 13, sistem python 3.13 (venv YOK): cv2 4.10, numpy 2.2.4, Qt 5.15.15, pymodbus 3.8.6,
  picamera2 0.3.36 (apt). Uygulama `/usr/bin/python main.py` ile çalışıyor.
- **İKİ imx477 (HQ, 12MP, ROLLING shutter) takılı (2026-09-23 `rpicam-hello` ile doğrulandı):**
  cam0 = i2c@88000, cam1 = i2c@80000. İkinci imx477 18 Eylül'de takıldı (o günkü log 14:19'da
  iki kamera birlikte açıldı). imx296'lar sökülü. dmesg'de I2C/CSI hatası YOK.
- PLC: Modbus TCP `192.168.10.10:502`, unit_id 0 — bugün bağlı, tetik geliyor.
  Pi eth0 statik `192.168.10.50/24` (gateway YOK, internet wlan0'dan).

## ⚠️ AKTİF SORUNLAR (2026-09-23)
000. **2026-09-28 12:55: UYGULAMA KAPALI.** Pi 12:47'de açıldı; kullanıcı 12:48'de uygulamayı açtı (yeni kod),
   2 tetik (#1 OK, #2 NOK nokta 1 açıklık %14.0 < 14 → operatör HATALI → ilk gerçek operatör kaydı
   `operator_kontrol/2026-09-28/` yazıldı), 12:48:33 parti Sıfırla (önceki parti 24 Eylül: 527 parça, 426 OK,
   87 NOK, 1 hata, 13 yanlış çekim), 12:48:35 kapattı. Sayaç 0, paket hedefi 1000.
   **14:30: görev çubuğundaki onlarca Python simgesi = Kontrol Merkezi pencere sızıntısı (düzeltildi; 13:51'de VS
   Code'dan açılan örnek eski kodda, restart gerekir).** 13:51-14:03 arası 111 analiz, 14 operatör penceresi, 4 ürün yok.
   **13:32: masaüstüne "Konveyör Denetim Sistemi" simgesi kuruldu** (`~/Desktop/konveyor-denetim.desktop` →
   `tools/baslat.sh`; her zaman güncel kod, ikinci kopya engeli). Sonraki açılış bu simgeden: karar bandı +
   başlıkta sürüm görünecek.
00. ⚠️ **KAMERA 1 (cam0) FİZİKSEL BAĞLANTI SORUNU TEKRARLIYOR — bugün 7 zorla kapanış, hepsi
   gerçek takılma** (09:21-09:25 ×5, 13:09 ve 13:14 ×2; 13:06:38 tetikte "Kamera görüntüsü yok").
   Sağlıklı kapanış 0,45 s ölçüldü → 3 sn zaman aşımı doğru. **Kablo/konnektör değiştirilmeli.**
   Ayrıntı (09:20 stdout): 46 sn kare verdikten
   sonra libcamera `Camera frontend has timed out! Please check that your camera sensor
   connector is attached securely` → sensörden kare akışı donanım seviyesinde kesildi; donmanın
   asıl sebebi bu. Kablo/konnektör kontrol edilmeli (14 Eylül'deki imx296+uzatıcı arızasıyla
   aynı sınıf). Tekrarını görmek için masaüstündeki **Kamera Önizleme** simgesi (terminalde aynı
   mesaj canlı görünür). Uygulama şu an kullanıcı tarafından 09:25'te açılmış (pid 137655, VS
   Code terminali), Kamera 1 çalışıyor, gecikme ayarı sahada kullanılıyor.
0. ✅ **ÇÖZÜLDÜ (09:20) — "kapatamıyorum" (gerçek karşılıklı kilitlenme, gdb ile doğrulandı):**
   Pi 09:10'da yeniden başlamış, pid 5553 boot'tan 28 sn sonra açılmış, ~5 dk sonra donmuş.
   Ana thread `closeEvent`'te süresiz `worker.wait()`'te, kamera worker'ı bir kare bekleyip
   takılı kalmıştı — klasik karşılıklı kilitlenme. `kill -9` ile kapatıldı; `closeEvent` artık
   sınırlı bekliyor (3 sn) ve zaman aşımında `os._exit` ile zorla kapanıyor (bir daha
   "kapatamıyorum" olamaz). Kameranın NEDEN donduğu kök sebebi hâlâ açık — tekrarlarsa
   `[HATA] Kamera thread'i 3 sn içinde kapanmadı` logunu izle. Uygulama pid 88319, 09:20'de
   yeni kodla açık, Kamera 1 çalışıyor.
1. ✅ **ÇÖZÜLDÜ (07:44) — kamerasız kalma.** 07:10:43'te K1 aç + K2 kapa aynı anda → Picamera2
   "Camera __init__ sequence did not complete" → OpenCV yedeği, kare yok, her tetik NOK. Kullanıcı
   07:25'te yeniden başlattı (kamera geldi); ajan 07:44, 07:48 ve 07:52'de YENİ KODLA yeniden başlattı (son: pid 446752, kamera + PLC OK, IPARPI spam yok):
   aç/kapa sırası düzeltildi + yedekten 10 s'de bir Picamera2'ye geri dönüş eklendi. Uygulama
   ajan tarafından `setsid nohup env DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 … python3 main.py` ile
   ayrık çalışıyor; stdout `~/konveyor_loglari/uygulama-stdout.log`. libcamera her karede
   "IPARPI Embedded data buffer parsing failed" basıyordu → `main.py` başında
   `LIBCAMERA_LOG_LEVELS=IPARPI:FATAL` ile susturuldu (kareler/poz metadata akıyor; kök sebep
   imx477 + libcamera sürümü, izlenmeli).
2. ✅ **KAMERA 1 (imx477) KALİBRASYONU KULLANICI TARAFINDAN YAPILDI (12:58-13:14, GUI'den;
   14:45 tam config okumasında fark edildi — hafıza geride kalmıştı):** 3 nokta yeniden çizildi
   (1,2=delik, 3=çentik; `reference_box [708,542]`), eşikler Kontrol Merkezi'nden ayarlandı
   (`point_overrides` 1: açıklık 13 / derinlik 9; 3: oluk 25), **yön referansı v3 alındı (+58)**,
   **poz kilidi AÇIK (1000 µs, gain 16)**, çekim gecikmesi **300 ms**. Sonuç: 13:19'daki son
   analizler OK (delik 1 açık %14 yuvarlak 0.89; delik 2 %34; oluk %38 blob %37; yön +58/+61),
   ürün çerçevesi ~x=656,y=293,w=673,h=516. Saat 13'te 98 OK / 23 NOK, saat 12'de 12 OK / 15 NOK
   (ayar sırasında). Kullanıcı "sistem on numara çalışıyor" dedi (13:0x).
   ⚠ `roi.handedness_reference` (v2 base64) ve `handedness_margin: 0.05` ölü anahtar olarak
   duruyor (zararsız). K2 (pasif) hâlâ imx296 dönemi ayarlarında.
3. ✅ Poz kilidi AÇIK (`camera.manual_exposure_enabled: true`, 1000 µs, gain 16). `camera2`
   kilitsiz ama kapalı.
4. **Çözünürlük 1456×1088 (K1) / 800×600 (K2)** imx477'de native değil; native modlar
   1332×990, 2028×1080, 2028×1520, 4056×3040. Ayarlar listesinde bunlar yok (kod imx296'ya göre;
   config'e elle yazılırsa combo'ya eklenir).
5. **imx477 ROLLING shutter** → hareketli bantta eğilme riski; kısa pozla üretim karesinde izlenmeli.

## ⚠️ Depo / altyapı (2026-09-23)
- **✅ GitHub ÇALIŞIYOR (13:35):** `origin` = github.com/tgteknikvision/kalite_kontrol_konveor_1-main
  (public). İlişkisiz geçmişler `-s ours` ile birleştirildi (25 Ağustos yükleme commit'i geçmişte),
  11 commit push edildi, `main` → `origin/main` izliyor. Kimlik: `gh auth setup-git`. Hesapta `kalite_kontrol_konveor_1-main` (public, tek commit 00227cb
  25 Ağustos upload, FARKLI geçmiş) ve `GI_PI_KAMERA_SISTEM-main` (private) var. Yerel `main`
  origin'den önde → **15 Eylül'den beri push edilemiyor**; commit'ler yerelde birikiyor.
  gh CLI girişi var (tgteknikvision, repo scope) ama git credential helper yok. Karar kullanıcıda.
- `.gitignore` + `.gitattributes` 23 Eylül'de yeniden eklendi (**`.claude/skills/` = bu bilgi
  tabanı artık git'te**; `.claude/*` geri kalanı, venv, pycache, *.log dışarıda). Geçmiş: 2 upload
  commit + 23 Eylül yerel commit'ler; `surum1-sablon` dalı yok.
- `saha_ayarlari.conf` ✅ imx477 × 2 olarak güncellendi.
- Loglar: `~/konveyor_loglari/denetim-YYYY-AA-GG.log` (10 Ağustos'tan beri 5 gün var).

## Sayaç / kayıt (2026-09-23 13:30, kodda hazır; çalışan örnek eski kod → restart gerekli)
- Sol panel "Sayaç": geçen/OK/NOK/sistem hatası + nokta-sebep dağılımı; `PDF Rapor` (masaüstüne)
  ve `Sıfırla`. Kalıcı: `~/konveyor_loglari/sayac.json`; parça başına `parca-YYYY-AA-GG.csv`.
  Resim KAYDEDİLMİYOR (kullanıcı kararı; 16.000 parça JPEG ≈ 2,5-5 GB olurdu).
- **Operatör kontrol kayıtları (2026-09-24 16:10, kodda; restart gerekli):** NOK'ta açılan kontrol
  penceresinin resmi + kararı `<proje>/operator_kontrol/GÜN/tarih-saat_resimNNNN_KARAR.jpg` + `operator_kayit.csv`
  (yalnız NOK'lar → günde en fazla birkaç yüz KB × NOK sayısı; 30 gün saklanır, Ayarlar'dan değişir).
  **2026-09-28 13:20:** resmin ÜSTÜNDE renkli karar bandı (DOĞRU yeşil / HATALI kırmızı / CEVAPSIZ turuncu +
  tarih-saat, resim no, kamera, gerekçe); uygulama kapanırken açık pencere CEVAPSIZ yazılır. Restart bekliyor
  (bugünkü 12:48 kaydı eski kodla bantsız). **14:00: pencerede 3. seçenek YANLIŞ ÇEKİM** (OK'a da NOK'a da sayılmaz,
  yanlış çekim sayacına gider) ve "ürün algılanamadı" olayı da aynı pencereye gidiyor (DOĞRU=OK, HATALI=NOK,
  YANLIŞ ÇEKİM/kapatma=yanlış çekim kalır). **15:00: kayıtlar parti klasörlerinde** (`operator_kontrol/parti_<son Sıfırla
  tarih-saati>/`; Sıfırla biten klasöre parti_ozeti.txt + kalite_raporu.pdf yazar ve parti CSV'sini ANA listeye
  `operator_kontrol/operator_kayit.csv` ekler — 15:20). Bugünkü eski `2026-09-28/` gün klasörü kalır; kökteki eski biçimli
  CSV yeni kodun ilk açılışında `parti` sütunuyla taşınır (parti = `2026-09-28`); yeni kodla ilk kayıt
  `parti_2026-09-28_12-48-33/`'e gider.
- **Paket adedi (13:45):** `inspection.paket_adedi` = 100 (varsayılan); paket sayacı OK parçaları
  sayar, hedefte modal olmayan uyarı (Sıfırla/Devam et). Spinbox okları artık görünür.

## Uygulama ayarları (config.yaml @ commit 467040d = disk, son yazım 2026-09-24 15:13:56; 2026-09-28 tam okuma)
- `cameras`: camera1_enabled=**true**, camera2_enabled=**false**.
- `resolution` 1456×1088, `resolution2` 800×600. `camera`: zoom 1.0, fps 20, **exposure 200 µs, gain 16,
  kilit AÇIK** (24 Eylül 13:1x'te 1000→200). `camera2`: exposure 500, gain 16, kilit kapalı, zoom 1.0.
- K1 noktaları: `dynamic_rois` 1:[407,305,235,217] hole, 2:[80,265,218,229] hole, 3:[78,6,604,116] notch;
  `reference_box [723,566]`; `point_overrides` 1:{açıklık 14, derinlik 12, yuvarlaklık 0.20}, 2:{açıklık 10,
  derinlik 2}, 3:{oluk 25}; global `hole_dark_ratio_min 10`, **`notch_dark_min 50`** (25 yazılmıştı, çalışan
  uygulama geri yazdı; nokta 3 override'ı 25 → etkisiz), yuvarlaklık 0.55 / dolgu 0.50.
  **Yön v3: `handedness_hole_diff +38.55`, margin 12** (v2 base64 + `handedness_margin 0.05` ölü anahtar).
- `alignment`: `metal_v_min` / `metal_s_max` **YOK** → kod varsayılanı 110/85 (200 µs pozda bant eşiğin altında;
  28 Eylül çerçeveleri 727×565, 728×549 = referansa ±%3). Bant yine parlaklaşırsa Ayarlar'dan 160.
- `inspection`: `trigger_delay_ms` **40**, `paket_adedi` **1000** (kullanıcı); `operator_review`, `operator_kayit`,
  `operator_kayit_gun`, `product_presence_check`, `product_box_tolerance` yazılı değil → varsayılanlar
  (true / true / 30 / true / 0.25).
- PLC: modbus_tcp 192.168.10.10:502 unit 0, poll_ms 20, timeout 0.2, `registers {nok 100, trigger 101, stop 102}`,
  `paket_dolu_durdur true`. Ölü: `calibration` bloğu, `hole_use_circle_check`.
- K2 (pasif): imx296 dönemi 3 nokta + `reference_box [971,726]` + yön v3 (+48.4) → imx477 için GEÇERSİZ.

## Üretim durumu
**2026-09-28 12:48 — GÜNÜN İLK 2 PARÇASI:** #1 OK (nokta 1 açıklık 14.9 / derinlik 12.1 — eşiklerin hemen
üstünde), #2 NOK nokta 1 açıklık %14.0 < 14 (derinlik 7.7 de 12'nin altında) → operatör HATALI dedi (resimde delik
1'in üst yarısı parlak, havşa yansıması örüntüsü). Ürün çerçevesi 727×565 / 728×549 (referans 723×566) → ürün
bulma sağlam, gecikme 40 ms ile ürün kadrajda (y≈230). **Nokta 1 eşikleri (14 / 12) sağlam parçaların okuduğu
değerin tam üstünde** → 24 Eylül önerisi (açıklık 10, derinlik 8, Kontrol Merkezi kutularından) hâlâ bekliyor.
24 Eylül öğleden sonra partisi: 527 parça, 426 OK, 87 NOK (%16.5), 13 yanlış çekim, 1 hata (12:48'de sıfırlandı).
**2026-09-24 13:20 — BANT PARLAKLAŞTI, ÜRÜN ÇERÇEVESİ BANTLA BİRLEŞİYORDU:** bant V 100-125, ürün 180-240;
`alignment.metal_v_min` 110 → **160** yazıldı (config; Ayarlar'da da ayarlanır). Kullanıcı restart → Ürün
Çerçevesi Bul → noktaları yeniden çiz → gecikme. Netlik 108/132 (odak düzeldi). Kamera bugün en az iki kez
oynadı (ürün 670→830→626 px), sensör konumu/gecikme de değişti (10 ms).
**2026-09-24 11:50 — PLC'Cİ İŞİ BEKLİYOR:** program paket dolunca **HR102=1** (dur), Sıfırla/Devam et'te
0 yazıyor; PLC programı HR102'yi okuyup konveyörü durdurmalı/çalıştırmalı — henüz yapılmadı. HR102
PLC'de başka amaçla kullanılıyorsa Ayarlar → PLC → Dur register değiştirilir.
**2026-09-24 11:20 — REFERANS ESKİ:** 10:45'ten beri ürün karede ~%20 büyük (OK çerçeveleri 830×655,
referans 708×542) ve netlik 163→19: kamera/lens oynamış olabilir. Sınırdaki kareler sahte "yanlış çekim"
veriyor. Yapılacak: odak → Kontrol Noktaları yeniden çiz (referans güncellenir) → gecikme (şu an 50 ms,
ürün karenin altında).
**2026-09-24 10:30 — ÜRÜN VAR/YOK KAPISI kodda (restart bekliyor):** boş kare artık NOK değil,
"yanlış çekim" (sayaç `urun_yok`, operatör uyarısı, PLC'ye yine 1). Bugün 09:47-09:50 (gecikme 300):
21 tetik, 17 OK, NOK'lar çoğunlukla önceki tetikten 1-2 s sonra → sensör çift tetik şüphesi.
Kullanıcı 09:52'de gecikmeyi 10 ms yaptı. Delik 1 eşiği 13 sınırda (OK 12.8-14.5) → 11 önerildi.

Kamera 1 kalibre, parçalar OK geçiyor (13:19). Tek açık risk cam0 kablo/konnektör takılması
(yukarıdaki 00. madde): tekrarlarsa uygulama restart'a kadar her tetiğe NOK yazar.
