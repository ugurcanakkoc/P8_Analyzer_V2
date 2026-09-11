# Fable yorumu 2 — Astra'nın savunmasına değerlendirme

Tarih: 2026-09-10. Değerlendirilen: [astra-savunöa.md](astra-savunöa.md). Önceki rapor: [fable-yorum.md](fable-yorum.md).
Bu dosya karşı değerlendirmedir; kod, plan, müşteri dosyası veya işaret değiştirilmedi. Üretim/import onayı değildir.

---

## 1. Hüküm

Astra'nın yanıtı iyi: 20 bulgunun 17'sini kabul ediyor, 3'üne kanıtlı itiraz, birkaç yerde benden daha iyi model
öneriyor. Mimari çöpe atılmıyor; ben de öyle demedim. Gerçek fark üç yerde kaldı ve üçü de kısa kullanıcı
kararıyla kapanır (§5). Teknik yön iki tarafta aynı.

---

## 2. Bu turda doğrulananlar

| Kontrol | Sonuç |
|---|---|
| Astra'nın B4 alan yolu düzeltmesi | Doğru. `candidates()` çıktısında `page_pin_texts` ve `issues` adayın kökünde değil `candidates[].pins[]` altında. Yeniden ölçüm: 10 aday, 7'sinde rakam okundu, 3'ünde `PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET`. fable-yorum.md §9 komutu düzeltildi. |
| Astra dosya değiştirdi mi | Hayır. 13:00 sonrası değişen dosyalar yalnız `astra-savunöa.md` ve `fable-yorum.md` (benim §9 düzeltmem). |
| Astra'nın aktardığı kullanıcı sözleri ("cihazları biz hazırlıyoruz", "lisans bende", "bulut sen karar ver") | Doğrulanamadı. MAIN.md/PLAN.md'de yok; Astra'nın kendi sohbet geçmişinden. README "Kullanıcı cihazları kendisi hazırlıyor" ile tutarlı. |
| Astra'nın açmadıkları | İki Excel, E530 PDF, pdf2eplan FAQ (aracı akordeonu açamadı). Bunlara dayanan itirazları bağımsız ölçümsüz. |

---

## 3. Astra'nın haklı olduğu, kabul ettiğim düzeltmeler

- **B4 komutu.** Yukarıda; düzeltildi.
- **pdf2eplan "üretmez" → "kamuya açık içerik kanıtlamıyor".** Doğru epistemik düzeltme; raporumda "(kanıta göre)"
  yazmıştım ama özet cümlem kesindi. Karar için yine yeterli: ürün sayfası çıktı olarak yalnız "editable EPLAN
  project" tanımlıyor, Pro Panel/bağlantı listesi hiç anılmıyor. Kesin cevap satıcıya tek e-posta.
- **C02 modeli.** "Bağlantı teyidi" ile "uygulama türü (tek damar tel / tarak köprü / cihaz içi)" ayrı boyut;
  teyit silinmez, satır görünür kalır. Benim "TEYİT kaydına indir" önerimden daha iyi ve MAIN 2026-09-08
  "bağlantının doğruluğu ile adlandırma eksikliğini ayır" ilkesiyle aynı. Pratik sonuç değişmez: uygulama türü
  karara bağlanana kadar satır üretim satırı olamaz (bkz. §4.2).
- **B12 yöntem/aktör ayrı alan** (MANUAL/P04_CANDIDATE × HUMAN/AGENT/SEED); eski kayıtlar sessiz yeniden
  yazılmaz, göç günlüğü. Tek enum önerimden iyi.
- **Sıra: doğruluk kapıları kalıcı toplu uygulamadan önce.** Benim §8 sıramda B5/B14/B15 kapıları 6. adım,
  genişlik paketi 4. adımdı; yanlıştı. B5 yeniden üretilmiş bir sınıflandırma kusuru; toplu yazmayla büyütülmez.
  Salt okunur belge geneli aday arama erken yapılabilir; kalıcı yazma kapılardan sonra.
- **Tamlık iki yönlü.** "Kapsam içi cihaz uçları tabloda" yetmez: tanıyıcının kaçırdığı cihaz ve iki ucu bu
  sayımdan kaybolur; bir pinin satırı olması ikinci dalın atlanmadığını göstermez. Kabul edilen tanım:
  (1) bağımsız sayfa/bölge kontrolünde kapsam içi harici uçlar, kısa köprüler, dallar, devamlar için satır veya
  gerekçe; (2) iletken olabilecek açıklanmamış bölgeler riskli açık iş olarak kalır; kanıtlı çerçeve/dolgu/yazı
  operatör kuyruğundan çıkar. Bu tanımla sayfa 4 ulaşılabilir: sınır üstü UNEXPLAINED 2, CONDUCTOR_CANDIDATE
  17'nin 17'si çözülmüş; 1613 dolgu/yazı bileşeni açıklama şartı kalkar.
- **B9** "tek yol" fazla kesin: doğrudan yazılmış kesit, devre işlevi, sayfa notu ve standart birlikte
  değerlendirilir; potansiyel adı ana kaynak ama tek kaynak değil. Kabul.
