# Program Mimarisi — Konveyör Kalite Kontrol (otomatik üretildi: 2026-09-14)

Bu doküman, konveyör bant kalite kontrol denetim sisteminin modül modül çıkarılmış
dokümantasyonunun birleştirilmiş, tek mimari referansıdır. Satır numaraları,
dokümantasyonun çıkarıldığı andaki kaynak dosyalara aittir. Çelişki görülen yerler
"⚡ ÇELİŞKİ" etiketiyle iki taraflı not edilmiştir.

---

## 1. Genel Bakış ve Uçtan Uca Akış

**Proje:** Konveyör bandında akan **alüminyum braketlerin** otomatik görsel kalite
kontrolü. Asıl hedef: parçadaki **2 deliğin açılmış (delinmiş) olup olmadığını**
kontrol etmek. Donanım: Raspberry Pi 5 + imx296 Global Shutter kamera(lar) (HQ değil),
kubbe difüzör aydınlatma, iki yeşil LED kılavuz ray, Modbus TCP PLC, sinyal kulesi, HMI.
Kamera sabit, ürün tekrarlanabilir konumda gelir. Dil kuralı: arayüz ve yorumlar Türkçe,
kod tanımlayıcıları İngilizce.

### Uçtan uca üretim akışı

```
Wenglor reflektör sensörü ürünü görür → PLC'ye bildirir
  → PLC HR101 register'ını 0→1 yapar (TETİK)
  → main.py: GUI thread'indeki QTimer (_poll_plc, poll_ms aralıklı) yükselen kenarı görür
  → inspection.trigger_delay_ms kadar bekler (_delayed_capture — ürün ortalansın)
  → _capture_full_frame: HER etkin kameranın worker'ından son ham kareyi alır
       (_get_latest_camera_frame → worker.last_raw_frame kopyası; bayatlık kontrolü
        camera.max_frame_age_ms — bayat kare = kaymış ürün riski)
       [SIRA KRİTİK: kare ÖNCE alınır, _production_ready_error SONRA bakılır —
        nokta yoksa kare _store_setup_snapshot ile saklanır, analiz YAPILMAZ,
        PLC'ye ERROR yazılır → gerçek üretim karesi üzerinde nokta çizimi mümkün]
  → her kare _handle_snapshot(part_id, frame, cam_no):
       ├─ _camera_config_view(cam_no)   (kamera 2 için roi2→roi remap görünümü)
       ├─ alignment.find_product_box     (HSV metal maskesi → ürünü kırp, mode: contour)
       ├─ features.evaluate_with_profile (ROI'ler reference_box'a oranlı ölçeklenir;
       │    delik: koyu% bandı + şekil kapısı; çentik: koyu% + şekil kapısı;
       │    yön/el: iki nokta parlaklık asimetrisi → ayna parça NOK)
       └─ _display_snapshot + ROIResultPanel ("Kontrol Merkezi") + loglar
  → is_ok = VE(tüm kameralar)   (kısa devre YOK — operatör iki yüzü de görsün)
  → _publish_plc_result: HR100'e TEK sonuç yazılır (0 = OK, 1 = NOK/hata)
  → ~1 sn sonra QTimer ile HR100 = 0'a resetlenir (ACK okuması YOK)
```

Hata/hazır-değil/bayat kare yolları `publish_error` ile PLC'ye yine **HR100 = 1** yazar
(emniyet: denetlenemeyen parça asla OK geçmez).

### İki kamera modeli (uygulandı 2026-07-30)

- İki kamera **aynı parçanın farklı yüzünü** denetler (kamera 2 = havşalı yüz).
- **TEK PLC tetiği** → iki kamera da aynı `trigger_delay_ms` sonrası çeker → iki analiz
  **VE**'lenir → HR100'e **TEK** sonuç. PLC katmanı değişmedi.
- Çekirdek ilke: `features.py`/`alignment.py`'ye **hiç dokunulmadı** — kamera 2 için
  `main.py::_camera_config_view` config'i remap eder (`dynamic_rois_2`, `disabled_rois_2`,
  `roi2`, `camera2`, `resolution2`, ops. `alignment2` → standart adlar). Kamera 1'de
  görünüm config'in KENDİSİDİR (sıfır kopya/regresyon).
- Her kamera bağımsız açılır/kapanır (`cameras.camera1_enabled/camera2_enabled`);
  ikisi birden kapatılamaz (üç katmanlı emniyet).

---

## 2. Dosya Haritası

```
main.py                 (1987 satır) PyQt5 GUI + tüm orkestrasyon (MainWindow +
                        SettingsDialog + ROIResultPanel). Kamera worker'ları, PLC
                        timer'ı, üretim durum makinesi, loglama, koyu tema, excepthook.
config.yaml             Tek kalıcı UYGULAMA konfigürasyonu (GUI okur/yazar; git taşır).
inspector/worker.py     (289 satır) InspectionWorker(config, cam_index) — kamera QThread'i;
                        cam0='camera', cam1='camera2'. picamera2 ana, OpenCV yedek.
inspector/plc.py        (296 satır) NullPLCAdapter + ModbusTCPPLCAdapter + create_plc_adapter.
                        HR101 tetik / HR100 sonuç el sıkışması.
inspector/features.py   (642 satır) ROI analiz motoru: 'hole' (varsayılan) + 'template'
                        (eski) + yön/el kontrolü (HANDEDNESS_VERSION=3).
inspector/alignment.py  (161 satır) find_product_box: HSV metal izolasyonu ile tam braketi
                        bulup kırpar; Otsu yedeği.
inspector/roi_editor.py (703 satır) Kontrol noktası editörü (ROILabel + ROIDialog):
                        çizim/taşıma/silme, nokta başına eşik, yön referansı.
saha_ayarlari.conf      MAKİNE (Pi OS) seviyesi saha değerleri (statik IP, PLC IP/port,
                        beklenen kamera sayısı/sensörü, ajan adı). Tek tüketici:
                        tools/yeni_pi_kur.sh.
calistir.sh             Pi başlatıcı (venv varsa venv, yoksa sistem python + import denetimi).
calistir.bat            Windows başlatıcı (daima venv, pythonw, start "").
tools/kurulum_pi.sh     Pi tam kurulum: apt + venv (--system-site-packages) + pip + ikon.
tools/install_pi.sh     Menü/masaüstü ikonu (.desktop) kurulumu.
tools/yeni_pi_kur.sh    Yeni Pi'yi İKİZ yapar / --kontrol ile 6 maddelik salt-okunur denetim.
tools/plc_smoke_test.py Bağımsız Modbus TCP PLC testi (uygulamasız).
tools/make_icon.py      app.ico / app.png üretici (Pillow; runtime bağımlılığı değil).
requirements.txt        pip bağımlılıkları; GEREKLI_KUTUPHANELER.txt insan-okur karşılığı.
CLAUDE.md               AI ajanı/geliştirici bağlam dosyası (doğruluk kaynağı).
PROGRAM_KULLANIM_NOTLARI.md  Operatör kılavuzu (büyük ölçüde ESKİ arayüzü anlatır — bkz. §6).
~/konveyor_loglari/     Günlük denetim log dosyaları (proje DIŞI, repoya sızmaz).
veri_toplama/           venv (git'e dahil değil; sahadaki mevcut Pi'de venv YOK).
```

---

## 3. Modül Dokümantasyonu

### 3.1 `main.py` — Ana GUI + Orkestrasyon (2105 satır, 2026-09-23)

