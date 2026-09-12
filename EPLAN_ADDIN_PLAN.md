# PDF → EPLAN P8 — eklenti ve veri sözleşmesi uygulama planı

Tarih: 2026-09-11. Durum: **tasarım / Claude için kodlama şartnamesi; henüz çalışan eklenti yok.**
Bağlayıcı kararlar [MAIN.md](MAIN.md), tek iş sırası [PLAN.md](PLAN.md) S00–S06.
Bu belge S02/S03/S05'in uygulama ayrıntısıdır; ayrı bir mimari değerlendirme turu değildir.
Başlangıç ve teslim talimatı: [CLAUDE_NEXT.md](CLAUDE_NEXT.md).

## 1. Kesin karar ve ilk çalışır sonuç

**Mevcut Python çıkarıcı + yerel sayfa düzenleyici + küçük C# EPLAN add-in'i.**
Python PDF'yi anlar; EPLAN eklentisi hedef EPLAN nesnelerini bilir ve oluşturur. İkisi arasında
sürümlü dosya paketi vardır. Excel bu aktarımın ara formatı değildir.

İlk sonuç tam otomatik 58 sayfa değil: bütün sayfaları gezebilen ekran ve ardından küçük bir
gerçek PDF bölgesinin P8'de gerçek sembol/pin/bağlantılarla düzenlenebilir olması. Tanınmayan
bölge görünür kalır; kullanıcının eşlemesi/düzeltmesiyle ilerlenir.

```text
Müşteri PDF'si → Python: metin + vektör + sayfa kanıtı
                         ↓
                 Sürümlü sayfa modeli ← kullanıcı düzeltmeleri
                         ↑
EPLAN açık test projesi → sembol/pin kataloğu → kalıcı aile eşlemesi
                         ↓
                Seçili sayfalar + pano filtresi
                         ↓
             Paket → EPLAN önizleme → kullanıcı aktarımı
                         ↓
             Gerçek P8 nesneleri → geri okuma / fark raporu
```

Hedef: elektrik şeması aktarımı. Köprü tel/tarak kararı, tel kesim sırası, Pro Panel yerleşimi,
otomatik parça satın alma ve üretim serbest bırakma bunun parçası değildir. Şema nesnelerinin
oluşması, bu kararların verilmesini gerektirmez.

## 2. Mevcut ortam ve satın alma bağımlılığı

2026-09-11 salt okunur yerel kontrolde:

- `C:\Program Files\EPLAN\Platform\2026.0.3\Bin\EPLAN.exe`: **2026.0.3.25702**.
- Aynı klasörde `Eplan.EplApi.AFu`, `DataModelu`, `HEServicesu`, `Guiu`, `MasterDatau`,
  `Starteru` gibi API DLL'leri ve XML başvuru dosyaları var; DLL sürümleri aynı.
- `C:\Program Files\dotnet\dotnet.exe --list-sdks` çıktı vermedi. Bu konumda listelenen
  .NET SDK yok; başka derleyici/Visual Studio kurulumu bulunmadığı sonucu çıkarılmadı.
- Lisans yetkisi, API modülü yükleme, SDK geliştirme örneği ve EPLAN'da yazma testi yapılmadı.
  DLL bulunması tek başına geliştirme veya runtime yetkisini ispatlamaz.

