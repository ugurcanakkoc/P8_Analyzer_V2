# UVP PDF → EPLAN Atölyesi — mevcut pilot ve yeni şema hedefi

Önce kökteki MAIN.md'nin tamamı, ardından PLAN.md'nin **2026-09-11 güncel sırası** okunur.
Yeni hedef PDF sayfasını EPLAN P8'de düzenlenebilir elektrik şemasına dönüştürmektir;
köprü imalatı kullanıcıya bırakılır. Varsayılan şema filtresi pano içidir, isteğe bağlı tam
sayfa önizlemesi öngörülür. 37 sütunlu tel Excel'i ikincil çıktıdır.

**Mevcut kod henüz EPLAN sayfası oluşturmuyor.** Aşağıdaki bölümler mevcut/eski pilot
özelliklerinin tarihçesini de içerir; eski “yalnız bağlantı / cihazlar kullanıcıdan” ifadesi
yeni hedefi sınırlamaz. Yeni geliştirme [PLAN.md](../PLAN.md) S01–S06 ve
[CLAUDE_NEXT.md](../CLAUDE_NEXT.md) ile yürütülür. Bu belge değişikliği işaret/onay veya
üretim durumunu değiştirmez.

## Çalıştırma

Windows'ta kökteki `start_analyzer.cmd` dosyasını açın; ekrandaki yerel adresi ziyaret edin.
İlk çalıştırma yalnız bilinen E122 PDF'sinden yeni pilot klasörü oluşturur. Var olan sonuçlar
yeniden hazırlanmaz veya üzerine yazılmaz. Gerekirse başka portla sunucu başlatılabilir.

