# Saha Durumu — Konveyör Kalite Kontrol

> Bu dosya HEP güncel gerçeği tutar. Durum değişince ilgili satırı **üstüne yaz**.
> Son güncelleme: 2026-09-23 ~13:30

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
00. ⚠️ **KAMERA 1 (cam0) FİZİKSEL BAĞLANTI ŞÜPHELİ (09:20 stdout):** 46 sn kare verdikten
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
2. **imx477 kalibrasyonu hâlâ YAPILMADI.** K1 çalışırken bile (07:09:41-07:10:28) ürün
   çerçevesi x=440,y=0,w=397,h=1088 (tam boy dar şerit → yanlış), nokta 1 koyu %0.1, nokta 3
   bant dışı. K2 (800×600) çerçevesi tüm kare (0,0,800,600) + imx296 dönemi yön referansı (+48)
   ile "AYNA/TERS" → anlamsız. Yapılacak: çerçeve → noktalar → eşikler → yön referansı, HER
   kamera için ayrı.
3. **Poz kilidi KAPALI (bugün 07:10 kaydında kapatıldı):** `camera.manual_exposure_enabled:
   false`, `exposure_us: 1000`; `camera2` de kilitsiz (500). Oto-poz → hareket bulanıklığı +
   eşik kayması. 15 Eylül'de 400 µs kilitle iyi görüntü alınmıştı; kilit geri açılmalı.
4. **Çözünürlük 1456×1088 (K1) / 800×600 (K2)** imx477'de native değil; native modlar
   1332×990, 2028×1080, 2028×1520, 4056×3040. Ayarlar listesinde bunlar yok (kod imx296'ya göre;
   config'e elle yazılırsa combo'ya eklenir).
5. **imx477 ROLLING shutter** → hareketli bantta eğilme riski; kısa pozla üretim karesinde izlenmeli.

## ⚠️ Depo / altyapı (2026-09-23)
- **GitHub KARARI (09:45): uzak depo `kalite_kontrol_konveor_1-main`** (içeriği 10 Ağustos
  upload'ıyla birebir aynı, kayıp yok). Bağlama komutlarını kullanıcı çalıştıracak (ajanın
  set-url/push'u sınıflandırıcıca engellendi; komutlar CLAUDE.md §12'de). Tamamlanınca bu
  satırı "push çalışıyor" diye güncelle. Eski durum: `origin` = kalite_kontrol_konveor_1 →
  "Repository not found". Hesapta `kalite_kontrol_konveor_1-main` (public, tek commit 00227cb
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

## Uygulama ayarları (config.yaml — bugün 07:10'da GUI yazdı; 23 Eylül yerel commit'te)
- `cameras`: camera1_enabled=**true**, camera2_enabled=**false** (kullanıcı bugün 3 kez değiştirdi).
- `resolution` 1456×1088, `resolution2` 800×600. `camera`: zoom 1.0, fps 20, exposure 1000 µs,
  gain 16, **kilit KAPALI**. `camera2`: exposure 500, gain 16, kilit kapalı, zoom 1.0.
- K1 noktaları: 1,2=hole, 3=notch (`dynamic_rois` 1:[82,217,154,142] 2:[307,203,191,168]
  3:[51,3,452,80]), `reference_box [550,410]`, `point_overrides {'3': notch_dark_min 40}`,
  global `hole_dark_ratio_min 10`, `notch_dark_min 50`. Yön: v2 kalıntısı (kod v3 → sessizce atlanır).
- K2 (pasif): imx296 dönemi 3 nokta + `reference_box [971,726]` + yön v3 (+48.4) → imx477 için GEÇERSİZ.
- PLC: modbus_tcp, poll_ms 20, timeout 0.2, manual_mode false (üretim).
- `inspection.trigger_delay_ms`: **1** (kullanıcı artık SOL PANELDEKİ "Çekim Gecikmesi" kutusundan
  ayarlayacak; her çekimde resmin sol altında `Gecikme X ms | kare Y ms`, logda tetikten geçen süre).

## ⚠️ Üretim uyarısı
Kamera geri gelse de kalibrasyon yapılana kadar her PLC tetiğinde HR100'e NOK (1) yazılır. Hattı
bu hâlde üretimde kullanma; ayar sırasında "Elle Çekim Modu" (PLC devre dışı) kullanılabilir.
