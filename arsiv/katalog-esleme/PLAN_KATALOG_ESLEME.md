# Katalog eşleme planı + devir notu (2026-09-12)

Amaç: her cihazı tek tek etiketlemeyi bırakmak. EPLAN kataloğundaki sembolleri kendi
çıkarıcımızla **vektör** olarak tanıyıp müşteri PDF'indeki şekillerle eşleştirmek; kullanıcı
aileyi bir kez onaylasın, örnekleri program bulsun.

Bu dosya aynı zamanda devir notudur: sohbet sıkıştırılsa bile çalışmaya buradan devam edilir.

---

## 0. Bugünkü durum (kısa)

**Çalışan akış**
- Tarayıcı ekranı: `http://127.0.0.1:8766/` (`python -m analyzer_v3.server --port 8766`, proje kökünden).
- PDF seç → sayfa hazırla → ilişkiler → **Cihaz işaretle** (tıkla/kutu sürükle, tutamaçlarla kırp,
  Enter kaydet, Esc kapat, orta tuş/boşluk kaydırma, tekerlek zoom) → **Benzerlerini ara**
  (bu sayfa / tüm sayfalar) → **JSON çıkar** (`output/exchange/sayfa_<no>.json`).
- EPLAN: `eplan_addin/scripts/UvpKatalog.cs` (sembol kataloğu → `output/p8test/probe/capabilities.json`),
  `eplan_addin/scripts/UvpSayfaAktar.cs` (JSON seç → açık projeye veya yeni test projesine aktar).
- Derleme: `eplan_addin/build/build.bat` (her derleme zaman damgalı DLL; EPLAN kapatmaya gerek yok).
- Testler: `python -m pytest analyzer_v3/tests -q` → **142 geçiyor**.

**Kanıtlanmış bulgular**
- `DynamicConnectionLine` şema bağlantısı ÜRETMİYOR (23 çizgi, 4 bağlantı). Kaldırıldı.
- Çok fonksiyonlu parçanın makrosu tek kontağın yerine konamaz (röle 3RQ4018 kontağı bozdu).
  Artık makro uçları kaynakla karşılaştırılıp tutmazsa geri alınıyor.
- Ürün kodları belgenin Stückliste sayfalarından okunuyor: 88 cihazın 83'ünde tip numarası var.
- Adlı hat (PE/P24/N24) sayfada bir cihaza girmiyorsa hat aktarılmıyor, klemens konuyor.

**Açık doğrulamalar** (bkz. `TODO_AKTARIM.md`): T1 (grafik çizgiyle bağlantı), T2 (hat adı),
T4-EPLAN (makro ile gelen sigorta). Üçü de kullanıcı koşusu bekliyor.

---

## 1. Fikir ve neden mantıklı

EPLAN sembolü ile PDF'teki şekil aynı çizim dünyasından gelir: ikisi de vektör. Kataloğu resim
olarak değil **PDF olarak** dışa aktarırsak, sembolleri müşteri belgesiyle birebir aynı biçimde
(segment + eğri) okuruz ve elimizdeki şekil eşleştiricisi (`analyzer_v3/similarity.py`) doğrudan
çalışır. Böylece:

- Her aile için el ile sembol seçmek yerine, program "bu şekil şu sembollere benziyor" der.
- Dönme/aynalama sorunu kataloğun kendi varyantlarıyla çözülür (EPLAN sembolünün 8 varyantı
  zaten dönmüş hâlleridir); hepsini basarız.
- Eşleşme puanlıdır; kullanıcı aileyi **bir kez** onaylar, karar kayda geçer.

Sınırlar (baştan yazılı olsun):
- Müşteri çizimi başka kütüphaneden geldiyse şekil birebir tutmayabilir → puan düşer, karar
  kullanıcıya kalır. Program "bulamadım" demeyi bilecek.
- Çok fonksiyonlu cihaz (röle, PLC) sembolle değil parça/makro yoluyla kurulur; eşleşme yalnız
  "bu şekil kontak/bobin" ayrımını verir.
- Katalog PDF'i EPLAN'da üretilir: lisans gerekir, tek seferlik iştir, sonucu dosyaya yazılır.

---

## 2. İş paketleri

### K1 — Katalog örnek sayfası üretimi (EPLAN tarafı)
- Yeni action `UvpPdfToP8Catalog`: geçici test projesinde, seçilen kütüphanelerin (IEC_symbol,
  SPECIAL) sembollerini ızgaraya basar; her sembolün 0..7 varyantını ayrı hücreye koyar.
- Her hücre için kayıt: sayfa, hücre kutusu (mm), kütüphane, sembol adı, varyant, bağlantı
  noktası sayısı/yönleri → `output/catalog/yerlesim.json`.
- Sayfa sayısı sınırı ve sembol filtresi parametre (`/LIB:`, `/MAX:`) — 3000 sembolü tek seferde
  basmaya çalışmayız.
- **Kabul:** action çalışır, proje kapanır, `yerlesim.json` + EPLAN'da PDF çıktısı üretilir.

### K2 — Katalog PDF'ini vektör olarak okuma (Python)
- `analyzer_v3/catalog.py`: katalog PDF'ini sayfa sayfa `prepare.trace_page` ile okur, `yerlesim.json`
  hücre kutularıyla kırpar, her hücrenin segment/eğrilerini normalize eder (sol üst köşeye taşı).
- Çıktı: `output/catalog/sekiller.sqlite3` (veya json): sembol+varyant → şekil imzası
  (`similarity.descriptor` ile aynı biçim).
- **Kabul:** en az 200 sembol okunur; boş/çizimsiz hücre "şekil yok" diye işaretlenir, atılmaz.

