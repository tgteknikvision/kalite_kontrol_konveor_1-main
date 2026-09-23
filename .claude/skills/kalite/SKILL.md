---
name: kalite
description: Konveyör bandı kalite kontrol projesinin hafızası ve çalışma günlüğü. Bu projede (kamera/PLC/ROI/delik denetimi, Raspberry Pi saha sistemi) HERHANGİ bir soru, teşhis ya da değişiklik yapılırken kullan. Program mimarisini ve tüm geçmiş çalışmaları yükler; her turdan sonra günlüğü ve saha durumunu günceller. Türkçe.
---

# /kalite — Konveyör Kalite Kontrol Hafızası

Bu skill, konveyör bandı görsel kalite kontrol projesinin **kalıcı hafızasıdır**.
Amaç: her oturumda program mantığını ve tüm geçmiş çalışmayı hatırlamak, yapılan her
işi kaydetmek, bilgiyi sürekli güncel tutmak. Kullanıcı Türkçe konuşur; sen de Türkçe cevap ver.

## ⚡ SKILL ÇAĞRILINCA İLK İŞ (her /kalite'de)

Aşağıdaki dosyaları **Read ile oku** ve bağlamına al (yoksa atla, aşağıda üret):
1. `bilgi/saha_durumu.md` — donanımın/sahanın ŞU ANKİ durumu (en kritik, en güncel).
2. `bilgi/calisma_gunlugu.md` — kronolojik çalışma günlüğü (ne yaptık, ne konuştuk).
3. `bilgi/program_mimarisi.md` — programın dosya dosya, fonksiyon fonksiyon mantığı.
4. Proje kökündeki `CLAUDE.md` — kararlar, tuzaklar, saha tarihçesi (§12).

Bu dördü seni tam bağlama getirir: **programın nasıl çalıştığını, sahada ne durumda
olduğumuzu ve daha önce ne konuşup ne yaptığımızı** bilirsin. Sonra kullanıcının
sorusuna geç.

## 📝 HER TURDAN SONRA (SORMADAN, OTOMATİK) — hafızayı güncel tut

Kullanıcının sorusuna cevap verdikten / bir iş yaptıktan **hemen sonra**, ilgili olanları
güncelle (izin bekleme):

- **`bilgi/calisma_gunlugu.md`** → EN ÜSTE yeni bir madde ekle:
  `## YYYY-AA-GG SS:DD — <kısa başlık>` altında: kullanıcı ne sordu/istedi, ne bulundu/yapıldı,
  varılan sonuç, açık kalan iş. Kısa ama bilgi dolu yaz (gelecekteki sen okuyacak).
  Bugünün tarihini ortam bağlamındaki "Today's date"ten al.
- **`bilgi/saha_durumu.md`** → donanım/ışık/kamera/PLC/eşik durumu DEĞİŞTİYSE ilgili satırı
  revize et (üstüne yaz, eskisini "tarihçe" olarak bırakma; bu dosya HEP güncel gerçeği tutar).
- **`bilgi/program_mimarisi.md`** → **kodda değişiklik yaptıysan** etkilenen bölümü revize et
  (fonksiyon/satır/mantık). Belge ile kod asla ayrışmasın.
- **Proje `CLAUDE.md`** → proje kuralı gereği (bkz. CLAUDE.md başındaki "ÇALIŞMA KURALI")
  anlamlı kod/konfig değişikliğinden sonra ilgili bölümü + §12'yi güncelle, commit + push et.

Kural: **Küçük bir soru-cevap bile günlüğe düşer.** "Konuşmaları bu bilgisayara kaydet"
isteğinin karşılığı budur — her anlamlı alışveriş `calisma_gunlugu.md`'ye işlenir.

## 🔧 KOD DEĞİŞİKLİĞİ YAPARKEN

1. Değişikliği yap. 2. `program_mimarisi.md` + `CLAUDE.md`'yi güncelle. 3. `calisma_gunlugu.md`'ye
işle. 4. Commit + push (CLAUDE.md kuralı; `Co-Authored-By` satırını koru). Kör `--force` yok;
gerekirse önce `git pull`.

## 🗂️ Bilgi tabanı dosyaları

| dosya | içerik | ne zaman güncellenir |
|---|---|---|
| `bilgi/saha_durumu.md` | donanım/ışık/kamera/PLC/eşiklerin ŞU ANKİ durumu | durum her değiştiğinde (üstüne yaz) |
| `bilgi/calisma_gunlugu.md` | kronolojik oturum/konuşma günlüğü | HER turdan sonra (en üste ekle) |
| `bilgi/program_mimarisi.md` | programın tam teknik mimarisi | kod değişince |

## Mimariyi sıfırdan yeniden üretmek gerekirse

`bilgi/program_mimarisi.md` yoksa ya da baştan çıkarılması istenirse: `main.py`,
`inspector/*.py`, `config.yaml`, `tools/*`, `calistir.sh` dosyalarını **baştan sona** oku
(gerekirse Workflow ile paralel ajanlara dağıt) ve tek bir Türkçe mimari referans olarak
`bilgi/program_mimarisi.md`'ye yaz. Bölümler: genel akış, dosya haritası, modül modül
fonksiyon+satır dökümü, config anahtar referansı, thread modeli, tuzaklar, kurulum.
