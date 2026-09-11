# analyzer_v3 — PDF şema → pano içi bağlantı çıkarımı (yerel pilot)

Müşteri EPLAN P8 PDF'inden **pano içi fiziksel tel bağlantılarını** kanıta dayalı biçimde
çıkaran yerel araç. Tahmin yok: her bağlantının çizimde izlenmiş bir yolu, her elektriksel
değerin adı konmuş bir kaynağı var. Hiçbir şey otomatik onaylanmaz.

> **Bu branch yalnız kod ve dokümandır.** Müşteri PDF'leri, TROESTER/UVP standart dosyaları
> ve bunlardan türetilmiş pilot çıktıları (`output/`) `.gitignore` ile hariç tutulmuştur ve
> bu depoya **yüklenmez**. Araç, çalışmak için yerelde bu dosyalara ihtiyaç duyar.

## Ne yapar

- PDF'in vektör geometrisini ve yazılarını okur (OCR değil; `pdfplumber` + ham çizgi/eğri).
- Sayfa kimliğini çözer: Anlage / Einbauort / Blatt / belge türü; kapsam filtresi uygular.
- Onaylı bir sembol örneğinden **benzer adaylar** bulur; cihaz ve pin adlarını her örnek
  için **o sayfanın kendi yazısından** yeniden okur — şablondan kopyalamaz.
- Çizgiyi uçtan uca izler; ortak potansiyel ağı ile fiziksel tel çiftini **ayrı** tutar.
- Kesikli/noktalı hatları ölçer ve **önerir**; insan onayı olmadan graf birleştirmez.
- Sayfa devamlarını hedef sayfanın kendi geometrisiyle karşılıklı doğrular.
- Kesit ve rengi ancak devre görevi kanıtlandıktan sonra, kaynak zinciriyle doldurur.

## Ne yapmaz

Üretim listesi veya EPLAN import dosyası üretmez. Kullanıcı adına onay vermez. Ortak
potansiyelden daisy-chain türetmez. Akıma bakarak kesit hesaplamaz. Siyah çizgiden renk
çıkarmaz.

## Kurulum ve çalıştırma

```bash
pip install -r analyzer_v3/requirements.txt

# Yeni pilot çalışması hazırla (kaynak PDF yerelde olmalı)
python -m analyzer_v3.prepare --pages 4,2,5,28,36

# Var olan çalışmaya sayfa ekle
python -m analyzer_v3.prepare --run <run-klasoru> --add-pages 22

# Yerel ekran
python -m analyzer_v3.server        # http://127.0.0.1:8765
```

`/` sade durum ekranı (PDF solda, bulunanlar ve senden beklenenler sağda),
`/ayrinti` ayrıntılı teknik tablo.

## Testler

```bash
python -m unittest discover -s analyzer_v3/tests -t .
```

Testler gerçek müşteri PDF'i ve bir pilot çalışma klasörü gerektirir; bu depoda yoklar.
Temiz bir klonda **çalışmazlar** — bu beklenen durumdur.

## Yapı

| Yol | İş |
|---|---|
| `analyzer_v3/prepare.py` | İzole pilot çalışması; ham geometri, 300 DPI render, belge indeksi |
| `analyzer_v3/document.py` | Sayfa kimliği, çapraz referans, etiket türü, klemens çubuğu ve PLC modülü sahipliği |
| `analyzer_v3/geometry.py` | Muhafazakâr çizgi grafı; noktasız kesişim birleşmez |
| `analyzer_v3/similarity.py` | Şablondan aday bulma; sembolün kendi şekli ile çevre tesisatını ayırır |
| `analyzer_v3/dashed.py` | Kesikli hat ölçümü ve birleştirme önerisi |
| `analyzer_v3/service.py` | Tablo, kapsam, inceleme kaydı, kesikli hat köprüsü, sade durum özeti |
| `analyzer_v3/store.py` | Sürümlü SQLite işaret/inceleme günlüğü |
| `tools/sayfa_excel.py` | 37 sütunlu EPLAN inceleme çıktısı + kaynak/belirsizlik sayfaları |
| `tools/crop.py` | PDF koordinatıyla sayfa kırpma (kanıt görseli) |

## Bağlayıcı kurallar

`MAIN.md` bu projenin bağlayıcı elektrik yönergesidir; `PLAN.md` uygulama durumunu tutar.
Her ikisi de değişikliklerden **önce** okunmalıdır.
