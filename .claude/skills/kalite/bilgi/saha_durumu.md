# Saha Durumu — Konveyör Kalite Kontrol

> Bu dosya HEP güncel gerçeği tutar. Durum değişince ilgili satırı **üstüne yaz**.
> Son güncelleme: 2026-09-23 ~14:45 (tam kod+config okumasıyla düzeltildi)

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
000. **UYGULAMA 14:17'de KAPALI** (kullanıcı 13:50 ve 14:16'da yeni kodla açmış; 13:53'te PDF
   rapor üretmiş). Son PLC tetiği 13:19:42. `sayac.json` ilk parçada oluşacak.
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
- **Paket adedi (13:45):** `inspection.paket_adedi` = 100 (varsayılan); paket sayacı OK parçaları
  sayar, hedefte modal olmayan uyarı (Sıfırla/Devam et). Spinbox okları artık görünür.

## Uygulama ayarları (config.yaml @ commit 45e8ba8, 2026-09-23 14:45 tam okuma)
- `cameras`: camera1_enabled=**true**, camera2_enabled=**false**.
- `resolution` 1456×1088, `resolution2` 800×600. `camera`: zoom 1.0, fps 20, **exposure 1000 µs,
  gain 16, kilit AÇIK**. `camera2`: exposure 500, gain 16, kilit kapalı, zoom 1.0.
- K1 noktaları: `dynamic_rois` 1:[430,285,209,210] hole, 2:[87,268,217,203] hole,
  3:[88,5,548,115] notch; `reference_box [708,542]`; `point_overrides` 1:{hole_dark_ratio_min 13,
  hole_core_ratio_min 9}, 3:{notch_dark_min 25}; global `hole_dark_ratio_min 10`, `notch_dark_min 50`.
  **Yön v3: `handedness_hole_diff +58.02`, margin 12** (v2 base64 kalıntısı ölü anahtar).
- K2 (pasif): imx296 dönemi 3 nokta + `reference_box [971,726]` + yön v3 (+48.4) → imx477 için GEÇERSİZ.
- PLC: modbus_tcp, poll_ms 20, timeout 0.2, manual_mode false (üretim).
- `inspection.trigger_delay_ms`: **10** (2026-09-24 09:52'de kullanıcı 300→10 yaptı; 300 ile 09:47-09:50 arası 17/21 OK; `paket_adedi`
  anahtarı henüz yok → varsayılan 100).

## Üretim durumu
**2026-09-24 10:30 — ÜRÜN VAR/YOK KAPISI kodda (restart bekliyor):** boş kare artık NOK değil,
"yanlış çekim" (sayaç `urun_yok`, operatör uyarısı, PLC'ye yine 1). Bugün 09:47-09:50 (gecikme 300):
21 tetik, 17 OK, NOK'lar çoğunlukla önceki tetikten 1-2 s sonra → sensör çift tetik şüphesi.
Kullanıcı 09:52'de gecikmeyi 10 ms yaptı. Delik 1 eşiği 13 sınırda (OK 12.8-14.5) → 11 önerildi.

Kamera 1 kalibre, parçalar OK geçiyor (13:19). Tek açık risk cam0 kablo/konnektör takılması
(yukarıdaki 00. madde): tekrarlarsa uygulama restart'a kadar her tetiğe NOK yazar.
