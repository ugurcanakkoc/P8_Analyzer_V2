# PDF → EPLAN P8 şema dönüşümü — uygulama planı

Onay: kullanıcı, 2026-09-09. Bağlayıcı elektrik kuralları: [MAIN.md](MAIN.md).
Bu plan yalnız uygulama durumunu tutar; MAIN.md'yi değiştirmez.

## GÜNCEL İŞ SIRASI (2026-09-11) — tek yürürlükteki sıra

Bağlayıcı karar: MAIN.md **2026-09-11 — Şema aktarımına geçiş**. Birincil hedef artık
**düzenlenebilir EPLAN P8 şemasıdır**. Yalnız fiziksel tel çifti üretmeye göre tasarlanmış
eski sıra aşağıda tarihçe olarak korunur; eski “şema/cihaz oluşturma kapsam dışı” hükümleri
yeni hedef için geçerli değildir. 37 sütunlu Excel ikincil imalat görünümüdür.

Teknik karar ve araştırma: [Yeni akış ve EPLAN yaklaşımı](output/research/2026-09-11_PDF2EPLAN_Yon_Degisikligi.md).
Claude'a ilk uygulama görevi: [CLAUDE_NEXT.md](CLAUDE_NEXT.md).

### Bugün doğrulanan başlangıç (yeni geliştirme yapılmış sayılmaz)

- Kodda PDF vektör/metin okuma, sembol adayları, SQLite kayıt/geçmiş, çizgi grafı ve sayfa
  devamı çözümü var. Gerçek EPLAN sayfa yazıcısı ve EPLAN sembol eşleme kataloğu yok.
- 73 sayfalık mevcut indeks **58 IN_SCOPE Schaltplan** sayfası gösteriyor; 1 başka konumlu
  Schaltplan, 11 malzeme listesi ve 3 yerleşim sayfası ayrıca kayıtlı. Bu indeks sayımıdır,
  bağımsız görsel kapsam doğrulaması değildir. Eski “59 kapsam içi” ifadesi otomatik alınmaz.
- Canlı servis GET kontrolünde yalnız **2,4,5,22,28,36** hazırlanmış sayfalardı. Bütün belge
  metnini indekslemek bütün şemaları çözmek demek değildir.
- `3F22:1` (fiziksel 4 / Blatt 3) ve `4F22:1` (fiziksel 5 / Blatt 4) izleme çıktıları üst
  L1 çizgisini buluyor, ama `targets=[]`; tablo `SINGLE_END` gösteriyor. Devam çözümü aynı
  uçlarda L1 adını buluyor. **Eksik: geometri + hat kimliği + sunumun birleştirilmesi.**
- Son uygulayıcı raporu: 121 test, 30 tel çifti. Bu yön değişikliği turunda testler yeniden
  çalıştırılmadı; yeni şema akışının başarısı olarak sayılmayacak.

### Kullanıcının göreceği akış

PDF aç → bütün sayfaları gez → pano filtresini gör/düzelt → sembol ailesini EPLAN sembolüne
bir kez eşle → cihaz/pin/hat/devam önerilerini düzelt → aktarım önizlemesi → seçili sayfaları
EPLAN'a aktar → EPLAN'da düzenle. Köprü imalat biçimi ve üretim onayı sonradan, ayrı süreçtir.

### Uygulama paketleri

| ID | İş | Somut teslim / kabul |
|---|---|---|
| S00 | **Hedefi ve kuralları güncelle** | **Tamam (yalnız belgeler):** MAIN, bu sıra ve araştırma/ilk Claude görevi güncel. Eski veriye yeni onay verilmedi. |
| S01 | **Tüm sayfalarda gezinme + üst besleme ilişkileri** | 73 sayfa seçicide görünür; varsayılan 58 aday şema filtresi. Hazırlanmamış sayfa “boş/çözüldü” görünmez. Seçili sayfa önizlemesi öncelikli, kalan seçili şemalar durdurulabilir/devam edilebilir sırada hazırlanır. `L1→3F22:1` ve `L1→4F22:1`, L2/3 ve P24/N24 gerçek segmentleriyle görünür; fiziksel tel kararı aranmaz. |
| S02 | **Sayfa şema modeli ve düzeltme akışı** | Pinler yanında potansiyel, bara, birleşim, devam, açık sınır ve grafik nesneleri kimliklidir. Gerçek polyline/topoloji saklanır; üretim satırından şema türetilmez. Kullanıcı nesne/etiket/hat düzeltir; sürümlü düzeltme yeniden analizde ezilmez. S01'de yalnız gereken en küçük modeli başlat, büyük çatı kurma. |
| S03 | **Erken EPLAN aktarım kanıtı** | Bütün PDF tanımasını beklemeden ayrı test projesinde küçük gerçek bölge: L1→sigorta, sigorta→klemens, T dalı ve devam. Gerçek EPLAN fonksiyon/pin/bağlantıları oluşur, özellikleri düzenlenebilir; EPLAN'dan geri okunan kimlik ve topoloji kaynak modelle karşılaştırılır. Çalışan P8'de doğrulanmadan tamam işareti yok. |
| S04 | **58 aday şemaya tanıma ve kontrollü uygulamayı yay** | Mevcut şablon + modül/çubuk sahipliği bütün seçili sayfalarda aday üretir. İlk örnek öğretimi kalıcıdır; her sayfada ad/pin yeniden okunur. Adayları gruplu seçme/uygulama onay değildir. Tanınmayan aileler ve eksikler sayfa haritasında görünür. Büyük ajan taraması değil, değişen/eksik bölgede inceleme. |
| S05 | **Seçili sayfalarla P8 taslak teslimi** | Sembol eşleme sürümü, kapsam filtresi, sayfa adları, aktarım önizlemesi, çakışma/tekrar aktarım koruması ve geri okuma raporu. Desteklenmeyen bölge açıkça grafik/elle tamamlama; sessiz kayıp yok. Pano içi varsayılan, tam sayfa seçenekli. Üretim onayı ve otomatik köprü seçimi yok. |
| S06 | **Kullanılabilirlik ve ikinci TROESTER sınaması** | Sayfa başına operatör düzeltme süresi, tanınan/düzeltilen/belirsiz nesne ve yanlış/eksik ağ ilişkileri ölçülür. Ayrılmış E530 verisi ancak ilan edilen değerlendirmede açılır. Aynı sayfa/şekil kopyası kör test diye sunulmaz. |

Durum: **S01–S06 henüz uygulanmadı.** Eski pilot yetenekleri bunlara girdi sağlar; otomatik
olarak tamamlandı sayılmaz. İlk sonraki kod teslimi S01 + S02'nin gerekli küçük çekirdeği;
hemen ardından S03. Tüm 58 sayfanın kusursuz tanınmasını beklemek yasaktır.

### Yeni akışta bloke etmeyecek eski maddeler

- K1: tel/tarak imalat seçimi kullanıcıda; T ağını şemada göster, bu soruyla işi durdurma.
- K2: PE/toprak hattı semantiğini kaynak kanıtıyla göster; fiziksel bara numarası icat etme.
  Çerçeveyi/kesik sembol boşluğunu iletken yapmama testleri korunur. Kullanıcının genel yorumu
  eski tekil onay kayıtlarını tazelemez.
