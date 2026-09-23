# CLAUDE.md — Konveyör Bant Kalite Kontrol Denetim Sistemi

Bu dosya, projede çalışan AI ajanları (ve geliştiriciler) için hızlı bağlamdır.
Koddan çıkarılamayan kararları, tuzakları ve çalıştırma/dağıtım bilgisini içerir.
Dil: arayüz ve yorumlar **Türkçe**, kod tanımlayıcıları İngilizce.

> ## 🖥️ MAKİNE DEĞİŞTİYSE — İLK İŞ (yeni Pi / yeni kurulum)
> Kullanıcı **Pi değiştirdiğini, yeni makineye taşındığını ya da kurulum yapacağını**
> söylüyorsa (veya bu makinede daha önce çalışılmadığından şüpheleniyorsan) **ilk iş**
> şu komutu çalıştır ve sonucu kullanıcıya özetle:
> ```bash
> bash tools/yeni_pi_kur.sh --kontrol
> ```
> **Hiçbir şeyi değiştirmez**, 6 maddelik fark raporu verir (python kütüphaneleri,
> kameralar, statik IP, PLC erişimi, uygulama ayarları, ajan). Eksik varsa kullanıcıya
> söyle ve **onayını alarak** `--kontrol` olmadan çalıştır — betik zaten her değiştirici
> adımda ayrıca onay sorar. Ayrıntı ve elle adımlar: **§14**.
> **SORMADAN AĞ/SİSTEM AYARI DEĞİŞTİRME** (statik IP değişimi SSH bağlantısını keser,
> iki Pi aynı anda çalışırsa PLC çelişkili OK/NOK alır — §14).