Bu bilgisayarda doğrulanan Python yolu:
`C:\Users\UVW-U\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

Proje kökünden, bu Python ile çalıştırılan modüller:

```
python -m analyzer_v3.prepare
python -m analyzer_v3.server
python -m unittest discover -s analyzer_v3/tests -v
```

Bağımlılıklar requirements.txt içinde sabitlenmiştir. Başlatıcı paket indirmez/kurmaz.
Sunucu yalnız `127.0.0.1:8765` üzerinde çalışır. Yerel sayfa dışında HTTP erişimi/AI çağrısı yok.
Tarayıcıda pin ekleme/düzeltme yalnız bu pilotun SQLite dosyasına ve değişiklik günlüğüne yazılır.
Kaydı geri taşımak eski teyidi otomatik geri getirmez. Arayüzde yalnız **inceleme kaydı** tutulur
(kim, ne zaman, hangi pin sürümleri ve hangi sayfalar); bu kayıt üretim/import onayı değildir.

## Kullanım

1. Sağdaki C01/C02/C03 ilişkisine tıklayın: ilgili PDF çizgisi renklendirilir.
2. Şemadaki bir pini veya açılır listedeki pini seçin: işaretli diğer uçlara erişim gösterilir.
3. `Pin bilgisini düzelt` ile kimlik/konum değiştirin; `Pin ekle` ile yeni bir uç işaretleyin.
4. Değişiklik kaydı bütün geçmiş örnek teyitlerini askıya alır. Eski ilişkiler görünür kalır.

Kimlik ve konum elle girilir. Otomatik tanıma izlenimi verilmez. Aynı etiketin birden fazla
çizim konumu ayrı kayıt kimliklerine sahiptir. P24/N24 adları burada kesin fiziksel klemens
son eki değildir. Renk/kesit boş ve UNKNOWN kalır.

## P04 — Benzer sembol adayları (öneri)

Sağdaki `Benzer sembol adayları` bölümünde elle işaretli bir sembol (şablon kutusu) seçilir ve
`Benzerlerini ara` çalıştırılır. Eşleştirme yalnız **çizilen şekle** ve yalnız **öteleme**ye dayanır:

- Şablon kutusundaki çizim parçaları birebir eşleşmezse aday reddedilir ve `elenen konum` olarak görünür.
  NO/NC farkı gibi ek/eksik parça bu nedenle eşleşmez; sessizce elenmez.
- Aynalanmış/döndürülmüş yerleşim eşleşmez. Bu bir kapsam sınırıdır, bulunmamış olması yokluk kanıtı değildir.
- Cihaz ve pin adı **her örnek için sayfa yazısından yeniden okunur**; şablondan kopyalanmaz. Aynı sayfada
  17K52'nin üst pini `13`, 17K53/17K55'in üst pini `11`'dir ve aday listesi bu farkı uyarı olarak gösterir.
- Aynı konumda yazı yoksa veya birden fazlaysa ad üretilmez; `bulunamadı` / `belirsiz` işaretlenir.
- Her aday pin noktasında gerçek dış çizgi olup olmadığı ayrıca sayılır. Şekil eşleşmesi devre eşleşmesi
  değildir: dış hat sayısı şablondan farklıysa uyarı verilir.
- Aday hiçbir şey kaydetmez: pin oluşturmaz, teyit üretmez, mevcut ilişkilerin durumunu değiştirmez.
  `Pin taslağı` yalnız formu doldurur; cihaz ön eki şablondan gelir ve sayfadan doğrulanmamıştır,
  kayıt kullanıcının `Kaydet` işlemiyle olur.

Görsel kanıt: `output/pilots/E122/20260909_v3_p03/evidence/p04_benzer_adaylar.png`.

## P05 — Sayfalar arası, uç uzlaştırma, tamlık taraması

Sağdaki `Sayfalar arası` bölümünde üç ayrı görünüm vardır. Hiçbiri tel/bağlantı üretmez.

- **Çapraz referanslar.** `=Anlage/Blatt.Pozisyon` biçimindeki yazılar (`=122/17.52`, `/4.23`) sayfa
  kimliğinden çözülür: aynı belge türünde (Schaltplan/Stückliste) `Anlage + Blatt` eşleşmesi aranır.
  Birden fazla aday varsa `AMBIGUOUS_TARGET_PAGE` yazılır, seçim yapılmaz. Pozisyon eki (`.52`) ham
  metindir; pin, klemens veya sütun olarak **yorumlanmaz**.
  Bir cihazın altındaysa `KONTAK/BOBİN REFERANSI`, değilse `HAT DEVAMI ADAYI` olarak işaretlenir;
  ikisi de `CROSS_REFERENCE_ONLY_NOT_A_WIRE` ilişkisidir.
  Cihazın basılı fonksiyonu korunur: sayfa 4'teki `-17K52` ile sayfa 28'deki `=112-17K52` aynı
  cihazdır ve hedef sayfanın `=122` Anlage'si bu adı **değiştirmez**. Sayfadan miras alınan adres
  parçaları `DEVICE_ADDRESS_PART_INHERITED_FROM_PAGE` ile görünür kalır.
- **Cihazın kendi konumu.** Bir cihaz yazısının hemen altında `+Ort` basılıysa (ör. `-3A72` / `+M113`)
  o konum cihaza aittir ve sayfanın Einbauort'unun yerine geçer: saha cihazı pano içi sayılmaz.
  Bir konum işareti tek bir cihaza bağlanamıyorsa hiçbir cihaz sayfadan konum devralmaz; sayfa
  `LOCAL_LOCATION_MARKER_UNASSIGNED` alır ve o sayfadaki cihazlar kapsam dışı/belirsiz kalır.
  Belgede 25 böyle işaret var (`+M113`, `+M122`, `+M132`, `+M153`).
- **Uç uzlaştırma.** İşaretli her ucun (`cihaz:pin`) belgede nerede basılı olduğu aranır.
  Pin adı `:` içerebilir (`-4D27:X1:P1`); eşleştirme istenen cihaz adının önünden yapılır, sondaki
  `:` üzerinden bölünmez.
  Pin yalnız cihaz yazısında `:` ile basılıysa görülür; klemens sırasındaki ayrı rakamlar burada
  aranmaz (`DEVICE_PRINTED_PIN_NOT_PRINTED`). Aynı ad birden fazla sayfadaysa
  `multiple_drawing_locations` verilir: **ad eşleşmesi tek fiziksel nokta değildir.**
  Arama tüm belge türlerinde yapılır ve her satır kendi türünü yazar; Stückliste'de bulunan bir kayıt
  cihazın basılı olduğunu gösterir, bağlantı göstermez. Klemens tablosu bilerek yalnız şema
  sayfalarından kurulur; bu PDF'te ayrı bir Klemmenplan belgesi yoktur ve bu ekranda yazılıdır.
- **Sayfa devamı doğrulama.** Bir sayfa referansının yanında gerçekten açık bir çizgi ucu var mı ve
  hedef sayfada karşılıklı bir uç bulunuyor mu, hedef sayfanın **kendi geometrisi** üzerinden sınanır.
  Eşleşme iki kanıtla kurulur: (1) hedef sayfada kaynak sayfaya geri işaret eden referans,
  (2) iki uca da basılı **aynı potansiyel adı** (ör. `P24.32`, `L1`). Referansın pozisyon eki
  (`.23`) yine yorumlanmaz. Uçta çizgi yoksa `NO_LINE_END_AT_REFERENCE`, birden fazla uç varsa
  `MULTIPLE_LINE_ENDS_AT_REFERENCE`, hedef sayfa hazırlanmamışsa `TARGET_PAGE_NOT_TRACED` yazılır;
  hiçbirinde seçim yapılmaz. Kontak/bobin referansı bu kontrolden muaftır
  (`DEVICE_REFERENCE_NOT_A_CONTINUATION`).
  **Eşleşme fiziksel tel değildir:** aynı potansiyelin devam etmesi elektriksel ağdır; hedef
  sayfadaki cihaz ucu ancak o sayfada pin işaretlenirse doğrulanır.
  Sayfa 4 için sonuç: 19 referansın 10'u iki tarafta çizgi kanıtıyla eşleşti (sayfa 2 ve 5),
  3'ü kontak/bobin referansı, 4'ü uçsuz dikey klemens yazısı, 2'si çok uçlu demet.
- **Tamlık taraması.** Sayfada basılı olup hiç işaretlenmemiş cihazlar, izlenen yolların üzerindeki
  açık uçlar (varsa yanındaki sayfa referansıyla), izlenen/izlenmemiş çizgi sayısı ve bağlanamamış
  pinler listelenir. Bu bir tamlık kanıtı değildir; yalnız kapsanmayanı görünür kılar.

Belge indeksi 73 sayfanın tamamı için sayfa kimliği, çapraz referans ve cihaz yazılarını tutar
(`document_index.json`, manifest hash'ine dahil). Çizgi geometrisi yalnız `traced_pages`
listesindeki sayfalar için çıkarılır: bu çalışmada 4, 2 ve 5
(`python -m analyzer_v3.prepare --run <yeni-klasör> --pages 2,5`). Pin işaretleri artık sayfa
başınadır; bu çalışmada sayfa 4, 5 ve 2'de işaret vardır ve hepsi Claude tarafından konmuş
önerilerdir (kullanıcı görsel onayı bekleniyor). İşaretlenmemiş bir sayfada referansın hedef
taraftaki cihaz/pin ucu doğrulanmamış sayılır. Kapsam kararı fonksiyon **ve** konum ile verilir:
bu belgede sayfa 1 (`+E112`) ve sayfa 50 (`+E111`) kapsam dışıdır.

Dikey (döndürülmüş) basılı yazılar glif matrisinden okunur: ham metin `raw_text` olarak saklanır,
kayıt `rotated` işaretiyle görünür. Yön belirlenemezse ham sıra korunur ve sayfa
`ROTATED_TEXT_ORDER_UNDECIDED` alır. Uç uzlaştırma **tüm** belge türlerini tarar (Schaltplan,
Stückliste, Layout) ve her satırda türü yazar; klemens tablosu bilerek yalnız şema sayfalarından kurulur.

Görsel kanıt (önceki turdan taşındı): `.../20260910_v3_p05_rev8/evidence/p05_sayfa4_tablosu.png`,
`p05_yol_sayfa4.png`, `p05_yol_sayfa5.png`.
Bu turda tarayıcı ekran görüntüsü alınamadı (Playwright bağlanmadı); kütüphane ekranının görsel
kontrolü kullanıcıdadır.

## Uçtan uca pilot — sayfa 2/4/5

Kullanıcı kararıyla ilk uçtan uca deneme fiziksel sayfa **2, 4, 5** üzerinde yapılır.

- Üstteki `Sayfa` seçicisi görüntüyü, pinleri, kutuları ve şablon listesini o sayfaya çevirir.
  Her pin ve kutu bir sayfaya aittir; izlenmeyen sayfaya işaret konamaz.
- `Sembol kutusu` düğmesi: iki köşeye tıklayarak yeni sembol ailesinin sınırı çizilir. Kutu hem
  sembol içini izlemeden çıkarır hem de P04 şablonu olur. İlk örnek daima görselden elle doğrulanır.
- `Benzerlerini ara` aynı sayfadaki diğer örnekleri önerir; cihaz ve pin adı **o sayfadan** okunur.
  Örnek: şablon `-17K56`'nın üst pini `13` iken adaylar `-17K57`/`-17K59` için `11` okundu ve fark
  uyarı olarak gösterildi.
- `Sayfalar arası yolu göster`: seçili pin için kaynak sayfa izlemesi + doğrulanmış sayfa devamı +
  hedef sayfadaki işaretli uçlar. Karta tıklamak ekranı hedef sayfaya çevirir ve orada izlenen
  çizgiyi çizer. Sıçrama `NETWORK_CONTINUATION_NOT_ONE_PHYSICAL_WIRE` etiketiyle gelir:
  **aynı potansiyelin devamı elektriksel ağdır, tek fiziksel tel değildir.**
- Hedef sayfada işaretli uç yoksa `NO_MARKED_PIN_ON_TARGET_PAGE` gerekçesi verilir; uydurulmaz.
- `İşaretleme süresi`: her kayıt olayının yöntemi (`MANUAL` / `P04_CANDIDATE`) ve olaylar arası
  duvar saati farkı. Bu süre inceleme ve ara vermeleri de içerir; saf işaretleme süresi değildir.
- Bir pin taşındığında ona dayanan yol sonucu ve eski teyitler kendiliğinden düşer; geri taşımak
  eski onayı geri getirmez.

Görsel kanıt: `output/pilots/E122/20260910_v3_p05_rev8/evidence/p05_yol_sayfa4.png` ve
`p05_yol_sayfa5.png`. Pilot raporu: `.../review/20260909_uctan_uca_pilot.md`.

## Sayfa 4 sistematik tamamlama

- `Bağlantı tablosu`: sayfadaki her çizim ağı sınıflandırılır. `PHYSICAL_PAIR` (iki uç, dalsız,
  açık uçsuz) yalnız **fiziksel tel adayıdır**; `NETWORK_GROUP` ortak potansiyeldir ve ondan uç
  çifti türetilmez; `SINGLE_END` karşı ucu işaretlenmemiş ağdır. İşaretli ucu olmayan kapsam içi
  ağlar gerekçeli **boşluk** satırı olur. Kalanlar "incelenmemiş ağ" sayacında görünür.
- Bağımsız ikinci kontrol: kısa köprüler (≤12 pt) ve T dalları satırlardan bağımsız sayılıp
  satır/boşluk/graf dışı/hesapsız olarak dağıtılır.
- `Eksik iş listesi`: her kapsam içi cihazın işaretli pinleri, işaretsiz ağları ve çözülemeyen
  devamları. Cihaz durumu daima `NEVER_COMPLETE` — bir pinin bulunması cihazı tamamlamaz.
- `İncelemeler`: kullanıcı incelemesi, incelendiği **pin sürümleri ve bağlı olduğu sayfalarla**
  saklanır. O sayfada pin veya sembol kutusu değişirse kayıt silinmez, `NEEDS_REVIEW` olur ve
  eski geometri geri gelse bile kendiliğinden canlanmaz. Geçersizleştirme bu sürümde sayfa
  düzeyindedir (bilerek geniş). İnceleyen adı zorunludur.
- `Bağlantı tablosu` ayrıca `CONFIRMED_PHYSICAL_PAIR` satırları verir: yalnız açık kullanıcı
  teyitlerinden (tohum claim veya `PIN_PAIR` incelemesi) gelir, ortak ağdan çift türetilmez.
  Satırda **iki ayrı alan** vardır: `line_evidence` (güncel yol var mı) ve `review_state` (karar
  geçerli mi). Karar askıya alınırsa satır silinmez, `GEÇMİŞTE TEYİTLİ — YENİDEN İNCELEME
  GEREKİYOR` olur; `Yeniden inceledim olarak kaydet` ile tazelenir.
  Bir uç çifti **tek satırdır**: yön satır üretmez, yeniden onay yeni satır açmaz — güncel inceleme
  olur, eski kararlar `review_history` içinde kalır. `C02`/`C03` referansları sabittir.
- Sembol aileleri artık eğri nesnelerle de eşleşir (klemens dairesi, sigorta gövdesi).
  `geometry.json` içindeki `curves` yalnız sembol eşleştirme içindir; **tel olarak izlenmez**.
  Yanlış çizilen kutu silinmez, pasife alınır.

- `Bağlantı tablosu` her çizim bileşenini **kanıtlı sınıfa** ayırır (`unreviewed_breakdown`):
  `SYMBOL_FILL_SCANLINE` (dolu sembol gövdesinin tarama çizgisi), `DASH_ZONE_BOX_EDGE`,
  `DASH_CONDUCTOR_CANDIDATE`, `DASH_UNDECIDED` (ölçülmüş kesikli hat koşuları),
  `TEXT_STROKE`, `SYMBOL_INTERIOR_MASK`, `TITLE_BLOCK`, `PAGE_FRAME`,
  `CONDUCTOR_CANDIDATE` (tek eksende ≥20 pt, iki açık uç, dal yok) ve `UNEXPLAINED`.
  **İncelenmemiş bileşen sayısı bağlantı sayısı değildir.** Hiçbir sınıf toplu elenmez:
  `UNEXPLAINED` bileşenlerin tamamı tek tek listelenir. Yalnız sayfa çerçevesi, yazı bloğu,
  yazı çizgisi ve dolgu taraması "açık iş" sayılmaz; bunlar da dökümünde görünür kalır.
- Döndürülmüş (dikey) sayfa referanslarında uç, yazının yanında değil **kendi ekseninde altında**
  aranır; aksi hâlde gerçek devamlar `NO_LINE_END_AT_REFERENCE` diye kaybolur.
- **`PAGE_FRAME` üç kanıt ister, uzunluk tek başına yetmez:** (1) her İKİ yönde de sayfanın
  ≥%90'ı, (2) dört kenarın da sayfa sınırına yakın olması, (3) kapalı çerçeve geometrisi
  (≥4 parça, hem yatay hem dikey, ≥4 köşe). Biri eksikse çizim çerçeve sayılmaz ve **açık işte
  kalır**. Eski "%80 genişlik VEYA %80 yükseklik" kuralı sayfa 4'ün gerçek L1/L2/L3 baralarını
  çerçeve sayıyordu; onları yalnız üzerlerindeki pin işareti kurtarıyordu.
- **Her iletken adayı açık iştir:** düz ya da kesikli, yakınında kapsam içi cihaz yazısı olmasa
  bile boşluk (açık iş) kovasına girer. Yalnız sayfa çerçevesi, yazı bloğu, yazı çizgisi, dolgu
  taraması ve kapalı kutu kenarı iş sayılmaz — bunlar da sınıf dökümünde görünür kalır.

## Kesikli / kesikli-noktalı hatlar — `/api/dash` (yalnız ÖNERİ)

`analyzer_v3/dashed.py` kesikli hatları **ölçer ve önerir**; graf, `geometry.json` ve ham
parçalar değişmez (yanıtta `graph_unchanged`, `raw_geometry_untouched`).

- **Cetvel** kimliği `(eksen, koordinat, kalem kalınlığı)`. Kalınlık kimliğin parçasıdır:
  aynı eksende farklı kalemle çizilmiş iki nesne aynı hat değildir.
- **Kesikli mi?** desen yoğunluğu ≥0,02 parça/pt **ve** tipik boşluk ≤12 pt. (Ölçülen ayrım:
  kesikli 0,033–0,132; cihazlarla bölünmüş düz hat 0,0066–0,0091 parça/pt.)
- **Süreklilik ≠ bağlantı.** Kesikli hattın üstünden geçen tel onu kesmez ama ona bağlanmaz;
  `crossings_without_dot` altında ayrıca sayılır. Sembol maskesi/eğrisi veya yazı kutusu içeren
  boşluk koşuyu **kırar** (köprülenirse cihaz atlanır).
- **Birleşme noktası** çizimin kendi eş merkezli halkalarıdır (≥2 halka, tolerans 0,15 pt).
  Tek halkalı şekiller (lamba, motor, klemens dairesi) reddedilir ve `rejected_dots` altında
  raporlanır. Her nokta için kol sayısı ve kapalı kutu içinde olup olmadığı ölçülür.
  Nokta bir ÇİZİM işaretidir; fiziksel tel birleşmesi olduğu insan kararıdır ve **boşluk
  köprülemez**.
- **Kapalı kutu** (bölge/cihaz çerçevesi) dört cetvelin dikdörtgeni olarak bulunur ve köşeler
  çizimin kendi sıfır uzunluklu köşe iziyle doğrulanır — yakınlık eşiğiyle değil.
- Koşu sınıfı: `ZONE_BOX_EDGE` (iletken değil), `CONDUCTOR_CANDIDATE` (kapalı kutu parçası
  değil **ve** en az iki bağımsız kanıt), `UNDECIDED` (açık işte kalır). Aynı çizgi stili kanıt
  listesine girmez; aynı potansiyel adı tek başına yetmez.
- Her önerinin üç ayrı alanı vardır: `evidence` (görsel), `path_evidence` (grafın gerçekten
  izleyebildiği yol — ölçülür), `decision` (insan kararı, varsayılan `ONAY_BEKLIYOR`).
  Onaylanmış bir koşu bile yalnız **ortak potansiyel ağıdır**; ondan fiziksel tel çifti
  türetilmez.
- Var olan bir çalışmaya devam sayfası eklemek için:
  `python -m analyzer_v3.prepare --run <klasör> --add-pages 28,36`. Sayfa 4, tohumlar, işaretler,
  incelemeler ve kütüphane değişmez; yalnız hedef sayfaların geometrisi eklenir.

## Kalıcı sembol kütüphanesi

`output/library/symbols.sqlite3` — çalışmalardan **bağımsız**, yerel ve sürümlü. `Kütüphaneye kaydet`
seçili şablon kutusunu kaydeder; `Kütüphaneden adayları bul` kaydı açık sayfada arar.

- Saklananlar: aile adı (önerilir, düzenlenebilir), durum (`DRAFT`/`APPROVED`/`RETIRED`), şekil
  imzası ve çapa, göreli uç konumları ve türleri, cihaz/pin etiketi arama bölgeleri, kaynak kanıtı
  (PDF sha-256, çalışma, sayfa, kutu), müşteri/stil profili, desteklenen dönüşümler.
- **Kanıt olarak saklanan:** kaynak belgenin cihaz/pin yazısı (`evidence_only`). Yalnız
  karşılaştırma ve fark uyarısı içindir; yeni belgeye kimlik olarak aktarılmaz (`never_copied`) —
  aday satırlarında cihaz/pin alanı boştur, adlar o sayfadan okunur.
- **Hiç saklanmayan:** bağlantılar, renk, kesit, bağlantı onayı (`never_stored`).
- Eşleşme hiçbir şey kaydetmez: pin oluşmaz, maske uygulanmaz, bağlantı onaylanmaz
  (`applied_changes: false`). `Pin taslağı` cihaz alanını boş bırakır.
- Onay için onaylayan adı zorunludur; onaysız kayıt taslak kalır. Ad değişikliği ve onay sürüm
  artırır, geçmiş korunur.
- Yalnız **öteleme** desteklenir. Ölçek, dönme ve aynalama eşleşmez; eşleşmemesi yokluk kanıtı değildir.

## Şekil güvenilirliği ve çizgi esnekliği sınırları

Eğriler nokta yoluyla temsil edilir; aynı sınırlayıcı kutu aynı şekil sayılmaz. Nokta listesi
olmayan eski çalışmalarda eşleşme `CURVE_SHAPE_UNVERIFIED_BBOX_ONLY` ile işaretlenir.

| Durum | Bugünkü davranış |
|---|---|
| Tek çizgi / uç uca değen parçalar | destekleniyor |
| Aralıklı parçalar, gerçek kesikli hat | izlenmez (otomatik kapatma yok) |
| Sembol boşluğu, noktasız kesişim | köprülenmez |
| Aynı kutuda farklı şekil, ölçek, dönme | eşleşmez |
| Kutuda ek nesne (NC/PE deseni) | elenen olarak görünür |

## Veri ve güvenlik

- Çalışma: `output/pilots/E122/20260910_v3_p05_rev8/`. P03 çalışması `20260909_v3_p03/` ve ilk (hatalı
  dikey yazı çıkarımı içeren) P05 denemesi `20260909_v3_p05/` kanıt olarak değişmeden durur.
- `manifest.json`: kaynak hash, sayfa/Blatt, kutular/dönüş/dpi, bağımlılık ve ilk kod sürümü hash'leri.
- `raw_page.json`: değiştirilmemiş PDF çizgi/eğri/dikdörtgen/metin/görüntü metadatası.
- `geometry.json`: normalize edilmiş çizgiler; `page.png`: 300 DPI görsel.
- `seeds.json`: elle işaretli 13 pin, 3 kontak iç sınırı, 1 görsel düğüm işareti, 3 eski teyit.
- `pages/<n>/`: izlenen diğer sayfaların geometri, ham nesne, okuma sıralı kelime ve görselleri.
- `words.json`: okuma sırasına çevrilmiş kelimeler (ham metin `raw_text` alanında saklı).
- `document_index.json`: 73 sayfanın kimliği, çapraz referans ve cihaz yazıları (yalnız metin düzeyi).
- `annotations.sqlite3`: güncel pinler + artan sürüm + eski/yeni değerli olay günlüğü.
- Başlangıçta kaynak ve kanıt dosyalarının hash'leri doğrulanır. Çalışan sunucu girişleri
  bellekte sabit tutar; dosyalar değiştirilirse sunucuyu yeniden başlatmak gerekir.
- Host/Origin/tek oturum token kontrolü; üretim dışa aktarımı ve genel dosya okuma uç noktası yok.
- Bu, aynı Windows hesabındaki kötü niyetli yerel yazılıma karşı güvenlik sınırı değildir.

## Algoritma ve dürüst sınırlar

PDF'nin bağımsız yatay/dikey çizgi nesneleri bölünerek bir çizgi grafı kurulur. Her kenar ham
nesneye geri bağlanır. Kısa çizgiler için 5 pt filtresi yok; sayısal eşik 0,015 pt.
Noktasız X, dört ayrı parçayla çizilse bile bağlanmaz. T uçları geometrik erişimdir; fiziksel
dağıtım sırası değildir. Pinlere varınca takip durur. Belirsiz yakınlıkta en yakın uç seçilmez.

**Sınırlamalar:** geometri yalnız bu sayfada ve elle işaretlenen pinlerle; OCR, eğri/rect çizgi çıkarımı,
kesikli PE çizgisi yorumlama, genel sembol ayırma yok. Sayfalar arası ilişkiler (P05) yalnız yazı
düzeyindedir: başka sayfada çizgi takibi yapılmaz, bu yüzden bir referansın diğer uçtaki fiziksel
teli doğrulanmış sayılmaz. Yalnız üç kontağın
içi maskeli; başka cihaz bölgelerindeki çizgi erişimi elektriksel bağlantı kabul edilemez.
Graf dışı nesneler ham kayıtta ve ekrandaki sayaçta görünür. Bir çizgi nesnesinin tel olduğunu
genel olarak ispatlayan sınıflandırıcı henüz yok. Dolayısıyla bütün sayfada tamlık iddiası yok.

C01 ağ ilişkisi, C02/C03 kullanıcı teyitli çiftlerdir. Kullanıcı teyidi başlangıç örneğidir;
graf yolunun yeniden hesaplanması kör doğruluk testi değildir. Ham köprü çizgisini çıkartan
karşı-örnek testi C02'yi CONFLICT'e çevirir; çıktı sabit beklenen sonuçtan kopyalanmaz.
CONFIRMED_BOTH bu sınırlı örneklerde mevcut görsel/kullanıcı kanıtı + PDF çizgisidir;
iki bağımsız uzman onayı veya üretim doğruluğu anlamına gelmez. Her satır production_ready=false.

P04 aday önerileri yalnız bu sayfanın çizgi nesneleri üzerinde çalışır: eğri/kesikli parçalarla çizilmiş
semboller, döndürülmüş yerleşimler ve sayfa dışı örnekler kapsam dışıdır.
P05 sayfa kimliğini başlık bloğu yazılarından okur; başka bir çizim şablonunda bu etiketler
değişirse sayfa `UNKNOWN` olur ve sayfalar arası yanıt verilmez. Çapraz referansın hedef sayfada
gerçekten hangi uca gittiği (pin düzeyi) doğrulanmamıştır.
P06 gerekirse ölçülü AI; P07 standart ve 37 sütun; P08 görülmemiş bağımsız kabul testi.
İlk 10 sayfa kör test olarak kullanılamaz.

## Claude denetimi

`review_prompt.md`, Opus 5'e verilen dar, yalnız okuma görevini içerir. Çalıştırıcı mevcut
Claude kurulumunu kullanır; eklenti/hook/yazma/kabuk yetkisi açmaz, kurulum veya kredi alımı yapmaz.
Sonuç `output/pilots/E122/20260909_v3_p03/review/` altında saklanır. Denetçi bulguları ayrıca
ana yürütücü tarafından sınanır; modelin olumlu görüşü elektriksel onay değildir.