- K3: mevcut TROESTER>UVP kuralını uygula; kaynak eksikse onu açıkla, tercihi yeniden sorma.
- K4: eski kayıtlar tarihtir; yeni sayfa önizlemesini eski beş teyidin yenilenmesine bağlama.
- İsimsiz PLC uçları, sembolsüz düşüşler ve saha damar çelişkisi ayrı açık iş olarak kalır;
  bunlardan uydurma elektrik nesnesi üretme, diğer sayfalara geçişi engelleme.

### Sert teknik kontroller

- Sahiplik: fiziksel sayfa / Blatt / tam DT / fonksiyon örneği birbirine karışmaz. Aynı
  rölenin kontak ve bobini aynı cihazın farklı fonksiyonlarıdır, iki ayrı yeni cihaz değildir.
- L1/L2/L3 ayrık; noktalı birleşim bağlı, noktasız kesişim bağlı değil; sembol içi çizgi tel
  değil. İki cihaz pini şartı şema ilişkisinin şartı değildir. Aynı potansiyel yazısı tek başına
  uzak ağları birleştirmez.
- EPLAN sembol pin yönü, sayısı ve numarası eşleşir; öteleme/ölçek/ayna/dönüşüm açık kaydedilir.
  PDF→P8 koordinat, grid ve pin hizası gerçek P8 testiyle kontrol edilir.
- Aktarım çıktısı cihaz+pin+net geri okumasıyla sınanır; yalnız ekran benzerliği veya API 200
  yeterli değildir. P8'nin otomatik oluşturduğu imalat sırası kaynak PDF gerçeği sayılmaz.
- Eski kullanıcı düzeltmeleri, PDF, standartlar, canlı incelemeler ve hedefte kullanıcıya ait
  nesneler korunur. Belirsiz nesne sessizce atlanmaz; aktarım önizlemesinde görünür.

---

## GEÇMİŞ — 2026-09-10 bağlantı çıkarımı sırası (artık yürürlükte değil)

Bu bölüm ve devamı eski teslimlerin izidir. Aşağıdaki bağlantı-listesi hedefi ve kapsam
sınırları, 2026-09-11 tarihli şema aktarımı hedefinin yerine geçmez.

| # | Adım | Kapsayacağı | Bitti sayılma ölçütü |
|---|---|---|---|
| 0 | **Test verisi ayrımı** | `13sb004-e530` kimlik + SHA-256, önceki erişimlerin ilanı, "kısmen görülmüş ayrı proje testi" etiketi, yeni proje varsayılanı boş işaret/boş onay | MAIN.md §6–7 yazılı **(tamam, 2026-09-10)** |
| 1 | **Doğruluk kontrolleri** | kapsam koşulu (teyitli çiftler dâhil), etiket türü ayrımı, sembol içi/harici jumper ayrımı, uygulama türü alanı, kaynak/sürüm kaydı | her madde için en az bir regresyon testi; mevcut testler yeşil **(tamam, 2026-09-10, 106 test)** |
| 2 | **Belge genelinde adaylar ve kontrollü uygulama** | salt okunur aday arama (yazı-önce aday üreteci dâhil), klemens etiketi yön/uzunluk duyarlı okuma, gruplu önizleme, örnek başına kanıt ve karar kaydı | kalıcı toplu yazma yalnız 1. adım kapıları geçtikten sonra; mükerrer işaret üretmez **(2026-09-11: PLC modül kimliği ve klemens kenar kuralı kapandı; sayfa 5 işaretlemesi açık)** |
| 3 | **Kaynaklı Excel** | seçili sayfalarda kesit/renk kaynağıyla, okunabilir tablo, 37 sütunlu inceleme çıktısı, EPLAN uç adı eşlemesi | eksik isim/renk/uygulama türü olan satırlar görünür ama üretimden ayrı |
| 4 | **Operatör ölçümü** | gerçek kullanıcıyla doğru/onaylı bağlantı başına toplam efor, kaçan/yanlış, yeniden inceleme yükü, öğrenme etkisi | başarı yalnız dışarı verilen satırlarla hesaplanmaz; atlanan kapsam içi iş de görünür |
| 5 | **İkinci TROESTER projesi ve deneme aktarımı** | parametreli proje açma (boş işaret/boş onay), ayrılmış veride değerlendirme, ayrıca yetkilendirilmiş deneme aktarımı | üretim serbest bırakma ayrı adımdır |

Sıra dışı bırakılanlar: yeni AI/YOLO kurulumu, bütün panoyu otomatik işaretleme, otomatik onay,
üretim Excel'i ve EPLAN'a kalıcı aktarım. P06 (ücretli AI) bu sırada zorunlu değildir.

### 2026-09-11 (ikinci tur) · KALAN TESLİM — sayfa 5, PLC beslemesi, kesit/renk, PE yolu

Rapor: `review/20260911b_kalan_teslim.md`. **121 test geçiyor.** Üretim/aktarım kapalı;
canlı onay verilmedi.

| İş | Durum |
|---|---|
| Sayfa 5 adayları + bağlantılar | ✅ 17 onaysız işaret, **6 fiziksel çift**; 11–11 + `X4:8` ortak ağ olarak kaldı, `C02`/`C03` **kopyalanmadı** |
| PLC `L+`/`M` beslemesi | ✅ Belgede arandı: sayfa 22'de `-11D31:1L+/1M → P24.30/N24.30 → -X4`. Modüllerin `L+`/`M` beslemesi **istasyon içi dağıtımdır**, harici tel üretilmedi |
| Kesit / renk | ✅ 30 satırın tamamı kaynaklı: güç 6 satır `2,5` + `BK`, kumanda 24 satır `1` + `DBU`. Kaynak zinciri `Kaynak_Kontrol`'de |
| PE yol izleme | ✅ `dash_bridges` eklendi; izole veride onay sonrası yol izleniyor, **fiziksel tel yine çıkmıyor** (ortak ağ). Canlı graf değişmedi |

Kesit yazısı artık **kendi işaret çizgisinin kestiği** iletkenlere atanıyor (önce çizginin
kendisine atanıyordu). Devre görevi önce kanıtlanıyor: `L1/L2/L3` → güç, `N24/P24` veya modül
başlığındaki `24VDC` → kumanda. Kanıt yoksa değer yazılmıyor.

**Kullanıcı kararı bekleyen 4 madde:** K1 sayfa 5 üç uçlu ortak ağ (`net:5:369.5:227.77`);
K2 PE koşularının birleştirilmesi (`y=440.37#0`, `x=185.25#0`, `x=482.89#0`); K3 güç fazı
rengi `BK` (6 satır, TROESTER sessiz → UVP seviye 3); K4 askıdaki beş inceleme
(`C01`,`C02`,`C03` + 2 kayıt).

**Kalan teknik eksikler:** sayfa 5'te klemens sembolü olmayan dört dikey; sayfa 2'de tel yok;
sayfa 22 işaretlenmedi; PLC modülünde adı basılmamış 10 uç; `-3W67` damar çelişkisi;
belgedeki diğer kapsam içi sayfalar.

### 2026-09-11 · PLC KİMLİĞİ · X4.I:10/11 · PE · ONAY AYRIMI — dört işin durumu