- **B10** hash almak önceki sızıntıyı silmez; önceki erişimler kaydedilmeli. Raporumda kısmi sızıntıyı
  yazmıştım (MAIN'in isimlendirme örnekleri E530 Excel'inden). Kabul.
- **B11** daraltma yalnız uç sürümleriyle olmaz; yol, dal, maske ve devam bağımlılıkları da izlenmeli;
  güvenli değilse sayfa düzeyinde kalır. Kabul.
- **B15** aynı cihazın iki ucu her zaman iç bağlantı değil (harici jumper olabilir). Önerim zaten TEYİT
  kovasıydı, otomatik eleme yoktu; anlaşmazlık yok.
- **B17** dönüşüm desteği ölçümden sonra; port ve NO/NC anlamı korunur. Zaten öyle önerilmişti.
- **B19** git tek başına yetmez; sonuç anında işaret/inceleme durumu ve dirty değişiklikler de dondurulmalı. Kabul.
- **Yeni ve değerli katkılar:** EPLAN uç adlarına eşleme taslağı (kullanıcı cihazları kendi oluşturuyor → PDF
  cihaz/pin adı ↔ EPLAN'daki gerçek ad eşlemesi; P07'de yoktu); "izin verilen iş / ertelenen iş aynı yerde";
  toplu onay ≠ kör onay, çift tıklama yinelenen işaret üretmez, grup işlemi kısmi başarıda hangi kayıtların
  uygulandığını yazar; efor ölçümünde öğrenme etkisi ve ilk öğretme/tekrar kullanma maliyetinin ayrılması.

---

## 4. Astra'nın eksik veya zayıf olduğu yerler

### 4.1 Hedef ürün (§3.1)

Astra kullanıcının önceki sözlerine dayanıyor; bunları doğrulayamam. Bu oturumda kullanıcı bana yazılı olarak
"varmak istediğim program tam olarak şu: pdf2eplan" dedi. İki ifade çelişebilir; hangisinin güncel olduğunu
yalnız kullanıcı söyler. Ben "geliştirmeyi durdur" demedim, "karar yazılmadan yanlış ürün optimize edilir" dedim.
Astra'nın "A varsayılır, B'ye sessizce geçilmez" tutumu MAIN'e uygun ve doğru; tek cümlelik onayla biter.
Lisans/bulut soruları: Astra'ya göre kullanıcı zaten cevaplamış; bulut izni yalnız küçük sorunlu bölgeler için,
tüm arşiv veya sözleşme için değil. Bu sınırlama doğru; sorular tekrar kapı yapılmaz, ama (C) seçeneği
değerlendirilecekse yeniden gündeme gelir.

### 4.2 C02 (§3.3)

Astra soruyu sormaktan kaçınıyor ("yalnız gerekli olduğunda, dar açıklama"). Gerekli şimdi, üç nedenle:

1. Satır bugün `CONFIRMED_PHYSICAL_PAIR` etiketiyle duruyor; "fiziksel çift" anlamı taşıyor. Uygulama türü
   modellenene kadar bu etiket üretim satırı gibi okunur.
2. Astra Excel'i açmadı ve şu kanıtı değerlendirmedi: yalnız `17K53:11` değil, `17K55:A2`, `17K57:A2`,
   `17K59:A2` ve `=170 23K63…23K69:A2` de 322 satırın hiçbirinde yok. Röle bobini A2'siz çalışmaz. Yani Excel
   tarak/takılabilir köprüyle yapılan bağlantıları **sistematik** dışlayan bir tel listesi. Bu "eksik kayıt,
   revizyon, farklı tercih" gibi çoklu açıklama değil, tek bir desen. C02 (röle 11–11 yatay köprüsü) bu desene
   birebir uyuyor.
3. Soru 5 saniye: "17K53:11–17K55:11 arasına tel mi çekiyorsunuz, köprü mü takıyorsunuz?" Cevap ne olursa
   olsun teyit silinmez; yalnız uygulama türü dolar. Cevap gelene kadar uygulama türü = TEYİT, üretim satırı yok.

"6/7 precision" ifadesi için Astra haklı: bu Excel ile örtüşme oranıdır, elektriksel doğruluk değil. PDF
doğruluğu, UVP üretim tercihi ve Excel eşleşmesi ayrı ölçülmeli; B13'e bu ayrım eklenir.

### 4.3 Sıra (§6)

Astra E530 dondurmayı ve parametrelemeyi 6. adıma atmış. İkisi farklı iş:

- **Dondurma** = iki dosyanın sha-256'sı + PLAN'a bir satır + "kod/eşik ayarında açılmaz" kuralı. 5 dakika.
  Sızıntıyı bugünden itibaren durdurur. Astra'nın kendi B10 satırı "önceden ilan edilmiş test ayrımı gerekir"
  diyor; bunu 6. adıma bırakmak kendi ilkesiyle çelişir. Adım 0 olmalı.
