# Claude — sonraki uygulama: tüm sayfa gezgini ve şema ilişkileri

Çalışma kökü: `C:\Users\UVW-U\Desktop\astra 6 test`.
Önce AGENTS.md, MAIN.md'nin **tamamı**, PLAN.md'nin güncel S00–S06 sırası ve
`output/research/2026-09-11_PDF2EPLAN_Yon_Degisikligi.md` okunacak.

## Değişen hedef

Artık PDF sayfasını **düzenlenebilir EPLAN P8 şemasına** dönüştürüyoruz. Eski “yalnız fiziksel
tel çiftleri” odağı ana akış değil. Köprü tel mi tarak mı kararını kullanıcı çizimi aldıktan
sonra verir. PE bara/toprak hattı olarak temsil edilir; yapay fiziksel numara üretilmez.
Varsayılan pano içi filtre; gerekirse kullanıcının seçebildiği tam sayfa taslağı. K3 standart
önceliği yeniden sorulmaz. Eski onayları yeni doğruluk gibi kullanma veya tazeleme.

Bu görev **S01 ve S02'nin gerekli en küçük çekirdeğini** uygular. Yeni AI, kapsamlı yeniden
mimari, başka müşteri, E530 ayarı ve çok ajanlı genel inceleme turu açma.

## 1. Önce gerçek eksikliği kapat: pin → hat → devam

Canlı kontrolde görüldü: fiziksel 4 / Blatt 3'te `3F22:1`, fiziksel 5 / Blatt 4'te `4F22:1`
üstteki L1 hattına kadar izleniyor. Trace `line:1916`, `line:1878`, `line:1915` veriyor,
fakat hedef pin yok diye tablo `SINGLE_END`. Devam çıktısı aynı hattı L1 diye adlandırıyor.
Bu sayfa/cihaz/segment adları **regresyon örneği**, üretim koduna hardcode edilecek kural değil.

- Geometri + aynı uçtaki potansiyel yazısı + devam kaydını birleştir.
- Genel bir şema ilişkisi üret: pin→potansiyel/bara, pin→sayfa devamı, pin→pin,
  gerçek birleşim ve gerçek açık uç birbirinden ayrı olsun.
- L1→sigorta:1, L2→:3, L3→:5 ve P24/N24 üst beslemeleri ana sayfa görünümünde açık dursun.
  Hedef potansiyeli sahte cihaz/pin gibi kaydetme. İki fiziksel uç şartını bu görünümden ayır.
- Satıra/pine/hat etiketine tıklayınca **gerçek segmentleri** vurgula; düz yardımcı çizgiyi
  gerçek yol diye gösterme. Devam kaydı varsa hedef sayfaya git; hedef hazırlanmamışsa bunu
  gösterip hazırlama olanağı ver. “Karşı uç yok” yerine gerçekten bilinen ve eksik olanı yaz.
- Sembol içinden kısa devre üretme; L1/L2/L3, noktasız kesişim, kesikli sınır ve PE ayrımı
  regresyonlarını koru. Aynı adlı kopuk potansiyelleri yalnız metinden birleştirme.

## 2. Kullanıcı artık bütün sayfaları gezebilsin

- Seçici yalnız `Pilot.pages()` içindeki hazırlanmış altı sayfa ile sınırlı kalmasın.
  Belge indeksinin 73 sayfasını göster; fiziksel sıra, Blatt, =/+ yapı ve tür beraber görünsün.
- Varsayılan filtre +E122 ve 112/122/132/152/170 şemaları. Mevcut indeks 58 aday şema gösteriyor;
  eski rapordaki 59'u kopyalama. Diğer sayfalar bağlam olarak erişilebilir ama otomatik şema
  aktarımına seçili gelmesin. Eksik kapsam bilgisini açık göster.
- Seçilen sayfayı önce aç; küçük önizleme/hazırlık durumu göster. “Hazırlanmadı” ile “boş” ve
  “çözüldü” ayrı. Seçili kapsamın geri kalanı devam edilebilir bir hazırlama kuyruğuyla işlensin.
  Durdur/devam, hata ve yeniden deneme var; her tıklamada PDF'nin tümü yeniden okunmasın.