Rapor: `review/20260911_plc_kimligi_pe_ve_onay_ayrimi.md`. **119 test geçiyor** (tur başı 114).
Üretim/EPLAN aktarımı kapalı; hiçbir bağlantı kullanıcı adına onaylanmadı; beş askıdaki inceleme
tazelenmedi; `C02`'nin `TEL` kararı korundu ve genellenmedi.

| # | İş | Durum | Kalan |
|---|---|---|---|
| 1 | **PLC cihaz–pin sahipliği** | ✅ **Tamamlandı** | — |
| 2 | **Sayfa 36 `X4.I:10/11`** | ✅ **Tamamlandı** | — |
| 3 | **PE devresi** | ⚠️ **Teknik kısmı bitti — kullanıcı kararı bekliyor** | Bara ↔ klemens fiziksel tel kaydı |
| 4 | **Görsel inceleme + kullanılabilir teslim** | ⚠️ **Teknik eksik var** | Sayfa 5'te 8 bağlantı işaretlenmemiş |

**1 — PLC kimliği (tamamlandı).** Modül gövdesi tek uzun yatay çizgidir; kural çubuk sahipliğiyle
çözülmüyordu. `document.module_bars/module_owner/module_pin_name/module_pin_mark` eklendi:
sınırlar çizimden okunur, başlıkta **tek** cihaz yazısı varsa sahiplik kurulur (birden fazlaysa
`AMBIGUOUS_MODULE_HEADER_TAGS`, komşu modülün adı taşınmaz), pin adı ucun sağındaki yazıdan,
**DO/DI ayrımı ucun üstündeki tanım yazısından** (şekilden değil) gelir. Sonuç: sayfa 28
`=122+E122-17D22:1..8` (`DO`), sayfa 36 `=122+E122-25D22:1..8` (`DI`); 10 uç "iletkeni yok"
kovasında (**kaçırılmış tel değil**), 10 uç adı basılmadığı için çözümsüz. **İzole ölçüm:** 19
`AJAN_TASLAK` işareti silinmiş bir kopyada sonuç aynı — kimlik çizimden geliyor. Canlı işaret
kaynakları geriye dönük değiştirilmedi.

**2 — `X4.I:10/11` (tamamlandı).** Kök neden: şablonun çekirdeği kutu kenarına değen **dış tel
uçlarını** da sayıyordu; bu iki klemensin altına saha teli çizilmediği için 3↔2 parça farkıyla
eleniyordu. `similarity.edge_row/split_core/distinctive` ile sembolün kendi çizgisi ile çevre
tesisatı ayrıldı; fark eleme değil **not** oldu. Sayfa 36: 6 → **8** çift (mevcut altısı
bozulmadı). Yan kazanç: sayfa 2'de `-X4:N24.30` bulundu. `distinctive()` olmasaydı "yalnız daire"
ailesi sayfa 4'te 1 → 20 adaya çıkıyordu; ölçülüp engellendi.

**3 — PE (kullanıcı kararı bekliyor).** `_dash_run_end`: uçların hepsi aynı **ölçülmüş** koşuya
aitse referansın ucu o koşunun ucudur — kesik boşluğu köprülenmez. `/1.510` → sayfa 2, `/4.51` →
sayfa 5, ikisi de `RECIPROCAL_END_MATCHED`; sayfa 4'te çözülemeyen sayfa devamı kalmadı.
`-X1:PE` ve `-X4:PE` barada **çizilmiş birleşme noktasıyla** ve kesikli düşüşle bağlıdır; karşı uç
bir cihaz ucu değil ortak baradaki bir nokta olduğu için **fiziksel tel çifti üretilmedi**.
Kesikli düşüşlerin algoritmik yol kanıtı yok (graf boşluğu köprülemez) — `ONAY_BEKLIYOR`.
"PE tamamlandı" denmiyor.

**4 — Görsel inceleme (teknik eksik var).** Beş sayfa, tablodan bağımsız olarak tarandı; her
sayfa için ayrı bir çürütme turu çalıştı (10 ajan). **Sayfa 28, 36 ve 4'te program ile görsel
tarama 8/8 örtüştü; yanlış öneri ve kaçırılan bağlantı yok.** Sayfa 2'de ikisi de 0 buldu.
**Sayfa 5'te görsel 8 bağlantı gördü, program 0 üretiyor — bu turun kapatmadığı en büyük boşluk.**
Görsel incelemenin bulduğu gerçek eksik: `C01` ana tabloda kendi satırında değildi (MAIN.md
2026-09-08 §1). Yeni satır türü `CONFIRMED_NETWORK_RELATION` eklendi — **fiziksel tel sayılmaz**,
üretime giremez, sade ekranda `line_relations` altındadır.

**Onay özeti düzeltildi:** `overview()` sabit `approved=0` döndürüyordu ve başlık satırlarla
çelişiyordu. Artık ilişki teyidi (güncel / askıda / onay bekliyor), yeniden inceleme ve üretime
uygunluk **ayrı** sayılır; özet satırlarla tutarlıdır. Uçları birleştiren düz çizgi artık noktalı
ve "gerçek güzergâh değildir" diye yazılı.

**Tarayıcı kontrolü gerçekten yapıldı:** 8765 kapalıydı, mevcut yöntemle gizli arka planda
başlatıldı (başka süreç öldürülmedi); Playwright ile sade ekran açıldı, sayfa değiştirildi ve
satıra tıklanınca çizimde odaklandığı ekran görüntüsüyle doğrulandı.

**Çıktılar:** `review/20260911_sayfa{2,4,5,28,36}_inceleme.xlsx` (`EPLAN_37` 37 sütun + `Kontrol`
+ `Kaynak_Kontrol` + `Teyit_Bekleyenler` + `Sayfa_Kapsami`), `evidence/20260911_*.png`,
`tools/crop.py`, `tools/sayfa_excel.py`.

**Kesit/renk:** 24 çiftin hiçbirinde iletkene yazılı kesit yok; sayfa notundaki 1,5/1 mm² kuralı
için "bu kumanda teli mi" kararı **kullanıcınındır**, verilmeden yazılmadı. Renk kanıtı yok.
Gerekçeler `Kaynak_Kontrol` sayfasında; eksiklik teslimi durdurmadı.

### 2026-09-10 · SOMUT TESLİM — dondurma, görsel inceleme, aday akışı, sayfa çıktıları

2. adımın (belge genelinde adaylar ve kontrollü uygulama) **ilk somut teslimi**. Kalıcı toplu
uygulama hâlâ açılmadı.

| Teslim | Dosya |
|---|---|
| Dondurulmuş durum + işaret kaynakları | `review/20260910_dondurulmus_durum.md` / `.json` |
| Beş sayfa görsel inceleme taslağı ve fark tablosu | `review/20260910_gorsel_inceleme_5_sayfa.md` |
| Sayfa Excel inceleme çıktıları (5 adet) | `review/20260910_sayfa{2,4,5,28,36}_inceleme.xlsx` |
| PDF kırpmaları | `evidence/20260910_s28_*.png`, `s2_*`, `s36_*`, `s5_*` |

