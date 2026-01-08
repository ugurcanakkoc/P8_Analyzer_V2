# P8 Analyzer V2

P8 formatindaki elektrik semalarini analiz eden profesyonel bir PDF tabanli arac. Otomatik olarak terminalleri (klemensler) tespit eder, etiketleri okur ve baglanti raporlari (netlist) olusturur.

## Ozellikler

- **Vektor Analizi**: PDF vektor verilerini ayristirarak yapisal elemanlari (cizgiler, daireler, yollar) tespit eder
- **Terminal Tespiti**: Elektrik semalarindaki terminal bloklarini icbos daireler olarak tanimlar
- **Hibrit Metin Tanima**: Dogru etiket okuma icin PDF metin katmanini OCR yedegi ile birlestirir
- **Akilli Gruplama**: Miras algoritmasiyla grup etiketleri (-X1, -X2 vb.) atar
- **Pin Tespiti**: Komponent kutulari icindeki kablo uclarinda pin etiketlerini bulur
- **Baglanti Raporlari**: Terminal-komponent baglantilarini gosteren netlist olusturur
- **Interaktif Arayuz**: PDF'lerde gezinin, komponent kutulari cizin, analiz sonuclarini gorun

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

### Bagimliliklar

```bash
pip install PyQt5 pymupdf pydantic pillow numpy
```

Opsiyonel (OCR yedegi icin):
```bash
pip install easyocr
```

Opsiyonel (YOLO komponent tespiti icin):
```bash
pip install ultralytics
```

### Klonlama ve Calistirma

```bash
git clone https://github.com/your-repo/P8_Analyzer_V2.git
cd P8_Analyzer_V2
python start_gui.py
```

## Kullanim

### Temel Is Akisi

1. **PDF Ac**: "PDF Ac" butonuna tiklayin veya uygulamanin `data/ornek.pdf` dosyasini otomatik yuklemesini bekleyin
2. **Gezinme**: Sayfalar arasinda gezinmek icin "Onceki/Sonraki" butonlarini kullanin
3. **Analiz**: Vektor analizini baslatmak icin "Analiz Et" butonuna tiklayin
4. **Kutu Cizme**: Komponent sinirlarini isaretlemek icin "Kutu Ciz" moduna gecin
5. **Baglanti Kontrolu**: Netlist olusturmak icin "Baglanti Kontrol" butonuna tiklayin

### Analiz Ciktisi

Analiz sunlari uretir:
- **Terminaller**: Etiketli tespit edilmis terminal bloklari listesi
- **Gruplar**: Terminal gruplari (-X1:1, -X1:2, -X2:PE vb.)
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
├── start_gui.py              # Uygulama giris noktasi
├── gui/                      # PyQt5 arayuz bilesenleri
│   ├── main_window.py        # Ana uygulama penceresi
│   ├── viewer.py             # Interaktif PDF goruntuleyici
│   ├── worker.py             # Arka plan analiz thread'i
│   ├── circuit_logic.py      # Baglanti tespit mantigi
│   └── ocr_worker.py         # OCR karsilastirma worker'i
├── src/                      # Cekirdek analiz modulleri
│   ├── models.py             # Pydantic veri modelleri
│   ├── terminal_detector.py  # Terminal daire tespiti
│   ├── terminal_reader.py    # Metin motoru ile etiket okuma
│   ├── terminal_grouper.py   # Grup atama algoritmasi
│   ├── pin_finder.py         # Kutularda pin tespiti
│   └── text_engine.py        # Hibrit PDF/OCR metin motoru
├── YOLO/                     # ML komponent tespiti
│   ├── scripts/              # Egitim scriptleri
│   ├── images/               # Egitim goruntuleri
│   ├── labels/               # Anotasyon etiketleri
│   └── best.pt               # Egitilmis model agirliklari
├── data/                     # Ornek dosyalar
│   └── ornek.pdf             # Ornek P8 semasi
└── tests/                    # Test paketi
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
│  6. Pin Bulma (PinFinder)                                        │
│     - Komponent kutulari icindeki kablo uclarini bul             │
│     - Uc noktalar yakininda pin etiketlerini oku                 │
│     - Pinleri kutularla iliskilendir                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. Baglanti Analizi (circuit_logic)                             │
│     - Yapisal gruplari terminallerle ve kutularla esle           │
│     - Kesisimlerden netlist olustur                              │
│     - Baglanti raporu uret                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CIKTI                                    │
│  - Etiketli ve gruplu terminal listesi                           │
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
pytest tests/ -v

# Kapsam raporu ile calistir
pytest tests/ --cov=src --cov=gui --cov-report=html
```

## Gelistirme

### Yeni Terminal Turleri Ekleme

1. `src/terminal_detector.py` dosyasini duzenleyin
2. `_is_terminal()` metodunu yeni kriterlerle guncelleyin
3. `tests/unit/test_terminal_detector.py` dosyasina testler ekleyin

### OCR Dogrulugunu Artirma

1. `src/text_engine.py` dosyasindaki `SearchProfile` parametrelerini ayarlayin
2. Etiket dogrulama icin regex desenlerini ince ayarlayin
3. Arayuzdeki OCR karsilastirma araci ile test edin

### YOLO Modeli Egitme

1. Anotasyonlu goruntuleri `YOLO/images/` ve `YOLO/labels/` klasorlerine ekleyin
2. `YOLO/multi_class_data.yaml` dosyasini sinif tanimlariyla guncelleyin
3. Egitimi baslatin: `python YOLO/scripts/train_multi_class.py`

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