- Aday tanıma sırası ve işaret uygulaması ayrı: belge geneli öneri otomatik insan onayı değildir.
- Sayfa 22'de bulunan istasyon giriş beslemelerini de pin→P24.30/N24.30→devam olarak görünür
  kıl. Modül iç dağıtımını harici tel yapma. Sembolsüz/isimsiz noktaları açık gerekçeyle koru.

## 3. Küçük sayfa modeli ve kullanıcı kontrolü

- Mevcut modülleri yeniden kullan. Sayfa, sembol örneği, pin, potansiyel/hat, devam, birleşim,
  polyline ve belirsizlik için sürümlü, kaynak kimlikli kayıt tanımla.
- Çıkarım sonucu ile kullanıcı düzeltmesi ayrı kalsın; yeniden analiz düzeltmeleri ezmesin.
- Pano filtresi ham veriyi silmesin. Sınırda gerçek klemens/konnektör veya açık devam görünür
  kalsın. “Tam sayfa” seçeneği kullanıcıya önizlemeli olsun; otomatik kapsam genişletme yok.
- Şema taslağı tamamlığı ile imalat uygunluğu ayrı. Köprü seçimi/renk/UVP fiziksel son eki
  eksik diye sayfa gezgini veya geometrik şema ilişkileri kilitlenmesin.
- Bu pakette çalışan P8 yazıcısı varmış izlenimi verme. EPLAN düğmesi varsa mevcut durumu
  açıkça “eşleme/aktarım henüz hazırlanmadı” desin.

## 4. Doğrulama ve teslim

- Kaynak PDF, standartlar, eski Excel ve onay kayıtlarını koru. Geliştirme/regresyonu izole
  veride yap; normal yeni çalışma tohum pin/onay taşımasın. Mevcut pilot yalnız regresyondur.
- Testler: üst faz/potansiyel ilişkileri; gerçek devam + çözülmeyen devam; fiziksel/Blatt ayrımı;
  işaretsiz sayfaya gezinme; hazırlama kuyruğu iptal/devam/hata; yerel pano filtresi; eski
  düzeltmenin korunması; noktasız kesişim ve sembol içi yolun yanlış birleştirilmemesi.
- Tarayıcıda gerçekten yeni bir sayfaya geç, L1→sigorta yoluna tıkla ve devam sayfasına git.
  Ekran görüntüsü/kanıt ver. HTTP 200 tek başına görsel teslim değildir.
- Aynı bilinen beş sayfayı çok ajanla baştan tarama; değişen özellik ve bölgeyi kontrol et.
- Teslim: çalışan adres, gezilebilir/hazırlanmış sayfa sayıları ayrı; L1 örneği önce/sonra;
  otomatik aday ile elle kayıt sayıları ayrı; test sonucu; kalan somut eksikler. PLAN S01/S02
  ancak bu kanıtla işaretlensin. Yeni onay verilmiş gibi yazma.

## Hemen sonraki paket — S03, sona ertelenmeyecek

Mevcut Python sayfa modelini küçük C# EPLAN bağdaştırıcısıyla **ayrı test projesine** yaz.
Önce yüklü P8/SDK ve gerçek hedef sembol kütüphanesini kontrol et; lisans konusunu genel
geliştirmeyi durduran tekrar soruya çevirme. Gerçekten gereken çalışma ortamı eksikse onu
somut belirt. L1→sigorta→klemens, bir T dalı ve bir devam örneği yeterli ilk kanıttır.
Gerçek fonksiyon/pin/net ve düzenlenebilirlik geri okumayla doğrulanmadan “P8 aktarımı
tamamlandı” deme. Yalnız resim, DXF veya uydurma sembol numaralı JSON başarı değildir.
Mevcut EPLAN kullanıcı nesnelerini değiştirme/silme; yeniden aktarma çakışmalarını önizle.

Tüm 58 sayfanın otomatik kusursuz tanınmasını S03'ün ön koşulu yapma.
