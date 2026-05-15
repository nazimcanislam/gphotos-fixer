# gphotos-fixer 📸

**Gerçekten çalışan bir Google Photos Takeout düzenleyici.**

Google Takeout dışa aktarmaları bir kaos: tutarsız JSON sidecar isimleri, Windows MAX_PATH sınırı nedeniyle kesilen dosya adları, tek bir metadata dosyasını paylaşan kopyalar ve gerçek tarih yerine bugünün tarihini alan dosyalar. Mevcut araçların çoğu bu edge case'lerde sessizce başarısız olur.

`gphotos-fixer`, 12.000'den fazla dosyalık gerçek bir Takeout arşivi üzerinde çalışılarak, yol boyunca karşılaşılan her hata düzeltilerek geliştirildi. Diğerlerinin kaçırdığı şeyleri halleder.

---

## Özellikler

- **Tarihe göre düzenler** → `YYYY/AA/dosyaadı` yapısı
- **Albümleri korur** → `albums/<albüm adı>/` klasörleri olduğu gibi saklanır
- **Dosya tarihlerini düzeltir** → `mtime` gerçek çekim tarihine ayarlanır
- **Güçlü JSON eşleştirme** — bilinen tüm Takeout sidecar adlandırma varyantlarını destekler:
  - `foto.jpg.json`
  - `foto.jpg.supplemental-metadata.json`
  - Kesik varyantlar: `.suppl.json`, `.supplemen.json`, `.supplemental-met.json`, vb.
  - Uzantı değiştirilmiş: `foto.json`
  - Uzantı kesik: `foto.jp.json`
  - Sonda noktalama: `foto_.mp4` → `foto.json`
  - JSON'u paylaşan kopyalar: `lp_image (21)(1).jpeg` → `lp_image (21).jpeg.json`
- **Windows MAX_PATH güvenli** — yol kesme sorunlarını önlemek için `glob()` yerine `os.listdir()` kullanılır
- **Duplicate tespiti** — MD5 hash kontrolü; aynı dosyaları atlar, çakışanları yeniden adlandırır
- **Gelecek tarih tespiti** — geçerli yıldan büyük timestamp'li dosyalar `suspicious_date/` klasörüne alınır
- **Dry-run modu** — tek bir byte yazmadan ne olacağını önizle
- **Kaynak/çıktı sayısı doğrulama** — eksik dosya varsa uyarır
- **Opsiyonel EXIF fallback** — JSON yoksa Pillow aracılığıyla `DateTimeOriginal` okur
- **Dosya adı pattern fallback** — `IMG_20230615_143000`, `2023-06-15`, `1702044110343` gibi kalıplardan tarih çıkarır

---

## Gereksinimler

- Python 3.10+
- `Pillow` *(opsiyonel)* — EXIF tarih okuma için

---

## Kurulum

```bash
git clone https://github.com/YOUR_USERNAME/gphotos-fixer.git
cd gphotos-fixer
pip install Pillow   # opsiyonel ama önerilir
```

---

## Kullanım

### İnteraktif mod

```bash
python -m gphotos_fixer
```

Araç giriş ve çıkış klasörlerini sorar, başlamadan önce onay ister.

### Non-interaktif (CLI)

```bash
python -m gphotos_fixer \
  --input  "/path/to/Takeout/Google Fotoğraflar" \
  --output "/path/to/Düzenlenmiş_Fotoğraflar"
```

### Dry-run — dosya yazmadan önizleme

```bash
python -m gphotos_fixer \
  --input  "/path/to/Takeout/Google Fotoğraflar" \
  --output "/path/to/Düzenlenmiş_Fotoğraflar" \
  --dry-run
```

### Tüm parametreler

| Parametre | Kısa | Açıklama |
|-----------|------|----------|
| `--input DIR` | `-i` | Takeout arşivindeki Google Fotoğraflar klasörü |
| `--output DIR` | `-o` | Hedef klasör |
| `--dry-run` | | Dosya yazmadan simüle et |
| `--quiet` | `-q` | Sadece özeti göster, dosya bazlı çıktıyı gizle |
| `--version` | | Sürümü yazdır ve çık |
| `--help` | `-h` | Yardımı göster |

---

## Çıktı yapısı

```
Düzenlenmiş_Fotoğraflar/
├── 2021/
│   ├── 06/
│   │   ├── IMG_20210612_143022.jpg
│   │   └── ...
│   └── 11/
├── 2022/
├── 2023/
├── albums/
│   ├── Kediler 🐱/
│   └── Ankara Gezisi/
├── unknown_date/       ← tarihi belirlenemeyen dosyalar
└── suspicious_date/    ← bozuk metadata nedeniyle gelecek tarihli dosyalar
```

---

## Tarih çözümleme nasıl çalışır?

Her dosya için şu kaynaklar sırayla denenir:

1. **Takeout JSON sidecar** — `photoTakenTime` veya `creationTime` alanı
2. **EXIF metadata** — `DateTimeOriginal` (Pillow gerektirir)
3. **Dosya adı pattern'ları** — `IMG_20230615_143022`, `2023-06-15`, `1702044110343` gibi

Hiçbirinden geçerli tarih elde edilemezse dosya `unknown_date/` klasörüne koyulur.

---

## Neden sadece gpth kullanmıyorsunuz?

[GooglePhotosTakeoutHelper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) bu iş için en bilinen araç; ancak belirli Takeout yapılarında başarısız olabiliyor ve yardımcı olmayan hata mesajları veriyor. `gphotos-fixer`, derlenmiş bağımlılığı olmayan, şeffaf mantıklı ve karşılaştığımız her edge case için açık çözüm içeren saf Python bir alternatif.

---

## Aynı geliştiriciden

Google Takeout fotoğraflarınızı kurtardınıza göre, şimdi sıkıştırmak isteyebilirsiniz.

**[Shrinkify](https://github.com/nazimcanislam/shrinkify)**, aynı geliştirici tarafından yapılmış bir masaüstü uygulamasıdır. Medya kütüphanenizi — video, fotoğraf ve daha fazlasını — donanım hızlandırmalı kodlama kullanarak tekilleştirir ve sıkıştırır.

İki araç doğal bir akış oluşturur: `gphotos-fixer` Takeout arşivinizi düzenler, Shrinkify sonucu temizler.

---

## Claude ile yapıldı

Bu proje, [Nazımcan İslam](https://github.com/YOUR_USERNAME) ile [Claude](https://claude.ai) (Anthropic'in yapay zeka asistanı) arasındaki gerçek bir iş birliğiyle oluşturuldu.

Geliştirme süreci gerçek anlamda iteratifti: 12.000'den fazla dosyalık gerçek bir Takeout arşivi başından sonuna test vakası olarak kullanıldı. Kesik JSON adları, Windows yol limitleri, kopya numaralandırma, bozuk timestamp'ler — her sorun gerçek çıktıdan teşhis edildi ve anında düzeltildi. Ortaya çıkan araç, varsayılan sorunlara değil gerçek sorunlara göre şekillendi.

Fotoğraflarınızı kurtardıysa, bu ortak bir başarı.

---

## Lisans

[MIT](LICENSE)
