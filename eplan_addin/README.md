# Uvp.PdfToP8 — EPLAN P8 host adaptörü (PLAN S03 / EPLAN_ADDIN_PLAN E00–E04)

Kaynak model Python'dadır (`analyzer_v3.page_model`, `analyzer_v3.eplan_export`). Bu klasör yalnız
EPLAN'a dokunan ince host katmanıdır. Paket bizim sözleşmemizdir (`uvp.pdf2p8.import-request` 1.0);
EPLAN'ın import biçimi değildir. Sembol seçimi ayrı eşleme dosyasındadır.

| Dosya | Görev |
|---|---|
| `src/Uvp.PdfToP8.Host/UvpPdfToP8Host.cs` | Add-in kaydı + `UvpPdfToP8Probe`: ortam raporu, şablondan YENİ test projesi, IEC_symbol/SPECIAL kataloğu → `capabilities.json` |
| `src/Uvp.PdfToP8.Host/UvpPdfToP8Import.cs` | `UvpPdfToP8Import`: YENİ test projesinde sayfa, sigorta/klemens fonksiyonu, T düğümü, kesinti noktası, potansiyel tanımı; `Generate.Connections`; geri okuma → `receipt.json` + `readback.json` |
| `build/build.bat` | Yerel P8 2026 `Bin`'e karşı derleme. EPLAN DLL'leri repoya/dağıtıma girmez |
| `src/Uvp.PdfToP8.Host/UvpPdfToP8Panel.cs` | `UvpPdfToP8Panel`: aracı EPLAN'IN İÇİNDE açar. WebView2 penceresi yerel motora (127.0.0.1) bağlanır; motoru yoksa başlatır, pencere kapanınca yalnız kendi başlattığını kapatır. Sayfadan gelen mesaj SINIRLI: `ping` ve `import` |
| `build/run_action.ps1` | EPLAN'ı gizli başlat → add-in kaydet → action → kaydı geri al. Açık bir EPLAN varsa başlamaz; yalnız kendi başlattığı süreci kapatır |

Her iki action da yalnız kendi oluşturduğu yeni test projesine yazar; açık/canlı projeyi açmaz,
değiştirmez, silmez.

## E00 bulguları (2026-09-11)

- P8 Platform `2026.0.3.25702`, `C:\Program Files\EPLAN\Platform\2026.0.3\Bin`. API DLL'leri
  **.NET Framework 4.8.1** hedefler (DLL metadata'sından). Makinede .NET Framework 4.8.1 runtime var;
  .NET SDK/targeting pack yok, gerek de yok: Windows `csc` (C# 5) ile derleniyor.
- `build.bat` gerçek 2026.0.3 DLL'lerine karşı **0 hata** ile derliyor (tek uyarı:
  `ConnectionsFilter.Page` eski API).
- Kurulu varyant **`Pro Panel`** (kullanıcı kısayolu `Eplan.exe /Variant:"Pro Panel"`).
  `/Variant:"Electric P8"` bu makinede `...\Electric P8\2026.0.3\CFG\install.xml` bulamayıp durur.
- Şablon: `C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9`.
- Doğrulanan imzalar (DLL metadata): `ProjectManager.CreateProject(string,string) → Project`,
  `Function.Create(Page,SymbolVariant)`, `SymbolReference.Create(SymbolVariant,Page)` (sembol türüne göre
  `InterruptionPoint` / `PotentialDefinition` üretir), `SymbolVariant.ConnectionPoints : PinBase[]`
  (`PinBase.Location`), `PotentialDefinition.PotentialName`, `Generate.Connections(Page[],bool)`,
  `Pin.TargetPins / ParentFunction`, `Connection.StartPin / EndPin / StartSymbolConnPoint`.

## Engel: EPLAN lisansı bu makinede açılmıyor

Gizli başlatma denemesi (Pro Panel varyantı) EPLAN lisans penceresinde durdu:

> Hata [70.34]: `C:\Users\Public\EPLAN\Common\lservrc` lisansı geçerli değil. İade edildi veya bu
> bilgisayar için etkinleştirilmedi.

EPLAN lisans almadan açılmadığı için action zinciri hiç çalışmadı: add-in kaydı yapılmadı, test
projesi oluşmadı, EPLAN ayarlarında iz yok (HKCU tarandı). Başlatılan iki EPLAN süreci (yalnız
bizimkiler) kapatıldı. Lisans yönetimine dokunulmadı — etkinleştirme/iade kullanıcının kararıdır.

**Bu yüzden P8 aktarımı kanıtlanmadı; S03 açık.**

## Kullanıcı akışı (hedeflenen çalışma biçimi)

Araç tarayıcı uygulaması değildir; EPLAN içinde açılır:

1. EPLAN > add-in yüklü > `UvpPdfToP8Panel` action → EPLAN penceresi açılır (WebView2).
2. Pencere yerel motoru başlatır (`python -m analyzer_v3.server --port 8791`, yalnız 127.0.0.1).
   Ekran: sayfa gezgini, hazırlama kuyruğu, şema ilişkileri, işaretleme.
3. **Cihaz işaretle**: çizimdeki cihaza tıkla → program kutusunu ve uçlarını çıkarır, cihaz/pin
   adlarını o sayfanın kendi yazısından okur → onayla. Şekil bulunamazsa kutuyu sen sürükle.
   Yanlış işaret “Geri al” ile pasifleşir; kayıt ve geçmiş silinmez.
4. **EPLAN'a aktar**: sayfa paketi üretir (`POST /api/package`) ve WebView2 köprüsünden add-in'e
   gönderir; add-in `UvpPdfToP8Import` ile YENİ test projesine yazar, geri okur.
   Tarayıcıda açıldığında bu düğme kapalıdır: aktarımı yalnız EPLAN içindeki add-in yapar.

Panel derlenir (0 hata) ama EPLAN lisansı açılmadan çalıştırılamadı: aşağıdaki engel geçerli.
WebView2 çalışma zamanı makinede kurulu (153.0.4234.32) ve EPLAN `Bin` klasörü WebView2
bileşenlerini taşıyor.

## Lisans düzeldiğinde kanıt adımları

1. Paketi üret: `python -m analyzer_v3.eplan_export --out output/exchange/proof_s03/package.json`
   (sayfa 4: `L1 → -3F22:1`, `-3F22:2 → -X1:1`, çizilmiş noktalı T, `/4.11` → sayfa 5 `/3.19`).
2. Katalog: `run_action.ps1 -Dll <dll> -Action 'UvpPdfToP8Probe /OUT:"..." /TEMPLATE:"...IEC_bas001.zw9"' -Result <OUT>\capabilities.json`
   — ya da kullanıcının normal EPLAN oturumunda add-in'i yükleyip aynı action'ı çalıştırmak.
3. `capabilities.json` kataloğundan eşleme dosyasını yaz (aileler: `fuse_1pole`, `terminal`,
   `tnode_down`, `interruption`, `potential_definition`; kütüphane/sembol/varyant). Pin indeksi ve
   bağlantı noktası sayısı katalogdan doğrulanır; tahmin edilmez.
4. `UvpPdfToP8Import /PACKAGE:... /MAPPING:... /OUT:... /TEMPLATE:...` → `receipt.json`, `readback.json`.
5. Karşılaştır: `python -m analyzer_v3.eplan_export --out <paket> --readback <OUT>\readback.json`
   → `diff.json`. "P8 aktarımı tamamlandı" yalnız `complete: true` (eksik bağ, fazla bağ, uç kimlik
   sorunu sıfır) ve EPLAN'da ekran kanıtıyla söylenir.