**Ölçülen fark (109 görsel uç):** program 31 uç işaretli, aday akışı 56 uç buluyor, **52 uç
kaçırılıyor**. Kaçırmanın nedeni ölçüldü: PLC modülü (36 uç) ve röle bobini (12 uç) aileleri
kütüphanede yok; sayfa 2'nin klemensi farklı çizilmiş (2); `-X4.I:10/11` şablonla eşleşmedi (2).

**Dürüst sayım:** 32 mevcut işaretin 12'si programın (P04/kütüphane) bulgusudur; 20'si elle
konmuştur ve program başarısı sayılamaz. Sayfa 28 ve 36 dondurma anında sıfır bulguluydu.

**Bu pakette düzeltilenler:** kütüphane çok sayfalı arama; uzun/döndürülmüş klemens etiketi
okuma; şablon yakalarken etiketin komşu sembolden alınması (PE ailesi `PE` yerine `3` okuyordu —
eski kayıtlar `RETIRED`, silinmedi); kontrol ekranında ilk 40 sınırı kaldırıldı, satıra basınca
uçlar ve mevcut yol gösteriliyor, gruplu uygulama yalnız seçilenleri kaydediyor ve mükerrer
kayıt üretmiyor.

**Sayfa 5 bağımsız yüzey değildir:** vektör geometrisi sayfa 4 ile birebir aynı.

### 2026-09-10 · SAYFA 28 UÇTAN UCA + kimlik sahipliği

| Teslim | Dosya |
|---|---|
| Sayım ayrımı ve sayfa 28 bağlantı karşılaştırması | `review/20260910_sayim_ve_s28_baglanti.md` |
| Beş sayfa görsel inceleme + fark tablosu (güncel) | `review/20260910_gorsel_inceleme_5_sayfa.md` |
| Sayfa Excel'leri (güncel) | `review/20260910_sayfa{2,4,5,28,36}_inceleme.xlsx` |

**Sayfa 28 uçtan uca:** 8 fiziksel tel çifti izlendi (`-17D22:1…8` ↔ 6 röle bobini A1 + 2 `-X4.Q`),
`N24.30` barası tek `NETWORK_GROUP` olarak kaldı — **tel zinciri üretilmedi**.

**Kimlik sahipliği çözüldü:** bir kez yazılan `-X4.Q` / `-X4.I` / `-X1` / `-X4` adı, aynı satır
bandında **sağındaki** klemens grubuna bağlanır ve bir sonraki çubuk etiketinde biter; komşu gruba
taşmaz. Adı çözülemeyen şekil eşleşmesi `IDENTITY_UNRESOLVED_NOT_A_RECOGNISED_END` taşır ve
**doğru tanınmış uç sayılmaz**.

**Kısmi adres okuma:** `=112-17K53` gibi `+Ort`'suz etiketler artık okunuyor; eksik parça
sayfadan devralınıyor ve hangi parçanın devralındığı kayıtta (`device_inherited`).

**DO ≠ DI:** iki aile ayrı öğretildi. Şekilleri aynı olduğu için şablon her iki sayfada da
eşleşiyor; ayırt edici kanıt modül etiketi (`-17D22` / `-25D22`) ve işlev yazısıdır
(`Q3632.x` / `I3631.x`). Bu yüzden PLC uçlarının kimliği program tarafından çözülemedi.

**Ölçülen sayım (dört ayrı sayı):** şekil bulundu 105 · kimlik okundu 69 · işaret kayıtlı 69 ·
bağlantı izlendi 22. İşaret kaynakları: `TOHUM_ELLE` 13 · `CLAUDE_ELLE` 7 · `AJAN_TASLAK` 19 ·
`PROGRAM_P04` 30. Yalnız sonuncusu program bulgusudur.

**Bu turda bulunan kusur:** sunucu mükerrer işareti kabul ediyordu (koruma yalnız arayüzdeydi);
sunucu tarafına kondu ve testi eklendi. Test sırasında oluşan tek kopya kayıt kaldırıldı, olay
geçmişi korundu.

### Karşılaştırma paydası (P08 hazırlığı)

Kullanıcı Excel'i **referans**tır, ground truth değil: C02 gerçek bir teldir ve Excel'de yoktur.
Ölçüm paydası dört küme olarak ayrılır: `KAPSAM` · `STANDART_PE` · `KAPSAM_DIŞI` ·
`REFERANS_EKSİK/AKSESUAR (kullanıcı kararıyla)`. Hat eşleşmesi ile fiziksel tel eşleşmesi ayrı
raporlanır.

## Karar ve sınır

Yerel, pin merkezli, kullanıcı destekli bağlantı çıkarımı. Cihaz oluşturma,
2D yeniden çizim, 3D yerleşim ve lisans/import yönetimi yok. İlk örnek kullanıcı
tarafından seçilen E122 PDF'sinin fiziksel 4. sayfası / Blatt 3'tür.
Kapsam +E122, fonksiyonlar 112/122/132/152/170; M/T yerleşimleri ve 113 dışarıda.
Bu bir geliştirme/regresyon örneğidir; kör test veya tam sayfa doğruluk ölçümü değildir.

PDF okuma, pin işaretleme, çizgi takibi, elektriksel ağ, fiziksel tel ve üretim onayı
ayrı katmanlardır. Ham kanıt silinmez. Benzer sembol tanıma P04, ücretli AI P06,
standart/Excel P07, bağımsız doğruluk ölçümü P08'de gelir.

## Görevler

- [x] P00 — İzole geliştirme alanı, çalışma talimatları, tekrar üretilebilir komutlar.
  Eski `P8_Analyzer_V2`, müşteri PDF'leri, standartlar ve mevcut Excel'ler değişmez.
- [x] P01 — Tam cihaz/pin kimliği, belge hash'i, sayfa/Blatt, koordinat ve kanıt modeli.
  Adres/son ek kaybı, boş kimlik birleştirme ve kanıtsız onay regresyon testleri.
- [x] P02 — PDF envanteri, ham geometri, 300 DPI görüntü, pin ekleme/düzeltme ekranı.
  Döndürme, sayfa kutusu ve kısa çizgi korunması testleri. Belge türü teşhisi başarı
  iddiası değildir; tarama/karışık içerik eksikleri görünür kalır.
- [x] P03 — İşaretlenmiş pinlerden çizgi takibi ve 4. sayfa kontrol örnekleri.
  P24.32→17K52:13 hat ilişkisi; 17K53:11→17K55:11 köprüsü;
  17K55:11→X4:4 dalı ayrı görünür. Ortak ağdan tahmini tel zinciri üretilmez.
  Kısa köprü, noktasız kesişim, T dalı, iç sembol, açık uç ve kapsam sınırı test edilir.
- [x] P04 — Onaylı sembol/pin örneklerinden benzer adayları bulma.
  Etiket/pin/harici hatlar her örnekte yeniden doğrulanır; NO/NC ve yön farkı sınanır.
- [ ] P05 — Sayfalar arası ilişkiler, klemens tablosu uzlaştırma, bağımsız tamlık taraması.
  Kontak-bobin referansı tel devamı olmaz; tam hedef pin uyuşmazlığı çatışmadır.
  Metin/sayfa indeksi düzeyi yapıldı; kullanıcı kontrolünde üç hata bulundu ve düzeltildi.
  Diğer sayfalarda gerçek uç izleme yapılmadığı için kutucuk yeniden açıldı.