**Kullanıcı API satın alacağını bildirdi.** Yeniden “alacak mısınız?” sorusu yok. Satın alma
teslim kontrolünde kendi eklentimizi geliştirme/test etme erişimi, SDK, hedef P8 uyumu ve
runtime dağıtımı için imzalama yetkisi doğrulanır. Resmi 2026 dokümanı developer ve runtime
lisansını ayırır; developer için normalde beş sayfa test sınırından, runtime için imzalı
program gereğinden söz eder. Kendi teslimimiz için geçerli şartlar satıcıyla doğrulanmalıdır.
[EPLAN 2026 lisans ve imzalama açıklaması](https://www.eplan.help/en-us/infoportal/content/api/2026/Signing_EPLAN_assembies.html).

İlk gerçek test 2–3 sayfalık ayrı projede tutulabilir. Lisans/derleyici eksikse Python,
sözleşme, doğrulayıcı ve saf C# çekirdek işleri ilerler; **host derlemesi/yüklemesi/gerçek
bağlantı kanıtı ayrı açık kalır**. Sahte API sınıflarıyla çalışan örneğe “P8 çalışıyor” denmez.
Kurulum ve buluta imzalama yüklemesi bu tasarım belgesiyle yapılmış/izin verilmiş sayılmaz.

## 3. Kullanıcının göreceği ekranlar ve komutlar

Mevcut web arayüzü korunur. İlk sürümde ikinci bir PDF editörü EPLAN içine yeniden yazılmaz;
EPLAN tarafında küçük bir aktarım penceresi yeterlidir. Gömülü tarayıcı ve canlı iki yönlü
bağlantı sonraya kalabilir. Dosya seçiciyle çalışan uçtan uca akış ilk teslimdir.

### Python sayfa ekranı

1. **Belge aç / sayfaları gez:** 73 sayfa, fiziksel sıra + Blatt + yapı + tür. Mevcut indekse
   göre 58 hedef şema varsayılan; malzeme/yerleşim sayfaları erişilebilir fakat seçili değil.
2. **Hazırla:** önce açılan sayfa, sonra seçili kapsam; durdur/devam/yeniden deneme. Açılmış,
   hazırlanmış, aday çıkarılmış, incelenmiş ve aktarılmış sayfa ayrı durumlar.
3. **Öğret / eşle:** PDF ailesini seç, EPLAN kataloğundan gerçek sembol veya kullanıcı makrosu
   seç, uç eşlemesini göster. Kalıcı eşleme diğer sayfada yeniden kullanılabilir.
4. **Düzelt:** cihaz/pin yazısını ve sahipliğini düzelt, nokta/hat ekle-taşı-ayır, birleşimi
   değiştir, devam eşlemesini düzelt, kapsamı düzelt; geri al ve kaynakla farkı gör.
5. **Şema ilişkileri:** pin→pin kadar pin→L1/PE/P24 ve pin→devam da görünür. Gerçek segment
   vurgusu ve hedef sayfaya geçiş var; yalnız iki uç arası düz çizgi gerçek yol sayılmaz.
6. **EPLAN paketi hazırla:** sayfa/kapsam/eşleme eksiklerini özetle; tam/kısmi taslak ayrımı
   görünür. Paket üretmek EPLAN projesine yazmaz veya imalat onayı oluşturmaz.

### EPLAN eklentisi

| Komut / ekran | Girdi | Sonuç / yazma sınırı |
|---|---|---|
| Ortamı kontrol et | Yüklü P8, açık projenin API bilgisi | Sürüm, yetenek ve eksik listesi; salt okunur |
| Hedef projenin kataloğunu çıkar | Kullanıcının seçtiği açık proje | Sembol/variant/pin, sayfa ayarı ve mevcut fonksiyon envanteri; salt okunur |
| Paketi seç ve kontrol et | Yerel paket + açık hedef proje | Doğrulama, kapsam, ad çakışması, eksik eşleme; yazma yok |
| Aktarım önizlemesi | Geçerli paket + katalog + hedef durumu | Yeni / yeniden kullanım / kullanıcı değişikliği / çakışma / grafik / dışarıda kalan listeleri |
| Seçili taslağı aktar | Önizlemede kullanıcı onayı | İlk sürüm yalnız açıkça seçilen ayrı test projesine, belirtilen sayfa/nesnelere yazma |
| Sonucu denetle | Aktarım kaydı + hedef proje | EPLAN'dan nesne, pin, bağlantı ve devamları tekrar okuyup fark raporu |
| Kaynakta / EPLAN'da bul | Kaynak örnek kimliği veya aktarım kaydı | İlgili sayfa/nesneyi seç/vurgula; PDF açılması güvenli yerel yol üzerinden |
| Yeniden aktarımı incele | Aynı kaynağın yeni paketi | Üç yönlü fark; kullanıcı değişmiş nesneye otomatik yazma yok |

Başarı rozeti tek sayı olmayacak: **elektrik nesnesi olarak aktarılan / yalnız grafik /
çözülemeyen / kapsam dışı / geri okumada hatalı** ayrı gösterilir. Tamamlanmamış aktarımda
“başarılı” tek başına yazmaz. Mevcut kullanıcı sayfasını üzerine yazarak değiştirme varsayılan
değildir; ilk toplu teslim yeni sayfalı ayrı taslak/test projesidir.

## 4. Hangi veri nereden gelecek?

| Veri | Birincil kaynak | İşleyen / kontrol | Hedefte kullanım |
|---|---|---|---|
| PDF hash, fiziksel sayfa, boyut, CropBox/dönme | Müşteri PDF'si | Python hazırlama | Kaynak kimliği, yerleşim dönüşümü |
| Blatt, =fonksiyon, +yerleşim, açıklama | Başlık + yerel yapı kutusu/yazısı | `document.py` + kullanıcı düzeltmesi | EPLAN sayfa yapısı/ad haritası; fiziksel sıra ad yerine geçmez |
| Cihaz adı ve fonksiyon örneği | O sayfanın yazısı ve sahiplik geometrisi | Mevcut tanıma + düzeltme | Tam DT ve doğru cihazın ayrı fonksiyonları |
| Pin yazısı ve görünen pin konumu | O örneğin metin/vektörü | Kimlik ve pin sahipliği | Hedef sembolün gerçek bağlantı noktası ile eşleme |
| Şekil ailesi / etiket arama bölgesi | Kullanıcı öğretimi + PDF kütüphanesi | Mevcut `library.py` | Aday bulma; eski cihaz/pin adını kopyalama değil |
| Hedef sembol/variant, fonksiyon tanımı, pin indeksi/yönü | Açık EPLAN projesi / yüklü erişilebilir kütüphane | C# katalog okuyucu + aile eşlemesi | Gerçek EPLAN yerleştirmesi; sayısal ID tahmini yok |
| Alternatif makro | Kullanıcının izin verdiği yerel EPLAN makrosu | Makro envanteri ve hash | Çok fonksiyonlu cihaz/PLC için isteğe bağlı eşleme |
| Çizgi, dal, kesişim ve sembol boşluğu | PDF vektörü + görsel kanıt | `geometry.py`, kesikli hat kuralları | Şema topolojisi / bağlantı sembolleri; tel imalat zinciri değil |
| L1/L2/L3, P24/N24, PE adı | Aynı çizgiye ait gerçek yazı, birleşim ve devam | Potansiyel/hat çözümü | Hat/potansiyel nesnesi; sahte ikinci cihaz değil |
| Devam eşlemesi | Kaynak ve hedef sayfanın kendi referans/geometrisi | Mevcut devam motoru + kullanıcı | EPLAN kesinti noktaları ve kaynak→hedef sayfa haritası |
| Pano sınırı/kapsam | Tam yapı + yerel konum kutusu + kullanıcı filtresi | Python model/kapsam önizlemesi | Varsayılan pano içi; tam sayfa yalnız seçilirse |
| Kesit/renk özgün değeri | PDF'de ilgili iletkene ait yazı | Kaynaklı özellik çıkarımı | Sadık şema özellikleri; yoksa bilinmiyor |
| Standarttan kesit/renk | Yüklü TROESTER > UVP ve proje notu | Mevcut kural/kaynak zinciri | Ayrı türetilmiş özellik; özgün PDF değeri gibi yazılmaz |
| Parça numarası/ürün | Açık PDF bilgisi veya hedefte mevcut kullanıcı verisi | Ayrı kaynak/eşleme | Biliniyorsa korunur; aileye bakarak parça uydurulmaz |
| Mevcut cihaz/ana fonksiyon/yerleşmemiş fonksiyon | Seçilen hedef EPLAN projesi | C# envanter okuyucu | Çoğaltma yerine kontrollü yeniden kullanım |
| Çizim grid'i, sembol pin aralığı, çerçeve ve proje ayarları | Hedef EPLAN projesi/kütüphanesi | C# katalog ve kalibrasyon | Bağlı pinler kopmadan yerleşim; çifte çerçeve yok |
| Kullanıcı düzeltmesi | PDF ekranındaki veya P8'deki açık kullanıcı işlemi | Sürümlü override / hedef geri okuma | Sonraki analiz/aktarımda korunur |
| Gerçekte oluşan nesne/pin/bağlantı | Aktarım sonrası EPLAN API | C# geri okuyucu | Başarı kanıtı, fark ve yeniden aktarım tabanı |

Her kritik alan `raw_value`, varsa `normalized_value`, `source_kind`, kanıt referansı ve
varsa kullanıcı düzeltme sürümünü taşır. **PDF gözlemi, standart yorumu, kullanıcı tercihi
ve EPLAN'da oluşan sonuç birbirinin üstüne yazılmaz.** Bilinmeyen değer null + gerekçedir;
boş string/0 kullanıp “okundu” sayılmaz.

## 5. Sürümlü veri sözleşmesi — ilk sürüm

### Ortak kurallar

- UTF-8 JSON, sözleşme sürümü `1.0`. Sayısal koordinatlar sayıdır; yerel virgüllü metin değil.
- Doküman kimliği PDF SHA-256; sayfa kimliği belge+fiziksel sıra. Basılı Blatt ayrı alandır.
- Nesneye atanmış kalıcı `source_id` taşınır; cihaz adı veya yuvarlanmış koordinat tek başına
  kimlik değildir. Taşımak/yeniden adlandırmak aynı nesnenin sürümünü değiştirir. Çıkarıcı
  değişip eşleme belirsizleşirse yeni kimlik ve uzlaştırma sorunu oluşturulur, sessiz birleştirme yok.
- Her dosyanın hash'i kendi UTF-8 baytlarından hesaplanır. Manifest kendi hash'ini içermez;
  paket hash'i manifestin dağıtılan baytlarından alınır. Manifest seçili tüm dosya hash'lerini
  içerir. Python/C# için ortak altın örnek ve bozulmuş dosya testleri yazılır.
- İlk sürüm yerel klasör paketi; gerekirse ZIP sonra. Yalnız manifestteki göreli dosyalar;
  `..`, kök dışı yol, symlink/reparse kaçışı, aşırı büyük dosya reddedilir. Kod, çalıştırılacak
  EPLAN action adı veya komut satırı paketten kabul edilmez. Bu biçim **EPLAN'ın resmi JSON
  import formatı değil, bizim uygulamamızın sözleşmesidir**.

### Dosyalar

| Dosya | Üreten → tüketen | Asgari içerik |
|---|---|---|
| `capabilities.json` | C# → Python/önizleme | P8 build, eklenti/contract sürümü, erişilebilen işlemler, test edilmemiş yetenekler, aktif hedef bağlamı; lisans anahtarı içermez |
| `catalog.json` | C# → eşleme ekranı | Hedef proje bağı, katalog hash'i, kütüphane/sembol/variant anahtarı, gerçek pin indeks/yön/konumu, fonksiyon tanımı, ilgili proje ayarları |
| `mappings.json` | Eşleme ekranı → paket/C# | PDF aile ve sürümü → hedef sembol/makro, pin eşlemesi, desteklenen dönüşüm, kaynak/kullanıcı, katalog sürümü; başka örneğin DT'si değil |
| `manifest.json` | Python → C# | Paket/çalışma/sözleşme sürümü, PDF hash, dosya hash'leri, seçili sayfalar, kapsam modu, eşleme sürümleri, oluşturucu sürümü |
| `pages/<id>.json` | Python → C# | Aşağıdaki sayfa modeli, kaynak geometri/yazı referansları, uygulanmış düzeltme sürümleri ve açık sorunlar |
| `assets/*` | Python veya kullanıcı → C# | İzin verilmiş yerel grafik/makro kanıtı; her dosya hash'li. Kaynak kanıt resmi elektriksel nesne sayılmaz |
| `import-request.json` | Kullanıcı önizlemesi → C# | Seçili sayfa/nesneler, hedef bağlam, sayfa adı haritası, kapsam, kısmi aktarım seçimi, kullanıcı seçimleri |
| `dry-run.json` | C# → kullanıcı/Python | Yürütme planı ID'si, paket/katalog/hedef parmak izleri, işlemler, çakışmalar, atlanan ve grafik kalanlar, engeller |
| `receipt.json` | C# → Python | İstek ve plan ID, kaynak→hedef kimlik eşlemesi, gerçek işlem sonuçları, hata/geri alma sonucu; append-only geçmiş |
| `readback.json` | C# → denetleyici | Gerçek sayfa/fonksiyon/pin, bağlantı uçları, potansiyel/devam, konumlar; hangi kontrolün çalıştığı ve çalışmadığı |
| `diff.json` | Denetleyici → kullanıcı | Eksik/fazla nesne, yanlış kimlik, yanlış/eksik/fazla elektriksel ilişki, görsel fark, korunan kullanıcı değişikliği |

### Sayfa modeli alanları

1. `page`: fiziksel sıra, kaynak Blatt/tam yapı, açıklama, birimler, Media/CropBox, UserUnit,
   dönüş, sayfa genişlik/yüksekliği, kanonik koordinata ve geri dönüş matrisi.
2. `device_groups`: tam yapılandırılmış DT; aynı rölenin bobin ve kontaklarının ortak cihazı.
3. `functions`: ayrı sembol örnekleri; `device_group_id`, PDF aile sürümü, kutu/çapa/dönüş,
   fonksiyon rolü, kaynak kanıtı, EPLAN eşlemesi veya eksik eşleme gerekçesi.
4. `pins`: örnek kimliği, ait fonksiyon, özgün ad, kanonik koordinat, yön ve kanıt. `A1`,
   `13`, `X3:15` metin olarak korunur. Hedef pin indeksi ayrı; “13 → indeks 13” yapılmaz.
5. `nodes`: `PIN`, `JUNCTION`, `POTENTIAL_ANCHOR`, `INTERRUPTION`, `SCOPE_BOUNDARY`,
   `OPEN_END`. Her biri açık türdür; potansiyel/PE çapası hayali cihaz değildir.
6. `segments`: uç düğümler, gerçek polyline, özgün çizgi kimlikleri, çizgi deseni, iletkenlik
   dayanağı, sembol içi/çerçeve ayrımı, kullanıcı ekleme/değiştirme kaydı.
7. `networks`: graf bileşeni ve üyeleri; potansiyel etiketleri ile karşılıklı devam bağı.
   Aynı adı taşıyan ayrık bileşenler ayrı kalır. Grafik ağ üyeliği ile fonksiyonun iç
   elektriksel davranışı karışmaz; sigortanın iki tarafı çizgi üzerinden kısa devre yapılmaz.
8. `continuations`: özgün basılı referans, kaynak uç, varsa doğrulanmış hedef uç/sayfa,
   eşleme kanıtı, seçilmeyen/çözülmeyen hedef durumu. Kontak-bobin çapraz referansı ayrı türdür.
9. `annotations`: serbest metin, kablo tanımı, açıklama çizgisi, çerçeve/grafik; devre çizgisi değil.
10. `scope`, `properties`, `issues`, `overrides`: kapsam kanıtı, ayrı özellik kaynakları,
    engelin hangi nesne/ağa yayıldığı ve kullanıcı düzeltme geçmişi.

“P8'de oluşturulabilir”, “kullanıcı inceledi” ve “imalata uygun” tek enum'a sıkıştırılmaz.
`production_released` bu akışta false kalır. İçeriği değiştiren bir düzeltme, bağlı hazırlama
ve önizlemeyi bayatlatır; eski kullanıcı kararlarını otomatik yenilemez.

## 6. EPLAN nesnelerine dönüşüm kuralları

### 6.1 Katalog ve iki kütüphane

PDF şekil kütüphanesi tanımayı; EPLAN eşleme kütüphanesi hedef elektrik nesnesini seçmeyi sağlar.
Önce açık projenin mevcut sembolleri ve gerekli aileler okunur; bütün üretici veri tabanı
indirilmez. Her eşleme pin sayısı/yönü/işlevi ve NO/NC, bobin/kontak farkıyla doğrulanır.
Katalog değişirse eski eşleme tekrar doğrulanır; sadece aynı sembol numarası yetmez.

Üç kutuplu sigorta için hedef kütüphane birden çok fonksiyon veya makro kullanabilir.
Altı görünür pin var diye rastgele altı pinli bir sembol seçilmez. PLC'de başlık, kutu,
bağlantı noktası ve modül kimliği birlikte modellenir; adı basılmayan uçlara katalogdaki
varsayılan ad müşteri PDF'sinde okunmuş gibi yazılmaz. Katalog şablon beklentisi öneri olabilir.
Makro içindeki sabit cihaz/ürün adları yeni PDF'ye kendiliğinden taşınmaz.

### 6.2 Cihaz ile fonksiyon ayrı

`=112+E122-17K55` cihaz grubudur; kontak ve başka sayfadaki bobin ayrı fonksiyon örnekleridir.
DT aynı diye bütün örnekler tek fonksiyona ezilmez. Mevcut ana/yardımcı fonksiyon ve henüz
yerleştirilmemiş fonksiyon varsa uyumlu eşleme önizlenir; atanmış parçalar korunur.
EPLAN tarafından türetilen çapraz referanslar yeni yerleşime göre oluşturulur. PDF'deki eski
referans kaynak kanıtında kalır, hedefte bozuk statik çapraz referans olarak kopyalanmaz.

İki `X4:N24.30` konumu kaynak örnek kimliğiyle ayrılır; uydurma son ek verilmez. Hedefte bu
ayrımı koruyacak klemens/bağlantı noktası eşlemesi bulunamıyorsa çakışma gösterilir.

### 6.3 Koordinat ve pin hizası

- Tek kanonik sistem: kırpılmış/görünür sayfada sol üst başlangıç, x sağa/y aşağı, PDF nokta
  birimi. Ham PDF→kanonik dönüşümü açık; UserUnit/dönüş kırpma kütüphane tarafından zaten
  uygulanmışsa ikinci kez uygulanmaz. Raster piksel koordinatı ayrıca dönüşümlüdür.
- PDF noktası fiziksel ölçü karşılığında 25,4/72 mm'dir; bu **EPLAN yerleşim ölçeğinin
  otomatik garantisi değildir**. Hedef grid/sembol aralığına kalibrasyon gerekir.
- EPLAN çerçevesinin mantıksal alanı, sayfa ölçeği, ekseni ve sembol çapasının gerçek anlamı
  gerçek testle doğrulanır. Üç dağınık nokta ve pin konumlarıyla dönüşüm hatası raporlanır.
- Bütün noktaları bağımsız en yakın grid'e yuvarlama yok. Aynı elektrik düğümü tek hedef
  koordinatı kullanır; hedef sembol pinleri yerleşince bağlı yollar birlikte uyarlanır.
- Önce desteklenen öteleme ve gerekli hedef varyantı. Dönüş/ayna/ölçek sadece eşleme ve
  pin permütasyonu doğrulanmışsa açılır; PDF tanıyıcısına desteksiz dönüşüm varmış denmez.
- Önerilen kabul: bağlı uçlar aynı host koordinatında; kalibrasyon/grid sapması belirlenen
  toleransın altında; yeni kısa devre, noktasız kesişimde birleşme ve sembol üzerinden tel yok.
  Tolerans E00/E04'te ölçülür ve test fixture'ında dondurulur; göz kararı “yakın” sayılmaz.

### 6.4 Hat, birleşim, potansiyel ve PE

Elektrik çizgileri genel grafik `Line` koleksiyonu olarak bırakılmaz. Hedef sembol pinleri,
uygun EPLAN bağlantı sembolleri/köşeler/T elemanları ve potansiyel/kesinti nesneleriyle
çizilmiş ağ temsil edilir. Ardından bağlantılar üretilir ve API'den okunur. Hangi host
nesnesinin kullanılacağı gerçek küçük örnekte kanıtlanır; uydurma `CreateWire` metodu yok.

`L1→3F22:1` gibi ilişki ikinci cihaz pini olmadan kaynak şemada gösterilir. P8 geri okumasında
potansiyel/bara/kesinti bağlantısı ayrıca denetlenir; bütün kanıtı yalnız iki uçlu Connection
sayısına indirgeyip yeniden “eksik” yapma. L1/L2/L3 ve bağımsız P24 ağları ayrık kalmalıdır.

PE yazısı + gerçek birleşim + devam + tutarlı çizgi deseniyle desteklenen PE koşusu elektriksel
şema adayı olabilir; otomatik sınıflandırma, eski insan onayı gibi kaydedilmez. Her tire için
yeniden kullanıcı sorusu gerekmez. Belirsiz koşu açık kalır. Çerçeve/pano sınırı/mekanik kesikli
çizgi, noktasız kesişim ve sigorta boşluğu asla bu genellemeyle birleştirilmez. Kesikli görünüm
ile elektriksel bağlantı ayrı özelliklerdir. Fiziksel PE klemens numarası ve tel zinciri üretilmez.

Üç kollu T, şema topolojisidir. EPLAN'ın bağlantı üretiminde seçtiği hedef sırası PDF'nin
imalat sırası olarak kabul edilmez. Hem doğrudan pin eşleşmeleri hem ağ erişilebilirliği
ve **beklenmeyen birleşmeler** kontrol edilir; yalnız aynı toplam bağlantı sayısı yetmez.

### 6.5 Sayfa devamı ve yalnız pano filtresi

Sayfa adı haritası kaynak belge+Blatt+yapıdan hedef tam sayfa adına gider. Referansın etiketi
ile elektriksel eşleme ayrı saklanır. Yalnız karşılıklı doğrulanmış uç veya açık kullanıcı
düzeltmesi bağlantı kurar; aynı `L1` metni tüm projeyi birleştirme talimatı değildir.

Seçilmeyen hedef sayfa için açık `EXTERNAL_TO_SELECTION` durumu; varsa kaynak referans notu.
P8'de mevcut kesinti noktalarıyla istenmeyen ad eşleşmesi önizlenir. Güvenli hedef isimlendirme
ve sıralama kanıtlanamıyorsa o devam elektriksel olarak bağlanmadan görünür açık iş kalır;
isimsiz hayali cihazla çözülmez. Eklenti iç UUID'si fiziksel pin etiketi olarak gösterilmez.

Varsayılan pano filtresi yerel konumu dikkate alır, sadece sayfa başlığına bakmaz. Gerçek
sınır klemensi korunur; hariç saha nesnesine giden yol sınırda açık uç/harici devam olarak
kalır. Kaynak ham sayfa ve kanıt silinmez. Kapsamı belirsiz nesne önizlemede çözülür veya
açıkça hariç tutulur. Kullanıcı “tam sayfa” seçerse saha nesneleri ayrı sınıflarıyla aktarılır;
imalat filtresi bu nedenle genişlemez.

### 6.6 Metin, çerçeve ve desteklenmeyen bölge

Başlık alanları hedef sayfa özelliklerine eşlenir. Hedef çerçeve kullanılıyorsa PDF çerçevesi
ikinci kez üstüne çizilmez. Kaynak notları, kablo açıklamaları ve döndürülmüş metinler görünür
metin/grafik olarak korunur; referans metni gerçek kesinti nesnesinin yerine geçmez.

Bilinen nesneler semantik; desteklenmeyen bölge kaynak kırpma/vektör grafik + açık sorun olabilir.
Grafik nesnesi elektriksel uçlara sahipmiş gibi gösterilmez. Bu bölgeye komşu tellerin belirsiz
uçları da raporlanır. Kısmi aktarım seçiminde kullanıcı hangi işlevin eksik kaldığını görür.
Bir bilinmeyen sembol tüm belgeyi durdurmaz; ancak bağlı belirsiz ağ tam çözüldü sayılmaz.

## 7. Güvenli aktarım, tekrar çalıştırma ve hata davranışı

### Önizleme → yürütme

1. Dosya/şema/hash kontrolleri; kaynak, eşleme, katalog ve hedef proje bağı doğrulanır.
2. Tam sayfa adları, nesne eşlemeleri ve değişecek nesneler hesaplanır; **yazmadan** önizlenir.
3. Plan ID; paket hash'i, katalog hash'i, seçili hedef nesne/sayfa/ayar parmak izi ve seçimlerle
   bağlanır. Yürütme öncesi tekrar okunur. Değişmişse `PREVIEW_STALE`, otomatik devam yok.
4. Yazma kilidi alınamazsa işlem başlamaz. İlk sürüm bir hedef proje ve tek yürütme; EPLAN API
   nesneleri arka plan Python işlerine veya paralel thread'lere verilmez. Host thread/lifecycle
   şartları E00'da doğrulanır; uzun PDF işlemi EPLAN ana işlemi dışında kalır.
5. Sayfa grubu/kesinti bağımlılıklarıyla sınırlı işlem; hatada durdur, etkileneni geri almayı
   dene ve geri okuyarak sonucu doğrula. Önceden tamamlanan sayfa grupları ayrı kayıttır.
6. Bağlantı üretimi + geri okuma sonrası `COMPLETED`, `PARTIAL`, `FAILED_ROLLED_BACK` veya
   `FAILED_RECOVERY_REQUIRED`. Geri alınamadıysa asla başarı veya “hiç değişmedi” denmez.

Yazma hatası ve timeout sonrası kör retry yok. Önce hedef ve işlem kaydı uzlaştırılır;
sonuç belirsizse `OUTCOME_UNKNOWN` ve yeniden inceleme. Güvenli salt okunur işler sınırlı
tekrar denenebilir; bütün import komutu genel retry sarmalayıcısına konmaz.

### Kaynak → hedef kimlik ve kullanıcı değişikliği

Kalıcı aktarım deposu kaynak nesne kimliği, hedef proje bağı, nesne türü/kimliği, son aktarılan
alanlar ve parmak izini tutar. Oturumluk nesne/proje numarasının kalıcı olduğu varsayılmaz.
Kapat-aç, yeniden adlandırma ve proje kopyalama test edilir. Sadece sidecar eşlemesi yeterli
değilse hedefte izinli namespace ile kalıcı işaret desteği doğrulanır; kullanıcı özellik
alanları sessizce işgal edilmez. Bağ şüpheliyse isimle tahmini yeniden eşleme yapılmaz.

Üç yönlü karşılaştırma: **son aktarım tabanı / yeni PDF modeli / bugünkü EPLAN nesnesi**.

| Durum | Varsayılan karar |
|---|---|
| Paket aynı, hedef aynı | NO_OP; ikinci sembol veya satır yaratma |
| Kaynak değişmiş, hedef tabanla aynı | Eklentinin oluşturduğu nesne için önizlemeli güncelleme |
| Hedef kullanıcı tarafından değişmiş | Kullanıcının değişikliğini koru, farkı göster |
| İkisi de aynı alanı değiştirmiş | CONFLICT; alan bazında kullanıcı seçimi |
| Hedefte nesne kullanıcı tarafından silinmiş | Otomatik yeniden yaratma yok; silme kararını göster |
| Kaynakta artık yok | Hedef nesneyi otomatik silme yok; fark kaydı |
| Aynı DT/konumda kullanıcı nesnesi var | Uyumlu mevcut fonksiyon eşlemesini öner; otomatik kopyalama/ezme yok |
| Sidecar/proje kimliği kayıp veya değişmiş | Aktarım bağını yeniden doğrula; yazma kapalı |

İlk sürümde geniş otomatik senkronizasyon şart değil: NO_OP + çakışmayı yakala + kullanıcı
düzeltmesini koru yeterli. Kullanıcıya ait nesne silme/toplu üzerine yazma ayrıca yetkilendirilir.

EPLAN UndoStep, kalıcı proje nesneleri için yararlıdır fakat dosya/registry işlemlerinin tamamını
kapsamaz. Bu yüzden test projesi, aktarım günlüğü ve gerçek geri alma testi birlikte gerekir.
Proje açma/oluşturma veya özel özellik tanımı tümden geri alınabilir varsayılmaz.
[EPLAN UndoStep sınırları](https://www.eplan.help/en-us/infoportal/content/api/2026/Eplan.EplApi.DataModelu~Eplan.EplApi.DataModel.UndoStep.html).

## 8. Kodun yerleşimi ve sorumluluklar

Aşağıdaki yollar **oluşturulacak önerilen yapıdır**, mevcut dosya iddiası değildir. Var olan
aynı sorumluluğu kopyalamak yerine genişlet; bir çalışan dikey örnek için gerekli parçalarla başla.

```text
contracts/eplan/v1/                 JSON şemaları + golden/invalid örnekler
analyzer_v3/schematic/              sayfa modeli, ilişkiler, overrides, kapsam görünümü
analyzer_v3/eplan_exchange/         katalog okuma, eşleme, paket üretme, geri okuma farkı
eplan_addin/
  src/Uvp.PdfToP8.Core/             SDK bağımsız DTO, doğrulama, plan ve üç yönlü fark
  src/Uvp.PdfToP8.Host/             ince host-adapter; yerel P8 sürümüne derlenir
  tests/Uvp.PdfToP8.Core.Tests/     saf .NET sözleşme/işlem testi
  tests/host_cases/                 gerçek P8 test senaryoları ve kanıt şablonu
  build/                           keşif, build, paket ve imzalama talimatları
output/exchange/<run>/<request>/    manifest, sayfalar, önizleme, receipt/readback/diff
```

| Modül | Sorumluluk | Kesinlikle yapmayacağı |
|---|---|---|
| `SchematicBuilder` | Mevcut graph/continuation/etiketten sayfa modeli | Fiziksel tel Excel'inden şema uydurmak |
| `OverrideStore` | Kaynak sonucu üstüne sürümlü kullanıcı düzeltmesi | Kaynak PDF'yi değiştirmek veya eski incelemeyi yenilemek |
| `CatalogReader` / `MappingStore` | Hedef kataloğu + kalıcı aile/pin eşlemesi | Eski örneğin ad/bağlantısını kopyalamak |
| `PackageBuilder/Validator` | Hash'li, kaynaklı seçili paket ve yapısal kontroller | Paket oluştururken P8'ye yazmak |
| `IEplanHost` | Keşif, katalog, snapshot, yerleştirme, bağlantı üretme, geri okuma sınırı | Core testinde gerçek host varmış gibi davranmak |
| `ImportPlanner` | Deterministik dry-run, kimlik/scope/pin/koordinat kontrolü | Önizlemede nesne oluşturmak |
| `ImportExecutor` | Sınırlı onaylı işlem planını host üzerinden uygulamak | Pakette gelen keyfi komutları yürütmek |
| `ImportLedger` / `ConflictResolver` | Kaynak-hedef bağ, sonuç, NO_OP, kullanıcı değişikliği | Hedef sahipliği belirsizken ezme/silme |
| `ReadbackAuditor` | API'nin gerçek nesne/net sonucunu beklenenle karşılaştırmak | Sadece aynı toplam sayıdan tamlık çıkarmak |

C# çekirdeği EPLAN DLL referansı taşımaz. Host projesi yerel API referans yolunu build ayarından
alır; DLL'ler repoya/dağıtıma kopyalanmaz. Hedef .NET/CPU ve UI kütüphanesi yüklü 2026 SDK
uyumundan seçilir, ezbere net8/net48 veya DLL adı yazılmaz. Bağımlılık lisansları kaydedilir.

### Yerelde doğrulanan API dayanakları

2026.0.3 `Bin` içindeki XML başvuruları salt okunur tarandı:

- `DataModelu.xml`: `Project.SymbolLibraries`; `Function.Create(Page, MasterData.SymbolVariant)`
  ve diğer overload'lar mevcut. Fonksiyon oluşturma yolu var; doğru variant seçimi hâlâ gerekir.
- `HEServicesu.xml`: `Generate.Connections(Page[], bool)` seçili sayfaların bağlantılarını
  günceller. İlk sürümde doğrudan tipli çağrı tercih edilir; bütün projeyi gereksiz yeniden
  üretmek yerine bağımlı sayfa grubu ve etkileri test edilir.
- `Page.Create(Project, DocumentType, PagePropertyList)` resmi 2026 başvurusunda mevcut.
  [Sayfa oluşturma](https://www.eplan.help/en-us/Infoportal/Content/api/2026/Eplan.EplApi.DataModelu~Eplan.EplApi.DataModel.Page~Create.html).
- Add-in yaşam döngüsü `IEplAddIn` ile başlatma/kayıt/arayüz/kapatma olaylarını ayırır;
  yeniden yüklemede çift menü/olay dinleyicisi oluşmamalıdır.
  [IEplAddIn üyeleri](https://www.eplan.help/en-us/Infoportal/Content/api/2026/Eplan.EplApi.AFu~Eplan.EplApi.ApplicationFramework.IEplAddIn_members.html).
- Connection başvurusu başlangıç/bitiş pinleri, potansiyeller ve T/köşe sembol ilişkilerini
  sunar. Bu, geri okumanın dayanağıdır; her çizilmiş ağı basit iki pinli tele dönüştürme izni değildir.
  [Connection modeli](https://www.eplan.help/en-us/Infoportal/Content/api/2026/Eplan.EplApi.DataModelu~Eplan.EplApi.DataModel.Connection.html).

Bu başvuru okuması **derleme/çalıştırma kanıtı değildir**. E00 çıktısında kullanılan gerçek
metot imzaları, SDK yolu ve küçük host denemesinin sonucu kaydedilir. İnternette farklı
sürümlerden kopyalanmış kod yerine yerel 2026.0.3 başvurusu esas alınır.

## 9. Claude için iş paketleri ve check listesi

Tüm kutular başlangıçta açıktır. Doküman yazmak kod paketini tamamlamaz. İşler tek uygulayıcıyla
yürütülebilir; gereksiz çok ajanlı aynı sayfa taraması yok. Tamamlanan iş tekrar yazılmaz.

| ID | İş / ön koşul | Dosya veya ekran teslimi | Tamamlanma kanıtı |
|---|---|---|---|
| E00 | Ortamı keşfet; S01'i bekletme | Build/SDK/P8 sürümü, API envanteri, capability raporu | Yerel imzalar, derleyici ve lisans/test durumu ayrı; SDK eksiği somut |
| E01 | S02 küçük çekirdeği | Sayfa modeli, kaynak/düzeltme ayrımı, JSON şemaları, Python/C# örnekleri | Aynı paket iki tarafta doğrulanır; bozuk hash, sürüm, pin bağı ve yol kaçışı reddedilir |
| E02 | EPLAN host kabuğu | Yüklenir add-in, ortam/katalog komutları | Gerçek P8'de yükle-kapat-yükle; çift komut yok; açık projeye yazmadan katalog çıkar |
| E03 | İlk ailelerin hedef eşlemesi | Sigorta, normal/PE klemens, kontak/bobin, T/kesinti eşleme ekranı ve kayıt | Pin indeksi/ismi/yönü gerçek katalogdan; yanlış NO/NC veya pin sayısı reddi; proje değişince yeniden kontrol |
| E04 | **Erken gerçek aktarım, PLAN S03** | L1→sigorta→klemens + T + ikinci sayfaya devam; koordinat kalibrasyonu | Ayrı 2–3 sayfalık P8 test projesinde editlenebilir nesne; API readback; kopuk uç ve yanlış birleşme sıfır; ekran kanıtı |
| E05 | S04 belge geneli + kalan aileler | 58 aday şemada hazırlama/tanıma ve düzeltme; PLC/çok fonksiyonlu eşleme | Kaynak adı her örnekte kendi sayfasından; boş sayfa≠hazırlanmamış; gerçek PE/sınır negatif testleri; eksik aile görünür |
| E06 | Kapsam/çerçeve/devam ve kısmi paket | Pano içi varsayılan / tam sayfa seçenek; ad haritası, grafik fallback | Yerel saha kutusu, seçilmemiş hedef sayfa, aynı adlı kopuk potansiyel ve çifte çerçeve testleri |
| E07 | Tekrar aktarım ve hata dayanımı | Dry-run bağı, ledger, üç yönlü fark, kontrollü rollback | Aynı paket NO_OP; hedef değişince koruma; stale plan reddi; yarıda hata ve kapat-aç sonrası mükerrer yok |
| E08 | **Seçili sayfa paketi, PLAN S05** | Kullanılabilir aktarım penceresi, kaynakta/hedefte bul, receipt/readback/diff | İki veya daha fazla farklı gerçek şema sayfasında tam kullanıcı akışı; beklenmeyen net birleşmesi yok; kalan grafik açık |
| E09 | Build/dağıtım | Tekrarlanabilir build, sürüm paketi, kurulum/kaldırma, imzalama rehberi | Geliştirici ve runtime yükleme ayrı sınanır; API DLL/anahtar dağıtıma girmiyor; başarısız kurulum açık rapor |
| E10 | **S06 kullanım ölçümü** | Sayfa ve nesne paydalı rapor, kullanıcı süresi, ayrı TROESTER sınaması | Operatör düzeltme süresi ve eksik/yanlış sayımı; ayrılmış E530 yalnız ilan edilen değerlendirmede |

Uygulama sırası: **S01 + E01'in gereken bölümü → E00/E02/E03/E04 erken P8 kanıtı →
S02'nin kalan editör işleri + E05 → E06/E07/E08 → E09/E10**. E04 için bütün ailelerin ve
bütün sayfaların tanınması beklenmez; ilk kanıtta gereken birkaç eşleme yeterlidir.

### Paket başına durum kaydı

- [ ] Kod ve ilgili negatif/regresyon testleri yazıldı.
- [ ] Sentetik/kopya test ile gerçek PDF testi ayrı raporlandı.
- [ ] UI değiştiyse tarayıcıda gerçek akış kontrol edildi; yalnız HTTP 200 yeterli değil.
- [ ] Host değiştiyse gerçek P8 kanıtı veya açık `NOT_RUN / ENVIRONMENT_BLOCKED` yazıldı.
- [ ] Kaynak PDF/standart/Excel, canlı pilot onayları ve kullanıcı nesneleri korunuyor.
- [ ] PLAN'da yalnız kanıtı gelen alt iş işaretlendi; kalan iş ve dosya yolu belli.

## 10. Zorunlu test matrisi

| Katman | En az gereken testler |
|---|---|
| Mevcut çıkarım regresyonu | L1/2/3 üst besleme, C01/C02/C03 geçmiş görünürlüğü, PE≠çerçeve, noktasız kesişim, sembol boşluğu, PLC/klemens sahipliği |
| Sayfa/kimlik | Fiziksel 4=3F22, Blatt 4/fiziksel 5=4F22; aynı adlı iki klemens; kontak/bobin aynı DT ayrı örnek; yeni proje boş işaret/onay |
| Sözleşme | Bilinmeyen sürüm, bozuk hash, yabancı page/pin referansı, eksik katalog, NaN/sonsuz koordinat, dizin kaçışı, çift source_id |
| Geometri | Döndürülmüş/kırpılmış sayfa, karışık boyut, ters eksen, grid hizası, pin permütasyonu, T dalı ve birbirine değmeyen kesişim |
| Kapsam/devam | Yerel +M/+T alanı, pano içi/tam sayfa farkı, hedef sayfa seçilmemiş, karşılıksız referans, aynı potansiyelin yanlış global birleşmesi |
| EPLAN gerçek nesne | Page/Function/pin özellikleri ve bağlantı navigator/geri okuma; sigorta/kontak/bobin/klemens/PLC görev ayrımı; potansiyel ve kesinti |
| Hata/tekrar | Aynı paket iki kez, pin/P8 etiketi elle değişimi, hedefte silme, önizleme sonrası değişiklik, kilit hatası, işlemin ortasında hata, ledger kaybı, kapat-aç |
| Kullanıcı ekranı | İşaretsiz yeni sayfayı açma, L1 yoluna tıklama, devamda gezinme, aile eşleme, pin/hat düzeltme, geri alma, kısmi aktarımı görme |

Başarı paydası yalnız aktarılan nesneler değildir: seçili kaynak sayfadaki tüm kapsam içi
işlev/hat/bölge için semantik aktarım, grafik fallback veya gerekçeli açık iş bulunmalıdır.
Bağımsız ikinci PDF incelemesi örneklemin tamamlığı içindir; bütün 58 sayfa incelenmeden
“belge eksiksiz” denmez. Aynı şeklin sayfa 4/5'te kopyası farklı stil başarısı sayılmaz.

Geri okuma, aktarılacak modelin kendi kopyası değil **EPLAN API'den taze okuma** olmalıdır.
Kaynak net grafıyla normalize karşılaştırma ve görsel kontrol beraber yapılır. Beklenmeyen
birleşme ve kaynakta olmayan bağlantı, yalnız eksik bağlantı kadar kritik hatadır.

## 11. Maliyet, güvenlik ve sürüm teslimi

Mevcut vektör PDF için her sayfayı ücretli AI'ya gönderme yok. Sayfa/model/katalog/eşleme hash'i
ile önbellek; UI için küçük görüntü, detay için seçili bölge. AI/YOLO yalnız ölçülmüş eksiklere
yönelik sonraki geliştirme; EPLAN aktarımını başlatmanın şartı değil.

Müşteri PDF'si ve katalog varsayılan yerel kalır. İmzalama gerekiyorsa yalnız gerekli derleme
ürünleri, ayrıca yetkilendirilmiş işlemle gönderilir; müşteri projesi/paket/kanıt dosyası
imzalama yüküne konmaz. Kimlik bilgileri, PAT ve özel anahtar repoda/raporda/logda tutulmaz.

Dağıtım belgesi: desteklenen P8 build'i, derleyici hedefi, bağımlılık/lisans listesi, sürüm/hash,
kurulum ve eklentiyi kaldırma adımları, gerçek runtime testi. Otomatik güncelleme veya kullanıcı
projesini dönüştüren geri dönüşsüz migration ilk sürümün parçası değildir. Eski import kaydı
formatı yükseltilecekse yedek ve uyumluluk testi gerekir; veritabanı yeniden yaratılmaz.

## 12. Kullanıcıdan gerçekten gerekecekler — geliştirmeyi şimdi durdurmaz

1. API satın alımında kendi add-in'imiz için geliştirme/test ve runtime imzalama erişiminin
   teslim edilmesi. Lisans anahtarını sohbete yapıştırmak gerekmiyor.
2. İlk P8 kanıtında ayrı test projesi/temel proje seçimi; mevcut gerçek kütüphane kullanılacak.
3. Katalogda birden çok doğru seçenek kaldığında bir kez aile→sembol/pin eşleme kontrolü.
4. Çalışan sayfa ekranı ve P8 taslağında operatör görsel kontrolü; eski sohbet teyitlerini
   topluca tekrar onaylatmak yerine yeni somut çıktı üzerinden kontrol.

Claude önce yapabildiği kodu ve testleri tamamlar. Host çalıştırma engeli varsa tek somut
eksik/yetkiyi bildirir; bütün planı durdurmaz, “tamamlandı” diye gizlemez. Mevcut canlı EPLAN
projesine yazma veya kullanıcı nesnesi silme talebi bu dokümandan türetilmez.
