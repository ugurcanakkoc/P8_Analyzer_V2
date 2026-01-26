# P8 Analyzer V2

P8 formatindaki elektrik semalarini analiz eden profesyonel bir PDF tabanli arac. Otomatik olarak terminalleri (klemensler) tespit eder, etiketleri okur ve baglanti raporlari (netlist) olusturur.

> **Bekleyen gorevler ve bilinen sorunlar icin [OPEN_TASKS.md](OPEN_TASKS.md) dosyasina bakin.**

## Ozellikler

- **Vektor Analizi**: PDF vektor verilerini ayristirarak yapisal elemanlari (cizgiler, daireler, yollar) tespit eder
- **Terminal Tespiti**: Elektrik semalarindaki terminal bloklarini icbos daireler olarak tanimlar
- **Hibrit Metin Tanima**: Dogru etiket okuma icin PDF metin katmanini OCR yedegi ile birlestirir
- **Akilli Gruplama**: Miras algoritmasiyla grup etiketleri (-X1, -X2 vb.) atar
- **Pin Tespiti**: Komponent kutulari icindeki kablo uclarinda pin etiketlerini bulur
- **Kablo Anotasyon Yakalama**: Semalardan kablo anotasyon etiketlerini tespit eder ve okur
- **Baglanti Raporlari**: Terminal-komponent baglantilarini gosteren netlist olusturur
- **Interaktif Arayuz**: PDF'lerde gezinin, komponent kutulari cizin, analiz sonuclarini gorun
- **CLI Destegi**: Toplu isleme ve otomasyon icin arabirim

## Ekran Goruntuleri

Uygulama sunlar saglar:
- Zum ve kaydirma ozellikleri ile PDF goruntuleyici
- Terminal overlay gorsellestirmesi
- Analiz sonuclari icin log paneli
- Baglanti raporu olusturma

## Kurulum

### On Kosullar

- Python 3.8+
- Windows (test edildi), Linux/macOS (calismali)

### Sanal Ortam ile Kurulum (Onerilen)

```bash
git clone https://github.com/your-repo/P8_Analyzer_V2.git
cd P8_Analyzer_V2

# Sanal ortam olustur
python -m venv venv

# Aktiflesitir (Windows)
.\venv\Scripts\activate

# Bagimliliklari yukle
pip install -r requirements.txt
```

### Bagimliliklar

Temel bagimliliklar (requirements.txt icinde):
- PyQt5 - GUI cercevesi
- pymupdf - PDF isleme
- pydantic - Veri modelleri
- pillow - Goruntu isleme
- numpy - Sayisal islemler

Opsiyonel:
- easyocr - OCR yedegi
- ultralytics - YOLO komponent tespiti

## Kullanim

### GUI Modu

```bash
# Windows
.\venv\Scripts\python.exe start_gui.py

# Linux/macOS
./venv/bin/python start_gui.py
```

### CLI Modu

```bash
# Kablo anotasyonlari ile tek sayfa analizi
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations

# Birden fazla sayfa analizi, JSON olarak kaydet
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11-14 --include-annotations -f json -o results.json

# Tablo icin CSV ciktisi
.\venv\Scripts\python.exe analyze_pdf.py analyze data/ornek.pdf -p 11 --include-annotations -f csv -o terminals.csv

# PDF bilgilerini goster
.\venv\Scripts\python.exe analyze_pdf.py info data/ornek.pdf

# Tam yardim
.\venv\Scripts\python.exe analyze_pdf.py --help
```

### Temel GUI Is Akisi

1. **PDF Ac**: "PDF Ac" butonuna tiklayin veya uygulamanin `data/ornek.pdf` dosyasini otomatik yuklemesini bekleyin
2. **Gezinme**: Sayfalar arasinda gezinmek icin "Onceki/Sonraki" butonlarini kullanin
3. **Analiz**: Vektor analizini baslatmak icin "Analiz Et" butonuna tiklayin
4. **Kutu Cizme**: Komponent sinirlarini isaretlemek icin "Kutu Ciz" moduna gecin
5. **Baglanti Kontrolu**: Netlist olusturmak icin "Baglanti Kontrol" butonuna tiklayin

### Analiz Ciktisi

