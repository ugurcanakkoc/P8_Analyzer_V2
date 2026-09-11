# Claude çalışma sözleşmesi

Herhangi bir analiz, yanıt veya değişiklikten önce bu klasördeki **MAIN.md'nin tamamını**
oku. Ardından PLAN.md ve analyzer_v3/README.md oku. MAIN bağlayıcı elektrik kurallarıdır.
Eski P8_Analyzer_V2/CLAUDE.md bu projenin güncel talimatı değildir.

Kullanıcı P00–P03 uygulamasını ve ardından Claude Opus 5 kod denetimini onayladı.
Claude'a verilen ilk görev **yalnız okuma denetimi**: dosya değiştirme, üretim/import,
kurulum, dış servise başka dosya gönderme, alt ajan başlatma veya kapsam genişletme yok.
MAIN'e aykırı bir kod bulursan dosya/satır ve somut hata senaryosuyla bildir.
Testlerin geçmesi, görsel/vektör uyumu veya iki AI'ın anlaşması üretim onayı değildir.

Özellikle ara: adres/pin son eki kaybı; grafikte noktasız kesişim birleştirme;
yakınlıktan hayali tel zinciri; pin düzeltmesi sonrası eski onayın sürmesi;
bilinmeyen kayıtların silinmesi; tüm geometrinin otomatik tel sayılması;
yalnız seçili örneğin çalışmasını genel doğruluk diye gösterme; güvensiz yerel servis.

Manuel pin işaretleri ve geçmiş kullanıcı teyitleri otomatik çıkarım olarak sunulamaz.
4. sayfa bir regresyon/development örneğidir; bağımsız dondurulmuş ground truth değildir.

Denetim yanıtı Türkçe olsun. Her bulgu için önem, dosya/satır, yeniden üretim,
etki ve en küçük düzeltme önerisi ver. Bulgular dışında "kontrol ettim, sorun yok"
gibi genel güvence verme; incelenmeyen alanları açıkça yaz.
