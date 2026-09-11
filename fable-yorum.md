# Fable yorumu — PLAN.md incelemesi ve pdf2eplan karşılaştırması

Tarih: 2026-09-10. Yazan: Claude Fable 5.1 (yalnız okuma denetimi; tek yazılan dosya bu rapor).
Bağlayıcı kurallar: [MAIN.md](MAIN.md). İncelenen plan: [PLAN.md](PLAN.md), [analyzer_v3/README.md](analyzer_v3/README.md).
Kullanıcı sorusu: "Mantığımız ve gidişatımız mantıklı mı, gözden kaçırdığımız hata/eksiklik var mı;
varmak istediğim program tam olarak https://www.acceleratis.com/en/pdf2eplan."

Bu rapor üretim/import onayı değildir. Hiçbir bağlantıya onay vermez, hiçbir Excel'i değiştirmez.

---

## 0. Yöntem ve beyanlar

- Okunan: MAIN.md (tamamı), PLAN.md, analyzer_v3/README.md, AGENTS.md, CLAUDE.md, analyzer_v3/*.py
  (ajanlar aracılığıyla), rev8 çalışma klasörü (`output/pilots/E122/20260910_v3_p05_rev8/`) verileri,
  `output/research/2026-09-09_PDF_Baglanti_Stratejisi.md`, rev8 `review/*.md` (8 dosya),
  iki kullanıcı Excel'i (E122: 322 satır, E530: 106 satır), ham PDF geometrisi (fiziksel sayfa 4; kısmen 2/5).
- pdf2eplan: ürün sayfası ve FAQ (11 soru) Playwright ile akordeon açılarak birebir çekildi.
  Üçüncü taraf inceleme/referans aranıp bulunamadı. Ürün denenmedi; müşteri belgesi dış servise gönderilmedi.
- Ajan kullanımı: kullanıcı talimatıyla Opus/Sonnet alt ajanlar (kanıt toplama 6, ek bulgu 4,
  karşı-doğrulama 126). Her bulgu 3 bağımsız doğrulayıcıya verildi (kanıt kontrolü, elektrik/kural
  kontrolü, maddilik). En az 2/3 çürütemezse "ayakta" sayıldı. 42 aday bulgudan 22 ayakta kaldı; ayakta
  kalanlar doğrulayıcı düzeltmeleriyle birlikte yazıldı.
- Değişiklik: proje dosyası değiştirilmedi (test koşusundan 1 `__pycache__` dosyası hariç). Testler koşuldu:
  `python -m unittest discover -s analyzer_v3/tests -t .` → `Ran 100 tests ... OK`.
- Bu rapordaki satır numaraları 2026-09-10 11:00 civarındaki dosya sürümlerine aittir.

---

## 1. Kısa hüküm

**Mantık sağlam.** Kanıt katmanları (çizim → ağ → fiziksel tel → onay), tahmin yasağı, "aynı ağ ≠ aynı
tel" ayrımı, sessiz silme yokluğu, adres/pin son eki koruması kodda tutuyor. Yakınlıktan hayali zincir
üretilmiyor; noktasız kesişim birleştirilmiyor; pin değişince eski onay canlanmıyor.

**Temel geometri varsayımı doğrulandı.** EPLAN PDF'i çizgi nesnesini yalnız elektriksel bağlantı
noktasında bölüyor, kesişmede bölmüyor. Sayfa 4 ölçümü: 8 T noktası (hepsi bölünmüş, hepsinde 3 iç içe
dolgusuz çember Ø4,96/3,54/2,12 pt), 49 uzun-hat kesişmesi (hiçbiri bölünmemiş, çember yok). Graf yaklaşımı
doğru temel üstünde.

**Gidişat iki yerde sorunlu:**

1. **Hedef ürün tanımı ile "tam olarak pdf2eplan" aynı şey değil.** pdf2eplan EPLAN içinde düzenlenebilir
   proje üretir; fiziksel tel listesi (kesit, renk, klemens son eki, T dağıtımı, tarak köprü, standart PE)
   üretmez. MAIN ROL'ü tam bunları ister ve "EPLAN'da yeniden çizmeden" der. Karar kullanıcıya ait (bkz. §3).
2. **Sıralama derinlik öncelikli.** 58 kapsam içi şema sayfasından 5'i izlenmiş, 1'i analiz edilmiş;
   32 pin, 6 fiziksel tel adayı; hedef Excel 322 satır. "Sıradaki iş" listeleri hâlâ sayfa 4 detayı
   (PE kesikli hat, polyline). pdf2eplan'ın çekirdeği olan "belge geneli aday arama + onaylanan ailenin toplu
   yerleştirilmesi" planda yok. Bu hızla MAIN'in 2026-09-10 önceliği (TROESTER'de kullanılabilir sonuç) gelmez.

---

## 2. pdf2eplan — doğrulanmış olgular

Kaynak: https://www.acceleratis.com/en/pdf2eplan ve /faq (2026-09-10 çekimi). Tümü satıcı beyanı; bağımsız
doğrulama yok.

| Konu | Satıcı beyanı |
|---|---|
| Ürün biçimi | EPLAN Electric P8 **add-in**; "Runs as an add-in directly inside EPLAN and uses the symbol library of the currently open project." |
| Girdi | Doğal PDF **ve** taranmış PDF (yerleşik OCR). DWG/DXF anılmıyor. Kaynak ECAD sistemi belirtilmiyor. |
| Çıktı | "Editable EPLAN project"; tanınan veri açık projeye doğrudan uygulanır (FAQ Q8). Dosya biçimi (.elk/.zw1/XML) belirtilmiyor. |
| Süreç | 01 Import PDF → 02 Capture structure and metadata (sheet, plant structure) → 03 User-guided recognition of devices, connections, structures → 04 Sync to EPLAN. |
| Otomasyon | FAQ Q3: sembol bir kez atanır, aynı sembolün diğer örnekleri belge boyunca otomatik önerilir; kullanıcı onaylayınca elemanlar sayfaya grafik olarak uygulanır. Tam otomatik değil (Q10), her kritik atama onaylanır (Q5). |
| Sayfalar arası | Q4/Q9: sayfa sayfa veya sayfalar arası; "several hundred pages" destekli; cihaz/bağlantı/yapı belge genelinde işlenir. |
| Gereksinim | EPLAN Electric P8 + **EPLAN Runtime API (müşteri sağlar, teklife dahil değil)**; asgari sözleşme 12 ay. |
| Fiyat | Super Early Adopter: 0 €/ay (12 ay) + 2,50 €/sayfa (20 kişilik, 5'i dolu). Starter 69,50 €/ay + 2,50 €/sayfa. Professional 139 €/ay + 1 €/sayfa (≈47 sayfa/ay üstünde avantajlı). Enterprise özel. |
| Süre iddiası | Elle çizim ~30 dk/sayfa, pdf2eplan ~5 dk/sayfa; 100 sayfada ~42 saat tasarruf. "Actual time savings depend on the quality, structure, and complexity of the source documents." |
| Referans | SITLog GmbH: sayfa yapısı aktarımı saatlerden dakikalara; eleman/bağlantı aktarımı "significantly faster". |
| Doğruluk | Hiçbir yüzde/hata oranı verilmiyor. |

**Ne yapmıyor (kanıta göre):** kesit/renk/klemens son eki/T dağıtımı/tarak köprü/standart PE kararı yok;
Pro Panel veya bağlantı listesi üretimi anılmıyor. Bu kararlar EPLAN'a aktarımdan sonra da UVP'nin işi.

**Bizim planla örtüşenler:** sembolü bir kez eşle → benzerlerini öner → kullanıcı onaylasın (P04/P05b);
sayfa yapısı/başlık bloğu okuma (document_index.json, 73 sayfa); insan onayı ilkesi.

**Örtüşmeyenler:** EPLAN'a yazma; belge geneli aday arama; toplu uygulama; tarama/OCR (bilinçli kapsam dışı);
sayfa yapısı teslimi.

---

## 3. Hedef ürün kararı (kullanıcıya)

Üç yol; biri seçilmeden ilerlemek yanlış ürünü optimize eder.

- **(A) MAIN hedefi kalır: pano içi fiziksel tel listesi (37 sütun Excel).** pdf2eplan'dan yalnız UX
  döngüsü alınır (bir kez öğret, belge boyunca öner, onayla, uygula). Mevcut kod bu yola uygun; eksikler §5.
- **(B) EPLAN projesi üretimi (pdf2eplan'ın yaptığı).** Gerekenler: EPLAN Runtime API lisansı, C#/.NET
  add-in, sembol→makro eşlemesi, sayfa/cihaz oluşturma. Bunların hiçbiri planda yok. Üstüne yine (A)'nın tel
  listesi katmanı gerekir; MAIN'in ana çıktısı (B) ile kendiliğinden gelmez.
- **(C) Yeniden çizimi satın al, yalnız tel listesi katmanını yaz.** E122 için 73 sayfa ≈ 183 € (erken
  kullanıcı) veya ≈ 212 € (Professional, ilk ay). En kısa yol; ama iki ön koşul hiç sorulmamış:
  1. UVP'de **EPLAN Runtime API** lisansı var mı? Yoksa (B) ve (C) kapalı; bu, geliştirmeye devam kararını
     güçlendiren bir olgudur.
  2. Müşteri PDF'ini **dış servise yüklemek** serbest mi? MAIN dış servise dosya gönderimini onaysız yasaklar.
  Ayrıca: 12 ay taahhüt, doğruluk rakamı yok, bağımsız referans yok; deneme yalnız hassas olmayan bir belgeyle
  ve kullanıcı izniyle yapılmalı.

Not: Araştırma dosyası (`output/research/2026-09-09_PDF_Baglanti_Stratejisi.md:41-53`) fiyatı ve API
koşulunu zaten kaydetmiş ve "üstünlük kanıtı değildir" demiş; karşılaştırma protokolü de (§7.4: aynı
dondurulmuş testte üç aday, eşit ölçülen düzeltme süresi) orada. PLAN.md bunları taşımıyor.

---

## 4. Ölçülen mevcut durum

**Belge/kapsam** (document_index.json): 73 sayfa; Schaltplan 59, Stückliste 11, Layout 3; Klemmenplan /
Kabelplan / Verbindungsliste yok. Kapsam içi Schaltplan 58. 230 ayrık kapsam içi cihaz etiketi: X 68, K 48,
A 34 (çoğu +M saha bağlayıcısı), D 22, F/Q 14, W 24. 122 etiket birden fazla sayfada; 48 röle etiketinin
48'i 2-3 şema sayfasına yayılmış; -X4 23, -X1 15 şema sayfasında.

**Pilot** (rev8): traced_pages [2,4,5,28,36]; inventory'de analyzed=true yalnız sayfa 4; 32 pin
(sayfa 4: 24, sayfa 5: 7, sayfa 2: 1; 20 MANUAL, 12 P04_CANDIDATE; 32'sinin tamamı Claude kaynaklı);
7 sembol kutusu; 5 inceleme (hepsi CHAT_APPROVAL_TRANSCRIBED). Sayfa 4 tablosu: 6 fiziksel tel adayı,
3 ağ ilişkisi, 5 tek uçlu ağ, 85 boşluk, 1613 incelenmemiş ağ; kesit/renk hiçbir satırda dolu değil;
her satır production_ready=false. Kütüphane: 1 kayıt (DRAFT, "K çizgili 2 uçlu sembol", yalnız öteleme).

**Kullanıcı Excel'leri** (openpyxl, salt okuma):

| | E122 | E530 |
|---|---|---|
| Dolu satır | 322 | 106 |
| En az bir -X ucu | 239 (%74) | 88 (%83) |
| UVP koşu son eki (`-n:m`) taşıyan satır | 56 (hepsi P24/N24) | 31 |
| Renk | DBU 257, BK 51, GNYE 13, BU 1 | DBU 87, GNYE 13, BK 4, BU 2 |
| Kesit | 1 mm² 237, 2,5 61, 1,5 17, 6 5, 16 2 | 1 mm² 88, 2,5 5, 1,5 5, 6 5, 16 2, 10 1 |
| Pano gövde PE satırı (Not sütunu) | 7 (%2,2) | 7 (%6,6) |
| Çok damarlı/Ethernet satırı | 0 | 0 |

37 başlık MAIN listesiyle sıra olarak aynı; her başlıkta `\n` var. MAIN "6 sütun varsayılan" der; dosyalarda
~23 sütun dolu (CE yapıları, döşeme yönü, min/max kesit, sıyırma, H07V-K/H05V-K tipi) — muhtemelen EPLAN
üretimi alanlar; MAIN:660/671 bunu "varsayılan + kullanıcı isterse" olarak zaten düzenliyor.

**Ham PDF geometrisi, sayfa 4** (raw_page.json = pdfplumber ile birebir):
- 2118 çizgi (hepsi 2 noktalı, mcid/tag yok, stroking_color 0), 142 eğri, 29 dikdörtgen, 245 kelime, 0 görüntü.
- T noktalarında eğik/ok işareti yok; EPLAN hedef yönü nesne yapısından okunamıyor. Tek ipucu eşdoğrusallık.
- Klemens: Ø5,67 pt çember (12 adet, y=483,88). Ad ayrı kelime, çemberin sağ üstünde; rakamlar merkeze
  9,3-10,0 pt, potansiyel adları 19,9 pt; -X4 yazıları 90° döndürülmüş (ham '23.42P'), words.json düzeltiyor;
  -X1 düz. Sıra adı bir kez, ilk çemberin 25-28 pt solunda.
- Kablo tanımı: -3W67 çizgisi lw 0,71 (tel 0,99), 12 dikey teli keser, her kesişmede 45° işaret, damar
  numaraları ayrı kelime (tel +2,55 pt). -3W62 aynı yapıda (4 damar).
- Renk kodu kelimesi sayfa 2/4/5'te yok. Kesit yalnız antet notu ("Alle Leitungen ohne Querschnittsangabe
  sind 1,5 mm² Cu, Steuerleitungen 1 mm² Cu") ve kablo niteliği olarak var.
- Potansiyel kelimesi ile ray ucu tipik mesafe 3,54 pt.
- PE barası ~50 ayrı kısa nesne (dash niteliği yok, gerçek 4,25 pt boşluk).
- Sayfa 5'in vektör geometrisi sayfa 4 ile bayt-aynı; yazılar farklı (-17K56/57/59, -4F22, -4W67).
- Koordinat notu: geometry.json = pdfplumber koordinatı − render_bbox (−1, +1); tohumlar geometri uzayında
  tam uç üzerinde. Kanıt toplama aşamasındaki "(+1,−1) kayma" ifadesi yanlış okumaydı, bulgu türetilmedi.

---

## 5. Bulgular (karşı-doğrulamadan geçenler)

Format: Önem · Yer · Yeniden üretim · Etki · En küçük düzeltme · Doğrulama notu.

### P1

**B1 — Hedef ürün kararı yok.**
- Yer: [PLAN.md:8-9](PLAN.md#L8-L9) "Cihaz oluşturma, 2D yeniden çizim, 3D yerleşim ve lisans/import yönetimi
  yok"; [MAIN.md:15-24](MAIN.md#L15-L24) ROL; [analyzer_v3/models.py:144-145](analyzer_v3/models.py#L144-L145)
  üretim dışa aktarımı hata verir; PLAN'da "Hedef ürün", EPLAN API veya add-in maddesi yok (pdf2eplan yalnız
  PLAN.md:87'de araştırma dayanağı).
- Yeniden üretim: PLAN.md:8-9 ile ürün sayfasının "04 Sync to EPLAN — editable EPLAN project" adımını yan yana koy.
- Etki: "Tam olarak pdf2eplan" isteniyorsa mevcut plan onun alt kümesi; MAIN'in istediği ürün ise pdf2eplan'ın
  üstünde ayrı bir katman. İkisi de doğru olabilir, ama hangisi olduğu yazılı değil.
- Düzeltme: PLAN'a "Hedef ürün" bölümü: (A)/(B)/(C) seçimi + §3'teki iki soru. Kod değişmez. (B) açık
  kalsın isteniyorsa iç modelde sembol örneği (aile + konum + dönüşüm + cihaz etiketi) birinci sınıf varlık olur;
  kütüphane şekil/çapa/uç ofsetlerini zaten saklıyor ([library.py:52-62](analyzer_v3/library.py#L52-L62)).
- Doğrulama notu: kural doğrulayıcı "PLAN MAIN ile çelişmiyor, MAIN'i uyguluyor; çelişki kullanıcının yeni
  ifadesiyle" dedi ve (B)'nin MAIN çıktısını üretmeyeceğini vurguladı. Doğru; bu yüzden bulgu "hata" değil
  "karar" olarak yazıldı. 2/3 ayakta.

**B2 — Kod ikinci projeyi açamıyor; kapsam, PDF, klasör ve tohumlar sabit kodlu.**
- Yer: [prepare.py:15-16](analyzer_v3/prepare.py#L15-L16) `SOURCE` + `KNOWN_HASH`;
  [prepare.py:136-141](analyzer_v3/prepare.py#L136-L141) çalışma klasörü `output/pilots/E122` altına kilitli,
  hash uyuşmazlığında ValueError; [prepare.py:159](analyzer_v3/prepare.py#L159) `page = pdf.pages[3]`;
  [prepare.py:101-133](analyzer_v3/prepare.py#L101-L133) `seeds()` 13 sayfa-4 pini, 3 maske, C01-C03
  teyitlerini her yeni çalışmaya koşulsuz yazar (prepare.py:172); [models.py:8,22](analyzer_v3/models.py#L8)
  `FUNCTIONS` ve `"E122"`; [document.py:12](analyzer_v3/document.py#L12) `LOCATION="E122"`;
  CLI yalnız `--run/--pages/--add-pages` (prepare.py:236-244).
- Yeniden üretim: `python -c "from analyzer_v3.prepare import prepare; prepare('output/pilots/E530/test')"`
  → ValueError (klasör kuralı); SOURCE değiştirilmeden hash kapısı da geçilmez.
- Etki: klasörde hazır duran ikinci TROESTER projesi (`13sb004-e530/=530.pdf` + 106 satırlık Excel) araca
  giremiyor; P08 "görülmemiş test" kod düzenlemeden çalışmaz; "projeden bağımsız kütüphane" (PLAN.md:37)
  iddiası sınanamaz (kütüphanenin tek yeniden kullanımı aynı belgenin iki çalışma klasörü arasında).
  E122 belgesinin 22. sayfasında `=530+E530-4D23:P2` yazısı var; panolar arası ilişki tek proje varsayımıyla
  temsil edilemez (çıkarım).
- Düzeltme: `--pdf` (hash dosyadan hesaplanır, manifest'e yazılır; KNOWN_HASH yalnız bilinen belge için
  doğrulama), `--scope 'E122:112,122,132,152,170'` (manifest'ten okunur, `in_scope` imzası değişmez),
  çalışma kökü `output/pilots/<proje>/`; `seeds()` yalnız `--seeds e122p4` verildiğinde. PLAN'a "P05d — proje
  kaydı" maddesi. Kod yazmadan önce tek karar: kapsam adresi kullanıcı girdisi mi, başlık bloğundan çıkarım mı?
- Doğrulama notu: "tek sayfaya çivili" ifadesi fazla geniş (`--add-pages` var); `--run` varsayılanları argparse
  varsayılanıdır, sabit değil. Gerçek kilitler yukarıdaki satırlar. Aynı belgenin işaretsiz sayfalarında kör
  test bugün de yapılabilir. MAIN 2026-09-10 "ayrı projeleriyle sınama"yı "daha sonra" der; bulgu "şimdi yap"
  demiyor, "yol yok" diyor. 3/3 ve 3/3 ayakta (iki mercek bağımsız buldu).

**B3 — Belge geneli aday arama ve toplu öneri yok; "sayfa/pano bitti" tanımı throughput'u sınırsız düşürüyor.**
- Yer: [service.py:161-175](analyzer_v3/service.py#L161-L175) `candidates()` ve
  [service.py:232-243](analyzer_v3/service.py#L232-L243) `library_candidates()` yalnız tek izlenen sayfada;
  [server.py:96](analyzer_v3/server.py#L96) tek kayıtlık POST; `app.js draftPin()` yalnız formu doldurur;
  kütüphane her aday için mutlak pin noktası üretiyor ([similarity.py:296-300](analyzer_v3/similarity.py#L296-L300))
  ama yazma yolu yok. PLAN.md:257-262 ve 298-302 "Sıradaki iş" listeleri: PE kesikli hat, polyline, sayfa 2/5.
  PLAN.md:205 "1671 ağ kovası kapanmadan sayfa 4 için tamamlandı denemez".
- Yeniden üretim: document_index.json → 58 kapsam içi Schaltplan; manifest traced_pages 5; annotations pins 32.
- Etki: iki günde 6 fiziksel tel adayı; hedef 322 satır × sonraki projeler. "Sayfa bitti" = tüm çizim
  bileşenleri açıklanmış tanımı, pdf2eplan'ın 5 dk/sayfa ekonomisinin tersidir. Pano düzeyinde "bitti"
  (bir rölenin bobin sayfası açılmadan kontak sayfası bitmiş görünmesin) hiçbir yerde tanımlı değil.
- Düzeltme: (1) kapsam içi tüm sayfalarda aday arama + toplu **öneri** uç noktası; onay örnek başına kalır,
  cihaz/pin adı her örnekte sayfadan okunur (MAIN.md:1031 kör kopyayı yasaklar; "aile bazlı tek onay" bu
  yüzden yanlış olurdu). (2) "Sayfa bitti" = kapsam içi her cihaz ucunun satır veya gerekçeli boşluk kaydı
  var; çizim bileşeni açıklama şartı kaldırılır (döküm görünür kalır). (3) "Pano bitti" = kapsam içi her
  etiketin her basılı sayfası ziyaret edilmiş. (4) PLAN'a operatör dakikası/sayfa ve /100 doğru bağlantı hedefi.
- Doğrulama notu: "çekirdek döngü planda yok" başlığı yanlıştı — P04/P05b "bir kez ata → öner" adımını
  içeriyor ve uygulanmış; eksik olan son iki adım (belge geneli arama, toplu uygulama). Kanıt satır numaraları
  düzeltildi (`server.py:96`, `library.py:52-54`). 2/3 ayakta, önem P2 önerildi; sıralama etkisi nedeniyle P1'de
  tutuldu.

### P2

**B4 — Klemens pin adı okuma eksik: metin/indeks katmanında hiç yok, P04 yolunda döndürülmüş çok karakterli adlar kaçıyor.**
- Yer: [document.py:263-275](analyzer_v3/document.py#L263-L275) `terminal_table()` yalnız `X\d+` cihaz
  yazısı; [document.py:320-323](analyzer_v3/document.py#L320-L323) "klemens sırasındaki ayrı rakamlar burada
  aranmaz"; [similarity.py:12](analyzer_v3/similarity.py#L12) `LABEL_TOL=2.0` pt sabit etiket ofseti.
- Yeniden üretim: `Pilot(...).candidates('box_0904b5fe6b7d42f2b204aee8e0ec0655')` → 10 aday; 7'sinde
  pin rakamı okundu ('1','2','3' / '1','2','3','4'), 3'ünde `PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET`
  (N24.30, P24.32, N24.30).
- Etki: Excel'in %74-83'ü klemens uçlu; belge geneli klemens envanteri (hangi sıra, hangi numaralar, hangi
  sayfalarda) yok; aynı adın iki kez geçmesi (-X4'te iki N24.30) sistematik yakalanamıyor.
- Düzeltme: klemens ailesi için etiket bölgesi çemberin sağ üstünde geniş pencere (rakam ~10 pt, potansiyel
  adı ~20 pt), döndürülmüş kelime düzeltmeli; aday adı `X4:<kelime>`; çift ad → belirsiz. Belge geneli klemens
  envanteri `terminal_table()` üstüne.
- Doğrulama notu: maddilik doğrulayıcısı başlığı ("otomatik okunmuyor") ölçümle çürüttü — 7/10 okunuyor.
  Bulgu daraltıldı. 2/3 ayakta.

**B5 — Pano sınırı kuralı bağlantı tablosunda uygulanmıyor.**
- Yer: [service.py:805-807](analyzer_v3/service.py#L805-L807) `clean=...; if len(pins)==2 and clean → PHYSICAL_PAIR`;
  uç başına `in_scope` [service.py:760](analyzer_v3/service.py#L760)'ta üretiliyor, kararda okunmuyor;
  `owner_in_scope` yalnız boşluk kovasında (service.py:777); aynı eksik `_confirmed_pairs` yolunda
  (service.py:~906-922). Buna karşılık tohum teyitleri kapsamı uyguluyor (service.py:133) — iç tutarsızlık.
  MAIN.md:107-129 "PANO SINIRI KURALI".
- Yeniden üretim (doğrulayıcı, çalışma kopyası üzerinde): temiz bir ağın ucu `=112+E122-3F22:2` →
  `=112+M113-3A72:1` yapıldı; satır yine `PHYSICAL_PAIR`, not "fiziksel tel adayı", `in_scope=False` yalnız
  metin olarak görünüyor (app.js:62 "kapsam dışı").
- Etki: saha cihazı ucu işaretlenir işaretlenmez (P04/kütüphane saha tarafındaki örnekleri de önerir) pano
  klemensi ↔ saha cihazı çifti "fiziksel tel adayı" olur. Bugün sayfa 4'te tüm uçlar kapsam içi olduğu için gizli.
  Tablo üretim listesi değil (production_ready=false), ama inceleme tablosu yanıltır.
- Düzeltme: koşula `and all(q['in_scope'] for q in pins)`; değilse `kind='OUT_OF_SCOPE_BOUNDARY_PAIR'`,
  ayrı kova; `_confirmed_pairs` aynı; regresyon testi (kapsam dışı uçlu ağ PHYSICAL_PAIR üretmez).
- Doğrulama notu: 3/3 ayakta.

**B6 — MAIN'in C02 örneği kullanıcı Excel'inde yok; tel/tarak köprü ayrımı hiçbir katmanda yok.**
- Yer: [MAIN.md:1025](MAIN.md#L1025) C02 = `-17K53:11 – -17K55:11` "kullanıcı teyit etti"; seeds.json C02
  `kind: PHYSICAL`; [tests/test_pilot.py:782-783](analyzer_v3/tests/test_pilot.py#L782-L783); rev8 tablosunda
  CONFIRMED_PHYSICAL_PAIR. Kodda satır türü kümesi kapalı (PHYSICAL_PAIR/SINGLE_END/NETWORK_GROUP/
  NO_MARKED_END_ON_NET/CONFIRMED_PHYSICAL_PAIR), TEYİT/aksesuar değeri yok; kısa köprüler yalnız sayılıyor
  ([service.py:18, 818-840](analyzer_v3/service.py#L18)). MAIN.md:551-571 ve 866 ayrımı zorunlu kılıyor.
- Yeniden üretim: E122 Excel'inde `-17K53` için pinler yalnız {14, A1, A2}; `:11` hiçbir satırda yok.
  `K\d+:11` deseni 14 satırda, hepsinde röle çiftinin yalnız birinin 11'i X4'e gidiyor. Ayrıca `-17K55:A2`,
  `-17K57:A2`, `-17K59:A2` ve `=170 -23K63..69:A2` Excel'de yok (bobin A2 fiziksel olarak zorunlu) →
  Excel takılabilir/tarak köprüyle yapılan bağlantıları içermeyen bir **tel** listesi.
- Etki: pilotun 3 "teyitli çift"inden 1'i, UVP pratiğinde tel değil aksesuar köprüsü olabilir. Kural
  genelleşirse her röle çiftinde 1 fazla tel (bu belgede ≥14 nokta). Ölçülen precision: sayfa 4'ün 7
  çiftinden 6'sı Excel'de birebir, 1'i (C02) yok. Aynı desen A2 zincirleri için de geçerli.
- Düzeltme: C02'yi CONFIRMED_PHYSICAL_PAIR'den "TEYİT — tel mi takılabilir köprü mü" kaydına indir ve tek
  soruyla kullanıcıya sor. Satıra `bridge_candidate` (aynı sıra/komşu röle, kısa) ve
  `wire_or_accessory='TEYİT'` alanı; bu satırlar ana listeye değil Teyit kovasına. Kullanıcıdan yazılı
  "UVP köprü kuralı" (hangi bağlantılar tarak/çapraz köprü ile yapılır) → sonraki projelerde kaynaklı öneri.
- Doğrulama notu: kural doğrulayıcı "çelişki değil, iki liste farklı kapsamda" dedi; doğru — bulgu buna göre
  yeniden yazıldı. Ek bulgu merceğindeki N24.30 örneği yanlıştı (o ağ doğru olarak NETWORK_GROUP). 2/3 ayakta.

**B7 — T dağıtımı için kaynaklı UVP kuralı yok; her T insana gidiyor.**
- Yer: [geometry.py:281-283, 296-297](analyzer_v3/geometry.py#L281-L297) `BRANCH_ORDER_NOT_INFERRED`;
  [service.py:811-812](analyzer_v3/service.py#L811-L812) "Fiziksel tel çiftleri buradan türetilmez";
  çiftler yalnız açık teyitten. Geometri: T'de hedef yönü nesne yapısında yok (§4).
- Yeniden üretim: raw_page.json (425.20,228.77) düğümü: L1882 aşağı (-17K55:11), L1933 sol (-17K53:11),
  L1934 sağ → L1935 (-X4:4); geçen yatay tel iki nesneye bölünmüş, ortak kimlik yok.
- Etki: panoda yüzlerce T; her biri elle karar → 5 dk/sayfa hedefine ulaşılamaz. Kullanıcının Excel'i UVP'nin
  fiili T kararlarını (ve köprü kapsam dışı bırakma kararlarını) içeriyor; bu bilgi kullanılmıyor.
- Düzeltme: kullanıcıdan yazılı "UVP T-dağıtım kuralı" (Excel örneklerinden türetilir, kullanıcı onaylar,
  MAIN'e eklenir) → satırlar "ÖNERİ (kaynak: UVP kuralı)", onay kullanıcıda. Tahmin değil: MAIN.md:437-439
  ve 482-489 isimlendirme algoritmasının kullanıcı tarafından verileceğini söylüyor; aynı yol.
- Doğrulama notu: "MAIN öncelik listesi: kullanıcının belirttiği kural" atfı yanlıştı (o madde yalnız renk
  önceliğinde, MAIN.md:256-260); genel öncelik MAIN.md:58-64, UVP standardı 3. sırada girer. Kural
  doğrulayıcı "öneri MAIN yasağına çarpar" dedi; kaynaklı kullanıcı kuralı tahmin sayılmadığı için 2/3 ayakta.

**B8 — Kablo tanımı (Kabeldefinition) modellenmiyor.**
- Yer: [document.py:16](analyzer_v3/document.py#L16) DEVICE regex `-3W67`'yi cihaz sayar; analyzer_v3'te
  kablo/damar kavramı yok (grep boş); kapsam yalnız adresle ([models.py:20-22](analyzer_v3/models.py#L20-L22));
  [document.py:224-240](analyzer_v3/document.py#L224-L240) `signal_labels` `112/3W67:6` yazısını devam
  eşleşmesinde potansiyel adı olarak kullanır (service.py:301-315).
- Yeniden üretim: raw_page.json lines[2061] lw 0,71, 12 dikey kesişme, lines[2048-2059] 45° işaretler,
  top=502,31 kelimeleri 1,2,3,4,5,PE,6..11; `continuations(4)` çıktısında `source_signal=112/3W67:6`.
- Etki: MAIN "ÇOK DAMARLI KABLOLAR" (damarlar ana listeye girmez) ve "hazır kablo" kurallarının kod karşılığı
  yok; kablo kavramı olmadan damar dışlaması ve Coklu_Kablolar sayfası yapılamaz.
- Düzeltme: kablo tanım çizgisi dedektörü (ince lw + 45° işaretler + `-W` etiketi + damar kelimeleri) →
  kesilen teller `CABLE_CORE` ve damar no. `signal_labels`'ta kablo damar etiketini **silme** (4 doğrulanmış
  devamın ikinci kanıtı kaybolur), tür olarak `CABLE_CORE_LABEL` işaretle.
- Doğrulama notu: "kablo çizgisi pano sınırıdır" ifadesi yanlıştı — pano/saha sınırı ayrı kesikli cetvel
  (y=572,18, DASHED_RULE_PIECE); kablo tamamen pano içinde de olabilir. 3/3 ayakta.

**B9 — Potansiyel adı ağa bağlanmıyor; renk/kesit için tek yol bu ve P07 ön koşul olarak yazmıyor.**
- Yer: [service.py:144](analyzer_v3/service.py#L144) kesit/renk sabit `''`+`UNKNOWN`;
  [service.py:768-772](analyzer_v3/service.py#L768-L772) satır sözlüğünde potansiyel alanı yok; potansiyel
  yalnız devam eşleşmesi ve dash kanıtında okunuyor. [PLAN.md:43-44](PLAN.md#L43-L44) P07.
- Yeniden üretim: `table(4)` satırlarında `potential` alanı yok; words.json P24.32 bbox ↔ L1880 ucu 3,54 pt.
- Etki: PDF'te renk kodu yok, kesit yalnız genel not; Excel'de DBU 257/322 ve 1 mm² 237/322 → renk/kesit
  ancak "bu tel P24/N24/PE/L1" bilgisi + TROESTER standardı ile doldurulur. Ağ→potansiyel olmadan 30/31.
  sütunlar boş kalır. Bazı uçlarda potansiyel pin adında (`-X4:P24.32`) — kısmi.
- Düzeltme: ağ→potansiyel iliştirme (ray ucu ≤4 pt kelime; xref/cihaz/kablo elenir), satıra `potential` +
  kaynak; PLAN P07'ye ön koşul; TROESTER standardı xlsx'inden kaynaklı renk/kesit kural tablosu.
- Doğrulama notu: 3/3 ayakta; satır referansı 800-804 → 768-772 düzeltildi.

**B10 — Kör test seti dondurulmamış; kısmi sızıntı zaten var.**
- Yer: `13sb004-e530/=530.pdf` (26 sayfa, aynı müşteri, aynı antet notu) + `UVP_Kablo_Üretim_List.xlsx`
  (106 satır). PLAN.md'de "530" hiç geçmiyor; P08 "hash'li referans" der, dosya adı vermez.
- Yeniden üretim: `grep -c 530 PLAN.md` → 0; `ls output/pilots` → yalnız E122.
- Etki: eşikler/kütüphane bu projeye bakılarak ayarlanırsa kör test kaybolur. MAIN'in isimlendirme örnekleri
  (`X4:N24.10-1:1`, `X4:P24.11-3:1`, `=530+E530-4D22:L1+`) yalnız E530 Excel'inde var → isimlendirme
  açısından tamamen kör değil. Bu denetimde E530 Excel'i okundu (yapı/sayı); PDF'in yalnız 1. sayfa metni okundu.
- Düzeltme: iki dosyanın sha-256'sı PLAN'a; "P08'e kadar kod/eşik ayarında açılmaz"; E122'nin
  işaretlenmemiş sayfaları ayrı "dev-test" listesi.
- Doğrulama notu: 3/3 ayakta.

**B11 — Sayfa düzeyi geçersizleştirme: her yeni işaret o sayfadaki tüm incelemeleri düşürüyor.**
- Yer: [service.py:1118-1124](analyzer_v3/service.py#L1118-L1124) `change()` → `mark_stale([page],...)`;
  service.py:1195 `change_box()` aynı; [store.py:96-110](analyzer_v3/store.py#L96-L110) kesişim yalnız sayfa
  kümesi, `pin_ids` kullanılmıyor. Dar imza deseni yalnız DASH_RUN'da var
  ([service.py:1147-1152](analyzer_v3/service.py#L1147-L1152)). [PLAN.md:220](PLAN.md#L220) "bilerek geniş".
- Yeniden üretim: rev8'de 2 PE işareti eklenince C01/C02/C03 + 2 kullanıcı kaydı NEEDS_REVIEW oldu
  (`review/20260910_sayfa4_sistematik_tamamlama.md:52-58`).
- Etki: işaretleme ile inceleme iç içe yapılırken O(N²) yeniden onay; toplu öneri eklendiğinde o sayfadaki
  tüm onayları süpürür. İşaretleme bittikten sonra yakınsar (doğrulayıcı düzeltmesi), ama gerçek iş akışı iç içedir.
- Düzeltme: PIN_PAIR/CLAIM için kesişimi `pin_ids` + o pinlerin graf bileşeni imzası üzerinden kur; sayfa
  düzeyi yalnız maske/kutu değişiminde. Yeni alan gerekmez.
- Doğrulama notu: "MAIN kuralı" atfı yanlıştı (kural PLAN.md:57'de). 2/3 ayakta.

**B12 — İşaret kaynağı yanlış etiketli.**
- Yer: [models.py:38](analyzer_v3/models.py#L38) `MARK_METHODS={'MANUAL','P04_CANDIDATE'}`;
  [prepare.py:104-106](analyzer_v3/prepare.py#L104-L106) tohum notu "Elle işaretlenmiş pilot pini".
- Yeniden üretim: annotations.sqlite3 pins → MANUAL 20 (13 koda gömülü tohum + 7 "Claude pilot işareti"),
  P04_CANDIDATE 12; README.md:106 ve PLAN.md:306 "hepsi Claude tarafından kondu".
- Etki: MANUAL kaydı "kullanıcı elle işaretledi" gibi okunur; asıl yanıltıcı olan MAIN.md:1024-1026
  tablosunda olmayan 8 tohum ucu (17K52/53/55:14, X4:1/2/3, N24.30×2). Effort ölçümü (0,1 s/olay) anlamsız.
- Düzeltme: `AGENT_PROPOSED` değeri; 32 kaydın olay günlüğüyle yeniden etiketlenmesi; arayüzde ayrı rozet.
- Doğrulama notu: 3/3 ayakta (P2/P3).

### P3

**B13 — P08 ölçüm tanımı eksik (birim, payda, sayfa düzeyi).**
- Yer: [PLAN.md:72-76](PLAN.md#L72-L76) precision ≥98 / recall ≥95 / çözülemeyen ≤5, birim ve evren yok;
  MAIN.md:521-548 üç düzeyi (EXACT PHYSICAL / SAME NETWORK / NOT FOUND) ve MAIN.md:733-800 karşılaştırma
  kurallarını zaten tanımlıyor ama PLAN ölçütü bunlara bağlanmamış.
- Ölçüm: standart pano PE satırları E122 7/322 (%2,2, tavan %97,8 — hedef sağlanabilir), E530 7/106 (%6,6,
  tavan %93,4 < %95). Not sütunu bu satırları 0 yanlış pozitifle ayırıyor. Excel'de sayfa/Blatt sütunu yok →
  sayfa düzeyi recall paydası türetilemez; precision bugün ölçülebilir (6/7). UVP koşu son eki (`-n:m`)
  56/322 satırda; fiziksel uç düzeyi eşleşme bu satırlarda ancak hat seviyesinde.
- Düzeltme: P08'e üç satır: (a) birim = yönsüz fiziksel uç çifti, iki düzeyde raporlanır (hat/ağ ve tam
  uç); (b) payda = KAPSAM / STANDART_TABANLI_PE / KAPSAM_DIŞI önceden sınıflandırılır (kullanıcı bir kez
  onaylar), hedefler yalnız KAPSAM'da; (c) UVP son ek algoritması P07 girdisi olarak kullanıcıdan alınır.
- Doğrulama notu: üç ayrı bulgu (birim, PE paydası, sayfa paydası) ayrı ayrı P3'e indirildi/düştü; burada birleştirildi.

**B14 — `signal_labels` kara liste; kesit/birim/renk yazısı potansiyel adı sayılabilir.**
- Yer: [document.py:236](analyzer_v3/document.py#L236) yalnız XREF/DEVICE/LOCAL_LOCATION/saf rakam eleniyor.
- Yeniden üretim: fonksiyona `['1,5','2,5mm²','0,75','12','1.5','P24.32','BK','Cu','mm²']` verince
  `['1,5','2,5mm²','0,75','P24.32','BK','Cu','mm²']` geçiyor. Sayfa 4'te gerçekleşmedi.
- Etki: sayfa devamı eşleşmesi sahte ikinci kanıtla kurulabilir (yanlış pozitif) veya yakın kesit yazısı
  gerçek potansiyeli gölgeleyebilir (yanlış negatif).
- Düzeltme: pozitif şekil (`^(P|N)24\.\d+$`, `^L[123]$`, `^(PE|N)$`, `^[0-9A-Z]+/[0-9A-Z]+W\d+:\S+$` kablo
  damarı ayrı türle).
- Doğrulama notu: 3/3 ayakta.

**B15 — Cihaz iç bağlantısı kuralının kod karşılığı yok; kütüphane eşleşmesi iç maskeyi taşımıyor.**
- Yer: PHYSICAL_PAIR kararında "iki uç aynı cihaz" kontrolü yok ([service.py:805-812](analyzer_v3/service.py#L805-L812));
  maske yalnız elle/tohum kutu ([geometry.py:62-89](analyzer_v3/geometry.py#L62-L89), prepare.py:115-117);
  sayfa 5'te 17K57/17K59 her iki ucu işaretli, maske yok; README:231 "eşleşme maske uygulamaz".
- Doğrulama notu: bugün koruyan şey eksen filtresi ([geometry.py:119](analyzer_v3/geometry.py#L119)
  `NON_AXIS_OR_DEGENERATE`, kontak bıçağı diyagonal), maske değil (6 maske kaldırılınca sayfa 4 sonucu
  değişmedi). Eksen hizalı iç bağlantılı sembol ailesinde (PLC kartı, bara) bu koruma yoktur. 2/3 ayakta.
- Düzeltme: `len({normalized(q['device'])})==1` → `DEVICE_INTERNAL_SUSPECT`, Teyit kovası; kütüphane
  kaydına iç maske; maskesiz aile için satıra `SYMBOL_INTERIOR_UNMASKED` uyarısı.

**B16 — Aday pin kökeni saklanmıyor.**
- Yer: [models.py:57-72](analyzer_v3/models.py#L57-L72) `validate_pin` fazladan alanı düşürür; pin gövdesi
  yalnız device/id/kind/method/note/page/pin/point/version; `library_entry/family/status` aday satırında var
  (service.py:245-247) ama POST'ta taşınmıyor.
- Etki: hatalı şablondan türeyen adaylar geriye dönük bulunamaz/toplu geri alınamaz.
- Düzeltme: `source_kind`, `source_id`, `source_version` alanları; 12 aday için tek seferlik geri doldurma.
- Doğrulama notu: kütüphane geometrisi değişmez (yalnız family/status/note güncellenir), bu yüzden
  "kütüphane değişince bayatlatma" gereksiz; eşleştirme skorsuz/ikili. 2/3 ayakta.

**B17 — Dönme/ayna desteği yok ve eşleşme oranı ölçülmemiş.**
- Yer: [library.py:23,59](analyzer_v3/library.py#L23) `TRANSFORMS={'TRANSLATION'}`;
  [similarity.py:272-274](analyzer_v3/similarity.py#L272-L274). Sınır PLAN.md:104,106,110,227 ve README'de yazılı.
- Eksik olan: öğretilen aile başına kapsam içi sayfalarda eşleşen/eşleşmeyen sayısı ve nedeni. Şablon tabanı
  tek sayfa (kutu: sayfa 4'te 6, sayfa 5'te 1). Döndürülmüş cihaz yazısı ≠ döndürülmüş sembol (117 döndürülmüş
  yazının 52'si +M saha bağlayıcısı `nA72:X3:m`; kapsam içi 43).
- Düzeltme: P04'e ölçüm görevi; oran anlamlıysa 8 sabit dönüşüm (4 dik dönme × 2 ayna) şablon imzasına.
- Doğrulama notu: "dik yerleşim farkı" çıkarımı ölçümle çürütüldü (sayfa 28'deki 14,17×5,67 nesneler 3 noktalı,
  sigorta gövdesinin döndürülmüşü değil). 2/3 ayakta.

**B18 — Arayüz boşluk/açık iş listesi 40'ta kesiliyor, sırasız.**
- Yer: [app.js:63-69](analyzer_v3/static/app.js#L63-L69) `slice(0,40)`; `boxOverlay` tek kutu çizer;
  `gaps` sıralanmıyor (service.py:844). Satır/inceleme/dash listeleri kesilmiyor.
- Etki: 85 boşluğun 45'i kart olarak görünmüyor; "tümünü çiz" örtüsü yok.
- Düzeltme: sayfalama veya sınıf filtresi; tümünü çiz düğmesi; review/ dökümüne bağlantı.
- Doğrulama notu: 2/3 ayakta, P3.

**B19 — Kod/MAIN hash'i doğrulanmıyor, bayat; `.git` yok.**
- Yer: [prepare.py:179,191](analyzer_v3/prepare.py#L179) yazıyor; hiçbir yerde okunmuyor;
  [service.py:36-41](analyzer_v3/service.py#L36-L41) yalnız artifact_sha256. rev8 manifest: 11 kod dosyasının
  5'i bugünkü dosyayla uyuşmuyor, `dashed.py` listede yok, `main_sha256` bugünkü MAIN.md'den farklı
  (2026-09-10 maddesi çalışma oluşturulduktan sonra eklenmiş). annotations.sqlite3, review/*.md, evidence/*.png
  hash dışı. `.gitignore` var, `.git` yok.
- Etki: bir raporun hangi kural/kod sürümüyle üretildiği genel olarak kanıtlanamaz. Karşı kanıt: en güncel
  rapor (`20260910_cerceve_ve_pe_kesikli_hat.md:7`) üç kod hash'ini gömüyor ve bugünkü dosyalarla aynı.
- Düzeltme: `git init` + ilk commit; her rapora commit kimliği; başlangıçta code/main hash uyuşmazlığı
  `CODE_DRIFT/MAIN_DRIFT` bayrağı (hata değil, görünürlük).
- Doğrulama notu: "kanıt silinmez" hükmü MAIN'de değil PLAN.md:15,60'ta. 2/3 ayakta.

**B20 — "Nesne bölünmesi = bağlantı noktası" varsayımı belgelenmemiş ve sayfa başına sınanmıyor.**
- Yer: [geometry.py:40-58, 169-178](analyzer_v3/geometry.py#L40-L58) `T_OR_END` koşulsuz birleşir;
  README.md:269-272 davranışı yazıyor, EPLAN dışa aktarım özelliğine dayandığını yazmıyor.
- Ölçüm: sayfa 4'te 8 T'nin hepsinde nokta çemberi; sayfa 4'te T olmayan 2 çember üçlüsü (PE kesikli);
  sayfa 2'de çembersiz 2 T ((680,31;257,11), (666,14;242,94)) — görsel doğrulanmadı. Çalışma raporu 877
  noktasız kesişme sayıyor, ham ölçüm 49 (yalnız uzun hatlar); iki sayım farklı yöntem.
- Düzeltme: README'ye varsayım; sayfa başına "çembersiz T" ve "çemberli T-olmayan" listesi
  (`dashed.junction_dots` zaten var) rapora bağlanır.
- Doğrulama notu: 3/3 ayakta.

---

## 6. Çürütülen iddialar (kayıt için)

| İddia | Neden düştü |
|---|---|
| Sayfa 5 bayt-aynı kopya, pilot kanıtı geçersiz | Yalnız vektör geometrisi aynı; yazılar farklı (30 token); PLAN.md:301 zaten yazıyor; kütüphane sayfa 5'te dx=0/+56,69/+113,38 ötelemeyle eşleşti. |
| PLAN değişiklik günlüğü, kritik yol yok, 3 "sıradaki iş" | PLAN.md:18-47 kutucuklu P00-P08 kritik yol; "Sıradaki iş" 2 kez (257, 298), sonuncusu güncel; 28/85 boşluk farkı ardışık iki koşu ve gerekçeli. |
| Arayüz testi yok / effort ölçümü betik | Doğru ama PLAN.md:110 ve rapor §5 aynı içerikle yazıyor; kullanıcı adımını değiştirmiyor. |
| P07 sütun kapsamı belirsiz | MAIN.md:660/671 "varsayılan + kullanıcı isterse" ile düzenlemiş; ek sütunlar PDF'ten çıkarılabilir veri değil (EPLAN alanları). |
| Yerel servis token GET'te | server.py 132 satır (verdiğim satırlar yoktu); loopback + Host/Origin + POST token; README sınırı yazıyor; düzeltme gerekmiyor. |
| OCR/tarama yok | MAIN.md:1051 genel PDF desteğini sonraya bırakıyor; belge 99 sayfa vektör, 0 görüntü. |
| manifest `pins_marked` bayat | prepare.py:98'de sabit False, hiçbir yerde okunmuyor, hash'e dahil değil; ölü alan. |
| Sayfa yapısı/metadata teslimi yok | pdf2eplan'ın tasarrufu EPLAN'a yazmadan doğuyor; CSV dökümü aynı değeri üretmez; MAIN çıktı listesinde yok. |
| Belge düzeyi cihaz görünümü yok | `endpoints()` ve `coverage().other_pages` belge geneli çalışıyor; eksik olan yalnız "işlenmişlik" toplaması (B3'e katıldı). |
| MAIN karşılaştırma bölümü kodda yok | MAIN bağlayıcı, PLAN tekrar etmiyor; P07/P08 açık; payda tanımı B13'e katıldı. |
| C01-C03 kalıcı UNRESOLVED | `expected_revision=1` her yazımda düşer; tasarım (PLAN.md:57); kullanıcı arayüzden tazeler; `original_visual_evidence` korunuyor. |
| 58 sayfa 58 el turu | `--add-pages` virgüllü liste, tek komut + tek yeniden başlatma; arayüzden sayfa eklenemiyor (doğru ama P3). |
| PLC ailesi için model yok | Sayılar yanlıştı (56 → ~19 D modülü; A ailesi saha cihazı); sayfa 28 (ET200SP 8DO) zaten izlenmiş. Kalan doğru kısım: PLAN'da "PLC" hiç geçmiyor, MAIN QA listesinde var; kütüphanede tek 2 uçlu aile. |
| Ekonomik karar kapısı yok | Fiyat/API/12 ay araştırma dosyasında (satır 51) ve karşılaştırma protokolü §7.4'te var; PLAN'a taşınmamış (§3'e katıldı). |
| Döndürülmüş 117 etiket klemens+PLC | 52'si +M saha bağlayıcısı; yazı dönmesi sembol dönmesi kanıtı değil. |

---

## 7. İncelenmeyen alanlar

- `static/app.js` satır satır; `dashed.py` iç eşikleri; `tests/test_pilot.py`'nin tek tek iddiaları.
- Sayfa 28/36 tam geometri; sayfa 2'deki çembersiz iki T'nin görsel doğrulaması; rev1-rev7 klasörleri.
- E530 PDF içeriği (yalnız 1. sayfa metni); TROESTER/UVP standart xlsx'leri; 40+ sayfa performans/bellek.
- pdf2eplan fiilen denenmedi; FAQ Almanca sürümü ve "side by side" görselleri bakılmadı.
- Hiçbir çıktı elektriksel olarak PDF görseliyle satır satır doğrulanmadı; bu rapor kod/plan/geometri
  denetimidir, üretim doğruluğu kanıtı değildir.

---

## 8. Önerilen sıra

1. **Karar:** hedef ürün (A/B/C) + iki soru (EPLAN Runtime API lisansı; dış servise belge izni). PLAN'a yazılır.
2. **Dondurma:** E530 PDF + Excel sha-256 PLAN'a; "P08'e kadar açılmaz".
3. **Parametreleme (B2):** `--pdf/--scope/kök`, tohumlar bayrakla; ikinci proje açılabilir hale gelir.
4. **Genişlik paketi (B3+B4):** kapsam içi tüm sayfalarda aday arama, toplu öneri, klemens adı okuma, "sayfa/pano
   bitti" tanımı, operatör dk/sayfa ölçümü (kullanıcıyla 30 dk gerçek oturum).
5. **UVP kuralları (B6+B7):** Excel'den T-dağıtım ve köprü/aksesuar kuralı yazımı, kullanıcı onayı, MAIN'e ek;
   C02 sorusu.
6. **Doğruluk kapıları (B5, B8, B9, B14):** pano sınırı koşulu, kablo tanımı, ağ→potansiyel, pozitif etiket regex'i.
7. **P08 tanımı (B13)** ve `git init` (B19).
8. P06 (ücretli AI) bu sırada açılmaz; pdf2eplan denemesi ancak 1. adımdaki izinlerle.

---

## 9. Yeniden üretim komutları (salt okuma)

```
# Testler
python -m unittest discover -s analyzer_v3/tests -t .

# Kapsam ölçeği
python -c "import json,collections;d=json.load(open('output/pilots/E122/20260910_v3_p05_rev8/document_index.json',encoding='utf-8'));p=d['pages'];print(len(p),collections.Counter(x['doc_type'] for x in p),sum(1 for x in p if x['doc_type']=='Schaltplan' and x['scope']=='IN_SCOPE'))"

# Pin yöntemi / sayfa dağılımı
python -c "import sqlite3,json,collections;c=sqlite3.connect('output/pilots/E122/20260910_v3_p05_rev8/annotations.sqlite3');print(collections.Counter((json.loads(b)['method'],json.loads(b)['page']) for (b,) in c.execute('select body from pins')))"

# Pano sınırı: satır türü kararında in_scope yok
sed -n '804,813p' analyzer_v3/service.py

# Klemens adayları (7/10 pin okunuyor)
python -c "from analyzer_v3.service import Pilot;p=Pilot('output/pilots/E122/20260910_v3_p05_rev8');p.refresh();r=p.candidates('box_0904b5fe6b7d42f2b204aee8e0ec0655');print([[(pn['page_pin_texts'],pn['issues']) for pn in c['pins']] for c in r['candidates']])"
# (Düzeltme 2026-09-10: alanlar adayın kökünde değil candidates[].pins[] altında; Astra'nın tespiti doğru. Çıktı: 7 adayda rakam, 3 adayda PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET.)

# C02 Excel'de var mı
python -c "import openpyxl;ws=openpyxl.load_workbook('13SB003_05_+E122/UVP_Kablo_Üretim_List.xlsx',read_only=True)['UVP_Kablo_Üretim_List'];print([(r[0],r[14]) for r in ws.iter_rows(min_row=2,values_only=True) if r[0] and '17K53' in str(r[0])+str(r[14])])"

# Kod hash sapması
python -c "import json,hashlib,pathlib;m=json.load(open('output/pilots/E122/20260910_v3_p05_rev8/manifest.json'));d=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();print([n for n,h in m['code_sha256'].items() if d(pathlib.Path('analyzer_v3')/n)!=h], m['main_sha256']==d(pathlib.Path('MAIN.md')))"

# İkinci proje açılamıyor
python -c "from analyzer_v3.prepare import prepare;prepare('output/pilots/E530/test')"
```