Analiz sunlari uretir:
- **Terminaller**: Etiketli tespit edilmis terminal bloklari listesi
- **Gruplar**: Terminal gruplari (-X1:1, -X1:2, -X2:PE vb.)
- **Kablo Anotasyonlari**: Semalardan tespit edilen kablo etiketleri
- **Baglantilar**: Hangi terminallerin hangi komponentlere baglandigini gosteren netlist

Ornek cikti:
```
====== BAGLANTI RAPORU ======
NET-001 Hatti:
   Terminal -X1:1
   Terminal -X1:2
   BOX-1:13
NET-002 Hatti:
   Terminal -X2:PE
   Terminal -X3:PE
```

## Mimari

```
P8_Analyzer_V2/
├── start_gui.py              # GUI giris noktasi
├── analyze_pdf.py            # CLI giris noktasi
├── p8_analyzer/              # Ana paket
│   ├── __init__.py           # Paket disa aktarimlari
│   ├── core/                 # Cekirdek analiz modulleri
│   │   ├── models.py         # Pydantic veri modelleri
│   │   ├── analyzer.py       # Sayfa vektor analizi
│   │   ├── analysis_engine.py # Birlesik analiz motoru
│   │   ├── session.py        # Analiz oturum yonetimi
│   │   └── export.py         # SVG/PNG disa aktarim
│   ├── detection/            # Tespit modulleri
│   │   ├── terminal_detector.py
│   │   ├── terminal_reader.py
│   │   ├── terminal_grouper.py
│   │   ├── wire_annotation_reader.py
│   │   ├── pin_finder.py
│   │   ├── busbar_finder.py
│   │   └── cluster_detector.py
│   ├── text/                 # Metin cikarma
│   │   └── hybrid_engine.py  # PDF + OCR metin motoru
│   ├── circuit/              # Baglanti analizi
│   │   └── connection_logic.py
│   ├── cli/                  # CLI modulu
│   │   ├── analyzer.py       # PDFAnalyzer sinifi
│   │   ├── output.py         # JSON/CSV/Text formatlayicilar
│   │   └── main.py           # CLI giris noktasi
│   └── gui/                  # PyQt5 GUI bilesenleri
│       ├── main_window.py
│       ├── viewer.py
│       └── worker.py
├── YOLO/                     # ML komponent tespiti
│   ├── scripts/              # Egitim scriptleri
│   ├── data/                 # Egitim verisi
│   └── best.pt               # Egitilmis model agirliklari
├── data/                     # Ornek dosyalar
│   └── ornek.pdf             # Ornek P8 semasi
├── tests/                    # Test paketi
│   ├── unit/                 # Birim testleri
│   ├── integration/          # Entegrasyon testleri
│   └── e2e/                  # Uctan uca testler
├── PRP/                      # Proje gereksinimleri
│   ├── REQUIREMENTS.md       # Tam gereksinim dokumani
│   ├── requirements/         # Ek dokumanlar
│   └── feedback/             # Musteri geri bildirimi
├── OPEN_TASKS.md             # Bekleyen gorevler listesi
└── requirements.txt          # Python bagimliliklari
```

## Isleme Hatti