Tek giriş noktası ve orkestrasyon katmanı; analiz `features.py`'de, hizalama
`alignment.py`'de, kamera IO `worker.py`'de, PLC `plc.py`'de — main.py bunları
**değiştirmeden** birbirine bağlar. Başlangıçta `OMP_NUM_THREADS=1` /
`MKL_NUM_THREADS=1` set edilir (satır 5-7, Pi'de CPU tasarrufu).
`CONFIG_PATH = "config.yaml"` (satır 25) — **göreli yol**; uygulama proje kökünden
çalıştırılmalı (`calistir.sh` bunu sağlar).

#### Yardımcı widget sınıfları (satır 28-73)

- **`NoWheelMixin` (28):** `wheelEvent` (38) **`event.ignore()`** çağırır — tekerlek
  DEĞERİ değiştirmez ama olay üst widget'a gider, kaydırılabilir sayfa normal kayar.
  (`accept()` olsaydı sayfa da kaymazdı.) Türevleri: `NoWheelSlider` (42),
  `NoWheelSpinBox` (46), `NoWheelComboBox` (72).
- **`NoWheelDoubleSpinBox` (50):** ondalık ayıraç düzeltmesi. tr_TR yerelinde Qt `0.5`
  girişindeki noktayı SESSİZCE atıp değeri `5.0` yapıyordu (eşik 10 katına çıkıyordu).
  `_ayirac_duzelt` (60), `validate` (65), `valueFromText` (68) metni yerel ayıraca çevirir.

#### `ROIResultPanel` (satır 76-274) — "Kontrol Merkezi"

Canlı görüntünün üstündeki sonuç tablosu; her kontrol noktası bir satır:
`ad | OK/NOK rozeti | ölçüm + "en az" + eşik kutusu (1-2 adet) | sebep`.

- `THRESHOLDS` (94): `hole → [(hole_dark_ratio_min,"açıklık",black_ratio,20.0),
  (hole_core_ratio_min,"derinlik",core_ratio,2.0)]`; `notch → [(notch_dark_min,"oluk",
  black_ratio,50.0)]`. **Delikte İKİ eşik var** (açıklık + derinlik). `MAX_ESIK = 2` (99).
- `threshold_changed = pyqtSignal(str, str, float)` (101) → `_on_panel_threshold_changed`.
- Metotlar: `__init__` (103, grid kurulum), `_set_header` (124, PARÇA OK/NOK başlığı),
  `_make_row` (133 — 'YON' satırında eşik sütunları HİÇ oluşturulmaz; spinbox
  `keyboardTracking(False)` + ok tuşları için 400 ms tek atımlı QTimer debounce),
  `_add_separator` (192), `_emit_change` (199), `_clear` (204),
  `update_results` (213 — dışa dönük API).
- **TUZAK (253-256):** spinbox programatik doldurulurken `blockSignals(True)` şart —
  yoksa güncelleme config'e geri yazar (sonsuz döngü; testte korunuyor).
- Tüm eşikler **ALT SINIRDIR** (ölçülen ≥ eşik); `≥`/`<` sembolleri kaldırıldı, "en az"
  yazısı kullanılır. Alt sınırı geçtiği hâlde NOK olan noktada satır sonunda SEBEP yazar.

#### Modül seviyesi

- `load_config(path=CONFIG_PATH)` (277). **Test tuzağı:** varsayılan argüman tanım anında
  sabitlenir → `CONFIG_PATH` yaması etkisiz, `load_config`'un kendisi yamalanmalı.
- `STYLESHEET` (281-393): koyu (grafit) tema; buton vurguları `accent` property'siyle.

#### `SettingsDialog` (satır 395-622) — "⚙ Ayarlar"

Yalnız arayüzü kurar ve değerleri toplar; yan etkiler `_apply_settings`'te.
Kalibrasyon modunun (2026-07-10'da kaldırıldı) yerini alan tek ayar penceresidir.

- `RESOLUTIONS` (407): `["1456x1088", "1280x960", "800x600", "640x640", "640x480"]`
  (1456×1088 = imx296 native).
- `__init__` (409): bölümler PLC / Kamera 1 / Kamera 2 / Çekim; içerik `QScrollArea`'da.
  `_enabled(n)` (458): yeni `cameraN_enabled` yoksa eski `enabled_count` geriye uyumu.
  Kamera 2 ön-dolumu (470): `{**cfg_cam, **cfg_cam2}` devralma.
- `_build_camera_group` (508): grup başlığındaki kutu = kamera aç/kapa
  (`QGroupBox.setCheckable`). Listede olmayan özel çözünürlük sessizce değiştirilmez,
  combo'ya eklenir (522). Exposure spinbox **20…1.000.000 µs, adım 50** (eski min=100/
  adım=100 hareketli bant için gereken ~50-150 µs'ye inemiyordu; sensör alt sınırı 29 µs).
  Analog Gain **1.0…16.0, adım 0.5** — imx296 gerçek analog tavanı 15.7; libcamera 251'e
  kadar kabul eder ama üstünü SESSİZCE dijital kazanca çevirir (satır 560-576).
- `_camera_values` (586), `values()` (599 — kamera 1 anahtarları düz, kamera 2 `"cam2"`),
  `accept()` (615 — iki kamera da kapalıysa reddeder).

#### `MainWindow` (satır 625-1926)

**`__init__` (626):** kamera 1 alanları eski adlarıyla (`worker`, `rois`, `_last_snapshot`,
`_last_full_snapshot`, `_snapshot_full_pixmap`, `_last_product_box` ...), kamera 2 `_2`/`2`
ekli paralel alanlarda. Durum: `_inspection_state` (READY), **`_dialog_paused`** (Ayarlar/
Kontrol Noktaları açıkken PLC tetiği işlenmez), `_capture_pending`, `_last_plc_connected`,
`_nok_reset_pending`. `self.plc = create_plc_adapter(self.config)`.

**`_init_ui` (670):** sol sabit panel (320 px scroll içinde) + sağda `content_widget`.
Sol panel: "Sistem Durumu" (`lbl_state`, `lbl_fps`, `lbl_focus` Netlik, `lbl_exposure` Poz,
`lbl_plc`) + "Çalışma Modu" (`chk_manual_mode`) + **en dipte `btn_settings` "⚙ Ayarlar"**
(satır 755-758: bilinçli sol panelde — eskiden kamera satırındaydı, kamera kapatılınca
erişilemiyordu; regresyon testi var). Sağ: `_build_camera_row(1)` + `(2)` alt alta +
tam genişlik "Sistem Logları" (`txt_logs`).

**`_build_camera_row(cam_no)` (803):** solda `ROIResultPanel` + `video_label` (tık →
elle çekim); sağda `lbl_snapshot` (tık → `_open_snapshot_zoom`) + o kameraya ait 2 buton:
"Kontrol Noktaları" ve "Ürün Çerçevesi Bul" (iki kamera modunda "(Kamera 2)" ekli).
Satır 864: "⚙ Ayarlar" bilinçli burada DEĞİL. Widget adları: kamera 1 eski, kamera 2 `_2`
ekli (887-898).

**İki kamera ortak yardımcıları:**

| Metot | Satır | Ne yapar |
|---|---|---|
| `_camera_enabled(cam_no)` | 904 | `cameras.cameraN_enabled`; yoksa eski `enabled_count` geriye uyumu. |
| `_second_camera_enabled` | 914 | Kısayol. |
| `_camera_config_view(cam_no)` | 917 | **En kritik yardımcı (§13 çekirdek ilkesi).** Kamera 1: `self.config`'in KENDİSİ. Kamera 2: remap kopya (`camera←camera+camera2`, `roi←{**roi,**roi2}`, `dynamic_rois←dynamic_rois_2` vb.). **TUZAK (928-936):** nokta KİMLİĞİNE bağlı anahtarlar (`roi_types`, `point_overrides`, `reference_box`, `handedness_*`) `roi2`'de yazılı değilse görünümden SİLİNİR — devralınsa kamera 2, kamera 1'in noktalarını/yön referansını kullanırdı. |
| `_cam_widgets(cam_no)` | 953 | `{"video","snapshot","errors"}` erişim sözlüğü. |
| `_active_cameras()` | 963 | Açık kamera listesi; hepsi kapalıysa `[1]` (emniyet). |
| `_cam_prefix(cam_no)` | 1287 | Log öneki ("Kamera N: "). |

**Elle çekim / modlar:**

| Metot | Satır | Ne yapar |
|---|---|---|
| `keyPressEvent` | 967 | BOŞLUK/ENTER → `_manual_capture()`. |
| `_restart_plc_adapter` | 976 | Adapter'ı kapat + yeniden kur, READY. |
| `_on_manual_mode_changed` | 983 | `plc.manual_mode` yazar (`setdefault`), adapter yeniler. **`plc.type` korunur.** |
| `_manual_capture` | 1001 | Üretimde (manual kapalı) tuş/tık YOK SAYILIR; manual'da `_capture_full_frame`. |
| `_on_video_clicked` | 1010 | Canlı görüntüye tık → elle çekim. |

**Ayarların uygulanması:** `_open_settings` (1014, `_dialog_paused` try/finally) →
`_apply_settings(v)` (1026) — **yalnız DEĞİŞEN tarafı uygular:** PLC beşlisi karşılaştırılır;
kamera restart yalnız fps/kilit/exposure/gain değişince (`change_camera_controls()` — tek
restart yeter, worker config'ten yeniden okur); zoom restartsız `set_zoom`; **⚠ satır 1069:
`was = {n: _camera_enabled(n)}` yeni bayraklar yazılmadan ÖNCE okunmalı**; eski
`enabled_count` silinir (`pop`); çözünürlük/zoom değişince
`_invalidate_snapshot(clear_references=True)` (template referansları ölçeğe bağımlı);
PLC değiştiyse adapter + `_plc_timer.setInterval(poll_ms)`; sonda `_save_config()`.

**Kamera worker yaşam döngüsü:** `_start_worker` (1128 — açık kameralar için
`_start_camera(n)` + `_plc_timer` kurulumu), `_start_camera` (1137 — idempotent;
`InspectionWorker(self.config, cam_index=0|1)`, sinyal bağlantıları, netlik "en iyi"
sıfırlama), `_stop_camera` (1164 — `stop()` + `wait(3000)`), `closeEvent` (1917).

**Canlı görüntü / göstergeler:**

| Metot | Satır | Ne yapar |
|---|---|---|
| `_update_focus_metric` | 1181 | Netlik: merkez 480×360 native pencerede Laplacian varyansı, ~4 Hz; kamera başına anlık + en iyi. TUZAK: gürültüyü de sayar — yalnız aynı kamera + sabit ışık/pozda kıyaslanır. |
| `_camera_exposure_locked` | 1220 | `manual_exposure_enabled` kilidi; kamera 2'de anahtar yoksa kamera 1'den devralır (worker ile aynı mantık). |
| `_update_exposure_label` | 1227 | Poz: `KN X.X ms (gain G) 🔒/⚠ OTO`. **Kilit kapalıysa etiket HEP SARI** — oto-pozlama her an pozu uzatabilir (sahada yaşandı: 200 µs yazılıydı, kutu kapalıydı → kamera 19 ms kullanıyordu). |
| `_render_frame` | 1258 | BGR→RGB→QImage→ölçekli pixmap. |
| `_update_frame` / `_2` | 1268/1272 | `frame_ready` slotları. |
| `_update_state` | 1278 | Worker durum metni. |
| `_update_fps_for/_1/_2` | 1758/1764/1768 | Tek FPS etiketi: ilk AÇIK kameranın değeri. |

**Çekim → analiz → PLC zinciri:**

| Metot | Satır | Ne yapar |
|---|---|---|
| `_poll_plc` | 1675 | `_dialog_paused` iken hiçbir şey yapmaz; `plc.poll()`; `_nok_reset_pending` + bağlantı geldiyse `_reset_plc_nok` tekrar denenir; `"capture"` → `_capture_from_plc`. |
| `_capture_from_plc` | 1697 | BUSY/pending yok sayar; `trigger_delay_ms` > 0 ise `QTimer.singleShot`. |
| `_delayed_capture` | 1708 | `_dialog_paused` olduysa çekimi İPTAL eder. |
| `_capture_full_frame` | 1561 | **SIRA (1565):** kareler ÖNCE, hazırlık kontrolü SONRA. Kare veremezse ERROR; `ready_error` varsa `_store_setup_snapshot` + `publish_error` + ERROR; normal yolda kamera başına `_handle_snapshot`, kararlar VE'lenir, `_publish_plc_result`; yazım başarısızsa ERROR. Tüm istisnalar → `publish_error` + ERROR. |
| `_handle_snapshot(part_id, crop_img, cam_no)` | 1291 | Tek karenin analizi; `cfg_view` → `_prepare_roi_analysis_frame` → `evaluate_with_profile` → gösterim + panel + ayrıntılı log. **`part_id == 0` = ÖNİZLEME:** PLC'ye yazılmaz ama LOGLANIR (`[Önizleme] ... (PLC'ye YAZILMAZ)`) — kaydet-bak-ayarla döngüsü ürün geçirmeden yapılır. |
| `_get_latest_camera_frame` | 1902 | `last_raw_frame` KOPYASI; `max_frame_age_ms` bayatlık kontrolü (bayatsa `None`). |
| `_production_ready_error` | 1728 | Her etkin kamerada en az bir aktif, `yon` OLMAYAN nokta; template'te referans şartı; PLC bağlı mı. |
| `_store_setup_snapshot` | 1512 | Analizsiz tetik karesi saklama + `[Kurulum] ürün çerçevesi: x,y,w,h | referansa göre en %±X boy %±Y` logu (kutu yayılım ölçümü). |
| `_publish_plc_result` | 1624 | HR100'e 0/1; NOK'ta 1 sn sonra `_reset_plc_nok`, OK'ta `_set_ready_after_result`. ACK yok. |
| `_publish_plc_error` | 1632 | HR100=1 + 1 sn sonra reset. |
| `_reset_plc_nok` | 1638 | HR100=0; başarısızsa `_nok_reset_pending=True` (NOK takılı kalmasın). |
| `_set_ready_after_result` | 1652 | **ERROR yapışkan** — READY'ye ancak yeni tetik ya da PLC yeniden bağlanınca. |
| `_set_inspection_state` | 1662 | Durum + `lbl_plc` rengi. |
| `_update_plc_connection_status` | 1714 | Yalnız DEĞİŞİNCE loglar; bağlantı gelince ERROR→READY toparlar. |
| `_append_plc_debug_events` | 1690 | `drain_debug_events` → `[PLC DEBUG]` logları. |
| `_handle_error` | 1799 | Worker hata slotu; üretimde `publish_error` + ERROR. |

**Hizalama:** `_alignment_enabled` (1392), `_prepare_roi_analysis_frame` (1396 —
`find_product_box` + `crop_box`; ürün bulunamazsa `ValueError`), `_capture_product_box_for_roi`
(1417 — "Ürün Çerçevesi Bul" butonu, sarı çerçeve önizleme).

**Sonuç paneli / eşik döngüsü:** `_point_thresholds` (1339 — öncelik analiz motoruyla
AYNI: nokta override → global → varsayılan), `_update_live_errors` (1352 — `"YON"` adlı
sonuç bir ROI değildir, eşiği yok), `_on_panel_threshold_changed` (1373 —
`point_overrides`'a yazar, `_save_config`, `[Eşik]` logu, `_handle_snapshot(0, ...)`
önizlemesi).

**Snapshot gösterimi:** `_display_snapshot` (1456 — tek gösterim noktası; tam çözünürlük
`_snapshot_full_pixmap`'te), `_rescale_snapshot` (1469), `resizeEvent` (1485),
`_open_snapshot_zoom` (1490), `_invalidate_snapshot` (1809 — `clear_references=True` ise
template referansları sıfırlanır).

**Kontrol noktası editörü entegrasyonu — `_open_roi_manager(cam_no)` (1821):**
kamera 1 → `dynamic_rois`/`roi`, kamera 2 → `dynamic_rois_2`/`roi2`. Editör açıkken
`_dialog_paused=True`. Kabulde: ROI'ler + tipler + override'lar (yalnız var olan noktalara
filtrelenir) yazılır; `reset_reference_requested` → `reference_profile` sıfırlanır;
**`reference_box = [kare_w, kare_h]`** yazılır; `dlg.handedness_ref_diff` doluysa
`handedness_hole_diff` + `handedness_check=True` + `handedness_version=HANDEDNESS_VERSION`
+ `handedness_margin_diff` setdefault 12.0; config doğrudan `yaml.dump` (1893);
`_handle_snapshot(0, ...)` önizleme analizi.

**Loglama:** `LOG_DIR` (1777) = `~/konveyor_loglari`; `_log_file_path` (1779) günlük dosya;
`_append_log` (1782) ekrana + diske (saat damgalı); yazma hatasında `_log_file_broken`
(1797) ile sessizce vazgeçilir — arayüzü asla bozmaz.

**Kapanış fonksiyonları:** `apply_dark_palette` (1928 — Windows beyaz-bant sızıntısına
karşı QPalette), `_install_global_excepthook` (1955 — pythonw'da sessiz çökme yerine
dialog), `main()` (1977 — `MainWindow()` parametresiz; açılışta doğrudan ROI ekranı).

### 3.2 `inspector/worker.py` — Kamera QThread'i (319 satır, 2026-09-23)

`InspectionWorker(QThread)` (satır 14): her örnek TEK fiziksel kamerayı (cam0/cam1)
açar, sürekli kare okur, Qt sinyalleriyle GUI'ye yollar; PLC'den tamamen habersizdir.

- **Sinyaller (15-19):** `frame_ready(np.ndarray)`, `state_changed(str)` (pratikte hep
  "CANLI"), `fps_updated(float)`, `log_message(str)`, `error_occurred(str)`.
- **`__init__(config, cam_index=0)` (21-42):** `config` **paylaşılan** sözlük (kopya
  değil). `last_raw_frame`/`last_frame_time` (35-36) = GUI'nin tetikte okuduğu KÖPRÜ;
  `last_exposure_us`/`last_gain` (39-40) = fiilen kullanılan poz/gain (Poz göstergesi);
  `_meta_fn` (34, OpenCV'de None); `_zoom` (42).
- **`_cam_cfg()` (44-50) / `_res_cfg()` (52-56):** kamera 2 için `{**camera1, **camera2}`
  birleşimi — yazılmamış anahtar kamera 1'den devralınır (yalnız KAMERA ayarları;
  `roi2.*` kimlik anahtarları main tarafında bilinçli devralınmaz).
- **`_open_camera()` (58-138):** picamera2 yolu (66-123): `Picamera2(cam_index)`,
  `create_video_configuration(BGR888 + FrameRate + _camera_controls())`, start sonrası
  1.5 sn bekleme (99), `safe_read()` kanal düzeltmesi (102-114, BGR888 fiilen RGB gelir),
  `_meta_fn = capture_metadata`. **TUZAK — DEĞİŞKEN GÖLGELEMESİ (satır 73):**
  `cam_cfg = cam.create_video_configuration(...)` ataması kamera config sözlüğünü EZER →
  `awb_mode` (79) ve `color_gains` (90) artık picamera2 nesnesini okur; config.yaml'daki
  `camera.awb_mode`/`color_gains` **fiilen ÖLÜDÜR**. OpenCV yedeği (125-138):
  `cv2.VideoCapture(opencv_index)`; `_meta_fn=None` → Poz göstergesi beslenmez.
- **`_release_camera()` (140-152):** backend'e göre kapatma; istisnalar yutulur.
- **Ayar metotları (GUI thread'inden):** `change_resolution` (154-158),
  `change_fps` (160-162), `change_camera_controls` (164-165 — sadece restart bayrağı),
  `set_zoom` (167-169, restartsız), `stop` (171-172). Restart bayrağı
  `getattr(self, "_restart_camera_requested", False)` kalıbıyla okunur (189).
- **`run()` (174-231):** restart isteği → kapat/aç/`continue` (yeniden açılamazsa thread
  **sessizce ölür**); kare oku — 100 ardışık hata (~2 sn) sonrasında bir kez
  `error_occurred`; `_read_exposure_metadata()`; `cv2.resize` config çözünürlüğüne (211);
  `_apply_digital_zoom`; `last_raw_frame = frame.copy()` + `last_frame_time`; FPS ölçümü;
  `frame_ready.emit`.
- **`_read_exposure_metadata()` (233-251):** picamera2 metadata'dan `ExposureTime`/
  `AnalogueGain`, saniyede en fazla 1 kez. Saha bilgisi: global shutter uzun pozdaki
  hareket bulanıklığını ÖNLEMEZ; oto-pozlama pozu 16.6 ms'ye uzatabilir.
- **`_apply_digital_zoom` (253-263):** ortadan kırp + geri büyüt; `zoom ≤ 1.01` dokunmaz.
  **DETAY ÜRETMEZ** (ölçüm: zoom 2'de gerçek detayın %21-54'ü kalır).
- **`_camera_controls()` (265-277) — ANA ŞALTER:** `manual_exposure_enabled` false ise
  **BOŞ sözlük** → `exposure_us`/`analogue_gain` KESİNLİKLE UYGULANMAZ, oto-pozlama.
  true ise `{"AeEnable": False, "ExposureTime": ..., "AnalogueGain": ...}`.
- **`_apply_opencv_camera_controls` (279-289):** OpenCV'de aynı şalter; değer semantiği
  sürücüye bağımlı.

Config'i diske YAZMAZ — yalnız bellekteki paylaşılan sözlüğü değiştirir; kalıcılaştırma
main.py'de.

### 3.3 `inspector/plc.py` — PLC Adaptörleri (296 satır)

Ortak arayüz: `poll`, `set_state`, `publish_result`, `publish_error`, `reset_nok`,
`close`, `is_connected`, `status_text`, `drain_debug_events`.

- **Sabitler (5-7):** `NOK_REGISTER = 100`, `TRIGGER_REGISTER = 101`,
  `ALLOWED_REGISTERS = {100, 101}`. **İNCELİK:** register adresleri KODDA SABİT;
  config'teki `plc.registers` bloğu bu modül tarafından **OKUNMAZ** (90-91) — bilinçli
  emniyet (yalnız 100/101'e dokunulur; beyaz liste başka adresi zaten keser).
- **`InspectionState(str, Enum)` (10-15):** READY/BUSY/OK/NOK/ERROR.
- **`NullPLCAdapter` (18-59):** `poll()` (29) hep `None` → otomatik tetik ASLA gelmez;
  `publish_*` yalnız iç durumu günceller, `True` döner; `is_connected()` hep True;
  `status_text()` = "PLC simülasyon".
- **`ModbusTCPPLCAdapter` (62-279):**
  - `__init__` (72-94): `host` (vars. 192.168.10.10), `port` (502), `unit_id`
    (`slave_id` takma adı; vars. 1 — sahada 0 doğrulandı), `timeout_s` (1.0),
    `reconnect_s` (3.0). **Yapıcı hemen `_connect()` çağırır** — PLC yoksa GUI thread'inde
    `timeout_s` kadar bloke eder; `plc.manual_mode`'un varlık sebebi budur.
  - `poll()` (96-114): `_ensure_connected` → HR101 oku → ham değer değişiminde debug log →
    **yükselen kenar** → `"capture"`.
  - `publish_result(ok)` (119-131): HR100 = 0/1; yazma başarısızsa `_mark_disconnected` +
    False. Reset darbesi bu modülde DEĞİL, main.py QTimer'ında; **ACK yok**.
  - `publish_error` (133-142): hata da **HR100 = 1** (NOK gibi — emniyetli taraf).
  - `reset_nok` (144-152): HR100 = 0.
  - `_connect` (163-187): pymodbus 3.x `pymodbus.client` / 2.x `pymodbus.client.sync`
    import uyumu; başarısızlıkta Türkçe `last_error`.
  - `_ensure_connected` (189-196): `reconnect_s` dalga kıranı (her poll bir TCP denemesine
    dönüşmesin).
  - `_mark_disconnected` (198-206): bağlantıyı kopuk işaretler VE **kenar durumunu
    sıfırlar** — yeniden bağlanınca hâlâ HIGH tetik YENİ yükselen kenar sayılır (bekleyen
    parça kaybolmasın; yan etki: olası çift tetik — bilinçli tercih, satır 200-203).
  - `close` (154-161); `is_connected` (208); `status_text` (211-214);
    `drain_debug_events` (216-219) + `_log_debug` (221-224): 100 kayıtlık halka tampon.
  - `_read_holding_registers` (226-248) / `_write_holding_register` (257-279): beyaz liste
    + pymodbus API kaskadı (`device_id=` 3.7+ → `slave=` 3.x → konumsal+`unit=` 2.x).
    `_write_holding_registers` (250-255) **hiçbir yerden çağrılmayan** ölü yardımcı.
- **`create_plc_adapter(config)` (282-296):** `manual_mode: true` → her koşulda
  `NullPLCAdapter` (286-287; `plc.type` KORUNUR). `type` normalize: `null/none/disabled` →
  Null; `modbus_tcp/modbus/tcp` → ModbusTCP; tanınmayan → `ValueError`.

Bu modülde thread YOK — tüm çağrılar GUI thread'indeki QTimer'dan; Modbus çağrıları
senkron/bloke edici → `timeout_s` küçük tutulmalı (sahada 0.2 s).

### 3.4 `inspector/features.py` — ROI Analiz Motoru (642 satır)

Saf analiz modülü: girdisi kare + config, çıktısı `(global_ok, results, display_img)`.
Qt/GUI/PLC bilmez; iki kamera desteği bu dosyaya dokunulmadan `_camera_config_view`
remap'iyle eklendi.

**Sabitler:** `TEMPLATE_SIZE (96,96)` (6), `DEFAULT_TOLERANCES` (7-12),
**`HANDEDNESS_VERSION = 3`** (371-380) — config'teki `handedness_version` eşit değilse
yön kontrolü **SESSİZCE atlanır** (v2 NCC referansları otomatik geçersiz).

**Genel API:**

| Fonksiyon | Satır | İş |
|---|---|---|
| `evaluate_with_profile(snapshot, config)` | 54 | Ana giriş. `roi.decision_method` `hole` (vars., 57) → `_evaluate_holes` (58-59); `template` → kendi gövdesinde (61-106) base64 referanslarla MAD karşılaştırma; hiç ROI kontrol edilmediyse global NOK (boş konfig asla OK üretmez). Çağıran: `main.py:1301` `_handle_snapshot`. |
| `roi_point_type(name, roi_types)` | 277 | Tip: `roi_types[ad]` → ad içi kelime (centik/çentik/oluk/slot/notch/kanal → notch; yon/yön/direction → yon) → varsayılan `hole`. Takma ad `_roi_type` (293). Dış çağıranlar: `main.py:1358` ve `main.py:1733`. |
| `hole_handedness_diff(snapshot, config)` | 416 | En sağ − en sol yön-ölçüm noktası gri ortalama farkı; <2 nokta → `None`. Çağıranlar: `_check_handedness`, `roi_editor.py:443`. |
| `extract_features` | 15 | Template özellik paketi (96×96 gri + Canny, base64). |
| `update_reference_profile` | 37 | Template referans ekleme (aktif UI çağrıcısı kalmadı). |
| `has_reference_profile` | 456 | `reference_profile.rois` dolu mu (main.py:1301 uyarısı). |
| `reference_metric_limits` | 460 | Bilgi amaçlı tolerans bantları (yalnız template). |
| `format_metrics` (489) / `format_limits` (499) | | Türkçe log metinleri (main.py:1330). |

**`_evaluate_holes(snapshot, config)` (109) — çekirdek karar:**
1. Eşikler config'ten okunur (117-154); `point_overrides` nokta başına globali ezer
   (187-190: `eff_notch_min`, `eff_hole_min`, `eff_core_min`).
2. `_roi_reference_scale` (159) ile `sx, sy` — ROI'ler `roi.reference_box` boyutuna
   göre saklanır, analiz karesi farklıysa oranlanır.
3. ROI döngüsü (161-256): `yon` tipi atlanır (166-167); boş kırpma → NOK (172-173);
   `dark_ratio` (= gri < `hole_dark_value` oranı) + `core_ratio` (= gri < `hole_core_value`
   oranı) hesaplanır (175-184).
   - **`notch` (191-217): İKİ KAPI** — (1) koyu% bandı, (2) `_notch_shape` şekil kapısı
     (`blob ≥ notch_min_blob_ratio` VE `aspect ≥ notch_min_aspect` VE
     `width_ratio ≥ notch_min_width_ratio`). Gerekçe (140-145): salt koyu-oran, oluksuz
     düz parçadaki dağınık gölgeyi "oluk VAR" sanıp yanlış OK veriyordu.
   - **`hole` (218-254): SIRALI KAPILAR** — (1) `dark_ratio < eff_hole_min` → NOK
     ("delik YOK") — **ANA KAPI** (221-223: tam açık ~%25 koyu, kısmen bantlı ~%11);
     (2) `dark_ratio > hole_dark_ratio_max` → NOK; (3) `core_ratio < eff_core_min` →
     NOK derinlik kapısı (130-134, 229-232; saha gerçeği: açık delikler GRİ okur →
     yalnız düşük zemin ~%2); (4) `_hole_shape` şekil kapısı
     (circ/fill/aspect/edge/blob — kısmen bantlı delik hilal blob → düşük fill ~0.5).
4. Yön kontrolü (258-261): `_check_handedness`; mesaj varsa `results["YON"]`.
5. Global karar (263): `checked_any_roi AND hand_ok AND tüm ROI'ler OK`. Başlık
   (264-273): "PARCA: NOK (AYNA/TERS)" / "PARCA: OK" / "PARCA: NOK (EKSIK)".

**Şekil yardımcıları:**
- `_hole_shape(gray, dark_value)` (296): MORPH_CLOSE (9×9, ×2 — delik merkezindeki parlak
  "kahve göz" yansımasını doldurur) → RETR_EXTERNAL → en büyük blob: `circ` = 4πA/P²
  (~0.9), `fill` = alan/minEnclosingCircle (~0.95 tam, ~0.5 yarım bantlı), `aspect` =
  min/max, `edge` (0-4 kenar değme), `blob` (%).
- `_notch_shape(gray, dark_value)` (327): `blob`, `aspect` = **bw/bh (>1 = yatay-uzun —
  delikteki tanımdan FARKLI!)**, `width_ratio`. **KRİTİK TUZAK (338-342): önce MORPH_OPEN
  (dağınık benek siler), sonra CLOSE (yarığı doldurur)** — yalnız CLOSE dağınık benekleri
  tek dev bloba birleştirip şekil kapısını boşa çıkarır.
- `_has_circle` (359): **ölü kod**, hiçbir yerden çağrılmıyor (config `hole_use_circle_check`
  de ölü anahtar).

**Yön/el zinciri:**
- `_hole_centers_brightness` (383): ölçüm noktaları `(x, gri_ort, ad)` x-sıralı; ÖNCE
  `yon` tipi (≥2), yoksa `hole` tipine düşer (UI'dan yon çizimi kaldırıldı → sahada fiilen
  2 delikten ölçülür); `notch` girmez.
- `_check_handedness` (427): güvenli atlama koşulları (hepsi `(True, "")`):
  `handedness_check: false`; **`handedness_version != 3` (SESSİZCE geçer)**;
  `handedness_hole_diff` yok; <2 ölçüm noktası. Karar: |referans| < `handedness_margin_diff`
  (vars. 12.0) → "yon kontrol zayif" ile geçirir; güncel fark referansla zıt işaretli VE
  |güncel| > margin → `(False, "AYNA/TERS parca ...")` → global NOK.

**Geometri/kodlama yardımcıları:** `_roi_reference_scale` (597 — buradaki "kare"
alignment sonrası ürün kırpmasıdır; kutu oynarsa TÜM ROI'ler birlikte kayar),
`_roi_bounds` (615), `_crop_roi` (590 — **template yolu ölçekleme YAPMAZ**),
`_prepare_roi` (520), `_roi_metrics` (529), `_reference_metrics` (542),
`_best_template_score` (553), `_mean_abs_score` (569), `_encode_png`/`_decode_png`
(575/582), `_draw_roi_result` (626 — yalnız `"ad: OK/NOK"` çizer; **`msg` parametresi
imzada durur ama BİLEREK çizilmez**, 629-634 docstring — kullanıcı kararı 2026-08-03).

Modül config'e hiç YAZMAZ; thread'i ve durumu yoktur (tüm fonksiyonlar girdi→çıktı,
`display_img = snapshot.copy()` ile giriş karesi mutasyona uğratılmaz — satır 68, 156).

### 3.5 `inspector/alignment.py` — Ürün Kutusu Bulma (161 satır)

Karede ürünü (tam braketi) bulup `[x, y, w, h]` kutusu döndürür; saf görüntü işleme,
durumsuz.

- **`DEFAULT_ALIGNMENT` (5-14):** `mode: contour`, `min_area_ratio: 0.02`,
  `padding_px: 20`, `foreground: bright`, `metal_v_min: 110`, `metal_s_max: 85`.
  Tasarım: parça PARLAK + RENKSİZ (gri metal); yeşil raylar parlak ama RENKLİ →
  doygunlukla (S) ayırt edilir. (`mode: off` ayrımını çağıran taraf uygular.)
- **`get_alignment_config` (17-20):** varsayılanlar + `config["alignment"]`.
- **`_to_gray` (23-29):** 2/3/4 kanala dayanıklı gri dönüşüm.
- **`_pick_box(mask, ...)` (32-82):** `findContours(RETR_EXTERNAL)` (41 — **delik ASLA
  ürün sanılmaz**); tüm-kare filtresi (46-47, ≥%98); `reject_thin` (49-50, `w < h*0.3`
  ince-dikey ret — yalnız metal yolunda); en büyük aday (53-58); `union=True` (62-76):
  en büyük konturla **YATAY örtüşen** (x-kesişimi ≥ dar olanın %30'u) parçalar yinelemeli
  birleştirilir (braketin alt flanşı gölge çizgisiyle ayrılınca tek çerçevede birleşsin);
  padding + kırpma (78-82).
- **`_metal_mask(frame, v_min, s_max)` (85-97):** HSV `V ≥ v_min AND S ≤ s_max`; yeşil
  (35≤H≤90, S≥60, V≥40) 25×25 çekirdekle **dilate edilip** metalden silinir (rayın
  üstündeki specular yansımanın komşuluğu da elensin); MORPH_OPEN ×1 + CLOSE ×4
  (delikler dahil iç boşlukları doldur, tek blob).
- **`_otsu_mask(frame, foreground)` (100-108):** yedek — Gaussian blur + Otsu
  (`dark` → BINARY_INV); OPEN ×1 + CLOSE ×2.
- **`find_product_box(frame, config)` (111-137) — ANA GİRİŞ:** `foreground != "dark"` +
  renkli kare → önce metal izolasyonu; metal bulunamazsa Otsu'ya düşer (134-136).
  Tarihçe (124-126): eski salt-parlaklık Otsu, parlak yeşil rayları da ürün sanıp
  çerçeveyi tüm kareye genişletiyordu.
- **`crop_box(frame, box)` (140-150):** sınıra kırpıp **kopya** dilim; geçersizse `None`.
- **`draw_product_box` (153-161):** sarı çerçeve + "URUN" etiketi (önizleme).

İncelikler: yeşil dilate 25×25 **sabit piksel** (çözünürlüğe oranlı değil); CLOSE ×4
agresif (yakın metal lekeleri yapıştırabilir — kutu kararlılığı sorunlarında ilk bakılacak
yer); Otsu yedeğinde `reject_thin`/`union` yok; kutu bulunamazsa `None` (çağıran dayanıklı
olmalı).

### 3.6 `inspector/roi_editor.py` — Kontrol Noktası Editörü (703 satır)

Config'e **doğrudan yazmaz** — sonuçlar dialog üyelerinde birikir, "Kaydet ve Kapat"
sonrası `main.py::_open_roi_manager` yazar. Koordinatlar HEP orijinal görüntü pikselinde
tutulur (`_scale`/`_zoom` yalnız gösterim).

**`ROILabel(QLabel)` (9-270) — çizim tuvali:**
- Sinyaller (10-13): `new_roi(x,y,w,h)`, `roi_selected(str)`,
  `roi_right_clicked(str, QPoint)`, `draw_cancelled()`.
- Durum (15-38): `rois`, `types`, `disabled_rois`, `draw_shape`, `_zoom` (0.25-4.0),
  **`drawing_mode`** — çizim modu SADECE "Yeni Kontrol Noktası" ile silahlanır;
  moddayken mevcut ROI'ler GİZLENİR. **Önemli:** dialog, label alanlarına kendi
  sözlüklerinin REFERANSINI atar (325-327) — aynı nesneler paylaşılır.
- Metotlar: `set_image` (40-44), `set_zoom` (46-54), `_update_display` (56-118 — tip
  görselleştirme: hole=elips, notch/yon=dikdörtgen; yon=turuncu #fab387, pasif=gri,
  seçili=cyan, normal=sarı; çizim modunda mevcut ROI'ler atlanır, satır 80),
  `cancel_drawing` (120-130), `mousePressEvent` (132-165), `mouseMoveEvent` (167-173),
  `mouseReleaseEvent` (175-217 — w>5 ve h>5 ise mod TEK SEFERLİK kapanır ve `new_roi`
  yayılır; çok küçük sürüklemede mod açık kalır), `_update_active_roi` (219-237),
  koordinat yardımcıları (239-256), `_hit_test` (258-270 — ters sıra; sağ-alt köşe ±10px
  = resize).

**`ROIDialog(QDialog)` (273-703):**
- Kurucu (274-415): `image` BGR (`QImage.Format_BGR888`, satır 320 — kopyasız; dialog
  ömrünce `self._image_bgr` yaşar), `self.rois = existing_rois.copy()` (X ile kapatmada
  config bozulmaz), `roi_types` normalize (294-296), `handedness_ref_diff = None`
  (298-302), `point_overrides` (303-306), `roi_defaults` (307-310 — Ayarlar ön-dolumu;
  main gerçek config değerleriyle ezer), `reset_reference_requested` (311-312).
  "＋ Yeni Kontrol Noktası" menü-butonu (358-371): Delik (daire) / Çentik (kutu) /
  ayıraç / "🧭 Yön Referansı Al (doğru parça)". **"Yön Tayini" çizim seçeneği menüde
  BİLİNÇLİ YOK** (kullanıcı kararı; `yon` yalnız eski config'ten geriye-uyum).
  `list_rois`: `ExtendedSelection` (Ctrl/Shift çoklu silme) + `CustomContextMenu`.
- Metotlar: `_reset_hint` (417), `_arm_draw` (423-434), `_on_draw_cancelled` (436),
  `_take_handedness_reference` (439-456 — `features.hole_handedness_diff` geç import;
  <2 delik → uyarı; başarıda `handedness_ref_diff` set), `keyPressEvent` (458-467 —
  **ESC diyaloğu KAPATMAZ, çizimi iptal eder**; Delete siler), `_selected_names`
  (469-477 — `"  ("` ayıracına dayanır), `_on_list_context_menu` (479-502),
  `_on_canvas_right_click` (504-512), `_request_reference_reset` (514-518),
  **`POINT_SETTINGS`** (521-535 — tip başına eşik alanları: hole → açıklık 0-50 +
  derinlik 0-30; notch → oluk 0-90; `yon` için giriş YOK), `_open_point_settings`
  (537-622 — **genel değere eşit girilen değer override YAZILMAZ**, 602-604; "Varsayılana
  Dön" o tipin anahtarlarını siler), zoom sarmalayıcıları (624-628), `_on_new_roi`
  (630-648 — otomatik sıralı rakam isim, ilk boş numara), `_del_roi` (650-653),
  `_delete_roi_by_name` (655-667 — **rois + roi_types + point_overrides + disabled_rois
  birden düşürülür**, öksüz anahtar kalmaz), `_current_name` (669-673), `_select_roi`
  (675-685), `_update_list` (687-703 — eşik rozetleri).
- **`_NoWheelSpin` (562-575, yerel sınıf):** iki koruma bir arada — `wheelEvent →
  ignore()` + tr_TR ondalık ayıraç düzeltmesi (main.py'deki `NoWheelDoubleSpinBox`'ın
  bağımsız kopyası). Bu diyaloğa eklenen her yeni sayısal giriş bu sınıfı kullanmalı.

### 3.7 Çalıştırma ve kurulum betikleri

**`calistir.sh` (Pi):** `set -e` (2); proje köküne cd (4); **venv varsa venv**
(`veri_toplama/bin/python`, 11-13, `exec`); **yoksa sistem python** — beş kütüphane
import denetimi (`picamera2, PyQt5, cv2, yaml, pymodbus`, 15-20; eksikse Türkçe hata +
iki kurulum yolu + exit 1), tamamsa `exec python3 main.py` (22). Sebep: sahadaki Pi'de
venv HİÇ kurulmadı (Debian 13'te paketler apt'tan); eski hali venv yolunu sabit varsayıp
duruyordu.

**`calistir.bat` (Windows):** `cd /d "%~dp0"` (9) +
`start "" "...\veri_toplama\Scripts\pythonw.exe" main.py` (10). `pythonw` = konsolsuz
(sessiz çökme riskini main.py excepthook'u karşılar); `start ""` = bloklamaz (ilk `""`
pencere-başlığı parametresi — klasik tuzak); DAİMA venv, sistem python'una düşüş YOK.

**`tools/kurulum_pi.sh`:** proje kökü (9-10) → [1/4] apt: `python3-picamera2
python3-pyqt5 libgl1` (12-17) → [2/4] `python3 -m venv --system-site-packages
veri_toplama` (19-25, idempotent) → [3/4] `pip install -r requirements.txt` (27-29,
piwheels) → [4/4] `install_pi.sh` (31-32). picamera2/PyQt5 apt'tan (pip DEĞİL);
`--system-site-packages` şart; `libatlas-base-dev` bilinçli YOK (trixie'de kaldırıldı).

**`tools/install_pi.sh`:** Python seçimi calistir.sh ile aynı mantık (19-27); import
ön kontrolü UYARIR ama engellemez (29-36 — eksik kütüphanede ikon sessizce açılmaz,
kullanıcı kurulumda uyarılsın); `~/.local/share/applications/konveyor-denetim.desktop`
yazımı (38-54, `Exec=$PY $DIR/main.py`, `Path=$DIR`, `Icon=$DIR/app.png`); masaüstü
kopyası `xdg-user-dir DESKTOP` → `~/Desktop` → `~/Masaüstü` (57-68);
`update-desktop-database` (71-72); "Allow Launching" notu (74-79). Tuzak: `Exec=`'e
kurulum anındaki PY mutlak yolu gömülür — venv sonradan kurulur/silinirse betik yeniden
çalıştırılmalı.

**`tools/yeni_pi_kur.sh`:** iki mod — `--kontrol` (HİÇBİR ŞEYİ DEĞİŞTİRMEZ, 6 maddelik
fark raporu) / normal (her değiştirici adımda onay). Değerleri `saha_ayarlari.conf`'tan
okur (source, satır 31); `set -u` var ama `set -e` YOK (bilinçli: rapor sona kadar aksın,
satır 18); `onayla` (39-44) `--kontrol`'de KOŞULSUZ `return 1`, normalde `/dev/tty`'den
okur. 6 madde: [1] Python kütüphaneleri (53-69, eksikse onayla `kurulum_pi.sh`);
[2] kameralar (71-85, `rpicam-hello --list-cameras`, `timeout 30`; yalnız raporlar +
kablo/CSI soket uyarısı); [3] statik IP (87-113, nmcli; SSH kopma uyarısı; **eth0'a
gateway verilmez**); [4] PLC erişimi (115-135: config.yaml ↔ conf tutarlılık + 2 sn ham
TCP connect); [5] uygulama ayarları özeti (137-151, salt bilgi); [6] uzaktan kontrol
ajanı (153-192, opsiyonel systemd user servisi + linger). Özet (194-207): 6/6 = "İKİZ";
her çıkışta koşulsuz uyarı: **İKİ Pi AYNI ANDA ÇALIŞMASIN**. Kişisel yol gömmez
(`$HOME`/`$USER`).

**`tools/plc_smoke_test.py`:** uygulamasız Modbus testi. `NOK_REGISTER = 100` (9),
`TRIGGER_REGISTER = 101` (10) — okuma yalnız 101, yazma yalnız 100 (aksi `ValueError`,
23-24/36-37; CLI reddi 80-82). Fonksiyonlar: `load_config` (13-15), `is_error` (18-19),
`read_holding_register` (22-32, pymodbus API kaskadı), `write_holding_register` (35-45),
`main` (48-98). CLI birleşimi (57-61): CLI > config > varsayılan; `unit_id` için
`is not None` (0 değeri `or` tuzağına düşmesin — sahadaki gerçek unit_id 0!). Çıkış
kodları: 0 başarı, 2 bağlantı, 3 okuma, 4/5 yazma/geri çekme, 6 güvenlik reddi.
`--write-test-register` HR100'e 1 yazıp 0.2 sn sonra 0'a çeker — **bant çalışırken
KULLANILMAMALI** (PLC'ye kısa NOK demektir). Bu betikle port 496 hatası bulunup 502'ye
düzeltildi, unit_id 0 doğrulandı (2026-07-29).

**`tools/make_icon.py`:** `S = 1024` süpersample (8), renk sabitleri (11-16),
`rounded` (19-20), `build` (23-55): kart → kademeli braket → delik (merkez 470,540 r=132)
→ büyüteç (önce sap, sonra halka, en üste cam parlaması) → 256'ya LANCZOS → `app.ico`
(çoklu boyut) + `app.png`. Bağımlılık Pillow (yalnız bu araç için). `app.png` gitignore
istisnası (`!app.png`).

#### `tools/kamera_onizleme.sh` — programdan bağımsız canlı önizleme (2026-09-23)
Masaüstü/menü simgesi "Kamera Önizleme" (`kamera-onizleme.desktop`, Terminal=true,
Icon=camera-photo; `install_pi.sh` kurar). Akış: (1) denetim uygulaması açıksa (`ps args`
`python*main.py`) zenity ile kapatma onayı, SIGTERM→5 s→SIGKILL; (2) `rpicam-hello
--list-cameras` ile indeksler; (3) config.yaml'dan kamera başına `--width/--height` (+ kilit
açıksa `--shutter/--gain`; kamera 2 kamera 1'den devralır); (4) `xrandr` ile ekran, pencereler
yan yana `--preview x,60,w,h`, başlık `--info-text "Kamera N (camI) | poz %exp | gain %ag |
%fps"`; (5) `rpicam-hello --camera I -t SURE &`, trap ile kapanışta hepsini öldürür. Test
kancaları: `ONIZLEME_APP_KONTROL=0`, `ONIZLEME_SADECE="1"`; ilk argüman süre (ms). libcamera
hataları ("Camera frontend has timed out" = kablo) terminalde canlı görünür.

#### `tests/` — ekransız regresyon testleri (2026-09-23)
`bash tests/calistir_testler.sh` (QT offscreen, her dosyanın TOPLAM satırı; çıkış = hatalı dosya
sayısı). Dosyalar: `test_gecikme_kamera.py` (worker gölgeleme/yedek/yarım nesne; gecikme kutusu,
damga, aç/kapa sırası, Enter, imx477 modları), `test_closeevent.py`, `test_sayac.py`,
`test_paket.py`. Ortak kalıp: geçici config (`main.load_config` yaması), `MainWindow.LOG_DIR`
geçici, `_start_worker` no-op, `QMessageBox` susturma, sahte worker/picamera2 modülleri.

### 3.8 CLAUDE.md ve PROGRAM_KULLANIM_NOTLARI.md

- **CLAUDE.md (900 satır):** doğruluk kaynağı; koddan çıkarılamayan kararlar, saha
  ölçümleri, tuzaklar. Ajan sözleşmesi: her anlamlı değişiklikten sonra sormadan
  doküman güncelle + commit + push (satır 21-33). Makine değişiminde ilk iş
  `yeni_pi_kur.sh --kontrol` (7-19). Bölüm haritası: §1-11 (35-271), §12 saha tarihçesi
  (273-720), **§14 dosyada §13'ten ÖNCE durur** (722-788), §13 ikinci kamera (790-899).
  ⚡ ÇELİŞKİ (doküman içi): satır 719-720'deki "İKİNCİ KAMERA... KOD YAZILMADI" notu
  ESKİDİR — §13 uygulamanın 2026-07-30'da bitip doğrulandığını söyler. Satır 537-547'deki
  "yalnız Kamera 2" saha ayarı 2026-08-10'da geçersizleşti (tarihçe için duruyor).
- **PROGRAM_KULLANIM_NOTLARI.md (130 satır):** operatör kılavuzu; **büyük ölçüde
  2026-07-10 öncesi arayüzü anlatır** — §2'deki kalibrasyon modu butonları artık YOK,
  §4'teki 8000 µs önerisi güncel değil (hareketli bantta ≤1 ms), §6/§8 template yöntemine
  ait (aktif yöntem `hole`, referans gerektirmez), iki kamera hiç anlatılmaz. Çelişkide
  CLAUDE.md geçerlidir; güncelleme §12 "Yapılacak" listesinde açık iştir. Hâlâ geçerli
  kavramlar: başlatma yolu, çekim gecikmesi mantığı, exposure/gain kilidi, "ayar
  penceresi açıkken tetik durur" (bugünkü karşılık `_dialog_paused`), "kamera/ışık
  oynarsa yeniden ayar" ilkesi.

---

## 4. `config.yaml` Anahtar Referansı (mevcut değerlerle)

Tek kalıcı uygulama konfigürasyonu. `main.py::load_config` açılışta okur; GUI'deki her
anlamlı etkileşimde `yaml.dump` ile **dosyanın tamamı yeniden yazılır** (yorumlar
kaybolur, SD aşınması riski; koda yeni anahtar `setdefault` ile eklenir). Git ile taşınır.

### `alignment` (satır 1-5)
| Anahtar | Değer | Not |
|---|---|---|
| `foreground` | `bright` | HSV metal izolasyonu; `dark` = Otsu-INV. |
| `min_area_ratio` | `0.02` | Ürün adayı min alan oranı. |
| `mode` | `contour` | `off` = tam kare, ROI'ler mutlak (kutu kararsızsa daha kararlı OLABİLİR — ölçülmeli). |
| `padding_px` | `20` | Kutu payı. |

`metal_v_min` (110) / `metal_s_max` (85) dosyada yazılı değil — kod varsayılanları geçerli.

### `calibration` (satır 6-18) — **ÖLÜ BLOK**
Kalibrasyon modu 2026-07-10'da koddan kaldırıldı; blok hiçbir yerden okunmaz/yazılmaz.
Değerler (`exposure_us: 2000`, `fps: 53`, `resolution [640,480]`, `zoom: 2.0` vb.)
640×480 döneminden tarihi kalıntı — güncel kamera ayarlarıyla karıştırılmamalı.

### `camera` (satır 19-29) — Kamera 1 (cam0)
| Anahtar | Değer | Not |
|---|---|---|
| `analogue_gain` | `16.0` | Gerçek analog tavan 15.7; üstü sessizce dijital kazanç. |
| `awb_mode` / `color_gains` | `Auto` / `null` | **worker.py satır 73 gölgeleme hatası yüzünden fiilen ÖLÜ.** |
| `backend` | `picamera2` | OpenCV yedek. |
| `exposure_us` | `500` | Yalnız kilit açıkken uygulanır. 2026-07-30 ölçümü: 500 µs "sağlam — önerilen". |
| `fps` | `20` | **⚠️ AÇIK RİSK:** düşük fps = bayat kare = tetik kayması (~2×); kırpılma görülürse fps 40-60'a geri al. |
| `manual_exposure_enabled` | **`false`** | **ANA ŞALTER — false iken poz/gain KESİNLİKLE UYGULANMAZ, oto-pozlama çalışır.** ⚡ ÇELİŞKİ: CLAUDE.md §12 "poz/gain sabitlendi (`true`)" der; dosyadaki güncel değer `false` — şu an iki kamera da OTO-POZLAMADA görünür ("Poz" göstergesi `⚠ OTO` + sarı). Sahada bilinçli mi kapatıldı teyit edilmeli. |
| `max_frame_age_ms` | `1000` | Bayat kare reddi. |
| `opencv_index` | `0` | |
| `zoom` | `1.0` | Yazılım zoom'u — detay üretmez; doğru ayar native + 1.0. |

### `camera2` (satır 30-40) — Kamera 2 (cam1, havşalı yüz)
Kamera 1 ile birebir aynı değerler; `opencv_index: 1`. Devralma kuralı: yazılmamış
anahtar kamera 1'den gelir (burada hepsi yazılı). Saha notu: cam1 aynı pozda daha loş
okur (500 µs'de metal 102 ≈ 70 eşiğine yakın — pay dar, `koyu%` loglarıyla izlenmeli).

### `cameras` (satır 41-43)
`camera1_enabled: true`, `camera2_enabled: true`. İkisi birden kapatılamaz; eski
`enabled_count` geriye-uyumlu okunur, yeni bayraklar yazılırken silinir.

### `disabled_rois` / `disabled_rois_2` (satır 44-45)
İkisi de `[]`. Aktif/Pasif düğmesi UI'dan kaldırıldı; veri yapısı korunur.

### `dynamic_rois` (satır 46-51) — Kamera 1
`'1': [33, 121, 46, 46]` (hole). **⚠️ 640×480/zoom 2.0 döneminden kalma**
(`reference_box [201,212]` ile birlikte) — gerçek üretim karesinde yeniden çizilmeli.

### `dynamic_rois_2` (satır 52-67) — Kamera 2
`'1': [571, 361, 301, 283]` (hole, havşalı), `'2': [138, 331, 268, 282]` (hole),
`'3': [119, 2, 747, 133]` (notch). `roi2.reference_box [971, 726]`'ya göreli; sahada aktif.

### `inspection` (satır 68-69)
`trigger_delay_ms: 1` (≈ gecikmesiz; iki kamera aynı gecikmeyle çeker).

### `plc` (satır 70-81)
| Anahtar | Değer | Not |
|---|---|---|
| `host` | `192.168.10.10` | `saha_ayarlari.conf::PLC_IP` ile tutarlılığı betik denetler. |
| `manual_mode` | `false` | Üretim modu. `true` → NullPLC, elle çekim. Sahada mutlaka `false`. |
| `poll_ms` | `20` | **Bilinçli 20** — sahada 100'e kaymıştı; 1 ms gecikme ≈ 4 px kayma; 20'ye çekilince temiz tespit %69→%100. 100'e GERİ ÇIKARILMAMALI. |
| `port` | `502` | 496 YANLIŞTI; 2026-07-29'da 502 doğrulandı. |
| `reconnect_s` | `3.0` | |
| `registers` | `{nok: 100, trigger: 101}` | **Bilgi amaçlı — plc.py bu bloğu OKUMAZ, adresler kodda sabit.** |
| `timeout_s` | `0.2` | GUI thread'inde bloke ettiğinden küçük tutulmalı. |
| `type` | `modbus_tcp` | |
| `unit_id` | `0` | Sahada doğrulandı. |

### `reference_profile` (satır 82-84) / `reference_tolerances` (satır 85-89)
`count: 0, rois: {}` — temiz (bir dönem 5 referansla ~148 KB'a şişmişti). Tolerans
değerleri (`template_score_max: 5.0` vb.) yalnız `template` yönteminde — şu an pasif.

### `resolution` / `resolution2` (satır 90-95)
İkisi de `800×600`. **⚡ ÇELİŞKİ:** CLAUDE.md §12 (2026-08-10) kamera 1 için
"1456×1088 (native)" der; dosyadaki güncel değer 800×600 — ya sonradan GUI'den
değiştirilmiş ya doküman/dosya ayrışmış. Hangisi güncel niyetse teyit edilmeli.
Keskinlik önerisi: native 1456×1088 + zoom 1.0.

### `roi` (satır 96-123) — Kamera 1 analiz ayarları
| Anahtar | Değer | Not |
|---|---|---|
| `decision_method` | `hole` | `hole` \| `template`. |
| `handedness_check` | `true` | |
| `handedness_margin` / `handedness_reference` | `0.05` / (base64) | **v2 kalıntıları** — v3 kodu okumaz; elle silinebilir (~1.4 KB). |
| `handedness_version` | **`2`** | **⚠️ KRİTİK: kod 3 bekler → kamera 1'de yön kontrolü SESSİZCE, FİİLEN KAPALI.** Kamera 1 açık → ayna parça o yüzde yakalanmaz. Çözüm: ≥2 hole nokta + "🧭 Yön Referansı Al" (şu an TEK nokta var). |
| `hole_dark_value` | `70` | Koyu piksel gri eşiği. |
| `hole_dark_ratio_min` | `10.0` | **ASIL KAPI** (min açık-alan koyu%). Doküman önerisi ~20; sahada 10 (gevşek — izlenmeli). |
| `hole_dark_ratio_max` | `85.0` | Üst bant. |
| `hole_core_value` / `hole_core_ratio_min` | `40` / `2.0` | "Derinlik" — yalnız düşük zemin (açık delikler GRİ okur). |
| `hole_shape_check` | `true` | Şekil kapısı. |
| `hole_min_circularity` / `hole_min_fill` / `hole_min_aspect` | `0.55` / `0.5` / `0.5` | fill yarım-bantlıyı da eler (~0.5 vs tam ~0.95). |
| `hole_max_edge_touch` / `hole_min_blob_ratio` | `1` / `3.0` | |
| `hole_use_circle_check` | `false` | **Ölü anahtar.** |
| `notch_dark_min` / `notch_dark_max` | `50.0` / `95.0` | Öneri ~35 (oluklu ~%50, oluksuz ~%17) — 50 dar paylı; kamera 1'de notch noktası olmadığından fiilen etkisiz. |
| `point_overrides` | `{'1': {hole_core_ratio_min: 0.6}}` | Nokta başına eşik (globali ezer). |
| `reference_box` | `[201, 212]` | Eski çözünürlük dönemi kalıntısı; noktalar yeniden çizilince güncellenir. |
| `roi_types` | `{'1': hole}` | |

Dosyada yazılı olmayan ilgili anahtarlar (kod varsayılanı): `notch_shape_check` (açık),
`notch_min_blob_ratio` (~25), `notch_min_aspect` (~1.2), `notch_min_width_ratio` (~0.30),
`handedness_margin_diff` (12.0), `handedness_hole_diff` (kamera 1'de yok).

### `roi2` (satır 124-144) — Kamera 2 analiz ayarları
| Anahtar | Değer | Not |
|---|---|---|
| `handedness_check` | `true` | |
| `handedness_hole_diff` | `48.4485...` | v3 referansı; pozitif = havşalı delik SAĞDA; işaret ters + \|fark\|>12 → AYNA/TERS NOK. |
| `handedness_margin_diff` | `12.0` | |
| `handedness_version` | **`3`** | Kamera 2'de yön kontrolü AKTİF. |
| `point_overrides` | `'1': {core 10.0, açıklık 12.0}` · `'2': {core 2.0, açıklık 35.0}` · `'3': {notch 25.0}` | **⚠️ Nokta 1'in derinlik 10.0 ŞÜPHELİ** (tr_TR ayıraç hatası öncesi girildi; `1.0` yazılmış olabilir → sahada teyit). Tüm eşikler tek DOĞRU parça ölçümüne göre — hatalı parça verisi YOK, paylar bilinmiyor. |
| `reference_box` | `[971, 726]` | |
| `roi_types` | `{'1': hole, '2': hole, '3': notch}` | |

**Devralma kuralı (§13):** kamera 2 görünümünde genel eşikler kamera 1'den devralınır AMA
nokta kimliğine bağlı anahtarlar (`roi_types`, `point_overrides`, `reference_box`,
`handedness_*`) `roi2`'de yoksa DEVRALINMAZ.

### `saha_ayarlari.conf` (makine seviyesi; tek tüketici yeni_pi_kur.sh)
| Satır | Anahtar | Değer |
|---|---|---|
| 20 | `PI_STATIK_IP` | `192.168.10.50/24` (iki Pi aynı anda bu adresi kullanamaz) |
| 23 | `PLC_ARAYUZU` | `eth0` |
| 27 | `PLC_ARAYUZU_GATEWAY` | `""` (**bilerek boş** — gateway yazılırsa internet kopar) |
| 31-32 | `PLC_IP` / `PLC_PORT` | `192.168.10.10` / `502` (asıl kaynak config.yaml; conf yalnız tutarlılık denetimi) |
| 37-38 | `BEKLENEN_KAMERA_SAYISI` / `_SENSORU` | `2` / `imx296` |
| 43 | `AJAN_ADI` | `agent_yazilim_konveor` (opsiyonel) |

### `requirements.txt`
`opencv-python-headless>=4.8.0` (headless bilinçli — GUI Qt'den), `numpy>=1.24.0`,
`PyYAML>=6.0`, `PyQt5>=5.15.0` (Pi'de apt), `pymodbus>=3.6.0`; `picamera2` yorum
satırında (Pi'de apt sistem paketi). `GEREKLI_KUTUPHANELER.txt` aynı listenin insan-okur
karşılığı — elle senkron tutulur.

---

## 5. İş Parçacığı (Thread) Modeli

- **Kamera:** kamera başına bir `InspectionWorker` (QThread). GUI'ye yalnız Qt
  sinyalleriyle (kuyruklu bağlantı → thread-güvenli) kare/durum/log/hata yollar.
  PLC'den haberi YOKTUR. Kamera nesnesine yalnız worker thread'i dokunur; restart bile
  bayrak üzerinden döngü içine devredilir.
- **PLC:** tamamen **GUI thread'inde**, `_plc_timer` (`QTimer`, `plc.poll_ms` aralıklı) →
  `_poll_plc`. Modbus okuma/yazma senkron ve bloke edicidir (`timeout_s` küçük tutulmalı;
  manual modda hiç bağlanmayan `NullPLCAdapter` bu yüzden var). Analiz
  (`evaluate_with_profile`) da GUI thread'inde koşar (ROI'ler küçük — pratikte sorun değil).
- **Köprü:** tetikte GUI, worker'ın `last_raw_frame` (+ `last_frame_time`) alanını okur
  ve **kopyalar** (`_get_latest_camera_frame`). Kilit yok; tek yazar (worker) / tek okur
  (GUI) + `.copy()` + GIL yeterli. GUI'nin worker'a yazdığı alanlar
  (`_restart_camera_requested`, `_running`, `_zoom`) tekil atama.
  **Düşük FPS = bayat `last_raw_frame` = tetik anında kaymış ürün** (ölçüm: 1 ms gecikme
  ≈ 4 px kayma).
- **Gecikmeli işler (`QTimer.singleShot`):** çekim gecikmesi (`_delayed_capture`),
  HR100 reseti (1 sn), READY dönüşü (1 sn), resize sonrası yeniden ölçek (0 ms),
  panel spinbox debounce (400 ms).
- **Yeniden giriş korumaları:** `_inspection_state == BUSY` (çekim), `_capture_pending`
  (gecikmeli çekim), **`_dialog_paused`** (Ayarlar/Kontrol Noktaları açıkken poll durur
  VE gecikmiş çekim iptal edilir).
- `features.py` / `alignment.py` durumsuzdur (state yok) → yeniden-giriş sorunu yok.

---

## 6. Tuzaklar ve Saha Bilgisi

### Dosya / ortam
1. `*.sh` dosyaları **LF** olmalı (`.gitattributes` zorlar); CRLF → Pi'de `bash\r: not found`.
2. `app.png` gitignore istisnası (`!app.png`); diğer PNG'ler hariç.
3. `config.yaml` her UI etkileşiminde komple yeniden yazılır → yorumlar kaybolur, SD
   aşınması; yeni anahtar `setdefault` ile eklenir.
4. `main()` global `sys.excepthook` kurar — pythonw'da sessiz kapanma yerine dialog.
5. `CONFIG_PATH` göreli — proje kökünden başlatılmalı.
6. Test tuzakları: `load_config` varsayılan argümanı tanım anında sabitlenir (fonksiyonu
   yamala); ekransız testte `QMessageBox.warning/critical` modal → BLOKLAR, susturulmalı.

### Kamera / optik
7. **`manual_exposure_enabled: false` iken `exposure_us`/`analogue_gain` SESSİZCE
   uygulanmaz** (worker `_camera_controls` boş sözlük) — sahada yaşandı: 200 µs yazılıydı,
   kamera 19 ms oto-pozla çalışıyordu (bulanıklığın asıl sebebi). Poz göstergesi bu yüzden
   kilit durumunu (🔒/⚠ OTO) gösterir; kilit kapalıysa etiket HEP SARI.
8. **Global shutter uzun poz bulanıklığını ÖNLEMEZ** — bulanıklık poz süresiyle orantılı;
   hareketli bantta hedef ≤1 ms (saha 300-500 µs). Fiziksel sıra: poz kısalt → gain
   yükselt → aydınlatma artır.
9. **İKİ YÖNLÜ poz tuzağı:** fazla poz da öldürür — 4000 µs'de metal doyar (254), delik
   `koyu%` %31→%0.6 → "delik yok". Poz ayarlarken parlaklığa değil `koyu%` loguna bak.
   Ölçülen aralık (gain 16, ışık açık): 300 µs sağlam, **500 µs önerilen**, 2000 doyguna
   yakın, 4000 DOYGUN.
10. **Analog gain gerçek tavanı 15.7** — libcamera 251.2 bildirir ama üstü sessizce
    `DigitalGain` (gürültüyü çarpar, bilgi eklemez); UI tavanı bilinçli 16.0.
11. **Zoom yazılımdır, detay üretmez** (zoom 2'de gerçek detayın %21-54'ü); keskinlik =
    native 1456×1088 + zoom 1.0; daha büyük görüntü = OPTİK çözüm.
12. Çözünürlük/zoom değişince template referansları + snapshot geçersizlenir (ölçeğe
    bağımlı).
13. Netlik metriği gürültüyü de sayar — yalnız aynı kamera + sabit ışık/pozda kıyaslanır;
    ISP `NoiseReductionMode/Sharpness` Laplacian'ı %1400 şişirir ama bu GÜRÜLTÜ — ISP'ye
    dokunulmadı.
14. Aydınlatma DC (titreme yok, sapma %0.10); PWM/AC + kısa poz = kare kare parlaklık
    oynaması (sebepsiz NOK) riski olurdu.
15. worker.py satır 73 gölgelemesi: `camera.awb_mode`/`color_gains` fiilen ölü.
16. Worker restart'ta yeniden açılış başarısızsa thread sessizce ölür (canlı görüntü
    donması belirtisi); picamera2 açılışındaki 1.5 sn bekleme = her restart'ta ~2 sn kesinti.
17. OpenCV yedeğinde poz/gain metadata'sı yok → Poz göstergesi beslenmez.

### Analiz
18. **`_notch_shape` morfoloji sırası: ÖNCE OPEN, SONRA CLOSE** — tersi dağınık benekleri
    tek bloba birleştirip şekil kapısını çökertir → oluksuz parça yanlış OK.
19. **Açık delikler siyah değil GRİ okur (~40-70)** — `<40` tabanlı "çekirdek/derinlik"
    açık deliği yanlış elemişti; asıl ayrım AÇIK ALAN (`hole_dark_ratio_min`), `core`
    yalnız düşük zemin.
20. **Delikte İKİ alt eşik** (açıklık + derinlik) + şekil kapıları — "eşiği geçiyor ama
    NOK" karışıklığında `msg` gerçek sebebi söyler, log'a bak.
21. **`_check_handedness` sürüm uyuşmazlığında SESSİZCE geçer** — "yön kontrolü
    çalışmıyor" şikayetinde ilk bakılacak yer `handedness_version` (kamera 1'de v2
    kalıntısı → fiilen kapalı). `results["YON"]` satırının panelde görünmemesi hata değil,
    kontrolün devrede olmadığının işaretidir; "yon kontrol zayif" mesajı geçirir ama
    referans yeniden alınmalı demektir.
22. **İki farklı `aspect` tanımı:** `_hole_shape` = min/max (1'e yakın = daire),
    `_notch_shape` = bw/bh (>1 = yatay-uzun).
23. **`checked_any_roi` emniyeti:** aktif kusur-ROI'si yoksa global NOK — boş kurulum
    asla OK üretmez (`yon` noktaları sayılmaz).
24. **`reference_box` ölçekleme iki ucu keskin:** kutu oynarsa TÜM noktalar birden
    kayar/ölçeklenir (~%3 kutu oynaması → 11-14 px ROI kayması → yanlış NOK olabilir).
    Alternatif `alignment.mode: off` — hangisi daha az yayılım verir ÖLÇÜLMELİ.
    Template yolu `reference_box` ölçeklemez.
25. `roi_types`'ta olmayan ad varsayılan `hole`; ad içinde "oluk/çentik/slot/kanal/notch"
    geçerse config'siz de `notch` olur — adlandırma karar mantığını değiştirebilir.
26. Ölü kod/anahtarlar: `_has_circle`, `hole_use_circle_check`, `calibration.*`,
    v2 `handedness_reference`/`handedness_margin`, `_write_holding_registers` (plc.py),
    `reference_profile` (hole yönteminde okunmaz).

### UI
27. Panel eşik kutuları programatik doldurulurken `blockSignals(True)` şart (sonsuz
    döngü); testte korunuyor.
28. `wheelEvent`'te `ignore()` kullan, `accept()` değil (sayfa kaydırma ölür). Editördeki
    `_NoWheelSpin` bağımsız kopyadır — yeni sayısal girişler aynı sınıfı kullanmalı.
29. tr_TR ondalık ayıraç: düz `QDoubleSpinBox` `0.5` → sessizce `5.0` yapar (eşik 10
    katına çıkar) — `NoWheelDoubleSpinBox`/`_NoWheelSpin` düzeltmeleri şart.
30. "⚙ Ayarlar" bilinçli SOL PANELDE (kamera satırında olsaydı kamera kapatılınca
    erişilemezdi); regresyon testi var.
31. ESC editörde diyaloğu kapatmaz, çizimi iptal eder (bilinçli override). Çizim modu tek
    seferlik; ≤5px sürüklemede açık kalır. Editör listesi ad ayrıştırması `"  ("` ayıracına
    dayanır. Nokta silinince override + tip + pasiflik birlikte silinir. Genel değere eşit
    override yazılmaz.
32. Önizleme analizleri (`part_id=0`) PLC'ye yazmaz ama loglanır ve panele düşer — eşik
    ayarı ürün geçirmeden yapılır.

### PLC / saha
33. Sahaya geçerken "Elle Çekim Modu" KAPALI olmalı (açıksa tetik beklenmez).
34. **İKİ Pi AYNI ANDA ASLA ÇALIŞMASIN** — ikisi de HR100'e yazar → PLC çelişkili OK/NOK
    (son yazan kazanır, emniyet açığı). Yeni Pi açılmadan eskisi kapatılır.
35. **eth0'a GATEWAY verme** — internet wlan0'dan; gateway yazılırsa internet PLC ağına
    yönlenip kopar.
36. **Kamera kabloları AYNI CSI soketlerine** (`cam0 = i2c@88000`, `cam1 = i2c@80000`);
    ters takılırsa tüm noktalar/eşikler/yön referansı yanlış kameraya uygulanır.
37. **Düşük FPS tetikli sistemde zararsız DEĞİLDİR** — son kare kullanıldığından bayat
    kare = konum kayması (fps-10 önerisi açıkça geri alındı). Ölçüm (2026-08-03, üç
    deney): `poll_ms 100→20` + `fps 20→60` ile temiz tespit %69→%100, `y` yayılımı
    309→114 px. ⚡ ÇELİŞKİ/RİSK: 2026-08-10'da kullanıcı fps'i tekrar 20'ye düşürdü —
    kayma geri gelebilir, izlenmeli.
38. ERROR durumu yapışkandır (READY'ye ancak yeni tetik/PLC yeniden bağlanınca); HR100
    reset başarısızlığı `_nok_reset_pending` ile telafi edilir; kopmada kenar sıfırlama
    bekleyen parçayı kurtarır (olası çift tetik bilinçli tercih).
39. Hata = NOK yazımı (`publish_error` HR100=1) — denetlenemeyen parça asla OK geçmez.
40. `plc_smoke_test.py --write-test-register` bant çalışırken KULLANILMAMALI.
41. Kalibrasyon karesi ≠ üretim karesi (konum + aydınlatma + operatör eli üç fark) —
    ayar GERÇEK üretim karesi üzerinden yapılır: noktaları sil → otomatikte ürün geçir →
    editör tetik karesiyle açılır → çiz → Kaydet.

### 2026-09-23 incelemesi — bulunan gizli hatalar ve DURUMU
- ✅ **DÜZELTİLDİ — `worker.py::_open_camera` gölgeleme:** picamera2 yapılandırması artık `pc_cfg`;
  `camera.awb_mode` / `color_gains` gerçekten uygulanıyor (test: sahte picamera2 ile `set_controls`
  çağrıları doğrulandı). Eski hata: `cam_cfg` (config sözlüğü) picamera2 dict'iyle üzerine
  yazılıyor, iki anahtar HİÇ uygulanmıyordu.
- ✅ **DÜZELTİLDİ — `main.py::_apply_settings` aç/kapa sırası:** iki döngü: önce tüm `_stop_camera`
  (thread wait), sonra `_start_camera`. 07:10:43 arızası (K1 aç + K2 kapa aynı anda → "Camera
  __init__ sequence did not complete" → OpenCV yedeği, kare yok) bu sırayla önlenir.
- ✅ **EKLENDİ — `worker.py` yedekten geri dönüş:** `_on_fallback` + `_last_picam_retry` +
  `PICAM_RETRY_S=10`; `run()` içinde 100 ardışık başarısız okumadan sonra `_fallback_retry_due`
  True ise `_restart_camera_requested` → `_open_camera` Picamera2'yi yeniden dener.
  `_release_camera` nesne TİPİNE göre kapatır (`hasattr(cap, "release")` → OpenCV; değilse
  picamera2 stop/close) — eskiden yedek VideoCapture sızıyordu.
- ✅ **DÜZELTİLDİ — yarım kalan Picamera2 nesnesi (`_open_camera` except):** `cam` oluşturulup
  configure/start'ta patlarsa `cam.close()` çağrılır; aksi halde kamera süreçte ACQUIRED kalıyor ve
  sonraki her `Picamera2(idx)` "Camera __init__ sequence did not complete" veriyordu (2026-09-23
  07:49 sahada görüldü: yeniden denemeler bu yüzden tutmadı).
- **TUZAK (işletme):** uygulamayı kapatırken pid'i `pgrep -f "^/usr/bin/python3 main.py"` ile al;
  `pgrep -f "python.*main.py" | head -1` nohup sarmalayıcısını verebilir → eski örnek kapanmaz, iki
  örnek aynı anda PLC'ye yazar. Ajan başlatması: `setsid nohup env DISPLAY=:0 WAYLAND_DISPLAY=wayland-0
  XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus python3 main.py
  >> ~/konveyor_loglari/uygulama-stdout.log 2>&1 &` (cwd = proje kökü; CONFIG_PATH göreli).
- ✅ **DÜZELTİLDİ — `SettingsDialog.RESOLUTIONS`:** imx477 modları eklendi (4056x3040, 2028x1520,
  2028x1080, 1332x990) + combo/poz ipuçları.
- ✅ **DÜZELTİLDİ — Enter/BOŞLUK koruması:** `MainWindow.keyPressEvent` odak QAbstractSpinBox /
  QLineEdit / QTextEdit / QComboBox'taysa çekim tetiklemez (QSpinBox Enter'ı ignore edip üste
  geçiriyordu → eşik kutusunda Enter, Elle Çekim Modunda çekim yapıyordu).
- ✅ **DÜZELTİLDİ (09:20, sahada GERÇEK olayla doğrulandı) — `closeEvent` `worker.wait()`
  zaman aşımı:** eskiden argümansız (süresiz) `wait()` vardı; gdb ile canlı donmuş sürece
  bağlanıp doğrulandı — ana thread `pthread_cond_wait`'te, worker thread'i GIL/kare bekleme
  noktasında, klasik karşılıklı kilitlenme. Artık `_stop_camera` ile aynı mantık: `wait(3000)`
  (sınırlı); zaman aşımına uğrarsa `event.accept()` ile pencere yine KAPANIR ve `os._exit(1)`
  ile zorla sonlandırılır (interpreter kapanışı da aynı şekilde asılabileceği için normal
  Python çıkışı beklenmez). 11 ekransız testle doğrulandı (`test_closeevent.py`). Kameranın
  NEDEN donduğu (kök sebep) hâlâ açık soru; `[HATA] Kamera thread'i 3 sn içinde kapanmadı`
  logu görülürse kamera tarafı ayrıca incelenmeli.
- ⏳ `main.py` `if True:` kalıntı (zararsız). `features._has_circle` ve config `hole_use_circle_check`
  ölü. `reference_profile`/template yolu yalnız eski config için.
- ⏳ `tools/plc_smoke_test.py` unit_id varsayılanı 1 (config'te 0; config okunduğu için sorun yok).
- ✅ Depo: `.gitignore` (`.claude/*` hariç `!.claude/skills/`, venv, pycache, *.png hariç app.png,
  *.log) + `.gitattributes` (*.sh LF, *.bat CRLF) yeniden eklendi. ⏳ `origin` GitHub'da yok.
- **TUZAK (test):** `MainWindow.LOG_DIR` sınıf niteliği → ekransız testte `_append_log` GERÇEK saha
  loguna yazar; testte `main.MainWindow.LOG_DIR = <geçici>` yap (2026-09-23'te 24 satır sızdı, silindi).

### Sayaç + parça CSV + PDF rapor (2026-09-23, kullanıcı isteği; resim kaydı yerine)
- **Veri:** `self._counters` = `{baslangic, toplam, ok, nok, hata, noktalar{etiket{kategori:n}},
  hata_sebepleri{sebep:n}, son_nok[{zaman,resim,sebep}] (son 500)}`; `~/konveyor_loglari/sayac.json`
  (`_load_counters` başlangıçta, `_save_counters` her parçada, tmp+`os.replace`).
- **CSV:** `_append_part_csv` → `~/konveyor_loglari/parca-YYYY-AA-GG.csv` (`;`): zaman, resim,
  kaynak (plc/elle), sonuc (OK/NOK/HATA/SIFIRLA), gecikme_ms, hatali_noktalar, sebepler, olcumler
  (`etiket: koyu X / çek Y`).
- **Kayıt noktası:** `_record_part(part_id, is_ok, {cam_no: results}, source, error=None)`;
  `_capture_full_frame` içinde 4 çağrı (kare yok → error; `_production_ready_error` → error;
  analiz sonrası; `except` → error). `_handle_snapshot` her analizde `self._last_results[cam_no] =
  results`. Etiket: `ad (delik|çentik|yön)`, `YON`→`YÖN`, çok kamerada `K{n} ` öneki. Sebep
  kategorisi `_nok_reason_category(msg)` (anahtar kelime tablosu; bilinmeyen → parantez öncesi).
- **UI:** `_refresh_counter_panel` (lbl_counter_period/total/ok/nok/err/breakdown); `_reset_counters`
  (QMessageBox.question → Yes: yeni `_bos_sayac()`, CSV'ye SIFIRLA satırı, log).
- **Paket (13:45):** `inspection.paket_adedi` (`_paket_adedi()`, vars. 100) ↔ `spin_paket`
  (`_on_paket_adedi_changed` → config + `paket_esik = (paket_ok//n+1)*n`). Sayaçta `paket_ok`,
  `paket_esik`. `_record_part`: OK → `paket_ok += 1`; `>= paket_esik` → `QTimer.singleShot(0,
  _paket_uyarisi)`. `_paket_uyarisi`: beep + NonModal `QMessageBox` (Sıfırla varsayılan / Devam
  et), `finished` → `_paket_pencere_kapandi` → `_paket_sifirla` (paket 0, esik n, CSV `PAKET`)
  ya da `_paket_devam` (esik += n). `_paket_penceresini_kapat` (parti sıfırlamada, sinyalsiz).
  `_refresh_counter_panel`: `lbl_paket` "Paket: n / esik" / turuncu "PAKET DOLDU".
- **Spinbox okları:** `STYLESHEET` up/down-button/arrow kuralları (`__UP__/__DOWN__`),
  `_arrow_icon_paths()` 10×6 PNG'leri `tempfile.gettempdir()/konveyor_ui/` altına çizer,
  `build_stylesheet()` yolları yerine koyar; `MainWindow.__init__` `setStyleSheet(build_stylesheet())`.
- **PDF:** `_build_report_html` (özet, dağılım, sistem hataları, son 300 NOK, CSV yolu) →
  `_write_report_pdf(path)` (`QTextDocument.print_` + `QPrinter(PdfFormat, A4)`) → `_export_pdf`
  (`QFileDialog.getSaveFileName`, varsayılan `~/Desktop/kalite_raporu_%Y-%m-%d_%H%M.pdf`,
  `QDesktopServices.openUrl`). Test: scratchpad `test_sayac.py` (27 test).

### Çekim gecikmesi — ana ekran + zamanlama damgası (2026-09-23, kullanıcı isteği)
- **UI:** sol panel "Çalışma Modu" → `spin_trigger_delay` (NoWheelSpinBox 0-5000 ms, adım 10,
  `keyboardTracking(False)`) → `_on_trigger_delay_changed` → `inspection.trigger_delay_ms` +
  `_save_config` + `[Gecikme]` log. `_apply_settings` Ayarlar'dan gelen değeri kutuya `blockSignals`
  ile yansıtır (iki kutu hep eşit).
- **Zamanlama:** `_capture_from_plc` tetik anında `self._trigger_time = time.time()`;
  `_capture_full_frame(source="plc"|"manual")` kareleri aldıktan sonra `_latest_frame_age_ms` ile
  kare yaşını ölçer, `self._last_capture_note = "Gecikme X ms | kare Y ms"` (elle: "Elle cekim"),
  loga `| gecikme X ms, tetikten Z ms sonra, kare yaşı Y ms` (başarılı analizde `[Tetik] Tam resim
  alındı…`, nokta yokken `[Kurulum] … saklandı (kamera 1) | …`).
- **Damga:** `_stamp_capture_note(img)` resmin sol altına siyah kutu + sarı ASCII yazı (cv2 Türkçe
  harf çizemez; punto resim genişliğine göre 0.45-0.8). `_handle_snapshot` → `display_img`
  (features'ın kopyası) damgalanır; `_store_setup_snapshot` → ekrana `analysis_img.copy()` damgalı
  gider, **saklanan `_last_snapshot` temiz kalır** (editör/analiz temiz kare kullanır).
- `_manual_capture` → `source="manual"`; `_delayed_capture` → `"plc"`. Kare seçimi değişmedi:
  worker'ın SON karesi (fps'e bağlı ≤1 kare periyodu belirsizlik; 20 fps'te ≤50 ms).

### Güncel açık riskler (2026-08-10 durumu)
- (1) fps 20 tetik kaymasını geri getirebilir (beklenen `y` yayılımı ~2×).
- (2) Kamera 1'de yön kontrolü fiilen kapalı (`handedness_version: 2`; ≥2 hole nokta +
  yeni v3 referansı gerek).
- (3) Kamera 1'in tek noktası + `reference_box [201,212]` eski çözünürlük döneminden —
  gerçek üretim karesinde yeniden çizilmeli.
- Nokta 1 (kamera 2) derinlik eşiği 10.0 şüpheli; hatalı parça verisiyle eşik payları
  hiç doğrulanmadı.
- ⚡ ÇELİŞKİ: `manual_exposure_enabled` config'te `false` ↔ CLAUDE.md "kilitlendi
  (`true`)"; `resolution` config'te 800×600 ↔ CLAUDE.md "1456×1088". İkisi de sahada
  teyit edilmeli.

---

## 7. Kurulum / Dağıtım

### Raspberry Pi (saha)
- **Ortam:** Debian 13 (trixie), aarch64, Python 3.13. `python3-picamera2` ve
  `python3-pyqt5` **apt'tan**; venv `--system-site-packages` ile kurulur ki bunları
  görsün. **Sahadaki mevcut Pi'de venv YOK** — paketler apt'tan, sistem python'u
  kullanılıyor; `calistir.sh` iki durumu da destekler.
- **Tek komut kurulum:** `bash tools/kurulum_pi.sh` (apt + venv + pip + ikon).
  Yalnız ikon: `bash tools/install_pi.sh`.
- **Çalıştırma:** `./calistir.sh` ya da menüdeki "Konveyör Denetim Sistemi" ikonu.
  Açılışta doğrudan ROI/Eşik ekranı (mod seçme diyaloğu yok; PaDiM kaldırıldı).
- **PLC testi:** `veri_toplama/bin/python tools/plc_smoke_test.py` (venv'siz `python3`).

### Windows (geliştirme)
- Python 3.12 + venv `veri_toplama`; PyQt5/opencv pip'ten (elle kurulum).
- Çalıştırma: `calistir.bat` (çift tık; pythonw, konsolsuz, bloklamaz) ya da
  `veri_toplama\Scripts\python.exe main.py`.
- Çapraz-makine: Windows ve Pi aynı repoyu paylaşır → push öncesi `git pull`, kör
  `--force` yok.

### Yeni Pi'ye taşıma (donanım aynı, yalnız Pi değişiyor)
1. **İlk iş:** `bash tools/yeni_pi_kur.sh --kontrol` (hiçbir şeyi değiştirmez, 6 maddelik
   fark raporu). Eksik varsa onay alarak `--kontrol` olmadan çalıştır (betik her
   değiştirici adımda ayrıca onay sorar).
2. **Git ile OTOMATİK taşınan (yeniden kalibrasyon GEREKMEZ):** `config.yaml` — kontrol
   noktaları, nokta başına eşikler, poz/gain kilidi, yön referansı (v3), PLC ayarları,
   `reference_box` — ve tüm kod (kameralar/optik/ışık değişmediği sürece).
3. **Git'e girmeyen, elle yapılacak:** sistem paketleri (`kurulum_pi.sh`); eth0'a statik
   `192.168.10.50/24` (NetworkManager profili — nmcli; GATEWAY YOK); uzaktan kontrol
   ajanı servisi (opsiyonel, `~/.config/systemd/user/` + linger); `.claude/` ve kişisel
   yollar (gitignore'da).
4. **SIRA:** eski Pi'yi KAPAT → yeni Pi'ye Debian 13 + git clone → `kurulum_pi.sh` →
   statik IP → kameraları AYNI CSI soketlerine tak → `./calistir.sh` → canlı görüntüde
   kamera eşleşmesini doğrula (Kamera 2 havşalı yüzü görmeli) → PLC'ye tek ürün geçirip
   HR100'ü izle.
5. **Üç gerçek çakışma riski:** iki Pi aynı anda çalışmasın (HR100); statik IP çakışması
   (.50 tek makinede); kamera portları ters takılmasın.

### Geri dönüş (reversibility)
- `git checkout surum1-sablon` → delik tespiti öncesi (template) sürüm.
- Yalnız kararı geri almak: `config.yaml → roi.decision_method: template`.
- PaDiM/ONNX geri gerekirse git geçmişinde (2026-07-09'da komple kaldırıldı).
