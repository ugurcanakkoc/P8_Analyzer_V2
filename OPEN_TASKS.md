# Open Tasks / Acik Gorevler

This document lists the remaining tasks and known issues for the P8 Analyzer project.

Bu belge, P8 Analyzer projesi icin kalan gorevleri ve bilinen sorunlari listeler.

---

## Status / Durum

**Last Updated / Son Guncelleme:** January 2026

**Current Branch / Mevcut Dal:** `feat/unified-requirements-doc`

---

## Priority Tasks / Oncelikli Gorevler

### 1. GUI Integration / GUI Entegrasyonu

**Status / Durum:** TODO

**English:**
- Integrate AnalysisSession with GUI
- Modify AnalysisWorker to return PageAnalysis
- Store AnalysisSession in MainWindow
- Add Save/Load Analysis menu options
- Update connection report to use new structure

**Turkce:**
- AnalysisSession'i GUI ile entegre et
- AnalysisWorker'i PageAnalysis dondurecek sekilde degistir
- AnalysisSession'i MainWindow'da depola
- Kaydet/Yukle Analiz menu secenekleri ekle
- Baglanti raporunu yeni yapiyi kullanacak sekilde guncelle

---

### 2. Quality Gate Testing / Kalite Kapisi Testleri

**Status / Durum:** TODO

**English:**
- Create `tests/run_quality_gates.py`
- Verify Page 11: 10+ terminals, 2+ components, 30% annotation ratio
- Verify Page 12: PE isolation (no cross-connections)
- Verify Page 13: Component pin detection
- Verify Page 14: SINAMICS detection with 10+ pins

**Turkce:**
- `tests/run_quality_gates.py` dosyasini olustur
- Sayfa 11: 10+ terminal, 2+ komponent, %30 anotasyon orani dogrula
- Sayfa 12: PE izolasyonu (capraz baglanti yok) dogrula
- Sayfa 13: Komponent pin tespiti dogrula
- Sayfa 14: 10+ pin ile SINAMICS tespiti dogrula

---

### 3. Wire/Line Detection via YOLO / YOLO ile Hat Tespiti

**Status / Durum:** TODO

**English:**
- FR-LD-01: Detect wire connections using YOLO model
- FR-LD-02: Trace wire paths between components
- FR-LD-03: Handle branching/forked wire paths (see ornek.pdf page 26)
- FR-LD-04: Associate wires with terminals and pins
- Train model to detect wire segments with >80% accuracy

**Turkce:**
- FR-LD-01: YOLO modeli ile kablo baglantilarini tespit et
- FR-LD-02: Komponentler arasi kablo yollarini takip et
- FR-LD-03: Catalli/dallanmis kablo yollarini isle (bkz. ornek.pdf sayfa 26)
- FR-LD-04: Kablolari terminallerle ve pinlerle iliskilendir
- Modeli >%80 dogrulukla kablo segmentlerini tespit edecek sekilde egit

---

### 4. OCR Integration Enhancement / OCR Entegrasyonu Iyilestirmesi

**Status / Durum:** TODO

**English:**
- FR-OCR-01: Graceful fallback when vector data unavailable
- FR-OCR-02: Read pin labels via OCR
- FR-OCR-03: Read terminal (Klemens) names via OCR
- FR-OCR-04: Read device names via OCR
- FR-OCR-05: Continue analysis without errors when vector data is missing
- Target: OCR reads >85% of labels correctly

**Turkce:**
- FR-OCR-01: Vektor verisi mevcut olmaduginda sorunsuz geri donus
- FR-OCR-02: Pin etiketlerini OCR ile oku
- FR-OCR-03: Terminal (Klemens) isimlerini OCR ile oku
- FR-OCR-04: Cihaz isimlerini OCR ile oku
- FR-OCR-05: Vektor verisi eksik oldugunda analizi hatasiz surdurmesi
- Hedef: OCR etiketlerin >%85'ini dogru okumali

---

## Data Collection Pipeline / Veri Toplama Hatti

### 5. LLM-Assisted Component Pre-Annotation / LLM Destekli Komponent On-Anotasyonu

**Status / Durum:** ON HOLD (Beklemede)

**English:**
Use vision LLM (GPT-4V/Claude) to generate initial bounding box suggestions for electrical components.

**Current findings:**
- Script: `YOLO/scripts/llm_annotation_helper.py`
- Test Results: 12 components found (10 Terminals, 2 PLC_Modules)
- **Issue:** Bounding box positions/sizes are imprecise - GPT-4o struggles with accurate pixel-level localization
- LLM can identify component types and labels, but not accurate bounding boxes

**Turkce:**
Elektrik komponentleri icin ilk sinir kutusu onerileri olusturmak amaciyla gorsel LLM (GPT-4V/Claude) kullan.