- [ ] P05b — Kalıcı sembol kütüphanesi (uygulandı, kullanıcı kabulü bekliyor): projeden bağımsız,
  yerel, sürümlü kayıtlar; yeni belgede ad/bağlantı taşımadan aday bulma.
- [ ] P05c — Sonraki geliştirme (bu pakette YOK): vektör + görüntü karşılaştırması ile eşleşmenin
  ikinci kanıtı; şüpheli bölgeden AI sembol önerisi. Ölçüt, maliyet ve insan onayı ayrıca tanımlanır.
- [ ] P06 — Yalnız ölçülen zor durumlarda sınırlı AI; bir çağrı + bir bağlamlı tekrar.
  Maliyet, önbellek, sürüm ve fayda ölçülür. AI doğrudan üretim onayı vermez.
- [ ] P07 — Kaynaklı standartlar, sayfa tabloları ve 37 sütunlu çıktı.
  Varsayılan 1/8/15/22/30/31 dolu. Fiziksel tel, ağ ilişkisi ve belirsizlik ayrı.
- [ ] P08 — Bağımsız referans ve görülmemiş test; süre/maliyet karşılaştırması.
  Önceden incelenmiş ilk 10 sayfa kör test değildir. Benzer devre aileleri bölünerek
  veri sızıntısı oluşturulmaz. Referans kullanıcı/bağımsız elektrik uzmanı onaylı ve hash'li.

Kutucuklar ancak uygulama + test + görsel kanıt + bilinen sınırların incelenmesiyle
işaretlenir. P00–P03 onayı üretim/import onayı değildir. İnsan kabulü ayrıca kaydedilir.

## Değişmez sözleşmeler

- Tam adres ve pin son ekleri özgün halleriyle korunur; normalizasyon yalnız boşluk/büyük harf.
- Geometri sonucu otomatik fiziksel dağıtım kararı değildir. Ağdan zincir/çift kombinasyonu yok.
- Başlangıç pinleri elle işaretlenmişse açıkça belirtilir; otomatik tanıma diye sunulmaz.
- Geçmiş kullanıcı onayları yalnız aynı belge/sayfa/uçlar için; pin taşınırsa onay geçersizleşir.
- Görsel/vektör durumları: CONFIRMED_BOTH, VECTOR_ONLY, VISUAL_ONLY, CONFLICT, UNRESOLVED.
- İnceleme onayı ayrı: PENDING, APPROVED, REJECTED. Sayısal güven kalibrasyonsuz yok.
- Dolu her elektrik niteliğinin ayrı kaynak kaydı; bilinmeyen değer boş/UNKNOWN.
- Çözülemeyen hat, eşleşmeyen pin, kısa çizgi ve hariç bırakma nedeni kayıtlı kalır.
- İki modelin anlaşması ve yazılım testlerinin geçmesi elektriksel doğruluk kanıtı değildir.

## İlk sürümün kabulü

P00–P03: çalıştırılabilir yerel ekran; pin seçme/ekleme/düzeltme; izlenen çizgiler ve
erişilen pinler; üç bilinen ilişkinin ayrı statüyle görünmesi; test ve sınır raporu.
EPLAN'a yazma, üretim Excel'i, ücretli AI ve otomatik sembol tanıma bu teslimde yok.
Sonra Claude Opus 5 komut satırından yalnız okuma denetimi yapar. Bulgular doğrulanır;
gerekli düzeltme ve tekrar test ana yürütücü tarafından yapılır.

P08 hedefleri (garanti değil): precision >=98%, recall >=95%, F1 >=96%, açık nitelik
doğruluğu >=98%, çözülemeyen <=5%. Kanıtsız değer, ilgili sayfa atlama veya sessiz
kayıt kaybı sert NO-GO'dur. Üretim için insan onayı ve ayrı kullanıcı talimatı gerekir.
Ekonomik ölçü: doğru/onaylı 100 fiziksel bağlantı başına toplam süre ve maliyet;
kontrol/düzeltme, geliştirme/bakım ve model kullanımı dahil edilir.

## Teknik yön

Python + pdfplumber/PDFium; sade yerel HTML/SVG ekran; SQLite düzeltme günlüğü;
JSON ham kanıt. Büyük GPU, özel model eğitimi, bulut sunucusu ve mikroservis yok.
PDF okuyucu değiştirilebilir. Sürümler kaydedilir. Kaynak PDF yerinde okunur.
Yeni sonuçlar `output/pilots/E122/<run-id>/` altında; eski sonuçların üzerine yazılmaz.

## Araştırma dayanakları

- https://www.acceleratis.com/en/pdf2eplan/faq — bir kez sembol eşleme, benzerleri önerme, kullanıcı kontrolü.
- https://schematicvision.com/en/faq/ — desteklenen belge ailesi ve otomasyon sınırları.
- https://www.actemium.de/docu2act/ — tanıma, dönüşüm, uzman kontrolü.
- Önceki ayrıntılı araştırma: `output/research/2026-09-09_PDF_Baglanti_Stratejisi.md`.

## Güncel durum

**2026-09-09 — P00–P04 uygulandı; kullanıcı kabulü ve üretim onayı YOK.**

- P00–P03: `analyzer_v3` yerel pilotu çalışır durumda. 33 test geçiyor
  (`python -m unittest discover -s analyzer_v3/tests -t .`). Üç bilinen ilişki (C01/C02/C03)
  ayrı satırlarda ve kendi izleme uyarılarıyla görünüyor.
- Opus 5 yalnız-okuma kod denetimi yapıldı: 44 ham bulgu, karşı-doğrulama sonrası 3 bulgu ayakta
  kaldı, 27'si çürütüldü. Üçü de düzeltildi ve ikisi regresyon testine bağlandı. Rapor:
  `output/pilots/E122/20260909_v3_p03/review/20260909_denetim_ozeti.md`.
  Düzeltilen en kritik hata: bağlanamamış işaretli bir ucun üzerinden geçip uzak ucu uyarısız
  erişilebilir gösteren izleme (artık orada durur ve `UNATTACHED_PIN_ON_PATH` verir).
- P04: şablon sembolden öteleme tabanlı aday bulma. Cihaz/pin adı her örnekte sayfadan yeniden
  okunur, şablondan kopyalanmaz; dış hat sayısı örnek başına yeniden sayılır; NO/NC farkı
  eşleşmez ve `elenen` olarak görünür; aynalanmış/döndürülmüş yerleşim eşleşmez. Aday hiçbir
  kayıt oluşturmaz. Görsel kanıt:
  `output/pilots/E122/20260909_v3_p03/evidence/p04_benzer_adaylar.png`.
- Bilinen boşluklar: arayüz tarafında otomatik test yok (kontrol tarayıcıdan yapıldı); ikinci bir
  sekme açıkken ekran bayat kalabilir; P04 yalnız bu sayfanın düz çizgi nesneleri üzerinde çalışır.

**2026-09-09 (ikinci tur) — P05 uygulandı; kullanıcı kabulü ve üretim onayı yine YOK.**