### K3 — Eşleştirme motoru
- `catalog.match(page_shape)` → en yüksek puanlı N aday (sembol, varyant, puan, fark nedeni).
- Puan: mevcut `similarity.same_shape` toleransı + uç sayısı + uç yönleri; ölçek farkı varsa
  eşleşme reddedilir (sembol ölçeği sabittir).
- **Kabul:** sayfa 4'teki sigorta kutbu, kontak ve klemens şekilleri için ilk 3 aday içinde doğru
  sembol çıkar (elle doğrulanmış küçük fikstürle test).

### K4 — Arayüz: aile onayı
- İşaretleme kartında "Bu şekil neye benziyor?" listesi: ilk 3 aday, puanıyla.
- Kullanıcı seçer → seçim **aileye** yazılır (`output/exchange/mapping.json`), bir daha sorulmaz.
- "Tüm sayfalarda ara" akışı bu aileyi kullanır.
- **Kabul:** bir kez onaylanan aile, sonraki sayfalarda otomatik gelir; onay kaydı sürümlüdür.

### K5 — Ürün kodu ile birleştirme
- Cihazın Stückliste kodu varsa: parça → makro yolu K3'ün önüne geçer (makro uçları tutuyorsa).
- Tutmuyorsa K3 sembolü kullanılır. Karar makbuzda görünür.
- **Kabul:** sigorta makroyla, röle kontağı sembolle gelir; ikisi de makbuzda gerekçeli.

### K6 — Regresyon
- Katalog okuma ve eşleştirme için testler; mevcut 142 testin hiçbiri bozulmaz.
- Katalog dosyaları `output/` altında kalır, repoya girmez.

### K7 — Ölçüm
- Sayfa 4 ve 6 için: kaç cihaz otomatik eşleşti, kaçı elle onay istedi, kaçı bulunamadı.
- Sonuç `TODO_AKTARIM.md` tablosuna yazılır.

---

## 3. Sıra

1. Önce açık doğrulamalar (T1/T2/T4) — kullanıcı koşusuyla kapanır.
2. K1 → K2 → K3 (motor), sonra K4 (arayüz), K5 (parça birleştirme), K6/K7.

Kural aynı: uydurma yok, sessiz atlama yok, her adımda ölçüm; "tamam" yalnız kanıtla yazılır.

---

## 4. Yapıldı / bekliyor (2026-09-12)

### Yol değişti: PDF'e basmak yerine kütüphaneyi doğrudan oku

`SymbolVariant.SubPlacements` sembolün kendi çizgi/yay/dikdörtgen/polyline nesnelerini veriyor.
Katalog sayfası basıp PDF'ten geri okumaya gerek yok. Kullanıcının gösterdiği
`C:\Users\Public\Eplan\Data\Semboller` klasörü zaten bu verinin kendisi, ama `.sdb` içindeki
`.eod/.eox` dosyaları EPLAN'ın kapalı ikili biçimi — okumanın desteklenen yolu API.

| İş | Durum | Ölçüm |
|---|---|---|
| Kütüphane okuma (`UvpPdfToP8Symbols`) | **çalışıyor** | 28 kütüphane, **113.595 varyant**, 113.335'inde geometri; 6805 varyant okunamadı; çevrilmeyen tür: Text 38348, PathText 698, Block 235, Shielding 8 |
| Şekil veritabanı (`catalog.build_from_library`) | **çalışıyor** | 113.334 sembol → **47.045 ayrı şekil**, 261 çizimsiz, 22 sn |
| PDF tarafı çevirici (`catalog.rows_from_pdf`) | **çalışıyor** | müşteri PDF'inde sembol tek YOL nesnesi; eksene paralel yol çizgilere ayrılıyor, eğri yol kutusuyla temsil ediliyor |
| Eşleştirme (`catalog.match`) | çalışıyor ama **ayırt edici değil** | bkz. aşağıdaki ölçüm |
| Katalog PDF yolu (K1/K2) | **terk edildi** | 45 sayfa basıldı, 2237 sembol hücreye sığmadı, semboller iç içe girdi |
| Testler | 9 yeni | takım **165 geçiyor** |

### Eşleştirmenin ölçülen sınırı (sayfa 4, gerçek veri)

Müşteri belgesi **1:1** çizilmiş (klemens aralığı tam 20.00 mm ölçüldü). Ama semboller bizdeki
28 kütüphanenin hiçbiriyle aynı ölçüde değil:

| Cihaz | Belgede | EPLAN'daki karşılığı | Sonuç |
|---|---|---|---|
| 3F22 sigorta kutbu | dikdörtgen 1.6×5.0 mm + orta çizgi | `IEC_symbol/F1` 3.0×8.0 mm | doğru sembol aday listesine hiç girmiyor; en iyi aday `HYD2ESS/Z14.1.5` (0.89) |
| X1 klemens | daire Ø2.0 mm | `IEC_symbol/X` Ø1.5 mm + kuyruk | 1.00 puanla eşleşen 44 sembol var (HVAC, SPECIAL/PLCCPING…) |

Ölçek taraması da işe yaramıyor: 1.0–4.0 arası her ölçekte 0.89–1.00 puanlı bir eşleşme
bulunuyor — çünkü "daire" ya da "dikdörtgen + çizgi" 47 bin şekil içinde onlarca kez geçiyor.

**Karar:** program tek başına "bu sigortadır" diyemez; şekil bunu taşımıyor. Elde kalan gerçek
kazanç şu: kütüphane + uç sayısı süzgeciyle aday listesi birkaç maddeye iner ve kullanıcı
AİLE BAŞINA BİR KEZ onaylar. Onaydan sonra aynı şekli tüm sayfalarda bulmak zaten çalışıyor
(`similarity.py`). Yani hedef "her örneği elle etiketlememek"ti, o duruyor; "programın sembolü
kendi bilmesi" ölçümle çürüdü.