> ## ⚠️ ÇALIŞMA KURALI — HER DEĞİŞİKLİKTEN SONRA (SORMADAN OTOMATİK)
> Kodda/konfigde her anlamlı değişiklikten **hemen sonra**, **ONAY BEKLEMEDEN/SORMADAN**
> şunları yap (kullanıcı kalıcı olarak istedi):
> 1. **Bu CLAUDE.md'yi güncel tut:** etkilenen bölümü revize et; §12 "Mevcut durum"u ve
>    başlığındaki tarihi güncelle. (Belge ile kod asla ayrışmasın.)
> 2. **Commit'le ve GitHub'a push et:** anlamlı bir mesajla commit; **hemen ardından push**.
>    "Commit'leyeyim mi?" diye SORMA — değişiklik tamamlanır tamamlanmaz otomatik yap.
>    Terminalde GitHub girişi yoksa VS Code "Sync/Push" ya da `gh auth login` kullan.
>    **⚠️ 2026-09-23: eski `origin` (kalite_kontrol_konveor_1) GitHub'da YOK. KULLANICI KARARI:
>    yeni uzak depo = `tgteknikvision/kalite_kontrol_konveor_1-main` (içeriği 10 Ağustos
>    upload'ıyla birebir aynı, kayıp yok). Ajanın `git remote set-url`/`push` komutları güvenlik
>    sınıflandırıcısınca engellendiği için ilk bağlama komutlarını kullanıcı çalıştırır (bkz. §12);
>    sonrasında push normal çalışır. Kör `--force` yerine `merge --allow-unrelated-histories -s ours`.**
>    Commit mesajının sonundaki `Co-Authored-By:` satırını koru.
> - **KAPSAM:** Yalnız proje dosyaları (kod/konfig/doküman). Kişisel makine ayarları
>   (`~/.claude`, VS Code `settings.json` vb., kişisel mutlak yollar) repoya GİRMEZ; `.claude/*`
>   gitignore'da (**istisna: `.claude/skills/` TAKİP EDİLİR** — `/kalite` proje hafızası, 2026-09-23). **Çapraz-makine:** Windows ve Pi aynı repoyu paylaşır → push'tan önce gerekiyorsa
>   `git pull` ile senkron ol, çakışmayı çözüp öyle push et (kör `--force` YOK).

## 1. Proje nedir
Konveyör bandında akan **alüminyum braketlerin** otomatik görsel kalite kontrolünü
yapan endüstriyel denetim istasyonu. **Asıl hedef: parçadaki 2 deliğin açılmış (delinmiş)
olup olmadığını kontrol etmek** (delik hataları).

Akış: Wenglor reflektör sensörü ürünü görür → PLC'ye haber verir → PLC tetik (HR101)
verir → program kamera karesini yakalar → analiz eder → **OK/NOK** kararını PLC'ye
(HR100) yazar.

**Donanım:** Raspberry Pi 5 + RPi Global Shutter kamera (imx296, tepeden), kubbe (dome) difüzör aydınlatma
(parlak metalde düzgün ışık), iki yeşil LED kılavuz ray (parçayı yanal sabitler),
Modbus TCP PLC, sinyal kulesi, HMI. Kamera sabit + ürün tekrarlanabilir konumda gelir.

## 2. Çalıştırma
- **Raspberry Pi (saha):** `./calistir.sh` ya da menüdeki "Konveyör Denetim Sistemi" ikonu.
  Sistem Python'u DEĞİL, `veri_toplama` venv'i kullanılır (pymodbus orada).
- **Windows (geliştirme):** VSCode'dan, ya da `veri_toplama\Scripts\python.exe main.py`.
- Açılışta doğrudan ROI/Eşik analiz penceresi açılır (mod seçme diyaloğu YOK; PaDiM kaldırıldı).

## 3. Ortam / dağıtım
- **Pi:** Debian 13 (trixie), aarch64, Python 3.13. `python3-picamera2` ve `python3-pyqt5`
  **apt'tan** (sistem) gelir; venv `--system-site-packages` ile kurulur ki bunları görsün.
  Tek komut kurulum: **`bash tools/kurulum_pi.sh`** (apt + venv + `pip install -r requirements.txt`
  + ikon). Sadece menü/masaüstü ikonu için: `bash tools/install_pi.sh`.
- **Windows:** Python 3.12 + venv `veri_toplama`; PyQt5/opencv pip'ten.
- venv (`veri_toplama/`) git'e DAHİL DEĞİL.

## 4. Mimari (dosya haritası)
```
main.py                 PyQt5 GUI + tüm orkestrasyon (MainWindow + SettingsDialog).
                        Kamera worker'(lar)ı, PLC timer'ı, üretim durum makinesi burada.
                        İKİ KAMERA (§13): _build_camera_row / _camera_config_view /
                        _start_worker2 / _capture_full_frame(VE'leme).
config.yaml             Tek kalıcı konfigürasyon (GUI okur/yazar).
inspector/worker.py     InspectionWorker(config, cam_index) — kamera QThread'i; cam0='camera',
                        cam1='camera2' anahtarları. picamera2 ana, OpenCV yedek; yedekten kare
                        gelmezse 10 s'de bir picamera2 yeniden denenir (2026-09-23).
inspector/plc.py        NullPLCAdapter + ModbusTCPPLCAdapter. Tetik/sonuç handshake.
inspector/features.py   ROI analiz motoru: 'hole' (delik açık-alan+şekil + delik/çentik tipi) +
                        'template' (eski) + YÖN/EL kontrolü (ayna/simetrik parça → NOK).
inspector/alignment.py  find_product_box: HSV metal izolasyonu ile ürünü (tam braket) bulup kırpar.
inspector/roi_editor.py Kontrol noktası çizim/düzenleme: tek "＋ Yeni Kontrol Noktası" menü-butonu
                        (delik=daire / çentik=kutu / YÖN=turuncu kutu seç → çizim modu silahlanır,
                        TEK çizim), sağ tık → Sil, otomatik rakam isim.
saha_ayarlari.conf      Makine seviyesi saha degerleri (Pi statik IP, PLC IP/port,
                        beklenen kamera sayisi/sensoru, ajan adi). config.yaml
                        UYGULAMA ayarlarini tutar; bu dosya Pi OS ayarlarini.
tools/                  kurulum_pi.sh, install_pi.sh, make_icon.py, plc_smoke_test.py,
                        yeni_pi_kur.sh (yeni Pi'yi IKIZ yapar / --kontrol ile denetler),
                        kamera_onizleme.sh (masaüstü "Kamera Önizleme" simgesi: programdan
                        bağımsız canlı kamera pencereleri, 2026-09-23)
```
**Threading:** Kamera arka plan QThread'inde (`worker`), Qt sinyalleriyle GUI'ye kare
yollar; PLC'den haberi yok. PLC tüm işlemleri GUI thread'inde `QTimer` ile (`poll_ms`,
20 ms) yürür. Köprü: tetikte GUI worker'ın `last_raw_frame`'ini okur.

**Arayüz düzeni (main.py):** Sol kolon ("Sistem Durumu" + "Çalışma Modu": Elle Çekim Modu
kutusu + **"Çekim Gecikmesi (ms)" kutusu (2026-09-23, canlı ayar; bkz. §8
`inspection.trigger_delay_ms`)** + ipucu; **en dibinde "⚙ Ayarlar" butonu**; kaydırılabilir, sabit 320px) + sağda
`content_widget`. **"⚙ Ayarlar" BİLİNÇLİ OLARAK SOL PANELDE (2026-07-30):** eskiden kamera
satırındaydı; bir kamera kapatılınca o satır gizlendiği için Ayarlar'a ERİŞİLEMİYORDU
(kamera 1 kapalıyken geri açmak imkânsızdı) — Ayarlar tüm kameralar+PLC için ortak olduğundan
yeri sol panel. Kamera satırlarında yalnız O KAMERAYA ait 2 buton kalır:
**"Kontrol Noktaları" / "Ürün Çerçevesi Bul"** (iki kamera açıkken "(Kamera 2)" ekli).
Testte kalıcı regresyon koruması var (Ayarlar butonu kamera satırının içinde OLMAMALI). **KALİBRASYON MODU/KİLİDİ KALDIRILDI (2026-07-10):** "Kalibrasyon Modunu Aç /
Kaydet ve Kilitle" yok; tüm PLC+kamera+çekim ayarları **`SettingsDialog`** ("⚙ Ayarlar")
penceresinde, "Kaydet"te `_apply_settings` YALNIZ değişen tarafı uygular (kamera restart /
zoom / PLC adapter yenileme + poll aralığı). Ayarlar ya da Kontrol Noktaları penceresi
AÇIKKEN **`_dialog_paused`** PLC tetiğini duraklatır (eski kalibrasyon davranışının yerine). content = ÜST SATIRDA 2 eşit görüntü (solda canlı `video_label`,
**üstünde son denetim sonucu paneli `lbl_live_errors` = `ROIResultPanel`** — başlıkta
PARÇA OK/NOK, altında **HER kontrol noktası için bir satır**: ad | OK/NOK rozeti
(yeşil/kırmızı kutu) | ölçülen `koyu%` | **eşik slider'ı** | eşik değeri.
Slider o noktanın eşiğini doğrudan `point_overrides`'a yazar (§12); `_update_live_errors`
doldurur, `_on_panel_threshold_changed` uygular),
sağda "Son Alınan Tam Resim" `lbl_snapshot` — her ikisi stretch 1) + ALTTA tam-genişlik
"Sistem Logları" (`txt_logs`). `lbl_snapshot` tıklanınca `_open_snapshot_zoom` tam
çözünürlükte kaydırılabilir QDialog açar (tam pixmap `self._snapshot_full_pixmap`'te).
Anlık gösterim tek yerden: `_display_snapshot` (hem `_handle_snapshot` hem önizlemeler).
`lbl_snapshot` paneli **doldurur** (canlı görüntü boyutunda); `_rescale_snapshot` +
`resizeEvent` ile pencere boyutu değişince yeniden ölçeklenir (eskiden tek seferlik ölçekle
küçük kalıyordu).

## 5. İki ROI analiz yöntemi (önemli)
`config.yaml -> roi.decision_method` ile seçilir:
- **`hole` (VARSAYILAN):** Her ROI'de `hole_dark_value` (gri eşik, ~70) altındaki koyu
  piksel oranı önce **alt-üst bant** kapısından geçer (`hole_dark_ratio_min` ≤ koyu% ≤
  `hole_dark_ratio_max`). Sonra ROI'nin **tipine** göre karar verilir — tip
  `roi.roi_types[ad]` ya da ROI adındaki "oluk"/"çentik" kelimesinden gelir:
  - **`hole` (delik):** koyu blob **GERÇEK yuvarlak delikse** OK — yuvarlaklık ≥
    `hole_min_circularity`, dolgu ≥ `hole_min_fill`, en/boy ≥ `hole_min_aspect`, ROI
    kenarına değme ≤ `hole_max_edge_touch`, blob ≥ `hole_min_blob_ratio`%. Çentik/gölge/bant
    elenir (yanlış-OK önlenir). `hole_shape_check: false` ile kapatılabilir.
    **TIKANMAYA KARŞI (KISMEN bantlı/pullu delik):** ÖNEMLİ — saha gözlemi: gerçek açık
    delikler **siyah DEĞİL gri** okur (~40-70), bu yüzden `<40` tabanlı "çekirdek/derinlik"
    ölçüleri açık deliği yanlış elemişti. Doğru ayrım **AÇIK ALAN miktarı**: tam açık delik
    bol koyu (`hole_dark_value` altı) okur (~%25); **deliği kısmen kapatan parlak bant/pul**,
    o kadar **AZ** koyu okutur (~%9-15). Bu yüzden `hole_dark_ratio_min` artık **asıl kapı**
    (saha ~%20'ye ayarlı): koyu% < eşik → "kapalı/eksik/tıkalı" NOK. Ek olarak **dolgu**
    (`fill` = koyu blob / minEnclosingCircle) yarım-bantlı delikte düşer (~0.5 vs tam ~0.95).
    Eşik **NOKTA BAŞINA** ayarlanır: Kontrol Noktaları → noktaya sağ tık → **Ayarlar** →
    "Delik Açıklık Eşiği (koyu%)" (`roi.point_overrides[ad]`; yoksa global config değeri;
    eski sol-panel slider'ları KALDIRILDI). `hole_core_ratio_min` (~%2) sadece düşük zemin.
  - **`notch` (oluk/çentik):** yuvarlaklık ARANMAZ. **İKİ kapı:** (1) koyu% bandı
    (`notch_dark_min` ≤ koyu% ≤ `notch_dark_max`; alt eşik nokta başına sağ tık →
    Ayarlar'dan, `point_overrides`) +
    (2) **ŞEKİL kapısı** (`notch_shape_check`, varsayılan açık): koyu bölge GERÇEK oluk
    mu? Gerçek oluk = **TEK, BÜYÜK, YATAY-UZUN koyu yarık**; en büyük (bağlı) koyu blob
    ROI'nin ≥ `notch_min_blob_ratio`%'i, en/boy ≥ `notch_min_aspect` (yatay), genişlik
    ROI'nin ≥ `notch_min_width_ratio`'su. **Neden:** salt koyu-oran, DÜZ parçadaki dağışık
    gölge/kenarı da "oluk VAR" sanıp yanlış-OK veriyordu (saha: oluksuz parça koyu ~%17;
    eski eşik %10 → yanlış OK). Şekil, koyu% bandı aldansa bile (ışık/gölge koyu%'ü
    yükseltse de) dağışık-koyu'yu eler. **TUZAK:** `_notch_shape` önce **MORPH_OPEN**
    (dağışık benek/ince gölgeyi siler) sonra CLOSE (yarık içini doldurur) yapar — sadece
    CLOSE yapılırsa dağışık benekler tek dev bloba birleşip şekli boşa çıkarır.
  Referans/öğrenme GEREKTİRMEZ. Konuma/dönmeye/ışığa toleranslı.
  `features.py::_evaluate_holes`, `_hole_shape`, `_notch_shape`, `_roi_type`.
- **YÖN/EL kontrolü (ayna/simetrik parça → NOK):** Parça asimetrik (KADEME/basamak + bir
  delikte HAVŞA/chamfer). Simetrik (ayna) varyantı delikleri yine ~aynı yerlere düşürüp OK
  verebilir; bunu ayrı kontrol yakalar. **Yöntem: İKİ DELİK PARLAKLIK ASİMETRİSİ
  (`HANDEDNESS_VERSION=3`).** Havşalı/kademeli delik kubbe ışıkta daha **KOYU** okur; **en sağ
  ve en sol hole-tipi ROI'nin gri-ortalama farkının (sağ−sol) İŞARETİ** havşalı deliğin tarafını
  → parçanın yön/elini verir. Referans alınırken (doğru parça) bu fark `handedness_hole_diff`
  olarak saklanır; analizde işaret TERS dönerse (ve |fark| > `handedness_margin_diff`~12) →
  "AYNA/TERS" → global NOK. **Neden bu yöntem (önceki 2 deneme ELENDİ):** (1) ikili silüet —
  kademe/havşa silüette yok, parça ~simetrik çıkıp ayıramadı; (2) 96×96 tüm-parça GRİ NCC —
  gerçek ayna parçada bile `normal~0.64 / ayna~0.61` (iki parça piksel düzeyinde temiz ayna
  değil + ayırt edici özellik tüm-parçada seyreliyor). İki-delik farkı ROI başına (konuma
  toleranslı) + göreli (ışığa dayanıklı): gerçek karelerde grup-içi ±0.1, doğru~−26 / ayna~+56
  → 80+ puan zıt-işaretli ayrım. Uçtan uca doğrulandı (ref=A→A OK/B NOK ve tersi).
  **Ölçüm noktaları:** ÖNCE kullanıcının çizdiği **`yon` tipi kontrol noktaları** (≥2 taneyse
  onlar — evrensel: deliksiz üründe de sol/sağ 2 yön noktasıyla yön tayini yapılır); yoksa
  geriye-uyum için hole-tipi noktalara düşer (UI'dan 'yon' çizimi kaldırıldı → pratikte ölçüm
  2 DELİKTEN). Referans **Kontrol Noktaları menüsünden "🧭 Yön Referansı Al (doğru parça)"**
  ile alınır (doğru parça görüntüsü açıkken bir kez tıkla; editördeki güncel noktalarla ölçülür,
  **"Kaydet ve Kapat"ta config'e yazılır**; ≥2 delik gerekir). `HANDEDNESS_VERSION` ile sürümlü
  (eski v2 NCC referansları otomatik geçersiz → yeniden al). `handedness_check: false` kapatır.
  `features.py::_check_handedness`, `hole_handedness_diff`, `_hole_centers_brightness`;
  `roi_editor.py::_take_handedness_reference` → `dlg.handedness_ref_diff` → `_open_roi_manager` yazar.
- **`template` (eski):** ROI'yi öğretilmiş OK referanslarıyla karşılaştırır (normalize
  gri MAD skoru ≤ `template_score_max`). OK referansı ÖĞRETİLMESİ gerekir.
- (PaDiM/ONNX anomali modu **2026-07-09'da projeden KOMPLE KALDIRILDI** — sahada işe
  yaramadı. Geri gerekirse git geçmişinde: `git log --oneline | grep -i padim`.)

## 6. Hizalama (alignment)
`alignment.mode: contour` → `find_product_box` ürünü bulup kırpar; ROI'ler ürüne göreli ve
**`roi.reference_box`'a göre ölçeklenir** (kutu boyutu değişse de ROI'ler oranlı gelir).
`mode: off` → tam kare. **Yöntem (`foreground: bright`):** HSV'de **parlak (V≥`metal_v_min`)
+ renksiz (S≤`metal_s_max`) = metal** maskesi; **yeşil kılavuz raylar renkle elenir**, ince-
dikey konturlar reddedilir. En büyük konturla **yatay örtüşen** parçalar (braketin alt flanşı
vb.) birleştirilir → **tam braket** tek çerçeve. `RETR_EXTERNAL` deliği "ürün" sanmaz. Metal
bulunamazsa eski **Otsu**'ya düşer (`foreground: dark` → THRESH_BINARY_INV). Eski hata: salt-
parlaklık Otsu, parlak yeşil rayları da ürün sanıp çerçeveyi tüm kareye genişletiyordu.
`alignment.py::find_product_box`, `_metal_mask`, `_pick_box`.

## 7. PLC / Modbus
- İstemci Pi, sunucu PLC. `192.168.10.10:502`, unit_id config'te.
- **HR101 = trigger** (PLC→Pi, yalnız oku): 0→1 yükselen kenar = denetim başlat.
- **HR100 = nok** (Pi→PLC, yalnız yaz): **0 = OK, 1 = NOK/hata**.
- Sadece 100/101 register'larına dokunulur (`ALLOWED_REGISTERS`).
- Sonuç yazıldıktan ~1 sn sonra HR100=0'a resetlenir (`QTimer`). **ACK okuması YOK.**
- `plc.type: null` → simülasyon (tetik otomatik gelmez; sadece "PLC Dışı Test Çekimi").
- **`plc.manual_mode: true` → ELLE ÇEKİM MODU (ev/test):** `create_plc_adapter` PLC tipine
  bakmaksızın `NullPLCAdapter` döner. PLC'ye **hiç bağlanılmaz** (olmayan PLC'ye bloke eden
  TCP connect denemesi yok → GUI/canlı görüntü donmaz, log temiz). Arayüzde **"Elle Çekim
  Modu (PLC devre dışı)"** çek kutusu (`_on_manual_mode_changed`, her zaman erişilebilir).
  `plc.type` KORUNUR → sahada kutuyu kapatınca PLC geri gelir. **DİKKAT:** sahaya/Pi'ye
  geçerken bu kutu KAPALI (manual_mode=false) olmalı; aksi halde tetik beklenmez.
- **Elle çekim tetikleri (`_manual_capture`):** Elle Çekim Modu açıkken resim
  **BOŞLUK/ENTER tuşuyla** (`keyPressEvent`) ya da **canlı görüntüye tıklayarak**
  (`_on_video_clicked`) çekilir (çekim BUTONU KALDIRILDI). Üretimde (PLC açık)
  tuş/tık yok sayılır (çekimi PLC tetiği yapar).
- Bağımsız test: `veri_toplama/bin/python tools/plc_smoke_test.py`.

## 8. Konfigürasyon — önemli anahtarlar (`config.yaml`)
- `roi.decision_method`: `hole` | `template`. **`hole_dark_ratio_min`** = asıl kapı (min
  açık-alan/koyu%; tıkanma+kısmen-bantlı deliği yakalar; saha ~%20). **`roi.point_overrides`**
  = `{ad: {hole_dark_ratio_min|notch_dark_min: X}}` — NOKTA BAŞINA eşik (editörde sağ tık →
  Ayarlar; yoksa global değer; eski sol-panel slider'ları KALDIRILDI).
  `hole_dark_value` (~70 gri eşik), `hole_dark_ratio_max` (~85, üst).
  `hole_core_value`/`hole_core_ratio_min` (~%2) sadece düşük zemin. Şekil:
  `hole_shape_check`, `hole_min_circularity/fill/aspect` (fill yarım-bantlıyı da eler),
  `hole_max_edge_touch`, `hole_min_blob_ratio`. Yön/el: `handedness_check` (bool),
  `handedness_hole_diff` (referans iki-delik parlaklık farkı, float; işareti yön/eli verir),
  `handedness_version` (sürüm=3; eskiyse atlanır), `handedness_margin_diff` (~12, ölü bant/min
  büyüklük). "Yön Referansı Al" hepsini yazar (≥2 hole ROI gerekir). Çentik: `notch_dark_min/max`
  (`notch_dark_min` nokta başına sağ tık → Ayarlar'dan da ayarlanır; oluklu parça ~%50,
  oluksuz ~%17 okur → eşik ~35). Çentik şekil kapısı (config'ten): `notch_shape_check`
  (bool, vars. açık), `notch_min_blob_ratio` (~%25, en büyük koyu blob alanı), `notch_min_aspect`
  (~1.2, yatay en/boy), `notch_min_width_ratio` (~0.30, ROI genişlik payı). Log'da `blob %X,
  en/boy Y` görünür → gerçek oluk düşük blob okursa `notch_min_blob_ratio` düşür.
  ROI tipleri: `roi.roi_types` = `{ad: hole|notch|yon}` (**`yon`** = yön tayini ölçüm
  noktası; kusur kontrolüne GİRMEZ, yalnız yön/el ölçümünde kullanılır).
  `roi.reference_box` `[w,h]` (ROI çizimindeki ürün kutusu boyutu; ölçekleme için, ROI editörü yazar).
- `alignment.mode`: `contour` | `off`; `alignment.foreground`: `bright` | `dark`;
  `alignment.metal_v_min`, `alignment.metal_s_max` (metal izolasyon HSV eşikleri).
- `camera.*`: backend (picamera2), exposure_us, analogue_gain, zoom, fps, max_frame_age_ms.
  **`manual_exposure_enabled` (bool) = ANA ŞALTER:** false iken `exposure_us`/`analogue_gain`
  KESİNLİKLE UYGULANMAZ (`worker._camera_controls` boş sözlük döner → oto-pozlama). Hareketli
  bantta **true + `exposure_us` 300-500** olmalı. Sensör limitleri (imx296, Pi'de ölçüldü):
  poz **29 µs**…15.5 s (altı kırpılır; 50→43, 100→88 gibi satır süresine yuvarlanır),
  analog gain gerçekte **1.0…15.7** (libcamera 251.2 der ama üstü dijital kazanç — §12).
  UI aralığı: poz 20…1e6 (adım 50), gain 1.0…16.0 (adım 0.5).
  **`zoom` OPTİK DEĞİL YAZILIM zoom'udur** (`_apply_digital_zoom`: ortadan kırp + geri büyüt) →
  DETAY ÜRETMEZ, bulanıklaştırır. Pi'de ölçüldü (aynı alanı gösteren çıktılar, Laplacian):
  640×480+zoom2 = gerçek detayın %21, 1280×960+zoom2 = %33, 1456×1088+zoom2 = %54,
  **zoom yok (native kırpma) = %100**. Keskinlik için: `1456x1088` (imx296 native, listeye
  2026-07-30'da eklendi) + `zoom: 1.0`. **imx477 native modları (4056x3040 / 2028x1520 /
  2028x1080 / 1332x990) listeye 2026-09-23'te eklendi** (4056x3040 ağır: ≤10 fps). Daha büyük görüntü gerekiyorsa tek gerçek çözüm
  OPTİK (kamerayı yaklaştır / lens değiştir).
- **İKİ KAMERA (§13):** `cameras.camera1_enabled` / `cameras.camera2_enabled` (bool; her kamera
  BAĞIMSIZ açılır-kapanır, ikisi birden kapatılamaz; eski `cameras.enabled_count` geriye-uyumlu
  okunur). Kamera 2 paralel anahtarları
  `camera2`, `resolution2`, `dynamic_rois_2`, `disabled_rois_2`, `roi2.*`, (ops.) `alignment2`.
  Kamera 2'de YAZILMAMIŞ kamera ayarı kamera 1'den devralınır; nokta kimliğine bağlı
  `roi2.roi_types/point_overrides/reference_box/handedness_*` DEVRALINMAZ.
- `dynamic_rois`: ROI'ler `[x,y,w,h]` (alignment açıkken ürün çerçevesine göreli).
- `plc.*`: host/port/unit_id/poll_ms/timeout_s/reconnect_s, registers {nok:100, trigger:101},
  **`manual_mode`** (true → PLC tamamen kapalı, elle çekim; bkz. §7).
- `inspection.trigger_delay_ms`: tetikten sonra çekime kadar bekleme (ürün ortalansın diye).
  **SOL PANELDEKİ "Çekim Gecikmesi" kutusundan CANLI ayarlanır (2026-09-23, kullanıcı isteği:
  "foto çekmeyi erteleme şansı, resme bakıp artırıp azaltacağım").** Ayarlar penceresinde de var ama
  pencere açıkken PLC tetiği durduğu için ürün geçirerek deneme oradan yapılamıyordu. Her PLC
  çekiminde resmin SOL ALTINA `Gecikme X ms | kare Y ms` damgası basılır (`_stamp_capture_note`;
  editörün kullandığı saklanan kare TEMİZ kalır) ve loga `gecikme X ms, tetikten Z ms sonra, kare
  yaşı Y ms` düşer (nokta çizilmemişken `[Kurulum]` satırında da → gecikme nokta çizmeden ayarlanır).
  Ayar döngüsü: ürün geçir → resme bak → ürün gelmemişse ARTIR, geçmişse AZALT. `kare yaşı` =
  worker'ın son karesinin eskiliği (20 fps'te ≤50 ms belirsizlik; kararlılık için FPS artır).
  Işık tetikle yanıp sönüyorsa gecikme ışık süresini aşmamalı.

## 9. Tuzaklar / kurallar (DİKKAT)
- **`*.sh` dosyaları LF olmalı** (`.gitattributes` zorluyor). Windows CRLF olursa Pi'de
  `bash\r: not found` hatası verir. (2026-09-23: bu klonda eksikti, yeniden eklendi.)
- **`app.png` gitignore istisnası** (`!app.png`): ikon repoda kalır; `*.png` diğerleri hariç.
  **2026-09-23: `.gitignore` yeniden eklendi.** Kural: `.claude/*` ignore, **`.claude/skills/` TAKİP
  EDİLİR** (`/kalite` skill'i = proje hafızası; Windows ↔ Pi arasında taşınsın, SD arızasında
  kaybolmasın); kişisel settings/hook'lar yine dışarıda. venv, `__pycache__`, `*.log` de ignore.
- **config.yaml her UI etkileşiminde yeniden yazılır** (`yaml.dump`): yorumlar kaybolur,
  uzun vadede SD kart aşınması riski. Anahtar eklerken kod tarafında `setdefault` kullan.
- **Ayarlar/Kontrol Noktaları penceresi açıkken PLC poll durur** (`_dialog_paused`).
  Kalibrasyon modu/kilidi 2026-07-10'da KALDIRILDI; config'teki eski `calibration.*`
  bloğu artık yazılmıyor (ölü anahtar, durabilir).
- Kamera çözünürlük/zoom değişince template referansları sıfırlanır (ölçeğe bağımlı).
- **Çökme güvenliği:** `main()` global `sys.excepthook` kurar → konsolsuz pythonw'da
  yakalanmamış hata uygulamayı SESSİZCE kapatmaz (dialog gösterir).
- **✅ 2026-09-23, GERÇEK sahada yaşandı — "uygulama donuyor, kapatamıyorum":**
  `closeEvent`'teki eski `worker.wait()` (argümansız = SÜRESİZ) ile kamera worker thread'i
  bir kare bekleyip takılırsa (gdb ile doğrulandı: ana thread `pthread_cond_wait`'te, worker
  GIL/kare bekleme noktasında) KARŞILIKLI KİLİTLENME oluyordu — pencere asla kapanmıyordu.
  Düzeltildi: `wait(3000)` sınırlı, zaman aşımında `os._exit(1)` ile zorla kapanır (11 testle
  doğrulandı). Kameranın NEDEN donduğu (kök sebep) hâlâ açık; log'da `[HATA] Kamera thread'i
  3 sn içinde kapanmadı` görülürse kamera tarafı ayrıca incelenmeli.

## 10. Geri dönüş (reversibility)
- **`git checkout surum1-sablon`** → delik tespiti eklenmeden önceki (template) sürüm.
- Sadece kararı geri almak için: `config.yaml -> roi.decision_method: template`.

## 11. İlgili dokümanlar
- `PROGRAM_KULLANIM_NOTLARI.md` — saha/operatör kullanımı.
- `GEREKLI_KUTUPHANELER.txt`, `requirements.txt` — bağımlılıklar.
- (Kaldırıldı: `PADIM_COLAB_PROMPT.md`, `COLAB_PADIM_EGITIM_NOTLARI.md`,
  `PLC_DEVREYE_ALMA_LISTESI.md`, `PLC_MODBUS_NOTLARI.md`.)

## 12. Mevcut durum (2026-09-23 itibarıyla)
- **📌 2026-09-23 ~09:45 — GITHUB KARARI: uzak depo `kalite_kontrol_konveor_1-main`.**
  Kullanıcı seçti. O depo tek commit (00227cb, 25 Ağustos upload); `gh api` tarball ile indirilip
  karşılaştırıldı: 7 farklı dosyanın hepsi 10 Ağustos yerel commit'iyle (b235a18) BİREBİR AYNI →
  bizde olmayan hiçbir değişiklik yok, kayıp olmaz. Yöntem: `-s ours` ile ilişkisiz geçmişleri
  birleştir (00227cb ata olarak kalır) → normal push, force YOK. Ajan `git remote set-url` ve
  `push`'u çalıştıramadı (auto-mode sınıflandırıcısı "Data Exfiltration" diye engelledi) →
  komutlar kullanıcıya verildi:
  ```bash
  git remote set-url origin https://github.com/tgteknikvision/kalite_kontrol_konveor_1-main.git
  git fetch origin
  git merge --allow-unrelated-histories -s ours origin/main -m "GitHub -main deposu ile birleştirildi (içerik: Pi'deki güncel sürüm)"
  gh auth setup-git
  git push -u origin main
  ```
  `gh auth setup-git`: git için kimlik yardımcısı yok, gh girişli (tgteknikvision, repo scope).
- **⚠️ 2026-09-23 ~09:35 — DONMANIN ASIL SEBEBİ: KAMERA 1 FRONTEND TIMEOUT (KABLO ŞÜPHESİ)
  + MASAÜSTÜ "KAMERA ÖNİZLEME" SİMGESİ:** 09:20'de yeni kodla açılan örneğin stdout'unda cam0
  46 sn kare verdikten sonra libcamera: `Dequeue timer of 1000000us has expired` → `Camera
  frontend has timed out! Please check that your camera sensor connector is attached securely.
  Alternatively, try another cable and/or sensor.` Sensörden kare akışı DONANIM seviyesinde
  kesildi; worker `capture_array()`'de bekledi; kullanıcı kapatınca yeni `closeEvent` 3 sn'de
  zorla kapattı (düzeltme sahada doğrulandı). **14 Eylül'deki imx296+HDMI-uzatıcı arızasıyla
  aynı sınıf → cam0 kablosu/konnektörü fiziksel kontrol.** Kullanıcı isteğiyle
  `tools/kamera_onizleme.sh` + `kamera-onizleme.desktop` (masaüstü + menü, Terminal=true,
  `install_pi.sh` kurar): tüm kameralar için yan yana `rpicam-hello` EGL önizleme pencereleri
  (config'teki poz/gain kilidi ve çözünürlükle), uygulama açıksa zenity ile kapatma onayı;
  libcamera hataları terminalde canlı görünür. Wayland oturumunda doğrulandı (cam1 ile uçtan
  uca). Ayrıntı: `PROGRAM_KULLANIM_NOTLARI.md` §3b, `/kalite` günlüğü.
- **✅ 2026-09-23 ~09:20 — "KAPATAMIYORUM" DONMASI: GERÇEK KARŞILIKLI KİLİTLENME BULUNDU
  VE DÜZELTİLDİ (kullanıcı: "uygulama dondu kapatamıyorum neden acaba"):** Pi 09:10'da yeniden
  başlamış, uygulama boot'tan 28 sn sonra açılmış, ~5 dk sonra donmuş. **gdb ile canlı sürece
  bağlanıp thread yığınları alındı (py-spy yoktu):** ana GUI thread'i `closeEvent` →
  `worker.wait()` (argümansız, SÜRESİZ) → `pthread_cond_wait`'te asılıydı; kamera worker
  thread'i de bir kare (libcamera tamamlanma callback'i) beklerken GIL/semafor noktasında
  takılıydı — klasik karşılıklı kilitlenme, ikisi de ilerleyemiyordu. Bu tam olarak §9'da daha
  önce "açık risk" diye not edilen madde, bugün ilk kez GERÇEK olayla doğrulandı. Donmuş süreç
  `kill -9` ile kapatıldı, `closeEvent` düzeltildi (`wait(3000)` + zaman aşımında `os._exit(1)`
  ile zorla kapanış — bkz. §9), 11 ekransız testle doğrulandı, uygulama yeni kodla yeniden
  başlatıldı (Kamera 1 geldi). **Kameranın NEDEN donduğu kök sebep hâlâ açık** (cold-boot'ta
  libcamera/CFE zamanlaması mı, sabah eklenen 10 sn'lik Picamera2 yeniden-deneme döngüsünden
  kalma bir yarış mı — belli değil); tekrarlarsa `[HATA] Kamera thread'i 3 sn içinde kapanmadı`
  logu iz bırakır.
- **✅ 2026-09-23 — İNCELEME SONRASI DÜZELTMELER + ÇEKİM GECİKMESİ ANA EKRANDA (kullanıcı:
  "önerilerini yapalım" + "foto çekmeyi erteleme şansı, resme bakıp süreyi artırıp azaltacağım"):**
  (1) **`_apply_settings` kamera aç/kapa SIRASI:** önce KAPAT (`_stop_camera` + wait) sonra AÇ.
  Eski sıra (aç→kapa) 07:10:43'te Kamera 1'i "Camera __init__ sequence did not complete" ile
  OpenCV yedeğine düşürmüş, kamera hiç gelmemiş, her tetik NOK olmuştu.
  (2) **`worker.py` OpenCV yedeğinden Picamera2'ye GERİ DÖNÜŞ:** picamera2 tercihliyken yedekten
  100 ardışık kare gelmezse `PICAM_RETRY_S`=10 s aralıkla Picamera2 yeniden denenir
  (`_fallback_retry_due`); `_release_camera` nesne TİPİNE göre kapatır (eskiden yedek
  VideoCapture'a stop() çağrılıp /dev/video* açık kalıyordu).
  (3) **`worker.py::_open_camera` gölgeleme düzeltildi:** picamera2 yapılandırması `pc_cfg`;
  `camera.awb_mode` / `color_gains` artık gerçekten uygulanıyor (testle doğrulandı).
  (4) **ÇEKİM GECİKMESİ SOL PANELDE:** "Çalışma Modu" grubunda `Çekim Gecikmesi (ms)` kutusu
  (`spin_trigger_delay`, 0-5000, adım 10, fare tekerleği kapalı) → `inspection.trigger_delay_ms`
  canlı yazılır, `[Gecikme]` loglanır; Ayarlar'daki kutuyla iki yönlü eşit. Her PLC çekiminde
  resmin SOL ALTINA `Gecikme X ms | kare Y ms` damgası (`_stamp_capture_note`; editörün
  kullandığı saklanan kare TEMİZ), loga `gecikme X ms, tetikten Z ms sonra, kare yaşı Y ms`
  (nokta çizilmemişken `[Kurulum]` satırında da → gecikme ayarı nokta çizmeden yapılabilir).
  `_capture_full_frame(source="plc"|"manual")`; `_trigger_time` tetik anında `_capture_from_plc`'de.
  **Enter koruması:** odak bir giriş kutusundayken (spinbox/metin) BOŞLUK/ENTER çekim tetiklemez
  (`keyPressEvent`; eskiden eşik kutusuna Enter → Elle Çekim Modunda beklenmedik çekim).
  (5) **Ayarlar çözünürlük listesine imx477 modları** (4056x3040, 2028x1520, 2028x1080,
  1332x990) + combo/poz ipuçları. (6) `.gitignore` + `.gitattributes` yeniden eklendi
  (`.claude/skills/` takip edilir, §9); `saha_ayarlari.conf` imx477×2;
  `PROGRAM_KULLANIM_NOTLARI.md` güncel akışa göre yeniden yazıldı.
  **27 ekransız testle doğrulandı** (session scratchpad `test_23eylul.py`: gölgeleme, yedekten
  dönüş + release, aç/kapa sırası iki yönlü, gecikme kutusu↔config↔Ayarlar, damga/temiz kare,
  Enter koruması). **TUZAK (test yazarken):** `MainWindow.LOG_DIR` sınıf niteliği gerçek saha
  loguna yazar → testte geçici klasöre yönlendir (ilk koşuda 24 test satırı saha loguna sızdı,
  temizlendi). Uygulama yeni kodla yeniden başlatıldı (bkz. `/kalite` günlüğü).
  **GitHub `origin` HÂLÂ YOK** → push başarısız; kullanıcı karar verecek.
- **✅ 2026-09-23 ~07:55 — YARIM KALAN Picamera2 NESNESİ KAPATILIYOR + RESTART TUZAĞI:**
  Ajan yeniden başlatırken `pgrep -f "python.*main.py" | head -1` nohup SARMALAYICISININ pid'ini
  verdi → eski uygulama kapanmadı, ikinci örnek açıldı ("Pipeline handler in use by another
  process"), ~1 dk İKİ ÖRNEK PLC'yi yokladı (tetik gelmedi, HR100 çakışması olmadı). Eski örnek
  kapatılınca yeni örneğin 10 s'lik yeniden denemeleri yine "Camera __init__ sequence did not
  complete" verdi: bir deneme `start()`'ta "Invalid argument" ile patlamış, nesne `close()`
  edilmediği için kamera bu süreçte ACQUIRED kalmıştı → sonraki her `Picamera2(0)` başarısız.
  **Düzeltme:** `worker.py::_open_camera` except bloğunda yarım nesne `cam.close()` edilir
  (testli). **KURAL:** uygulamayı kapatırken pid'i `pgrep -f "^/usr/bin/python3 main.py"` ile
  al; iki örnek ASLA aynı anda çalışmasın (ikisi de HR100'e yazar). Ajan başlatma komutu:
  `setsid nohup env DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus python3 main.py >> ~/konveyor_loglari/
  uygulama-stdout.log 2>&1 &` (proje kökünden). `main.py` başında
  `LIBCAMERA_LOG_LEVELS=IPARPI:FATAL` (setdefault): imx477 + libcamera v0.7.1 her karede "Embedded
  data buffer parsing failed" ERROR basıyordu (~140 MB/gün stdout); kareler/poz metadata akıyor.
- **⚠️ 2026-09-23 SABAH TAM OKUMA İNCELEMESİ — bulgular (düzeltmeler üstteki maddede):**
  (1) 07:10:43'te Ayarlar kaydında (K1 aç + K2 kapa aynı anda) Kamera 1 Picamera2 açılamadı →
  OpenCV yedeği → her tetik NOK; kullanıcı 07:25'te uygulamayı yeniden başlatınca kamera geldi.
  (2) **İKİ imx477 takılı** (cam0 + cam1; ikincisi 18 Eylül'de). Kalibrasyon yapılmadı: K1
  çerçevesi x=440,y=0,w=397,h=1088 (yanlış), K2 çerçevesi tüm kare. GUI'den
  `manual_exposure_enabled false` + `exposure_us 1000` yazıldı → **poz kilidi KAPALI**.
  (3) **GitHub `origin` YOK** ("Repository not found"; hesapta yalnız `kalite_kontrol_konveor_1-main`,
  25 Ağustos upload, FARKLI geçmiş) → yerel `main` 15 Eylül'den beri push edilemiyor.
  (4) `.gitignore`/`.gitattributes` eksikti (eklendi). `saha_ayarlari.conf` imx296 bekliyordu
  (düzeltildi). Ayrıntı: `/kalite` günlüğü 2026-09-23 + `program_mimarisi.md` §6.
- **⚠️ KAMERA DEĞİŞTİ: imx296 (Global Shutter) → imx477 (HQ, ROLLING shutter) (2026-09-15).**
  Sebep: Arducam CSI-HDMI uzatıcıları imx296'da fiziksel sinyal arızası yapıyordu
  (2026-09-14 doğrulandı: tekrarlayan `-121 Remote I/O error` / `stream on failed`; imx296 o
  uzatıcının resmi destek listesinde yok). Kullanıcı cam0'a imx477 taktı, cam1 boş, TEK KAMERA
  modu (`camera1_enabled: true`, `camera2_enabled: false`). [⚠️ 2026-09-23: cam1'e de imx477
  takıldı (18 Eylül) — şimdi İKİ imx477.] Yeni düzende I2C/CSI hatası YOK.
  **Güncel gerçek + kronoloji /kalite skill bilgi tabanında:**
  `.claude/skills/kalite/bilgi/{saha_durumu,calisma_gunlugu,program_mimarisi}.md`.
  - **imx477 için TÜM kalibrasyon SIFIRDAN gerekiyor** (farklı sensör/lens/FOV): alignment
    HSV eşikleri, kontrol noktaları, `reference_box`, eşikler, yön referansı. imx296 dönemi
    değerleri geçersiz.
  - **imx477 ROLLING shutter** (imx296 GLOBAL idi) → hareketli bantta eğilme (skew) riski;
    delik yuvarlaklık kontrolü üretim karesinde gözle doğrulanmalı.
  - **GERİ DÖNÜŞ imkânı:** imx296 sağlam — sensör değil, uzatıcı arızalıydı. Orijinal FPC ile
    DOĞRUDAN bağlanır, ya da **Arducam LAN/Ethernet Uzatma Kiti (SKU U6248, Pi sürümü)** ile —
    bu kit imx296/Global Shutter'ı AÇIKÇA destekler (Jetson sürümü U6279 desteklemez). İki
    kamera için iki kit (Pi 5'in iki CSI'si).
- **✅ ZOOM 2.0 → 1.0 + POZ KİLİDİ 400 µs (2026-09-15, "görüntü çok kötü" → düzeltildi):**
  Kullanıcı yakınlaştırmak için `camera.zoom`'u 2.0 yapmıştı → **yazılım zoom'u
  bulanıklaştırdı** (kırp+büyüt, detay üretmez; §8/§12 2026-07-30 ile aynı belgeli tuzak).
  Düzeltme (`config.yaml`, uygulama kapalıyken düzenlenip restart): `zoom 2.0→1.0`,
  `manual_exposure_enabled false→true`, `exposure_us 500→400`. imx477 poz taraması yapıldı
  (gain 16): 400 µs'de metal net + detaylı (havşa görünür), delikler koyu, aşırı parlama yok;
  otomatik poz metali yanık-beyaz veriyordu. 400 µs (0.4 ms) hareketli bant için de yeterince
  kısa. **⚠️ Zoom değişince ROI'ler kaydı: kontrol noktaları zoom 2.0 görüntüsünde çizilmişti,
  zoom 1.0'da FOV daha geniş → NOKTALAR YENİDEN ÇİZİLMELİ** (net görüntüde Ürün Çerçevesi Bul +
  noktalar). Kanıt kareleri: session scratchpad `ex_*.jpg` / `g16_400.jpg`.
- **SAHA AYARI DEĞİŞTİ — İKİ KAMERA AÇIK, TAM ÇÖZÜNÜRLÜK, FPS 20 (2026-08-10, kullanıcı
  GUI'den; `config.yaml`) [⚠️ 2026-09-15'te imx477 tek-kamera düzenine geçildi, üstteki maddeye bak]:**
  | anahtar | eski | **yeni** |
  |---|---|---|
  | `cameras.camera1_enabled` | false | **true** (ikisi de açık) |
  | `resolution` (kamera 1) | 640×480 | **1456×1088** (imx296 native) |
  | `camera.fps` | 52 | **20** |
  | `camera2.fps` | 60 | **20** |
  Kamera 1 artık native çözünürlükte + zoom 1.0 → §8'deki "keskinlik için 1456×1088 +
  zoom yok" önerisiyle uyumlu (yazılım zoom'u detay üretmiyordu).
  **⚠️ ÜÇ AÇIK RİSK — sahada izlenmeli:**
  (1) **`fps 60 → 20` TETİK KAYMASINI GERİ GETİREBİLİR.** 2026-08-03 deneyleri (aşağıda)
  ölçtü: worker'ın SON karesi kullanıldığı için düşük FPS = bayat kare = ürün kaymış kare.
  fps 60'ta kare yaşı ≤16.7 ms, toplam belirsizlik ~37 ms (deney 3: 10/10 temiz, `y`
  yayılımı 114 px). **fps 20'de kare yaşı ≤50 ms → belirsizlik ~70 ms → beklenen `y`
  yayılımı ~2 katı (~230-280 px).** İki kamerayı birden 1456×1088'de sürmek bant
  genişliği/CPU açısından makul bir gerekçe olabilir, ama **kayma yeniden ölçülmeli**
  (`[Kurulum] ürün çerçevesi` / `_handle_snapshot` logları). Kırpılma/tespit çökmesi
  görülürse ilk çevrilecek kol fps'i 40-60'a geri almaktır.
  (2) **KAMERA 1'DE YÖN KONTROLÜ FİİLEN KAPALI:** `roi.handedness_version: 2` (eski base64
  v2 kalıntısı), kod v3 bekliyor → `_check_handedness` sürüm uyuşmazlığında SESSİZCE geçer.
  Kamera 1 kapalıyken zararsızdı, **şimdi açık** → o yüzde ayna/ters parça yakalanmaz.
  Çözüm: Kontrol Noktaları (Kamera 1) → "🧭 Yön Referansı Al" (≥2 hole noktası gerekir;
  kamera 1'de şu an TEK nokta var → önce ikinci nokta çizilmeli).
  (3) **KAMERA 1'İN NOKTASI ESKİ ÇÖZÜNÜRLÜKTE ÇİZİLDİ:** tek nokta `'1'` (hole) +
  `roi.reference_box [201, 212]` 640×480/zoom 2.0 döneminden kalma. ROI'ler ürün kutusuna
  oranlı ölçeklendiği için tamamen bozulmaz ama **gerçek üretim karesinde yeniden
  çizilmesi** doğrusu (§12 "kalibrasyon karesi ≠ üretim karesi" akışı).
  Kamera 2 tarafı değişmedi: 3 nokta (1,2=hole, 3=notch), `roi2.reference_box [971, 726]`,
  yön referansı v3 (`handedness_hole_diff: 48.45`), `point_overrides` 12/10 · 35/2 · 25.
- **⚠️ KALİBRASYON KARESİ ≠ ÜRETİM KARESİ (2026-08-03, saha sorunu — kullanıcı teşhisi):**
  Kontrol noktaları ELLE ayarlanırken kullanıcı ürünü yeşil bariyere dayayıp Wenglor
  sensörü görene kadar İTİYOR, orada DURUYOR ve kare o anda alınıyor. Otomatikte ise
  bant HAREKETLİ: "sensör gördü → ışık aç → çek → ışık kapat" süresince ürün YOL ALIYOR
  → iki kare ÖRTÜŞMÜYOR, ROI'ler kaymış oluyor. **Üç fark birden var** (yalnız konum değil):
  (1) **konum** (ürün ilerlemiş), (2) **aydınlatma** (tetiklemeli ışık; elle ayarda sahne
  farklı okuyor — ekran görüntüsünde otomatik kare belirgin daha parlak/doygun, delik
  `koyu%` düşüp yanlış NOK veriyor), (3) **operatörün ELİ karede** (elle ayarda parçayı
  tutuyor; el `find_product_box`'ın HSV metal maskesini bozup ÜRÜN ÇERÇEVESİNİ kaydırabilir
  → ROI'ler ürüne göreli olduğu için hepsi kayar). **ÇÖZÜM: ayar GERÇEK üretim karesi
  üzerinden yapılmalı.**
- **✅ "NOKTA YOKKEN DE KARE SAKLA" EKLENDİ (2026-08-03) — yukarıdaki sorunun çözümü:**
  `_capture_full_frame`'de **sıra değişti**: kare ÖNCE alınır, `_production_ready_error`
  SONRA bakılır. Eskiden hazırlık kontrolü kare ALINMADAN dönüyordu → "noktaları sil,
  otomatikte çalıştır, gerçek kareyi yakala" akışı İMKANSIZDI. Artık nokta çizilmemişken
  de tetikle gelen kare `_store_setup_snapshot` ile saklanır (hizalama uygulanır, ekranda
  gösterilir, **analiz YAPILMAZ**) ve **"Kontrol Noktaları" editörü o kareyle açılır**
  (`_open_roi_manager` zaten `_last_snapshot`/`_last_snapshot_2`'yi kullanır). PLC'ye yine
  ERROR yazılır → üretim güvenliği bozulmaz. Log: `[Kurulum] Tetikle gelen GERÇEK üretim
  karesi saklandı`. **SAHA AKIŞI:** noktaları sil → otomatikte birkaç ürün geçir →
  "Kontrol Noktaları" → gerçek üretim karesi üzerinde çiz → Kaydet.
  **NOT:** noktalar VARKEN de aynı şey geçerliydi (editör her zaman son tetik karesini
  kullanır); yeni davranış SIFIRDAN kurulumu mümkün kılar. 9 ekransız testle doğrulandı
  (nokta yokken kare saklanır + ERROR; nokta varken analiz bozulmaz; bayat kare ERROR;
  ürün çerçevesi bulunamazsa çökmez).
- **⚠️ ASIL ŞÜPHELİ: ÜRÜN ÇERÇEVESİ KARARSIZ (2026-08-03, kullanıcı sezgisi doğrulandı —
  "ürünü bulup gerisini siliyor ya, ondan olmasın"):** Kontrol noktaları kareye değil
  **bulunan ürün kutusuna GÖRELİ** saklanır ve kutu boyutuyla **ÖLÇEKLENİR**
  (`_roi_bounds`: `sx = kutu_w/reference_box_w`, `x*=sx, w*=sx`). Kutu tetikten tetiğe
  oynarsa **TÜM noktalar birden kayar + büyür/küçülür**. Sahada `reference_box` bir gün
  içinde `[967,699] → [951,697] → [955,701] → [945,718]` gezindi (≈%3). `sx=0.977,
  sy=1.027` → kutu köşesinden 400 px aşağıdaki nokta **11 px**, 600 px sağdaki **14 px**
  kayar; küçük delik ROI'sinde bu delik kenarını dışarıda bırakıp `koyu%`'ü düşürür →
  **yanlış NOK**. Yani hareket kaymasından bağımsız, İKİNCİ ve muhtemelen daha büyük bir
  hata kaynağı var.
  **ÖLÇÜM İÇİN:** `_store_setup_snapshot` artık nokta çizilmemiş kurulum turunda da
  `[Kurulum] ürün çerçevesi: x=,y=,w=,h= | referansa göre en %±X boy %±Y` yazar →
  10-15 üründe yayılım okunabilir. (Nokta VARKEN zaten `_handle_snapshot` logluyordu.)
  **İKİ ÇÖZÜM YOLU:** (a) kutuyu kararlı hale getir (ışık/yansıma/parçanın kadraja tam
  sığması); (b) `alignment.mode: off` → ROI'ler TAM KAREDE mutlak olur, kutu oynaması
  kararı hiç etkilemez; tetik fiziksel olarak tekrarlanabilir olduğundan (Wenglor sabit
  nokta + sabit `trigger_delay_ms`) bu, kontur hizalamadan DAHA kararlı olabilir.
  Hangisinin daha az yayılım verdiği ÖLÇÜLMELİ — varsayma.
- **✅ ÖLÇÜLDÜ — KAYMANIN ASIL SEBEBİ TETİK GECİKMESİ (2026-08-03, 16 PLC tetiği):**
  Doğru ürün 16 kez geçirildi, `[Kurulum] ürün çerçevesi` logları çözümlendi:
  | | sonuç |
  |---|---|
  | temiz tespit | **11/16 (%69)** |
  | ürün kare DIŞINA taşmış (kutu kırpık) | 2/16 |
  | tespit tamamen çökmüş (kutu ≈ kare) | 3/16 |
  **Kutu BOYUTU aslında kararlı:** `w` yayılımı %1.4, `h` %3.1 → ROI ölçekleme hatası
  küçük, ASIL sorun bu DEĞİL. **Asıl sorun ürünün bant yönündeki konumu:** `y` = 0…584 px
  (temizlerde 55…364). Ürün boyu ~715 px, kare 1088 px → ürün ancak **y ≤ 373** iken tam
  sığıyor; geç tetiklerde ALTTAN TAŞIYOR (`y=470 h=618`, `y=584 h=504` → kutu kırpılıyor,
  ROI'ler yanlış ölçekleniyor). Tespitin çöktüğü 3 kare de ürünün kadrajı terk ettiği
  anlarda (kalan parlak yüzey/ray "ürün" sanılıyor).
  **SEBEP — İKİSİ DE YAZILIM, İKİSİ DE DÜZELTİLEBİLİR:**
  (1) **`plc.poll_ms: 100`** → HR101 yükselen kenarı **100 ms'ye kadar geç** fark ediliyor
  (§4 tasarımı 20 ms'ydi, config sahada 100'e kaymış);
  (2) **`camera2.fps: 20`** → çekimde worker'ın SON karesi kullanılır, o kare **50 ms'ye
  kadar bayat** olabilir. Toplam belirsizlik **150 ms**.
  Ölçülen 584 px / 150 ms ≈ **her 1 ms gecikme ≈ 4 px kayma**.
  **DÜZELTME:** `poll_ms 100 → 20` + `fps 20 → 60` (imx296 tavanı 60.4) → belirsizlik
  150 ms → ~37 ms, yani **~4× daha az kayma** (beklenen yayılım ~145 px). CPU/ısı sorun
  olursa 40 fps de yeterli.
  **UYGULANDI (2026-08-03):** `plc.poll_ms: 100 → 20`, `camera2.fps: 20 → 60`.
  Deney 2 (8 geçerli tetik) ayarlar UYGULANMADAN tekrarlandı ve deney 1'i doğruladı:
  `y` yayılımı 309 → 290 px, `w` 14 → 11 px (%1.1). Ölçüm tekrarlanabilir, teşhis
  sağlam. Ayarlar sonrası beklenen `y` yayılımı ~70-90 px.
  **✅ DOĞRULANDI — DENEY 3 (2026-08-03, ayarlar uygulandıktan sonra 10 PLC tetiği):**
  | | deney 1 | deney 2 | **deney 3** |
  |---|---|---|---|
  | temiz tespit | 11/16 (%69) | 6/8 (%75) | **10/10 (%100)** |
  | `y` yayılımı | 309 px | 290 px | **114 px** |
  | `w` yayılımı | 14 px (%1.4) | 11 px (%1.1) | **4 px (%0.4)** |
  | `h` yayılımı | — | 37 px (%5.2) | **28 px (%3.9)** |
  Kırpılma YOK, tespit çökmesi YOK. Deney 1-2'deki sistematik `y` sürüklenmesi
  (397→277 sonra 107) de KAYBOLDU → sebebi fiziksel değil, tetik gecikmesiymiş.
  Kalan 114 px, 37 ms'lik artık gecikme bütçesiyle (37×4≈148 px) tutarlı.
  **Kalan tek pürüz:** `h` %3.9 oynuyor (`w` %0.4). Kutu boyu ölçekleme yaptığı için
  (`sy`) kutunun altına düşen ROI'lerde ~15 px kayma demek. Kritik olup olmadığı
  ROI çizildikten sonra `koyu%` yayılımından anlaşılacak — geometri değil, KARARA
  giren ölçüm izlenmeli.
  **⚠️ ÖNCEKİ NOTUN DÜZELTMESİ:** "tetikle çalışan sistemde yüksek FPS gereksiz" (fps 10
  önerisi) KONUM DOĞRULUĞU açısından YANLIŞTI — düşük FPS doğrudan bayat kare = kayma
  demek. Poz süresi için fps önemsiz, ama TETİK ANI için kritik.
- **🐞 ONDALIK AYIRAÇ HATASI DÜZELTİLDİ (2026-08-03, kullanıcı: "derinlik değerlerini
  değiştiremiyorum"):** Sistem yereli **`tr_TR`**, ondalık ayıraç **','**. Kullanıcı `0.5`
  yazınca Qt noktayı reddetmiyor, **SESSİZCE ATIYOR** → değer **5.0**; `1.5` → **15.0**.
  Yani yanlış giriş fark edilmeden eşiği **10 KATINA** çıkarıyordu (derinlik eşiği 15 olsa
  HER sağlam parça NOK olurdu — sessiz ve tehlikeli). Tam sayı girilen `açıklık`/`oluk`
  kutuları etkilenmediği için sorun yalnız ondalık girilen `derinlik`te fark edildi.
  **Düzeltme:** `NoWheelDoubleSpinBox.validate/valueFromText` metinsel ayıracı yerelinkine
  çevirir → `0.5` de `0,5` de 0.5 verir. Aynı düzeltme `roi_editor.py`'deki nokta ayar
  kutusuna da uygulandı. 9 testle doğrulandı (nokta/virgül, tam sayı, tekerlek koruması).
- **SAHA EŞİKLERİ PANELDEN AYARLANMAYA BAŞLADI (2026-08-03):** Kontrol Merkezi
  kutularıyla girilen ilk saha değerleri (`roi2.point_overrides`):
  `1: hole_dark_ratio_min 12.0, hole_core_ratio_min 10.0` /
  `2: hole_dark_ratio_min 35.0, hole_core_ratio_min 2.0` / `3: notch_dark_min 25.0`.
  **⚠️ NOKTA 1'İN DERİNLİK EŞİĞİ 10.0 ŞÜPHELİ:** ondalık ayıraç hatası düzeltilmeden
  ÖNCE girildi; kullanıcı `1.0` yazmış olsa Qt noktayı atıp **10.0** yapardı (bkz.
  yukarıdaki 🐞 madde). Nokta 1 havşalı delik, doğru parçada koyu% ~%13.9 okuyor →
  çekirdek% bunun çok altında olmalı, yani 10.0 eşiği sağlam parçayı NOK'lar.
  Sahada teyit edilip düzeltilmeli.
  Üç noktanın da eşiği artık NOKTA BAŞINA (global `roi` değerleri 10/2/50 devrede değil).
  **DİKKAT — bunlar tek doğru parçanın ölçümüne göre elle konmuş, HATALI PARÇA verisi
  YOK:** payların yeterli olup olmadığı bilinmiyor. 4 hatalı parça geçirilip "kötü" taraf
  ölçülmeli, eşikler iki grubun ortasına oturtulmalı (§12 "Yapılacak").
  Nokta 1 doğru parçada ~%9.4-13.9 okuyordu → 13.5 SINIRDA, öncelikli izlenecek.
- **RESİMDEKİ ROI ETİKETLERİ KISALTILDI (2026-08-03, kullanıcı isteği):**
  `_draw_roi_result` eskiden kutunun üstüne `1: OK [delik VAR (acik %13.9, yuvarlak 0.88,
  dolgu 0.96)]` yazıyordu; etiket kutuları örtüp resmi okunmaz yapıyordu. Artık yalnız
  **`1: OK` / `2: NOK`** (punto 0.5→0.8, kalınlık 1→2 — kısaldığı için büyütüldü).
  Ayrıntılar zaten "Kontrol Merkezi" tablosunda ve loglarda. **Numara KORUNDU** ki resimdeki
  kutu tablodaki satırla eşleştirilebilsin. `msg` parametresi imzada duruyor (çağıranlar
  değişmesin) ama ÇİZİLMİYOR — `results[...]['msg']` aynen dolu, tablo/log onu kullanır.
- **✅ SONUÇ PANELİ + CANLI EŞİK SLIDER'I (2026-08-03, kullanıcı isteği):** Canlı görüntünün
  üstündeki band tek QLabel'di ve YALNIZ başarısız noktaları yazıyordu. Yerine
  **`ROIResultPanel`**: her kontrol noktası için bir satır —
  Başlığı **"Kontrol Merkezi"** (QGroupBox), satırlar **QGridLayout** ile hizalı ve aralarında
  ayırıcı çizgi → tablo görünümü. Satır:
  `ad | OK/NOK rozeti | <ölçüm> %X  "en az" [N %]  (delikte İKİ tane) | sebep`.
  **DELİKTE İKİ EŞİK VAR** (kullanıcı: "ölçülen %35.9, eşik %30, yine de hata"):
  `açıklık` (`hole_dark_ratio_min` ← `black_ratio`) **ve** `derinlik`
  (`hole_core_ratio_min` ← `core_ratio`). Panel eskiden yalnız açıklığı gösterdiği için
  derinlikten kalan nokta sebepsiz NOK görünüyordu; artık ikisi de gösterilir ve ikisi de
  buradan ayarlanır. Çentikte tek eşik (`oluk`). **`≥`/`<` sembolleri KALDIRILDI**
  (kullanıcı: "kafa karıştırıyor, 'en az' yeterli"). **'YON' satırında eşik sütunları HİÇ
  oluşturulmaz**, sonuç yazısı rozetin yanından başlar (boş sütunların sağına itilmesin).
  **YÖN AÇIKÇA GÖSTERİLİR (kullanıcı karışıklığı):** "eşik 12" yazınca 12'nin üstü mü altı mı
  geçerli belli değildi. İKİ EŞİK DE ALT SINIR — `ölçülen ≥ eşik` olmalı. Panel bunu hem
  **sembolle** (geçiyorsa yeşil `≥`, kalıyorsa kırmızı `<`) hem **"en az"** yazısıyla söyler.
  Nokta alt sınırı GEÇTİĞİ HALDE NOK ise (şekil/derinlik/üst sınır) satır sonunda SEBEP yazar —
  kullanıcı boşuna eşikle boğuşmasın. Eşik girişi **slider DEĞİL yazılabilir kutu**
  (`NoWheelSpinBox`, `keyboardTracking(False)` → her karakterde değil Enter/odak çıkışında bir
  kez sinyal; ok tuşları için 400 ms gecikme). Değer değişince
  `_on_panel_threshold_changed` o noktanın eşiğini `roi(2).point_overrides`'a yazar,
  config'i kaydeder, log'a `[Eşik]` satırı düşer ve **son kare yeniden değerlendirilir**
  (`_handle_snapshot(0,…)` = önizleme, PLC'ye YAZILMAZ) → ölç-gör-ayarla döngüsü tek ekranda.
  Eşik anahtarı tipe göre: `hole → hole_dark_ratio_min`, `notch → notch_dark_min`,
  `yon → eşik yok` (`_point_threshold`; önce nokta override'ı, yoksa global değer).
  **TUZAK:** panel yenilenirken kutu `blockSignals(True)` ile doldurulur — yoksa
  programatik güncelleme config'e geri yazar (sonsuz döngü). Testte korunuyor.
- **✅ FARE TEKERLEĞİ AYAR DEĞİŞTİRMİYOR (2026-08-03, kullanıcı isteği):** `NoWheelMixin`
  (+ `NoWheelSlider/SpinBox/DoubleSpinBox/ComboBox`) `wheelEvent`'te **`event.ignore()`**
  yapar. **NEDEN `ignore()`, `accept()` DEĞİL:** olayı yutmak sayfayı da kaydırmaz;
  yok saymak üst widget'a bırakır → kaydırılabilir Ayarlar penceresi normal kayar, yalnız
  DEĞER değişmez. Uygulandığı yerler: sonuç paneli eşik slider'ları, Ayarlar'daki PLC
  tip/port/unit/poll, çekim gecikmesi, kamera çözünürlük/FPS/zoom/exposure/gain, ROI
  editöründeki nokta ayar spinbox'ı. Değer değiştirme: tıkla-sürükle ya da klavye.
- **ÖNİZLEME ANALİZİ ARTIK LOGLANIYOR (2026-08-03):** "Kontrol Noktaları" kaydedilince
  `_handle_snapshot(0, ...)` ile son kare üzerinde önizleme analizi çalışır; eskiden
  `if part_id > 0` yüzünden HİÇ loglanmıyordu → ekranda "3: NOK (oluk YOK)" yazıyor ama
  ölçülen `koyu%`/`blob` hiçbir yerde görünmüyordu, eşik ayarlamak için ürün geçirmek
  şarttı. Artık `[Önizleme] son kare -> NOK (PLC'ye YAZILMAZ)` + tüm ölçümler loglanır →
  **kaydet-bak-ayarla döngüsü ürün geçirmeden yapılabiliyor.** 4 testle doğrulandı.
- **LOGLAR ARTIK DİSKE DE YAZILIYOR (2026-08-03):** `_append_log` her satırı
  `~/konveyor_loglari/denetim-YYYY-AA-GG.log` dosyasına da ekler (saat damgalı,
  çok satırlı loglar girintili). **NEDEN:** ekrandaki kutu uygulama kapanınca
  kaybolur; 15 tetiklik bir saha ölçümünü elle kopyalamak zahmetli ve hataya açık —
  dosya olunca ölçüm doğrudan okunabiliyor. Klasör PROJE DIŞI (repoya sızmaz).
  Yazma hatası arayüzü ASLA bozmaz: bir kez denenir, olmazsa `_log_file_broken`
  ile sessizce vazgeçilir. SD aşınması ihmal edilebilir (satır ~100 bayt; oysa
  config.yaml her UI etkileşiminde ~148 KB yeniden yazılıyor, §9).
- **⚠️ HAREKET BULANIKLIĞI — POZ SÜRESİ (2026-07-30, saha teşhisi):** Kullanıcı "görüntü
  bulanık" dedi; **konveyör DURURKEN netlik 500, ÇEKİM anında düşüyor** → sorun odak ya da
  zoom DEĞİL, **hareket bulanıklığı**. **Global shutter uzun pozdaki bulanıklığı ÖNLEMEZ**
  (yalnız rolling-shutter eğilmesini önler); bulanıklık doğrudan POZ SÜRESİYLE orantılıdır.
  **Ölçüldü (Pi, gerçek kamera):** `manual_exposure_enabled: false` → oto-pozlama parlaklık
  için pozu **16.6-19.2 ms**'ye kadar uzatıyor (gain 15.7). Bu, hareketli bantta 10-40 piksel
  bulanıklık demektir (0.071 mm/px'te 100 mm/s → 14 px @10 ms).
  **ÇÖZÜM:** Ayarlar → ilgili kamera → **"Exposure/Gain Kilidi" İŞARETLE** + `Exposure us`
  düşür (hareketli bantta hedef **≤1 ms**); karardıysa ışığı artır / Analog Gain yükselt.
  **TUZAK:** `exposure_us` config'te yazılı olsa bile `manual_exposure_enabled: false` iken
  UYGULANMAZ (kutu işaretli değilse oto-pozlama çalışır) — kullanıcı 200 µs yazmıştı ama
  kutu kapalı olduğu için etkisizdi.
  **YENİ GÖSTERGELER (sol panel "Sistem Durumu"):** **Poz** = kameranın FİİLEN kullandığı
  poz süresi + gain (`worker._read_exposure_metadata`, picamera2 metadata, 1 Hz);
  renk: ≤1 ms yeşil, 1-3 ms sarı, >3 ms kırmızı. Ayrıca **Netlik** (odak) göstergesi
  yüzde + renk gösterir (≥%90 yeşil). İkisi birlikte "odak mı, hareket mi" ayrımını
  saha personelinin tek bakışta yapmasını sağlar.
  **EXPOSURE/GAIN ARALIĞI DÜZELTİLDİ (2026-07-30, kullanıcı: "exposure 200'den aşağı
  inmiyor"):** `SettingsDialog._build_camera_group`'ta spinbox `min=100, adım=100` idi →
  hareketli bantta gereken **kısa pozlara (~50-150 µs) İNİLEMİYORDU**. **Pi'de gerçek
  kamerayla ölçülen sensör limitleri (imx296 @1456×1088):**
  `ExposureTime = (min 29 µs, max 15.5 s)`, `AnalogueGain = (1.0 … 251.2)`,
  `FrameDurationLimits min 16562 µs`. İstenen↔gerçek poz doğrulandı (29→29, 100→88,
  200→192, 1000→992 µs). **Yeni aralık:** exposure `20…1000000`, adım **50 µs**
  (sensör 29'un altını zaten kırpar); gain `1.0…64.0`, adım 0.5 (251 sensör tavanı ama
  üstü aşırı gürültü). İkisine de **açıklayıcı tooltip** eklendi (poz = ışık toplama
  süresi, uzun=bulanık; gain = elektronik yükseltme, ışık EKLEMEZ → gürültü artar).
  **NEDEN önemli:** poz süresi bulanıklığın TEK gerçek kolu; gain ve ışık onu kısaltmanın
  bedelini öder. Fiziksel sıra: **poz kısalt → gain yükselt → yetmezse AYDINLATMA artır**
  (ya da tetikle senkron strobe / çekimde bandı yavaşlat).
- **⚠️ ANALOG GAIN TAVANI GERÇEKTE 15.7 — ÜSTÜ SESSİZCE DİJİTAL KAZANÇ (2026-07-30, Pi'de
  gerçek kamerayla ölçüldü):** `libcamera` `camera_controls`'ta `AnalogueGain` aralığını
  **(1.0, 251.2)** diye bildirir ama bu YANILTICIDIR. Gain 26/43/64 istendi → metadata'da
  **analog HEP 15.7**, kalanı `DigitalGain` (sırasıyla 1.70 / 2.78 / 8.02) olarak eklendi.
  Dijital kazanç sinyalle birlikte gürültüyü de çarpar, **bilgi EKLEMEZ**: 29 µs +
  dijital 8.0'da görüntü grileşti, metal dokusu kayboldu (gözle teyit edildi).
  Bu yüzden gain spinbox tavanı **bilinçli olarak 16.0**'da (kısa süre 64'e çıkarılmıştı,
  ölçüm üzerine geri alındı). Testte kalıcı regresyon koruması var.
- **AYDINLATMA AÇIKKEN ÖLÇÜLEN ÇALIŞMA ARALIĞI (2026-07-30, gain 16, dijital kazanç yok,
  kamera 0 konveyöre bakarken):**
  | poz | metal gri | delik ROI koyu% | durum |
  |---|---|---|---|
  | 200 µs | 119 | %53.6 | çalışır (sınırda) |
  | **300 µs** | **148** | **%45.8** | **sağlam** |
  | **500 µs** | **186** | **%41.9** | **sağlam — önerilen** |
  | 1000 µs | 232 | %34.2 | sağlam |
  | 2000 µs | 251 | %31.2 | doyguna yakın |
  | 4000 µs | 254 | **%0.6** | ✗ DOYGUN — delik KAYBOLUR |
  **İKİ YÖNLÜ TUZAK:** az poz kadar **FAZLA poz da** öldürür — 4000 µs'de metal doyup
  (254) delik bölgesi de eşiğin üstüne çıkıyor, `koyu%` %31'den %0.6'ya düşüyor → delik
  "yok" sanılır. Poz ayarlarken `koyu%` log değerine bak, sadece parlaklığa değil.
- **AYDINLATMA DC — TİTREME YOK (2026-07-30, kullanıcı DC'ye çevirdi, ölçümle teyit):**
  500 µs'de 25 ardışık karede metal parlaklığı ortalama 221.1, sapma **0.21 (%0.10)**.
  PWM/AC aydınlatmada kısa poz LED döngüsünün rastgele anına denk gelip kare kare
  parlaklık oynatır (eşikler kayar, sebepsiz NOK) — burada o risk YOK.
  Işık bütçesi (`poz × gain`) aydınlatma açılınca **298.000 → 13.030** düştü (23× ışık).
- **✅ POZ/GAIN SABİTLENDİ (2026-07-30, kullanıcı: "ışık sabit, exposure ve gaini
  sabitleyelim... odak ve ışığı manuel yapıyorum zaten"):** Aydınlatma DC ve sabit
  olduğundan oto-pozlamaya gerek yok — config'te **her iki kamera da kilitlendi**
  (`manual_exposure_enabled: true`):
  | | poz | gain | metal gri | not |
  |---|---|---|---|---|
  | **Kamera 1** (cam0) | **500 µs** | 16.0 | 186 | delik ROI koyu %41.9 |
  | **Kamera 2** (cam1) | **1000 µs** | 16.0 | 154 | aynı pozda daha loş (500 µs'de metal 102 = 70 eşiğine yakın) |
  **NEDEN farklı:** cam1 aynı parçanın **havşalı yüzünü** eğik açıdan görüyor; ışık
  bütçesi benzer (11.349 vs 13.030) ama yüzey daha az ışık geri döndürüyor. Kamera 2'nin
  diyaframı açılırsa 500 µs'ye inilebilir (hareket payı iki katına çıkar).
  **DİKKAT — İKİ YÖNLÜ:** kamera 2'de 2000 µs'de metal 200'e çıkıyor ama havşa konisi
  parlayıp delik `koyu%`'ü %3.9'a düşüyor → poz ARTIRMAK da deliği kaybettirir.
- **SAHA AYARI: YALNIZ KAMERA 2 (2026-07-30) — ⚠️ ARTIK GEÇERSİZ, 2026-08-10'da ikisi de
  açıldı (bkz. §12 başındaki madde); tarihçe için duruyor:**
  `camera1_enabled: false` / `camera2_enabled: true`. Kamera 2 = parçanın **havşalı yüzü**;
  3 kontrol noktası çizili (1=hole, 2=hole, 3=notch), `reference_box [951, 697]`.
  `roi2.point_overrides`: `'3'.notch_dark_min: 40` (eski global 50 dar paylıydı — oluklu parça
  ~%50 okuyordu) + `'1'.hole_dark_ratio_min: 15` (global 10'un üstünde, o delik için sıkılaştırma).
  `camera2.fps: 10` (60'tan düşürüldü — tetikle çalışan sistemde yüksek FPS gereksiz, CPU/ısı
  kazancı; poz süresi 500 µs olduğu için 10 fps hâlâ fazlasıyla yeterli).
  Kullanıcı kamera 2 pozunu **1000 → 500 µs**
  çekti; §12 ölçümünde 500 µs'de metal 102 (eşik 70) çıkmıştı — **diyafram açılmadıysa pay
  dar**, sahada `koyu%` loglarıyla izlenmeli. Kamera 1'de tek nokta + eski v2 yön kalıntısı var.
- **POZ GÖSTERGESİNE KİLİT DURUMU EKLENDİ (2026-07-30):** "Poz" satırı artık
  `K1 0.5 ms (gain 16.0) 🔒` ya da `K2 19.2 ms (gain 15.7) ⚠ OTO` yazar
  (`_camera_exposure_locked`, kamera 2 anahtarı yoksa kamera 1'den devralır — worker ile
  aynı mantık). **NEDEN:** `manual_exposure_enabled: false` iken config'teki
  `exposure_us`/`analogue_gain` SESSİZCE uygulanmaz; kullanıcı 200 µs yazmıştı ama kutu
  kapalı olduğu için kamera 19 ms kullanıyordu (bulanıklığın asıl sebebi buydu). Kilit
  kapalıysa değer ne olursa olsun etiket **SARI** (yeşile hiç dönmez) — oto-pozlama her an
  pozu uzatabileceği için "şu an 0.5 ms" güvence değildir. 7 ekransız testle doğrulandı.
- **NETLİK (ODAK) GÖSTERGESİ EKLENDİ (2026-07-30):** Sol paneldeki "Sistem Durumu"nda
  **Netlik** satırı — kamera başına anlık + o kamerada görülen en iyi değer
  (`_update_focus_metric`, merkez 480×360 native pencerede Laplacian varyansı, ~4 Hz).
  **Kullanım:** lens odak halkasını yavaşça çevir, sayı TEPE yaptığı yerde bırak.
  Kamera yeniden açılınca "en iyi" sıfırlanır. **TUZAK:** metrik gürültüyü de sayar →
  yalnız AYNI kamerada ve ışık/exposure SABİTKEN kıyaslanır; mutlak "iyi" değeri yoktur.
  (Sahada denendi: Pi ISP'nin `NoiseReductionMode: Off` + `Sharpness` ayarları Laplacian'ı
  %1400 artırıyor gibi görünüyor AMA gözle bakınca bu **detay değil GÜRÜLTÜ** — karanlık
  sahnede yanıltıcı; ISP ayarlarına DOKUNULMADI.)
- **✅ İKİNCİ KAMERA (İKİ YÜZ DENETİMİ) UYGULANDI (2026-07-30) — ayrıntı §13.** Tek PLC
  tetiğinde iki kamera da çeker, iki analiz **VE**'lenir, PLC'ye TEK sonuç yazılır.
  Arayüz: kameralar **ALT ALTA** (her kamera bir satır + kendi "Kontrol Noktaları"/"Ürün
  Çerçevesi Bul" butonları); "⚙ Ayarlar" tek pencerede (PLC + Kamera 1 + Kamera 2 +
  her kamera için "kullan" kutusu). `features.py`/`alignment.py`'ye HİÇ dokunulmadı
  (`_camera_config_view` remap'i). **HER İKİ KAMERA DA BAĞIMSIZ AÇILIR/KAPANIR**
  (`cameras.camera1_enabled`/`camera2_enabled`) — yalnız Kamera 2 ile de çalışır.
  **Sahaya etkisi YOK:** varsayılan yalnız Kamera 1 açık → program birebir eskisi gibi;
  ekransız 37 test + Pi'de gerçek iki imx296 ile doğrulandı (hem çift kamera hem
  "yalnız kamera 2" senaryosu ekran görüntüsüyle teyit edildi). **Yapılacak (saha):** Ayarlar'dan 2. kamerayı aç → "Ürün Çerçevesi Bul
  (Kamera 2)" → "Kontrol Noktaları (Kamera 2)" ile o yüzün noktalarını çiz (çizilmezse
  her tetikte ERROR verir — bilinçli koruma).
- **KALİBRASYON MODU KALDIRILDI + "⚙ AYARLAR" PENCERESİ (2026-07-10, kullanıcı isteği:
  "kalibrasyon ve kamera analiz kısımlarını kaldıralım... ayarlar diye buton ekleyelim"):**
  (1) Sol paneldeki "Kalibrasyon" ve "Kamera & Analiz" grupları SİLİNDİ; solda yalnız
  "Sistem Durumu" + "Çalışma Modu" (Elle Çekim Modu kutusu + ipucu) kaldı. (2) Sağda
  "Kontrol Noktaları"nın altına **"⚙ Ayarlar"** butonu: `SettingsDialog` (PLC tipi/IP/port/
  unit/poll + çözünürlük/FPS/zoom/exposure-gain + çekim gecikmesi) — "Kaydet"te
  `_apply_settings` yalnız DEĞİŞEN tarafı uygular: kamera parametresi değiştiyse tek
  `change_camera_controls()` restart'ı (worker `_open_camera` config'ten yeniden okur),
  zoom değişimi restartsız `set_zoom`, PLC değiştiyse adapter+poll yenileme; çözünürlük/zoom
  değişince snapshot+referans geçersizlenir. Listede olmayan özel çözünürlük combo'ya
  eklenir (sessizce değişmez). (3) Kalibrasyon durum makinesi KOMPLE silindi
  (`_calibration_mode`, `_set_calibration_mode`, `_toggle_calibration`,
  `_save_calibration_and_lock`, `lbl_calibration`, `btn_calibration_toggle`,
  `lbl_detection_mode`, 6 eski ayar-değişti handler'ı): ayarlar hep erişilebilir, kilit yok —
  Kontrol Noktaları kaydedilince sistem hazır. Yerine tek bayrak **`_dialog_paused`**:
  Ayarlar/Kontrol Noktaları penceresi açıkken `_poll_plc`/`_delayed_capture` tetik işlemez.
  Kalibrasyona bağlı dallanmalar Elle Çekim Moduna bağlandı (`_manual_capture` yalnız manual
  modda; `_handle_error`/kamera-yok uyarı popup'ı manual modda; üretim-hazır kontrolü artık
  her çekimde). Ekransız 6'lı test + 11 regresyon testi geçti. (1) KALDIRILAN
  sol panel öğeleri: "Kalibrasyon Resmi Al/Tam Resim Al" çekim butonu (elle çekim artık yalnız
  BOŞLUK/ENTER ya da canlı görüntüye tık), elle-test ipucu, "OK Referans Ekle" (template
  öğretme UI'ı tamamen gitti; template yöntemi artık yalnız eski config referanslarıyla çalışır),
  "Referansı Sıfırla", 3 eşik slider'ı (ROI Toleransı / Oluk Eşiği / Delik Açıklık Eşiği).
  Silinen metotlar: `_add_ok_reference`, `_reset_reference_profile`, `_show_reference_preview`,
  `_update_capture_button_text`, 3 slider handler'ı. (2) **"Referansı Sıfırla" editöre taşındı**
  (`reset_reference_requested` → kabulde main temizler). (3) **Eşikler NOKTA BAŞINA:** editörde
  noktaya sağ tık → **"⚙ Ayarlar…"** (tek seçimde; menü artık Ayarlar+Sil) → **delikte İKİ eşik:**
  "Delik Açıklık Eşiği" (`hole_dark_ratio_min`) + **"Derinlik Eşiği"** (`hole_core_ratio_min`,
  çekirdek koyu%; kullanıcı sorusu üzerine eklendi — "ROI Toleransı" ise template'e ait olduğundan
  bilinçli KONMADI); çentikte "Oluk Eşiği". Alanlar `ROIDialog.POINT_SETTINGS`'te tanımlı;
  genel değere eşit girilen değer override yazılmaz. `roi.point_overrides` `{ad: {anahtar: değer}}`
  olarak "Kaydet ve Kapat"ta yazılır; `_evaluate_holes` noktanın override'ını, yoksa global değeri
  kullanır. Listede `[eşik %X, derinlik %Y]` görünür; nokta silinince override'ı da düşer.
  Ekransız 11 testle doğrulandı (açıklık/derinlik/oluk override'ları kararı değiştiriyor).
- **PaDiM/ONNX MODU PROJEDEN KOMPLE KALDIRILDI (2026-07-09, kullanıcı kararı: "işe
  yaramadı"):** silinenler — `inspector/padim_inference.py`, `PADIM_COLAB_PROMPT.md`,
  main.py'deki tüm PaDiM UI/metotları (model yükleme, özellik seçici, performans paneli,
  veri toplama, sonuç yapıştırma, ısı haritası), `StartModeDialog` (tek mod kaldı → açılışta
  doğrudan ROI ekranı), onnxruntime ön-yükleme bloğu, psutil kullanımı, config `analysis.*`
  + `padim.*` bölümleri, requirements'tan onnxruntime/psutil, gitignore PaDiM satırları.
  `MainWindow()` artık parametresiz. Geri gerekirse git geçmişi (93eb536 öncesi).
  Not: `C:/Users/Salik/Downloads/` altındaki .onnx/.npz dosyaları proje dışı — istenirse elle silinir.
- **⚠️ CONFIG SAHADAN GÜNCELLENDİ (commit a103055, 29.06) — CLAUDE.md'nin eski "geliştirme
  config'i" uyarıları ARTIK GEÇERSİZ.** Commit'li config şimdi SAHA durumu: `manual_mode: false`,
  `plc.type: modbus_tcp` (`unit_id: 0`, poll 100ms, timeout 0.2s),
  kamera 640×480@52fps, zoom 2.0, trigger_delay 10ms. **DÜZELTME (2026-07-29, Pi'de
  `plc_smoke_test.py` ile doğrulandı):** config'teki `plc.port: 496` YANLIŞTI (TCP connection
  refused → uygulama PLC'ye HİÇ bağlanamıyordu) → **502'ye çekildi** (gerçek PLC 502'yi dinliyor;
  496 kapalı). `unit_id: 0` ise 0 ve 1 ile de HR101 okundu → 0 doğru, dokunulmadı. **DÜZELTME:
  exposure "kilitli" DEĞİL:** config `manual_exposure_enabled: false` + gain 1.6 (1.7 değil) →
  `worker._camera_controls` boş sözlük döner, kamera OTO EXPOSURE çalışır (eski "2000µs/1.7 kilitli"
  notu yanlıştı). Bu Pi sistem python3 kullanıyor (pymodbus 3.13 + picamera2 sistemde), `veri_toplama`
  venv'i YOK → `calistir.sh`'daki venv yolu bu makinede geçersiz; sistem python'la çalıştırılıyor.
  Eşikler sahada slider'la ayarlanmış: `hole_dark_ratio_min: 10` (doküman önerisi ~20 idi),
  `notch_dark_min: 50` (öneri ~35 idi; oluklu parça ~%53 okuduğundan 50 dar paylı — izlenmeli).
- **✅ YÖN/EL KONTROLÜ AKTİF — KAMERA 2'DE v3 REFERANSI ALINDI (2026-07-30, sahada
  kullanıcı):** `roi2.handedness_version: 3`, `handedness_hole_diff: 45.886`,
  `handedness_margin_diff: 12.0`, `handedness_check: true` → **ayna/ters parça artık
  yakalanır** (uzun süredir bekleyen madde kapandı). Ölçüm değeri POZİTİF (+45.9): havşalı
  delik SAĞ tarafta okunuyor; ters/ayna parçada işaret negatife döner ve |fark| > 12 ise NOK.
  **⚠️ KAMERA 1'DE HÂLÂ ESKİ v2 KALINTISI VAR** (`roi.handedness_version: 2`, base64
  `handedness_reference`, `handedness_margin: 0.05`) — kod v3 beklediğinden
  `_check_handedness` sürüm uyuşmazlığında SESSİZCE geçer. Kamera 1 şu an KAPALI
  (`camera1_enabled: false`) olduğu için zararsız; **yeniden açılırsa o kamerada da
  "Yön Referansı Al" yapılmalı.** v2 kalıntıları (~1.4 KB base64) elle silinebilir.
- **reference_profile yeniden doldu (count 5):** sahada "OK Referans Ekle" kullanılmış; 3 ROI ×
  5 base64 referans → config.yaml ~148KB. `hole` yöntemi bunları OKUMAZ (zararsız), ama dosyayı
  şişiriyor; "Referansı Sıfırla" ile temizlenebilir. (`hole_use_circle_check` da ölü anahtar.)
- **"KONTROL NOKTASI" TERMİNOLOJİSİ + YÖN TİPİ (2026-07-09, kullanıcı isteği — evrensel
  program hedefi):** (1) Ana buton "ROI Çiz" → **"Kontrol Noktaları"**; editör butonu
  **"＋ Yeni Kontrol Noktası"** → menü: **Delik (daire) / Çentik (kutu) / Yön Tayini**.
  (2) **Yeni `yon` tipi** (`roi_types`): kusur kontrolüne girmez (`_evaluate_holes` atlar,
  `_production_ready_error` saymaz), yalnız yön ölçümünde kullanılır; editörde TURUNCU kutu.
  Yön ölçümü artık ÖNCE yön noktalarından (≥2), yoksa deliklerden (geriye uyum) —
  `_hole_centers_brightness` önceliklendirir; `roi_point_type` public API. Sentetik uçtan uca
  doğrulandı (7 test: öncelik, ayna→NOK, kusur döngüsünden hariç, geriye uyum, editör menü).
  (3) **"Yön Referansı Al" akışı — SON KARAR (kullanıcı, 3. iterasyon): Kontrol Noktaları
  MENÜSÜNDE, "Yön Tayini" çizim tipi UI'DAN SİLİNDİ** ("onu sonradan uydurdun"). Ana penceredeki
  buton + `_capture_handedness_reference` kaldırıldı. Menü: Delik / Çentik / (ayıraç) /
  "🧭 Yön Referansı Al (doğru parça)" — editördeki güncel noktalarla (2 delik) açık görüntüden
  ölçer (`_take_handedness_reference`), "Kaydet ve Kapat"ta config'e yazılır. NOT: features.py'de
  'yon' tipi desteği GERİYE-UYUM için duruyor (eski config'te yon noktası varsa kusur döngüsüne
  girmez, yön ölçümünde önceliklidir) — sadece UI'dan çizilemez.
- **"Kareyi Diske Kaydet" butonu KALDIRILDI (2026-07-09):** `_save_frame_to_disk` silindi
  (yön geliştirmesi için gerçek kare toplama amacına hizmet etmişti; iş bitti, kullanıcı
  istemedi). `~/Masaüstü/kareler/` klasörü ve toplanan kareler diskte durur, koddan bağımsız.
- **YÖN/EL kontrolü YENİDEN YAZILDI — gerçek karelerle çözüldü** (`HANDEDNESS_VERSION=3`, §5):
  Eski 96×96 tüm-parça gri NCC sahada ayna parçayı ayıramıyordu — gerçek ayna karelerinde
  `normal~0.64 / ayna~0.61` (kaydedilen kareler `~/Masaüstü/kareler`'den ölçüldü). Yeni yöntem:
  **iki delik ROI'sinin parlaklık farkı (sağ−sol); havşalı/kademeli delik daha koyu → farkın
  İŞARETİ yön/eli verir.** Gerçek karelerde doğru~−26 / ayna~+56 (grup-içi ±0.1, 80+ puan
  zıt-işaret). Uçtan uca offline doğrulandı: ref=A→A OK & B NOK; ref=B→tersi (kusursuz).
  `_check_handedness`/`hole_handedness_diff`. Config: `handedness_hole_diff` + `handedness_margin_diff`
  (~12). **DİKKAT: yöntem değişti → eski v2 referans geçersiz; sahada doğru parçayla yeniden
  "Yön Referansı Al" gerekir** (≥2 hole ROI). Kaldırılan ölü kod: `handedness_signature`/`_ncc`/
  `encode_handedness_reference` ve eski `handedness_reference`/`handedness_margin` anahtarları.
- Aktif yöntem: ROI + `hole`. **Delik** ROI'leri açık-alan (koyu%) + şekil ile, **çentik**
  ROI'leri koyu% bandı + **şekil kapısı** ile kontrol edilir (bkz. §5). Eşikler config'te; saha ile ayarlanır.
- **ÇENTİK ŞEKİL KAPISI EKLENDİ** (§5, `_notch_shape`): saha gözlemi — oluksuz DÜZ parça
  ROI 3'te koyu ~%17 okuyup eski eşik %10 ile yanlış "oluk VAR" OK veriyordu. Düzeltme iki
  yönlü: (1) "Oluk Eşiği"ni ~%35'e çek (iyi %53.5 / düz %17.5 arası; **slider, sahada**),
  (2) gerçek oluk = TEK/BÜYÜK/YATAY-UZUN koyu yarık şekil kapısı (`notch_min_blob_ratio` ~25,
  `notch_min_aspect` ~1.2, `notch_min_width_ratio` ~0.30). Sentetik uçtan uca doğrulandı:
  oluk VAR→OK (blob%46), bant-geçen-dağışık-düz→NOK (blob%0.3). **Gerçek parçayla saha
  teyidi bekliyor** (log'daki `blob %X` ile `notch_min_blob_ratio` ayarlanır). TUZAK: OPEN
  önce, CLOSE sonra (yalnız CLOSE dağışık koyu'yu tek bloba birleştirir).
- **Tıkanma/kısmen-bant tespiti DÜZELTİLDİ** (§5): önce `core_fill` (<40 tabanlı "tamlık")
  denendi ama saha gerçeği **açık delikler GRİ** (~40-70) → açık deliği yanlış NOK'ladı.
  Kaldırıldı. Doğru ayrım **AÇIK ALAN (koyu%)**: tam açık ~%22-28, kısmen bantlı ~%9-15.
  `hole_dark_ratio_min` (~%20, saha) asıl kapı + `fill` şekil kapısı. Gerçek görüntüde uçtan
  uca doğrulandı: bantlı→NOK (açık %9), iyi→OK (açık %22, dolgu 0.95). Slider: **"Delik Açıklık Eşiği"**.
- **YÖN/EL kontrolü eklendi** (§5): simetrik (ayna) parça → NOK. **GRİ imza + NCC** (ikili
  silüet bu parçada simetrik çıkıp ayıramadı — kademe/havşa silüette yok; gri tonlamada var).
  Gerçek ayna parçayla doğrulandı: doğru-NCC ~0.8-1.0, ayna-NCC ~0.4 (pay ~0.4). "Yön Referansı
  Al" butonu. **DİKKAT: yöntem değişti → eski referans geçersiz, yeniden "Yön Referansı Al"
  gerekir** (sürümleme ile eski otomatik atlanır). Saha: doğru parçayla referans al + gerçek ayna parçayla teyit.
- **`find_product_box` düzeltildi** (§6): HSV metal izolasyonu + union ile **tam braket**
  izole ediliyor (eskiden yeşil rayları/arka planı da alıp çerçeveyi tüm kareye genişletiyordu).
- **ROI editörü UX yeniden yazıldı (2026-07-09, kullanıcı isteği):** (1) tek **"＋ Yeni ROI
  Çiz"** menü-butonu → Delik (daire) / Çentik (kutu) seç → **çizim modu silahlanır** (fare ile
  TEK çizim; yanlışlıkla sürükleyip ROI oluşturma bitti). (2) **Çizim modundayken mevcut
  ROI'ler GİZLENİR** (temiz tuval; çizim bitince/iptalde geri gelir — kalıcı gizlenmez ki
  üst üste çizim olmasın). İptal: **ESC ya da sağ tık** (ESC diyaloğu kapatmaz, `keyPressEvent`
  override). (3) **Silme: listede ya da resimdeki ROI'de sağ tık → Sil** (`roi_right_clicked`
  sinyali + `CustomContextMenu`); "Seçileni Sil" butonu da durur. (4) KALDIRILDI: "Yeniden
  Adlandır", "Kopyala", "Aktif/Pasif" butonları (`_rename_roi`/`_duplicate_roi`/`_toggle_roi`
  silindi; `disabled_rois` veri yapısı korunur — eski pasif ROI'ler çalışmaya devam eder,
  sadece arayüzden değiştirilemez). (5) **Çoklu silme:** listede `ExtendedSelection` —
  Ctrl/Shift ile birden çok nokta seçilip **"Sil" butonu / Delete tuşu / sağ tık** ile tek
  seferde silinir (buton adı "Seçileni Sil" → **"Sil"**; sağ tık menüsü çoklu seçimde
  "Seçilen N noktayı Sil" der). Ekransız duman testleriyle doğrulandı.
- Eski not: editörde tip seçici + otomatik sıra-rakam isim; tipler `config.roi.roi_types`'a yazılır.
- Kamera **imx296 (Global Shutter)**, HQ değil. Aktif config: 2 delik (1,2) + 1 çentik (3).
- ~~`reference_profile` config'te temizlendi~~ **GÜNCELLEME:** sahada yeniden dolduruldu
  (count 5, bkz. yukarıdaki ⚠️ madde); `hole` yöntemi referans gerektirmediğinden karara etkisiz.
- **Yapılacak:** SAHADA v3 "Yön Referansı Al" (yukarıdaki ⚠️: yön kontrolü şu an devre dışı);
  ROI `hole` saha testi (OK/NOK + oluk-eksik parçayla band ayarı; `notch_dark_min: 50` dar
  paylı — izle); ~~`plc.unit_id` gerçek PLC değeri doğrula~~ **YAPILDI (2026-07-29): port 502 +
  unit_id 0 doğrulandı, port 496→502 düzeltildi;** koddaki kullanılmayan `reference_profile` template
  blokları sadeleştirilebilir; doğrulanmış PLC/durum-makinesi düzeltmeleri (latch/reconnect
  tetik/ERROR yapışkan) saha testi bekliyor; `PROGRAM_KULLANIM_NOTLARI.md` §8 hâlâ template
  akışını anlatıyor (aktif yöntem `hole`) — sadeleştirilebilir.
- **PLANLANIYOR — İKİNCİ KAMERA (iki yüz denetimi): §13'e bak.** Tasarım kararları alındı
  (2026-07-12), KOD YAZILMADI. Pi'de uygulanacak (kameralar orada takılı).

## 14. YENİ Pi'YE TAŞIMA (donanım aynı, yalnız Pi değişiyor)
Saha senaryosu: PLC, kameralar, aydınlatma, optik AYNI kalıyor; sadece Raspberry Pi 5
değiştiriliyor. Bu makinede ölçülen gerçek durum (2026-08-10):

> ## ⚡ TEK KOMUT — `bash tools/yeni_pi_kur.sh`
> Aşağıdaki her şeyi otomatik yapan/denetleyen betik var (2026-08-10, kullanıcı isteği:
> "ayarlar diye bir dosya yapsak... ikiz gibi olmuş olur"):
> ```bash
> bash tools/yeni_pi_kur.sh --kontrol   # HİÇBİR ŞEY DEĞİŞTİRMEZ, 6 maddelik fark raporu
> bash tools/yeni_pi_kur.sh             # eksikleri kurar (her adımda onay sorar)
> ```
> Değerleri proje kökündeki **`saha_ayarlari.conf`**'tan okur (Pi statik IP, PLC IP/port,
> beklenen kamera sayısı/sensörü, ajan adı). Denetlediği 6 madde: python kütüphaneleri,
> kameralar, statik IP, PLC erişimi + `config.yaml` ↔ conf tutarlılığı, uygulama ayarları,
> uzaktan kontrol ajanı. Sahadaki Pi'de **6/6 tamam** raporu verdiği doğrulandı.
> **İŞ BÖLÜMÜ:** `config.yaml` = UYGULAMA ayarları (git taşır) · `saha_ayarlari.conf` +
> betik = MAKİNE ayarları (git taşıyamaz, betik kurar).
> Betik kişisel yol GÖMMEZ (`$HOME`/`$USER` kullanır) → farklı kullanıcı adında da çalışır;
> `--kontrol` modu hiçbir şeyi değiştirmez, mevcut Pi'de de güvenle çalıştırılabilir.

**⚠️ ÜÇ GERÇEK ÇAKIŞMA RİSKİ**
1. **İKİ Pi AYNI ANDA ASLA ÇALIŞMASIN.** İkisi de HR101'i okur, ikisi de **HR100'e yazar**
   → PLC çelişkili OK/NOK alır (son yazan kazanır). Emniyet açığı. Yeni Pi'yi takmadan
   önce eskisini KAPAT (ya da ağdan çıkar).
2. **Sabit IP çakışması:** `eth0` **`192.168.10.50/24` MANUEL (statik)** — PLC 192.168.10.10.
   Yeni Pi'ye aynı adresi ver; iki makine birden .50 olursa ağ çakışır. (Pi Modbus
   İSTEMCİSİ olduğu için adresin .50 olması şart değil, ama PLC tarafında filtre varsa
   aynısı en güvenlisi.)
   **İKİ IP, İKİ AYRI YER — karıştırma:** *PLC'nin* adresi `config.yaml`'da (git ile
   TAŞINIR), *Pi'nin kendi* adresi NetworkManager profilinde
   (`/etc/NetworkManager/system-connections/`, repoda DEĞİL → elle kurulacak):
   ```bash
   nmcli -t -f NAME,DEVICE con show | grep eth0        # profil adini bul
   sudo nmcli con mod "<ad>" ipv4.method manual ipv4.addresses 192.168.10.50/24
   sudo nmcli con up "<ad>"
   ```
   **⚠️ eth0'a GATEWAY VERME** — bu makinede bilerek boş; internet `wlan0`'dan geliyor,
   eth0'a gateway yazılırsa internet PLC ağına yönlenip kopar.
   Doğrulama: `ip -4 -br addr | grep eth0` + `ping -c2 192.168.10.10`.
3. **KAMERA PORTLARI TERS TAKILIRSA HER ŞEY BOZULUR.** `cam0 = i2c@88000`,
   `cam1 = i2c@80000` (Pi 5'in iki CSI soketi). Kamera 1 ↔ Kamera 2 yer değiştirirse
   `dynamic_rois`/`roi` ile `dynamic_rois_2`/`roi2` yanlış kameraya uygulanır → tüm
   noktalar, eşikler ve yön referansı geçersiz. **Kabloları aynı soketlere tak.**
   Doğrulama: `rpicam-hello --list-cameras` + programda **Kamera 2 havşalı yüzü**
   görmeli (§12).

**GIT'LE OTOMATİK TAŞINAN (yeniden kalibrasyon GEREKMEZ):** `config.yaml` — kontrol
noktaları, nokta başına eşikler, poz/gain kilidi, yön referansı (v3), PLC ayarları,
`reference_box` — ve tüm kod. Kameralar/optik/ışık değişmediği sürece ayar aynen geçerli.

**GIT'E GİRMEYEN — YENİ Pi'DE ELLE YAPILACAK:**
- Sistem paketleri: `bash tools/kurulum_pi.sh` (apt: python3-picamera2, python3-pyqt5,
  libgl1 + venv + requirements + menü ikonu). **Bu makinede venv YOK**, sistem
  python'u kullanılıyor (Debian 13'te picamera2/PyQt5/pymodbus apt'tan geliyor) —
  `calistir.sh` artık ikisini de destekler (venv varsa venv, yoksa sistem python'u;
  kütüphane eksikse anlaşılır hata verir).
- Uzaktan kontrol ajanı: `~/.config/systemd/user/claude-agent-konveor.service`
  (+ `loginctl enable-linger`). Kişisel makine ayarı olduğu için repoda DEĞİL.
- `.claude/` (hook'lar, settings) — `.gitignore`'da, taşınmaz.
- `~/.local/bin/claude` sarmalayıcı betiği.
- **Kullanıcı adı `enes` / ana dizin `/home/enes`:** systemd unit'i ve hook'lar MUTLAK
  yol kullanır; yeni Pi'de kullanıcı adı farklıysa bu yollar güncellenmeli.
- Loglar (`~/konveyor_loglari/`) — taşınmasa da olur, yeniden oluşur.

**SIRA:** eski Pi'yi kapat → yeni Pi'ye Debian 13 + `git clone` → `tools/kurulum_pi.sh`
→ eth0'a statik `192.168.10.50/24` → kameraları AYNI soketlere tak → `./calistir.sh`
→ canlı görüntüde kamera eşleşmesini doğrula → PLC'ye tek ürün geçirip HR100'ü izle.

## 13. İKİNCİ KAMERA (İKİ YÜZ DENETİMİ) — ✅ UYGULANDI (2026-07-30)
> **Durum:** **KOD YAZILDI ve Pi'de GERÇEK 2 KAMERAYLA DOĞRULANDI (2026-07-30).**
> Ekransız 26 test geçti (tek-kamera regresyonu + VE mantığının 4 durumu + config görünümü
> + worker anahtar seçimi); ardından uygulama izole test config'iyle çalıştırıldı: cam0 ve
> cam1 (iki imx296) **aynı anda** açıldı, arayüzde iki canlı görüntü + iki snapshot paneli
> göründü (`[Kamera 1] Picamera2 açıldı (cam0)` / `[Kamera 2] ... (cam1)`, 640×480@52fps).
> **ARAYÜZ KARARI (uygulanan):** kameralar **ALT ALTA** — her kamera bir SATIR
> (solda canlı görüntü + üstünde sonuç bandı, sağda son çekim + o kameranın butonları),
> en altta tam-genişlik log. Değiştirmek kolay: `_build_camera_row` + `content_layout`.
>
> **HER İKİ KAMERA DA BAĞIMSIZ AÇILIP KAPANIR (2026-07-30, kullanıcı isteği: "biri sabit
> diğeri seçenekli değil, 2'si de seçenekli olmalı"):** `cameras.camera1_enabled` /
> `cameras.camera2_enabled` (bool). Ayarlar'da her kamera grubunun BAŞLIĞINDAKİ kutu =
> o kamerayı kullan/kullanma (`QGroupBox.setCheckable`); kapalı kameranın worker'ı HİÇ
> açılmaz ve satırı gizlenir. **Yalnız Kamera 2 ile çalışmak geçerli bir kurulumdur**
> (Pi'de gerçek donanımda doğrulandı: sadece cam1 açıldı, tek satır göründü).
> **Emniyet:** ikisi birden kapatılamaz — Ayarlar `accept()`'te uyarır, `_active_cameras()`
> hepsi kapalıysa kamera 1'e düşer. Eski `cameras.enabled_count` (1|2) config'leri
> `_camera_enabled` içinde geriye-uyumlu okunur; yeni bayraklar yazılırken o anahtar silinir.
>
> **SAHA İÇİN AÇMA SIRASI (config'te varsayılan: yalnız Kamera 1 açık — bilinçli):**
> (1) ⚙ Ayarlar → **"Kamera 2 (kullan)"** kutusunu işaretle + çözünürlük/fps/zoom/exposure →
> Kaydet (uygulama yeniden başlatmadan 2. worker'ı başlatır, satırı gösterir).
> (2) Kamera 2 satırında **"Ürün Çerçevesi Bul (Kamera 2)"** → (3) **"Kontrol Noktaları (Kamera 2)"**
> ile o yüzün delik/çentiklerini çiz → Kaydet ve Kapat.
> **DİKKAT:** Kamera 2 etkinken noktası ÇİZİLMEZSE `_production_ready_error` her tetikte
> ERROR verir (o yüz denetlenmemiş sayılır) — önce noktaları çiz, sonra üretime al.

**Amaç / senaryo (kullanıcı kararı):** Raspberry Pi 5'in İKİ CSI girişine (cam0/cam1) iki adet
Global Shutter (imx296, ~1.3MP) kamera. İki kamera **AYNI parçanın farklı yüzünü/açısını**
denetler (ör. biri üstten, diğeri alttan/yandan). **İkisi de OK ise parça OK**; biri NOK ise
parça NOK.

**Tetik modeli (kullanıcı kararı):** **TEK PLC tetiği** (HR101 0→1) → AYNI anda İKİ kamera da
parçayı çeker (ikisi de aynı `trigger_delay_ms` sonrası) → iki analiz **VE**'lenir → **TEK**
sonuç HR100'e yazılır. Ayrı tetik/register YOK. PLC katmanı (§7) DEĞİŞMEZ — tek sonuç yazılır.

**Tasarım ilkesi — REGRESYON YOK:** İkinci kamera **OPSİYONEL** (`cameras.enabled_count: 1|2`,
varsayılan **1**). count=1 iken program BİREBİR bugünküyle aynı çalışır (sahadaki tek-kameralı
sistem bozulmaz). Kamera 2, fiziksel takılıp **Ayarlar**'dan etkinleştirilene kadar pasif.

**Config yapısı (geriye uyumlu, PARALEL anahtarlar):**
- Kamera 1 → MEVCUT anahtarlar `camera`, `resolution`, `dynamic_rois`, `disabled_rois`,
  `roi.*` — **HİÇ DEĞİŞMEZ**.
- Kamera 2 → YENİ paralel anahtarlar: `camera2`, `resolution2`, `dynamic_rois_2`,
  `disabled_rois_2`, `roi2.*` (her kameranın kendi çözünürlük / exposure-gain / zoom / fps /
  ROI'leri / eşikleri / `reference_box` / yön referansı — **iki yüz farklı ışık ister, şart**).
- `cameras.enabled_count` (1|2) yeni. `config.yaml` yazımında `setdefault` kullan (§9 kuralı).

**ÇEKİRDEK İLKE — `features.py` / `alignment.py`'ye DOKUNMA:** `evaluate_with_profile` zaten
`config["dynamic_rois"]` + `config["roi"]` + `config["disabled_rois"]` okur. Kamera 2 için,
kamera-KAPSAMLI bir config GÖRÜNÜMÜ üret ve AYNI fonksiyona ver:
```python
cfg2 = {**config,
        "dynamic_rois": config.get("dynamic_rois_2", {}),
        "disabled_rois": config.get("disabled_rois_2", []),
        "roi": config.get("roi2", {})}
ok2, res2, disp2 = evaluate_with_profile(frame2, cfg2)
```
Böylece analiz motoru + hizalama + yön/el kontrolü hepsi **DEĞİŞMEDEN** iki kez çalışır.
(Aynı görünüm hilesi `_prepare_roi_analysis_frame` / `find_product_box` için de kullanılır:
kamera 2'nin alignment ayarları da `roi2`/`camera2` altından okunacak şekilde config remap'le.)

**UYGULANAN KOD (2026-07-30) — nerede ne var:**
1. **Worker (iki akış) — `inspector/worker.py`:** `InspectionWorker(config, cam_index=0|1)`.
   `_cam_key`/`_res_key` ile cam0 → `camera`/`resolution` (AYNEN), cam1 → `camera2`/`resolution2`.
   **`_cam_cfg()`/`_res_cfg()`: kamera 2'de YAZILMAMIŞ anahtar kamera 1'den devralınır**
   (yeni kamerada her ayarı baştan girmek gerekmesin). picamera2'de `Picamera2(cam_index)`,
   OpenCV yedeğinde `opencv_index` (varsayılan = cam_index). Loglar `[Kamera N]` etiketli.
   **count=1 iken 2. worker HİÇ oluşturulmaz.**
2. **Çekim & birleştirme — `main.py::_capture_full_frame`:** `_active_cameras()` üzerinden her
   kameranın son karesini alır (`_get_latest_camera_frame(cam_no)`, bayatlık kontrolü kamera
   başına), her birini `_handle_snapshot(id, frame, cam_no)` ile KENDİ config görünümüyle
   analiz eder, `is_ok = ok1 AND ok2` (**kısa-devre YOK** — operatör iki yüzü de görsün diye
   ikisi de analiz edilir), **TEK** `_publish_plc_result`. Biri kare veremezse → ERROR.
   `_production_ready_error` artık HER etkin kamerada aktif nokta arar.
3. **Config görünümü — `main.py::_camera_config_view(cam_no)`:** §13 çekirdek ilkesi;
   `features.py`/`alignment.py`'ye HİÇ dokunulmadı. Kamera 1'de `self.config`'in KENDİSİ döner
   (sıfır kopya/regresyon). Kamera 2'de `dynamic_rois_2`/`disabled_rois_2`/`roi2`/`camera2`/
   `resolution2`/`alignment2` remap edilir. **TUZAK:** eşikler kamera 1'den devralınır AMA
   nokta KİMLİĞİNE bağlı anahtarlar (`roi_types`, `point_overrides`, `reference_box`,
   `handedness_*`) `roi2`'de yoksa DEVRALINMAZ (silinir) — yoksa kamera 2 kamera 1'in
   noktalarını/yön referansını kullanır. Yön referansı yoksa `_check_handedness` sürüm
   uyuşmazlığında zaten sessizce geçer (güvenli).
4. **Arayüz — `main.py::_build_camera_row(cam_no)`:** her kamera bir SATIR (ALT ALTA).
   Kamera 1 widget'ları ESKİ adlarını korur (`video_label`, `lbl_snapshot`, ...), kamera 2
   `_2` ekli paralel adlarla (`video_label_2`, ...). Kamera seçimi ayrı diyalog DEĞİL:
   her satırda o kameranın **"Kontrol Noktaları (Kamera 2)"** / **"Ürün Çerçevesi Bul (Kamera 2)"**
   butonları var. **"⚙ Ayarlar" TEK ve SOL PANELİN DİBİNDE** (kamera satırında DEĞİL —
   satır gizlenince erişilemez olurdu): içinde PLC + Kamera 1 + Kamera 2 grupları
   (her grubun başlığındaki kutu o kamerayı açar/kapar); içerik kaydırılabilir, butonlar sabit.
   `_apply_settings` kutu değişince o kameranın worker'ını canlı başlatır/durdurur
   (`_start_camera(n)`/`_stop_camera(n)`; **SIRA: önce TÜM kapatmalar + wait, sonra açmalar** —
   2026-09-23 libcamera yarışı düzeltmesi) ve satırını gösterir/gizler — **uygulama yeniden
   başlatmaya gerek yok**. FPS etiketi tek olduğu için ilk AÇIK kameranın değerini gösterir
   (`_update_fps_for`; kamera 1 kapalıysa kamera 2'ninkini).
   `_open_roi_manager(cam_no)` kamera 2'nin noktalarını `dynamic_rois_2`/`roi2`'ye yazar.
5. **Doğrulama (yapıldı):** ekransız 26 test — tek-kamera regresyonu (2. worker HİÇ yok,
   config görünümü config'in KENDİSİ, OK/NOK doğru), VE mantığının 4 durumu, kamera 2 kare
   veremezse ERROR, config görünümü kimlik-anahtarı sızdırmıyor, worker anahtar seçimi.
   Ardından Pi'de gerçek iki imx296 ile uygulama açıldı (izole test config'i, PLC'ye
   dokunulmadan): iki canlı görüntü + iki snapshot paneli + `[Kamera 1/2] Picamera2 açıldı`.
   **TUZAK (test yazarken):** `main.load_config`'un varsayılan argümanı tanım anında
   sabitlenir → `CONFIG_PATH` yaması onu ETKİLEMEZ, `load_config`'un kendisini yamala.
   Ekransız testte `QMessageBox.warning/critical` modal olduğu için BLOKLAR → sustur.

**AÇIK KARAR — KARARA BAĞLANDI (2026-07-30):** İki görüntü **ALT ALTA** (her kamera bir satır).

**Pi test komutları:** kameraları listele `libcamera-hello --list-cameras` (cam0/cam1
görünmeli); picamera2 çoklu örnek `Picamera2(0)` / `Picamera2(1)`. İki imx296 aynı anda
Pi 5'te desteklenir; 640×480 civarı çözünürlükte bant genişliği sorun değil.