- Belge indeksi: 73 sayfanın kimliği (Anlage/Einbauort/Blatt/belge türü), çapraz referansları ve
  cihaz yazıları `document_index.json` içinde, manifest hash'ine bağlı. Kapsam fonksiyon **ve**
  konumla belirlenir; sayfa 1 (`+E112`) ve sayfa 50 (`+E111`) kapsam dışı işaretlendi.
- Çapraz referans: `=122/17.52` → fiziksel sayfa 28; oradaki cihaz `=112-17K52` olarak basılıdır ve
  hedef sayfanın `=122` Anlage'si cihazın fonksiyonunu değiştirmez. Kontak/bobin referansı ile hat
  devamı adayı ayrılır, ikisi de `CROSS_REFERENCE_ONLY_NOT_A_WIRE`. Pozisyon eki yorumlanmaz.
- Uç uzlaştırma tüm belge türlerini tarar, her satırda türü yazar; aynı ad birden fazla sayfadaysa
  tek fiziksel nokta sayılmaz. Ayrı Klemmenplan belgesi bu PDF'te yok, tablo şema sayfalarından kurulur.
- Tamlık taraması: sayfa 4'te işaretsiz 7 cihaz, izlenen yollardaki 4 açık uç (yanındaki sayfa
  referansıyla), izlenen/izlenmemiş çizgi sayısı. Tamlık iddiası yok.
- İkinci Opus 5 denetimi (P04+P05, 25 ajan): 20 bulgu doğrulandı, **4 ayakta kaldı**, 16 çürütüldü.
  Dördü de düzeltildi ve teste bağlandı. En ağırı: **döndürülmüş (dikey) yazılar sessizce
  düşüyordu** — sayfa 4'te 4 çapraz referans ve 4 klemens ucu görünmüyordu; artık glif matrisinden
  okuma sırasına çevriliyor, ham metin saklanıyor. Ayrıca uç aramasının yalnız şema sayfalarını
  taraması ve açık ucun kontak/bobin referansıyla "sayfa devamı" gösterilebilmesi düzeltildi.
  Rapor: `output/pilots/E122/20260909_v3_p05_rev2/review/20260909_denetim_ozeti_p04_p05.md`.
- Kullanılan çalışma `output/pilots/E122/20260909_v3_p05_rev2/`. Hatalı ilk P05 denemesi
  (`20260909_v3_p05/`) kanıt olarak silinmedi. 49 test geçiyor.
- Bilinen boşluklar: geometri hâlâ yalnız sayfa 4'te; bir referansın hedef sayfadaki fiziksel ucu
  doğrulanmıyor; klemens sırasındaki ayrı pin rakamları metinden okunamıyor; arayüz için otomatik
  test yok.

**2026-09-09 (kullanıcı kontrolü) — P05 kutucuğu geri açıldı; tamamlandı onayı verilmedi.**

Kullanıcı üç somut hata bildirdi; üçü de yeniden üretildi, düzeltildi ve teste bağlandı
(`output/pilots/E122/20260909_v3_p05_rev3/review/20260909_kullanici_bulgulari.md`):

1. **Saha cihazı pano içi sayılıyordu.** `-3A72` altındaki `+M113` işareti dikkate alınmıyordu.
   Artık cihaz yazısının altındaki `+Ort` o cihaza aittir ve sayfa konumunun yerine geçer
   (`=112+M113-3A72`, kapsam dışı). Belgede bu desende 25 işaret var, hepsi tek bir cihazın altında.
   İşaret tek cihaza bağlanamazsa hiçbir cihaz sayfadan konum devralmaz; sayfa ve cihazlar
   belirsiz işaretlenir.
2. **Çok parçalı pin adı eşleşmiyordu.** `-4D27:X1:P1` kaydı sondaki `:` üzerinden bölündüğü için
   pinin bir kısmı cihaz adına katılıyordu. Bölme artık istenen cihaz adının önünden yapılıyor.
3. **Ekran eski servisle açılıyordu.** 8765'teki eski süreç durduruldu; güncel kod ve
   `20260909_v3_p05_rev3` çalışmasıyla yeniden başlatıldı, beş uç nokta da 200 dönüyor.

Çalışma `output/pilots/E122/20260909_v3_p05_rev3/`; rev2 ve önceki denemeler kanıt olarak duruyor.
52 test geçiyor.

**2026-09-09 (kullanıcı onayı sonrası) — sayfa devamı artık hedef sayfanın çizgisiyle doğrulanıyor.**

Kullanıcı üç düzeltmeyi kontrol edip kapattı (`-3A72` kapsam dışı, `X1:P1` eşleşiyor, servis güncel,
52 test). Ardından P05'in kalan işinin ilk yarısı yapıldı:

- `prepare --pages` ile birden fazla sayfanın geometrisi çıkarılabiliyor. Yeni çalışma
  `20260909_v3_p05_rev4` sayfa 4, 2, 5, 28, 36'yı izliyor (7,5 MB, 19 sn). Sayfa 4 kök klasörde,
  diğerleri `pages/<n>/` altında; hepsi manifest hash'ine dahil.
- `continuations()`: bir sayfa referansının yanında gerçek açık çizgi ucu var mı, hedef sayfada
  karşılıklı uç bulunuyor mu — hedef sayfanın kendi geometrisiyle sınanıyor. Eşleşme iki kanıtla:
  hedef sayfadan kaynağa geri işaret eden referans **ve** iki uca basılı aynı potansiyel adı
  (`P24.32`, `L1`). Pozisyon eki yorumlanmıyor.
- Sayfa 4 sonucu: 19 referansın **10'u** iki tarafta çizgi kanıtıyla eşleşti (sayfa 2 ve 5);
  3'ü kontak/bobin referansı olarak muaf, 4'ü uçsuz dikey klemens yazısı, 2'si çok uçlu demet
  (seçim yapılmadı). Görsel kanıt: `.../20260909_v3_p05_rev4/evidence/p05_sayfa_devami_dogrulama.png`.
- 56 test geçiyor.

**2026-09-09 (kullanıcı kararı) — uçtan uca pilot: sayfa 2/4/5, P04 destekli, insan kontrollü.**

Kullanıcı kapsamı sayfa 2, 4, 5 olarak belirledi; işaretleme P04 destekli ama her sembol ailesinin
ilk örneği görselden elle doğrulanacak; kontak/bobin referansları tel devamı olarak izlenmeyecek;
bu aşamada AI yok. Uygulandı (`20260909_v3_p05_rev6`, 61 test):

- Çok sayfalı işaretleme: her pin ve sembol kutusu bir sayfaya ait; izlenmeyen sayfaya işaret konamaz;
  her sayfanın kendi grafiği kurulur. Kullanıcı arayüzden sembol kutusu çizebiliyor, sayfa değiştirebiliyor.
- `/api/path`: kaynak pin → doğrulanmış sayfa devamı → hedef sayfadaki işaretli uçlar. Sıçrama
  `NETWORK_CONTINUATION_NOT_ONE_PHYSICAL_WIRE` etiketlidir.