```
┌─────────────────────────────────────────────────────────────────┐
│                         GIRDI                                    │
│  PDF Dosyasi (P8 formatinda elektrik semasi) + Sayfa Numarasi    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. PDF Yukleme (PyMuPDF)                                        │
│     - Dokumani ac                                                │
│     - Belirli sayfayi yukle                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Vektor Cikarimi (UVP Kutuphanesi)                            │
│     - Yollari, daireleri, yapisal gruplari cikar                 │
│     - VectorAnalysisResult olustur                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Terminal Tespiti (TerminalDetector)                          │
│     - Kriterlere uyan icbos daireleri bul                        │
│     - Yaricap (2.5-3.5) ve CV (<0.01) ile filtrele              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Etiket Okuma (TerminalReader + HybridTextEngine)             │
│     - Terminal merkezleri yakininda PDF metin katmanini ara      │
│     - PDF metni bulunamazsa OCR yedegine bas                     │
│     - Gecerli etiketler icin regex filtreleri uygula             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Grup Atama (TerminalGrouper)                                 │
│     - Solda grup etiketlerini (-X1, -X2) ara                    │
│     - Bulunamazsa sol/ust komsundan miras al                     │
│     - Tam etiketler olustur (Grup:Pin formati)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Kablo Anotasyon Yakalama (WireAnnotationReader)              │
│     - Yapisal gruplar yakininda kablo anotasyon etiketlerini bul │
│     - Anotasyonlari kablo segmentleri ile iliskilendir           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Pin Bulma (PinFinder)                                        │
│     - Komponent kutulari icindeki kablo uclarini bul             │
│     - Uc noktalar yakininda pin etiketlerini oku                 │
│     - Pinleri kutularla iliskilendir                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  8. Baglanti Analizi (AnalysisEngine)                            │
│     - Yapisal gruplari terminallerle ve kutularla esle           │
│     - Kesisimlerden netlist olustur                              │
│     - Baglanti raporu uret                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CIKTI                                    │
│  - Etiketli ve gruplu terminal listesi                           │
│  - Kablo anotasyonlari                                           │
│  - Baglanti raporu (netlist)                                     │
│  - PDF uzerinde gorsel kaplama                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Yapilandirma

### Terminal Tespit Parametreleri

| Parametre | Varsayilan | Aciklama |
|-----------|------------|----------|
| `min_radius` | 2.5 | Minimum terminal daire yaricapi |
| `max_radius` | 3.5 | Maksimum terminal daire yaricapi |
| `max_cv` | 0.01 | Maksimum varyasyon katsayisi (yuvarliklik) |
| `only_unfilled` | True | Sadece icbos daireleri tespit et |

### Metin Arama Parametreleri

| Parametre | Varsayilan | Aciklama |
|-----------|------------|----------|
| `search_radius` | 20.0 | Terminaller yakininda metin arama yaricapi |
| `direction` | top_right | Birincil arama yonu |
| `y_tolerance` | 15.0 | Gruplama icin Y ekseni toleransi |

### Pin Bulucu Parametreleri

| Parametre | Varsayilan | Aciklama |
|-----------|------------|----------|
| `pin_search_radius` | 75.0 | Pin etiketleri icin arama yaricapi |

## Test

```bash
# Tum testleri calistir
.\venv\Scripts\python.exe -m pytest tests/ -v

# Sadece birim testleri
.\venv\Scripts\python.exe -m pytest tests/unit/ -v

# Entegrasyon testleri
.\venv\Scripts\python.exe -m pytest tests/integration/ -v

# Uctan uca testler
.\venv\Scripts\python.exe -m pytest tests/e2e/ -v

# Kapsam raporu ile calistir
.\venv\Scripts\python.exe -m pytest tests/ --cov=p8_analyzer --cov-report=html
```

## Gelistirme

### Yeni Terminal Turleri Ekleme

1. `p8_analyzer/detection/terminal_detector.py` dosyasini duzenleyin
2. `_is_terminal()` metodunu yeni kriterlerle guncelleyin
3. `tests/unit/test_terminal_detector.py` dosyasina testler ekleyin

### OCR Dogrulugunu Artirma

1. `p8_analyzer/text/hybrid_engine.py` dosyasindaki `SearchProfile` parametrelerini ayarlayin
2. Etiket dogrulama icin regex desenlerini ince ayarlayin
3. Arayuzdeki OCR karsilastirma araci ile test edin

### YOLO Modeli Egitme

1. Anotasyonlu goruntuleri `YOLO/data/images/` ve `YOLO/data/labels/` klasorlerine ekleyin
2. `YOLO/data/dataset.yaml` dosyasini sinif tanimlariyla guncelleyin
3. Egitimi baslatin: `.\venv\Scripts\python.exe YOLO/scripts/train_label_detector.py`

Ek egitim araclari icin `YOLO/scripts/` klasorune bakin.

## Acik Gorevler

[OPEN_TASKS.md](OPEN_TASKS.md) dosyasinda sunlar bulunur:
- Bekleyen gelistirme gorevleri
- Bilinen sorunlar ve sinirlamalar
- Musteri geri bildirimi entegrasyon durumu

## Lisans

[Lisansinizi buraya ekleyin]

## Katki

1. Repoyu fork'layin
2. Bir ozellik branch'i olusturun
3. Degisikliklerinizi yapin
4. Testleri calistirin
5. Pull request gonderin

## Tesekkurler

- PDF isleme icin PyMuPDF
- Optik karakter tanima icin EasyOCR
- Nesne tespiti icin Ultralytics YOLO