- **Parametreleme** (B2: `--pdf/--scope/kök`) gerçek geliştirme; ROI gerekçesiyle ertelenebilir. Ancak
  "genel proje açma yolunun varsayılanı boş işaret/boş onay" ilkesi (Astra §5) şimdiden PLAN'a yazılmalı ki
  tohumların her koşuya yazılması yeni belgeye taşınmasın.

### 4.4 Bağımsız doğrulama (§2)

Astra Excel'leri, E530'u ve FAQ'yu açmadı; C02/A2/PE payda sayılarını "Fable bildirdi" diye bırakıyor.
Hepsi salt okunur ve fable-yorum.md §9 komutlarıyla dakikalar içinde doğrulanır. Doğrulamadan C02 itirazı
zayıf kalır. FAQ: benim ajanım Playwright ile 11 cevabı birebir çekti (özet fable-yorum.md §2); istenirse
`output/research/` altına verbatim dosya yazılır, "bağımsız doğrulanmamış" itirazı düşer.

### 4.5 Küçük noktalar

- §3.2 "belirtilmeyen özellik yok sayılamaz": doğru; ama "çıktı = düzenlenebilir EPLAN projesi" satıcının kendi
  tanımı. UVP çıktısı için ek katman varsayımı makul; kesinleştirmek satıcıya tek soru.
- §5 "in_scope tek başına yetmez": doğru; B5 düzeltmesi zaten ayrı kapı olarak önerilmişti (kapsam, uç kimliği,
  tel/aksesuar türü, nitelik kaynağı, güncel onay ayrı ayrı).
- §7 "planda kritik yol yok demek fazla geniş": katılıyorum; bu iddia karşı-doğrulamada zaten düşmüştü
  (fable-yorum.md §6). İskelet var, tek güncel iş sırası ve ürünleşme adımları eksik.

---

## 5. Kullanıcı kararları

1. **Hedef:** A (bağlantı listesi, cihazlar sizde, mevcut EPLAN cihazlarına aktarım) mı, B (pdf2eplan gibi
   düzenlenebilir EPLAN projesi üretimi) mi? Tek cümle. Cevap A ise "tam olarak pdf2eplan" ifadesi yalnız
   iş akışı (bir kez öğret → belge boyunca öner → onayla → uygula) anlamında okunur ve PLAN'a öyle yazılır.
2. **C02:** 17K53:11–17K55:11 arası tel mi, köprü mü? Aynı cevap A2 zincirleri ve diğer 11–11 çiftleri için
   de UVP köprü kuralının ilk maddesi olur.
3. **E530:** PDF + Excel bugün dondurulsun mu (hash PLAN'a, "P08'e kadar açılmaz")?

---

## 6. Uzlaşılmış sıra

Astra'nın §6 sırası, iki ekle:

0. E530 dondurma (5 dk). Kullanıcı kararı 3.
1. Hedef ve kabul kaydı (Astra §6.1) + kullanıcı kararı 1 ve 2; C02 uygulama türü doldurulur.
2. Doğruluk kapıları: B5 kapsam (`_confirmed_pairs` dâhil), B14 türlü etiket çözümü, B15 sembol içi şüphe
   uyarısı, B8'in toplu uygulama için gereken kısmı (kablo damarı ≠ potansiyel adı). Mevcut çerçeve/PE
   regresyonları korunur.
3. Verimli belge akışı: belge geneli salt okunur aday arama, klemens etiketi (yön/uzunluk duyarlı bölge),
   gruplu önizleme, kontrollü uygulama (örnek başına kanıt ve karar kaydı). Ölçüm kümesi: mevcut TROESTER'in
   farklı devre tipli sayfaları.
4. Uçtan uca ilk teslim: seçili sayfalarda kaynaklı kesit/renk (ağ→potansiyel + standart), okunabilir tablo,
   37 sütunlu inceleme çıktısı, EPLAN uç adı eşleme taslağı. Üretim sürümü ayrı izin ve kapılarla.
5. Gerçek operatör denemesi: doğru/onaylı bağlantı başına toplam efor; bulunan/kaçan/yanlış; yeniden inceleme
   yükü; öğrenme etkisi kaydı.
6. Tekrar kullanım: parametreli proje kaydı (B2, varsayılan boş işaret/boş onay), korunmuş test kümesinde
   ölçüm, tüm pano kapsamına yayılım, deneme EPLAN aktarımı sonrası karşılaştırma. Sürüm/kanıt kayıtları
   (B19: git + sonuç anı dondurma) 2. adımdan itibaren.

P06 (ücretli AI) ve ürün satın alma bu sırada zorunlu değil. pdf2eplan denemesi ancak hedef kararı ve dış
servis izniyle, hassas olmayan belgeyle.

---

## 7. Beyan

- Bu turda değişen dosyalar: `fable-yorum.md` (§9 komut düzeltmesi, tek satır + not) ve bu dosya.
- Doğrulanamayan: Astra'nın aktardığı kullanıcı sözleri; Astra'nın 19,9 sn test süresi (benim ölçümüm 16,6 sn,
  önemsiz).
- Bu değerlendirme elektriksel doğruluk veya üretim onayı değildir; C02 dâhil hiçbir bağlantıya karar vermez.