- `/api/effort`: her işaretin yöntemi (`MANUAL` / `P04_CANDIDATE`) ve olaylar arası süre.
- Pilot sonucu: sayfa 4 `-X4:P24.32` → sayfa 5 `-17K56:13` + `-X4:P24.32`, sayfa 2 `-X4:P24.32`.
  P04, sayfa 5'teki diğer kontakları buldu ve adları o sayfadan okudu (`-17K57:11`, `-17K59:11`;
  şablonun `13`'ü kopyalanmadı).
- Rapor ve beş teslim ölçütünün durumu:
  `output/pilots/E122/20260909_v3_p05_rev6/review/20260909_uctan_uca_pilot.md`.

**2026-09-09 (çalışma paketi) — sayfa 4 sistematik tamamlama.** `20260909_v3_p05_rev7`, 65 test.

- Sürümlü inceleme kaydı: karar + incelenen pin sürümleri saklanır; pin değişince kayıt silinmez,
  `NEEDS_REVIEW` olur. Kullanıcının sohbetteki beş teyidi `CHAT_APPROVAL_TRANSCRIBED` kaynağıyla kaydedildi.
- 3F22 ve X1 aileleri eklendi: bu semboller PDF'te eğri nesnelerle çizildiği için P04 eşleştirmesi
  eğrileri de kapsayacak şekilde genişletildi; şablon çapası sembolün kendisi oldu. Pin adları her
  örnekte sayfadan okundu (X1: 2/3, sigorta: 1/2, 3/4, 5/6). PE klemensi farkı elenen olarak göründü.
- Eksik iş listesi (`/api/todo`) ve sayfa 4 bağlantı tablosu (`/api/table`) üretildi:
  6 fiziksel tel adayı, 3 ağ ilişkisi, 3 tek uçlu ağ, 29 gerekçeli boşluk, 1671 incelenmemiş ağ.
  Kısa köprü ve T dalları bağımsız ikinci kontrolde sayıldı.
- Kayıt hızlandırması: graf kurulumu 2,29 → 0,16 sn (imza birebir aynı), pin kaydı 1,7 → 0,01 sn.
  Yol panelinde hedef sayfa uyarıları gösteriliyor.
- Okunabilir tablo: `.../review/sayfa4_baglanti_tablosu.md`; paket raporu:
  `.../review/20260909_sayfa4_calisma_paketi.md`.

**Başarı ölçütü kısmen sağlandı:** işaretli ucu olan her ağın satırı, işaretsiz kapsam içi her ağın
gerekçeli boşluk kaydı var; ancak 1671 ağ "incelenmemiş" kovasındadır ve o kova kapanmadan sayfa 4
için tamamlandı denemez. Sıradaki adım kullanıcının tabloyu şemayla karşılaştırması; ardından aynı
yöntem sayfa 2 ve 5'e, sonra işaretlenmemiş bir sayfaya uygulanacak.

**2026-09-10 — Kalıcı sembol kütüphanesi ve iki güvenilirlik düzeltmesi.**
Çalışma `20260910_v3_p05_rev8`, kütüphane `output/library/symbols.sqlite3`, 83 test geçiyor.
Kullanıcı kontrolünde bulunan üç eksik kapatıldı: teyitli çift satırı artık çizgi kanıtı ile
inceleme durumunu ayrı gösterir ve askıya alınınca "geçmişte teyitli — yeniden inceleme gerekiyor"
olur (satır silinmez, tazeleme düğmesi var); arayüz yeni satır türünü doğru etiketler; kütüphane
açıklaması "kaynak yazı kanıt olarak saklanır, kimlik olarak aktarılmaz" biçiminde düzeltildi.
Yeniden inceleme akışı tek satıra bağlandı: aynı fiziksel uç çifti yönden bağımsız tek bağlantı
satırıdır, yeniden onay satır açmaz (güncel inceleme olur), eski kararlar geçmişte kalır,
C02/C03 referansları sabittir.

- İnceleme kaydı artık pin sürümlerinin yanında **bağlı olduğu sayfaları** da dondurur; o sayfada
  pin veya sembol kutusu değişirse kayıt `NEEDS_REVIEW` olur ve eski geometri geri gelse bile
  canlanmaz. Geçersizleştirme bu sürümde sayfa düzeyindedir (bilerek geniş; sınır yanıtta yazılı).
- MAIN.md'nin iki teyitli çifti (`C02`, `C03`) tabloda `CONFIRMED_PHYSICAL_PAIR` satırıdır; kaynak
  yalnız açık teyitlerdir, ortak ağdan çift veya zincir türetilmez.
- Kütüphane: şekil, uç ve etiket konumları, kaynak kanıtı, müşteri/stil profili ve desteklenen
  dönüşümler saklanır; cihaz adı, bağlantı, renk, kesit ve onay saklanmaz. Onaysız kayıt DRAFT.
  Kayıt, kaynak çalışmanın pinleri olmadan yeni sayfada eşleşti (sayfa 5'te 0 işaretli pin ile
  `-17K56/-17K57/-17K59` adları o sayfadan okundu) ve ayrı bir çalışmadan da kullanıldı.
- Eğriler nokta yoluyla temsil edilir: aynı kutuda farklı şekil, ölçek ve dönme eşleşmez; nokta
  listesi olmayan eski çalışmalarda eşleşme `CURVE_SHAPE_UNVERIFIED_BBOX_ONLY` ile işaretlenir.
- Çizgi esnekliğinin bugünkü sınırları testlerle belgelendi (aralıklı parça, kesikli hat, sembol
  boşluğu, noktasız kesişim kapatılmadı).
- Rapor: `output/pilots/E122/20260910_v3_p05_rev8/review/20260910_sembol_kutuphanesi_paketi.md`.
- Bu turda tarayıcı ekran görüntüsü alınamadı (Playwright bağlanmadı); görsel kontrol kullanıcıya kaldı.

**2026-09-10 (sıra) — sayfa 4'ün sistematik tamamlanması.** `20260910_v3_p05_rev8`, 85 test.
Güncel öncelik MAIN.md'nin 2026-09-10 maddesidir: **mevcut TROESTER projesinde kullanılabilir
sonuç**. Bu pakette başka müşteri desteği ve yeni AI altyapısı açılmadı.

- Bağımsız görsel tarama (tablodan bağımsız): sayfa 4'ün pano tarafındaki kapsam içi cihaz ucu
  **24**'tür (`-3F22` 6, `-17K52/53/55` 6, `-X1` 1/2/3/PE, `-X4` 1/2/3/4/N24.30/PE/P24.32/N24.30);
  tarama, tabloda eksik kalan başka kapsam içi uç bulmadı.
- Eksik iki işaret (`-X1:PE`, `-X4:PE`) P04 ile bulundu ve **aday** olarak eklendi; adlar her
  örneğin kendi yazısından okundu. PE klemensi ile normal klemens şekil olarak ayrışıyor
  (10↔2 karşılıklı red). Kullanıcı adına onay verilmedi; bu işaretler sayfa 4'e bağlı beş
  incelemeyi `NEEDS_REVIEW` yaptı (kararlar silinmedi).
- Döndürülmüş sayfa referansı düzeltmesi + `prepare --add-pages` ile hedef sayfalar **28** ve **36**
  izlendi: `=122/17.44`, `=122/25.67`, `=122/25.68`, `=122/25.69` devamları hedef sayfanın kendi
  geometrisinde karşılıklı doğrulandı (14 doğrulanmış devam).
