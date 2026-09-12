# Arşiv — katalog sembol eşleştirme (2026-09-12)

Fikir: EPLAN sembol kataloğunu okuyup müşteri PDF'indeki şekillerle eşleştirmek; kullanıcı
her cihazı tek tek etiketlemesin, aileyi bir kez onaylasın.

**Sonuç: bırakıldı.** Çalıştı ama ayırt etmiyor. Karar kullanıcının; burada yalnız ölçüm var.

## Ne yapıldı

- `UvpPdfToP8Catalog.cs` — sembolleri ızgara sayfalarına basıp PDF'e verir. 45 sayfa, 7774 sembol
  kondu; **2237 sembol hücreye sığmadı**, semboller iç içe girdi. Terk edildi.
- `UvpPdfToP8Symbols.cs` — sembol geometrisini `SymbolVariant.SubPlacements` ile kütüphaneden
  DOĞRUDAN okur. 28 kütüphane, **113.595 varyant**, 113.335'inde geometri.
- `catalog.py` — geometriyi mm'ye çevirir, aynı şekilleri gruplar, PDF tarafındaki yol
  nesnelerini aynı dile getirir, puanlı eşleştirme yapar. 113.334 sembol → **47.045 ayrı şekil**.

## Neden bırakıldı (ölçüm, sayfa 4)

Sayfa 1:1 (çerçeve tam 395.00 × 245.00 mm ölçüldü). Yine de:

| Cihaz | Belgede | EPLAN'da | Sonuç |
|---|---|---|---|
| Sigorta kutbu | dikdörtgen 1.6 × 5.0 mm + orta çizgi | `IEC_symbol/F1` 3.0 × 8.0 mm | her ölçekte en iyi puan 0.20 |
| Klemens | daire Ø2.0 mm | `IEC_symbol/X` Ø1.5 mm + kuyruk | 1.00 puanla eşleşen 44 farklı sembol |
| Kontak | tek eğik çizgi 1.5 × 5.0 mm | `IEC_symbol/S` 2.5 × 8.0 mm | eşleşme yok |

İki yapısal fark:
1. **Uç kuyrukları.** EPLAN sembolü bağlantı noktasına uzanan kısa çizgileri içerir; şemada o
   kuyruklar telin içinde kaybolur. Aynı cihaz iki tarafta farklı şekil görünür.
2. **Oran.** Belgedeki sigortanın dikdörtgeni 1.6/5.0 = 0.32 oranında; IEC F1'inki 3.0/6.0 = 0.50.
   Ölçek düzeltmesi bunu kapatmaz — belge bu 28 kütüphaneyle çizilmemiş.

Ölçek taraması da kurtarmadı: 1.0–4.0 arası **her** ölçekte 0.89–1.00 puanlı bir eşleşme çıkıyor,
çünkü "daire" veya "dikdörtgen + çizgi" 47 bin şekil içinde onlarca kez geçiyor.

## Saklamaya değer bulgular

- `SymbolVariant.GetBoundingBox()` yerleştirilmemiş sembolde NULL erişimi hatası veriyor
  (10850/10850). Kutu ancak yerleştirdikten sonra okunuyor.
- `SymbolVariant.SubPlacements` sembolün çizgi/yay/dikdörtgen/polyline nesnelerini verir.
- `SymbolLibrary.Initialize(ad)` projeye kayıtlı olmayan kütüphaneyi de açar.
- `C:\Users\Public\Eplan\Data\Semboller\...\*.sdb` EPLAN'ın kapalı ikili deposudur
  (`.eod/.eox`); okumanın desteklenen yolu API'dir.
- Müşteri PDF'inde bir sembol tek bir YOL nesnesidir (sigorta 7 nokta, klemens 12 nokta),
  ayrı çizgiler değil.
- PDF noktası → mm: 25.4/72, belge 1:1 çizilmiş.