**Mevcut bulgular:**
- Script: `YOLO/scripts/llm_annotation_helper.py`
- Test Sonuclari: 12 komponent bulundu (10 Terminal, 2 PLC_Module)
- **Sorun:** Sinir kutusu konumlari/boyutlari yetersiz - GPT-4o piksel seviyesinde dogru yerellesme yapmakta zorlanir
- LLM komponent turlerini ve etiketleri taniyabilir ama dogru sinir kutulari cizemiyor

---

### 6. Human Review and Annotation Refinement / Insan Incelemesi ve Anotasyon Iyilestirmesi

**Status / Durum:** TODO (Depends on Phase 5 / Faz 5'e bagimli)

**English:**
- Load LLM-suggested annotations into smart_annotator.py
- Accept/reject/adjust each suggestion
- Add any missed components manually
- Save approved annotations in OBB format
- Target: 200-400 fully annotated schematic pages

**Turkce:**
- LLM onerili anotasyonlari smart_annotator.py'a yukle
- Her oneriyi kabul et/reddet/ayarla
- Kacirilan komponentleri manuel ekle
- Onaylanan anotasyonlari OBB formatinda kaydet
- Hedef: 200-400 tam anotasyonlu sema sayfasi

---

### 7. Synthetic Data Augmentation and Model Training / Sentetik Veri Cogaltma ve Model Egitimi

**Status / Durum:** TODO

**English:**
- Use synthetic_data_generator.py to expand dataset 10-20x
- Split into train/val/test (70/15/15)
- Train YOLOv8-OBB model
- Target: 2000-5000 training samples, mAP > 0.7

**Turkce:**
- synthetic_data_generator.py ile veri setini 10-20 kat genislet
- train/val/test olarak bol (70/15/15)
- YOLOv8-OBB modeli egit
- Hedef: 2000-5000 egitim ornegi, mAP > 0.7

---

## Infrastructure / Altyapi

### 8. Offline Data Augmentation Script / Cevrimdisi Veri Cogaltma Scripti

**Status / Durum:** TODO

**English:**
Create script for offline augmentation to expand training dataset:
- Scale variations (0.8-1.2x)
- Brightness/contrast adjustment
- Gaussian blur (simulate scan quality)
- Noise injection
- NO rotation (symbols have meaning)
- NO flip (text becomes unreadable)

**Turkce:**
Egitim veri setini genisletmek icin cevrimdisi cogaltma scripti olustur:
- Olcek varyasyonlari (0.8-1.2x)
- Parlaklik/kontrast ayari
- Gaussian bulanikligi (tarama kalitesi simulasyonu)
- Gurultu enjeksiyonu
- Donus YOK (semboller anlam tasir)
- Cevirme YOK (metin okunamaz hale gelir)

---

### 9. CI/CD Pipeline / CI/CD Hatti

**Status / Durum:** TODO

**English:**
No CI/CD currently configured. Add GitHub Actions workflow for:
- Running pytest on push/PR
- Code linting (flake8/ruff)
- Type checking (mypy)
- Coverage reporting

**Turkce:**
Su anda CI/CD yapilandirilmamis. GitHub Actions is akisi ekle:
- push/PR'da pytest calistirma
- Kod linting (flake8/ruff)
- Tip kontrolu (mypy)
- Kapsam raporlama

---

## Known Issues / Bilinen Sorunlar

### Algorithm Limitations / Algoritma Sinirliliklari

**English:**
1. **Forked Paths:** Current algorithm struggles with continuity at branching points (see ornek.pdf page 26)
2. **Component Detection Noise:** Wire break detection produces too many results (572 breaks, 33 junctions on page 11) - needs refinement
3. **Limited Training Data:** Only ~3 images available for YOLO training - need 200-400+ for production quality

**Turkce:**
1. **Catalli Yollar:** Mevcut algoritma dallanma noktalarinda sureklilik sorunlari yasiyor (bkz. ornek.pdf sayfa 26)
2. **Komponent Tespiti Gurultusu:** Hat kopusu tespiti cok fazla sonuc uretiyor (sayfa 11'de 572 kopus, 33 kavsaklar) - iyilestirme gerekli
3. **Sinirli Egitim Verisi:** YOLO egitimi icin sadece ~3 goruntu mevcut - uretim kalitesi icin 200-400+ gerekli

---

## Customer Feedback Integration / Musteri Geri Bildirimi Entegrasyonu

Customer feedback documents are available in `PRP/feedback/`:
- `Analiz.docx` - Analysis feedback with images
- `Komponentler.docx` - Component feedback
- `images/` - Visual feedback screenshots

Musteri geri bildirim dokumanlari `PRP/feedback/` klasorunde mevcut:
- `Analiz.docx` - Gorsellerle analiz geri bildirimi
- `Komponentler.docx` - Komponent geri bildirimi
- `images/` - Gorsel geri bildirim ekran goruntuleri

---

## Contact / Iletisim

For questions about pending tasks, see the original team message in `PRP/requirements/message.md`.

Bekleyen gorevler hakkinda sorular icin `PRP/requirements/message.md` dosyasindaki orijinal ekip mesajina bakin.