- 1712 çizim bileşeni kanıtla ayrıştırıldı: 1375 dolu sembol tarama çizgisi, 145 kesikli cetvel
  parçası, 17 iletken adayı (hepsi çözüldü), 14 işaretli ağ, 5 yazı bloğu, 1 sayfa çerçevesi ve
  **155 açıklanmayan** (tek tek listeli; sınırın üstünde yalnız 2 tanesi var). Toplu eleme yok.
- Çözülemeyenler gerekçeleriyle bırakıldı: PE devresi (kesikli çizim, `/1.510` ve `/4.51`
  fail-closed), `-3W67` damar numarası çelişkisi (8 ↔ 6), `-X4`'te aynı adı taşıyan iki klemens,
  yazısız sınır klemensi (x=610,5), termoelement uçlarının pano tarafında çizilmemiş olması.
- Rapor: `output/pilots/E122/20260910_v3_p05_rev8/review/20260910_sayfa4_sistematik_tamamlama.md`;
  okunur tablo: `.../review/sayfa4_baglanti_tablosu.md`; görseller: `.../evidence/`.

**Sıradaki iş (bu hedefe hizalı):** (1) kullanıcının tabloyu şemayla karşılaştırması ve
`C01`–`C03` dâhil askıya alınan incelemeleri kendi onayıyla tazelemesi; (2) kesikli hat
birleştirmesi için kanıtlı kural (PE devresi bugünkü tek büyük boşluk); (3) aynı yöntemin
sayfa 2 ve 5'te tekrarı; (4) sonra bu müşterinin geliştirmede kullanılmamış sayfaları.
Vektör+görüntü karşılaştırması ve şüpheli bölgeden AI sembol önerisi planda **sonraki** iştir;
bu pakette açılmadı. P06'ya geçilmez.

**2026-09-10 (sıra) — çerçeve kuralı düzeltmesi ve kontrollü kesikli hat.** 100 test.

- `PAGE_FRAME` artık üç bağımsız kanıt ister (iki yönde ≥%90, dört kenar sayfa sınırında,
  kapalı çerçeve geometrisi). Eski "%80 VEYA" kuralı sayfa 4'ün gerçek L1/L2/L3 baralarını
  çerçeve sayıyordu; onları yalnız pin işareti kurtarıyordu. Regresyon testi: pin işareti
  kaldırılsa da L1 hattı çerçeve değil ve açık işte kalıyor; gerçek çerçeve hâlâ ayrılıyor.
- Her iletken adayı (düz/kesikli) artık her zaman açık iş: boşluk 28 → 90.
- `analyzer_v3/dashed.py` kesikli hatları ölçer ve **önerir**; graf ve ham parçalar değişmez.
  Sembol boşluğu ve noktasız kesişme birleştirilmez; süreklilik ile bağlantı ayrı sorulardır.
- Saha cihazı kutusu (`[128,56 · 572,18 · 801,79 · 709,66]`) PE hattından ayrıldı; köşeler
  çizimin kendi sıfır uzunluklu köşe iziyle doğrulandı, yakınlık eşiğiyle değil.
- Birleşme noktası dedektörü: eş merkezli halkalar, tolerans 0,15 pt, sayfa 4/2/28/36'da
  **yanlış pozitif 0**, kullanıcının elle onayladığı noktayı birebir üretiyor. Ölçülen bağlantı
  kazancı sayfa 4'te **sıfır kenardır**: değeri kanıt üretmek, bağlantı açmak değil.
- PE için üç kanıt ayrı: görsel (`evidence`), algoritmik yol (`path_evidence`, ölçülür — hiçbir
  koşuda izlenen hedef yok), insan kararı (`ONAY_BEKLIYOR`). Ortak PE ağından tel çifti
  türetilmiyor. Görsel: `evidence/20260910_s4_pe_birlestirme_onerisi.png`.
- Ölçüm katmanında kapatılan kusurlar: 2,0 pt parça filtresi gerçek mürekkebi siliyordu;
  eş merkez gruplaması bir noktayı kaybediyordu; farklı kalem kalınlıkları tek cetvelde
  birleşiyordu; kutu köşesi yakınlıkla kapatılıyordu; kısa parça muhasebesi çakışıyordu.
- Düzeltilen ifade: grafın kesikli hatta yapamadığı şey parçaları birleştirmek değil, kesik
  BOŞLUĞUNU köprülemektir. Bu sayfada hiçbir çizgide PDF dash niteliği yok (2118/2118).
- `-3W67` damar numarası çelişkisi (8 ↔ 6) ayrı notta; saha kablosudur, pano içi satırları
  bloke etmiyor.
- **Saldırgan denetim (10 ajan) yedi ölçülmüş kusur buldu, hepsi kapatıldı:** dolgu yığını testi
  yerel değildi (gerçek ok başı açık işten düşüyordu); boşluk köprülemesi genişlikte fail-open'dı
  (`-X4:PE` klemensini yalnız tek bir eğri nesnesi kurtarıyordu); eğri engeli bbox ile sınanıyordu
  (23/31 artifakt); uç yazısı komşu potansiyeli topluyordu (`N24.30` bir PE iletkeninin kanıtı
  olamaz); kendi ürettiğim aday işaret bağımsız kanıt sayılıyordu (döngüsel); kapsam kararı
  kanıtları eziyordu; `DASH_RUN` kararı sayfayı sessizce varsayıyordu.
- Sonuç DAHA İHTİYATLI: iki PE düşüşü artık `İLETKEN ADAYI` değil `BELİRSİZ`; yalnız PE barası
  iletken adayı olarak duruyor. Bu bir gerileme değil, kanıt eşiğinin sıkılaşmasıdır.
- Rapor: `output/pilots/E122/20260910_v3_p05_rev8/review/20260910_cerceve_ve_pe_kesikli_hat.md`.

**Sıradaki iş:** (1) kullanıcının PE önerilerini ve askıdaki incelemeleri kendi onayıyla
karara bağlaması; (2) onaylanan koşuların graf tarafında nasıl temsil edileceği (hâlâ yalnız
ağ ilişkisi olarak); (3) saha tarafı polyline eğrilerinin ayrı ve onaylı bir kararla ele
alınması; (4) bağımsız doğrulama yüzeyi olarak sayfa 2/28/36 (sayfa 5 sayfa 4'ün birebir
kopyasıdır, bağımsız değildir). P06'ya geçilmez.

**Kalan:** 5. ölçüt (süre) yalnız mekanizma olarak var; bu oturumun sayıları betik kaynaklıdır ve
operatör eforunu ölçmez — gerçek karşılaştırma kullanıcının kendi oturumunda oluşur. Bu oturumdaki
işaretler Claude tarafından kondu, kullanıcı görsel onayı bekliyor. Her kayıttan sonra graf yeniden
kuruluyor (~1,7 sn); çok uç işaretlenecekse önce bu maliyet düşürülmeli. Kapsam genişletmesi (2–8,
sonra kalan kapsam içi sayfalar) bu pilot kullanıcı tarafından doğrulandıktan sonra gelir.
P06'ya geçilmez.
