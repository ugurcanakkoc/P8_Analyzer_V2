# EPLAN aktarımı — açık işler (2026-09-12)

Kullanıcı isteği, aynen: sigorta sembol olarak geliyor, ürün kodundan makro gelsin (uçlar yanlış);
mavi çizgiler anlamsız, kalksın; hat gösterimlerinde hat adları yazsın; PE bir cihaza girmiyorsa
eklenmesin; P24/N24 de cihaza gitmiyorsa yalnız klemens olarak eklensin, cihaza gidiyorsa hat ile
gösterilsin.

Kural: her madde ayrı yapılır, yapılabilen yerde test yazılır/çalıştırılır, sonucu buraya işlenir.
"Tamam" yalnız kanıtla işaretlenir (test çıktısı veya EPLAN geri okuması).

---

## T1 — Anlamsız mavi çizgiler kalksın, bağlantı gerçekten oluşsun

**Kök neden:** semboller bağlantı noktası YÖNÜ gözetilmeden yerleştiriliyordu. `BP` (kesinti
noktası) iki noktalıdır (0 = Right, 1 = Left); rayın sağ ucuna sağa bakan nokta konunca ray solda
kalıyor ve EPLAN otomatik bağlamıyordu. Bu yüzden her bağ için çizgi çiziliyor, çizgiler de
bağlantı üretmiyordu (8 bağdan 2'si gerçek bağlantıydı).

- [x] Yerleştirmede karşı uca BAKAN bağlantı noktası seçiliyor (`FacingIndex`).
- [x] Çizgi artık peşin çizilmiyor: önce `Generate.Connections` çalışıyor, **yalnız otomatik
      bağlanmayan** bağlar için çizgi çiziliyor ve bu makbuza "otomatik bağlanmadı" diye yazılıyor.
- [x] Makbuzda `links_auto` / `links` sayısı ve özet satırı var.

**1. koşu ölçümü (2026-09-12, kullanıcı projesi):** otomatik bağlanan **0 / 23**. Sayfada 23
`DynamicConnectionLine` duruyordu ama gerçek bağlantı yalnız 4'tü (onlar da hizalı pinlerden
kendiliğinden oluşmuştu). **Sonuç: `DynamicConnectionLine` şema bağlantısı ÜRETMİYOR** — bilgi
tabanındaki eski not (kb/atlas-duzeltmeleri) bu yüzden yanlış; ölçümle düzeltildi.

**2. tur değişiklik:** `DynamicConnectionLine` tamamen kaldırıldı. Eksik her bağ için grafik
bağlantı çizgisi (`Graphics.Line`) çizilip `Generate.Connections` çalıştırılıyor; çizgi bağlantı
üretmediyse **çizgi siliniyor** ve makbuza "bağlantı oluşmadı" yazılıyor. Böylece sayfada anlamsız
çizgi kalmaz.

**Durum:** kod tamam, derlendi. **EPLAN koşusu bekliyor** — kanıt: özet satırındaki
"otomatik / çizgiyle / bağlanamayan" sayıları ve sayfada kalan çizgi sayısı.

---

## T2 — Hat adları (potansiyel) EPLAN'da görünsün

- [x] Kesinti noktasına hem `Name` hem `VisibleName` yazılıyor; makbuzda ikisi de raporlanıyor.
- [x] Geri okumada kesinti noktasının görünen adı ve çapraz referansı yazılıyor.

**Durum:** kod tamam, derlendi. **EPLAN koşusu bekliyor** — önceki koşuda ad `=+-L1` çıkmıştı;
bu koşuda `visible_name` ve `cross_reference` alanlarından ne geldiğine bakılacak.

---

## T3 — PE / P24 / N24: cihaza gitmiyorsa hat çizilmesin — **TAMAM**

- [x] `page_package`: adlı hattın üyeleri arasında klemens olmayan cihaz yoksa hat, birleşim ve
      kesinti noktası pakete girmiyor; klemens uçları giriyor.
- [x] Atlama sessiz değil: gerekçe `issues` altında.
- [x] Test: `test_page_package_splits_poles_and_skips_lines_without_a_device`.

**Kanıt (sayfa 4):** kalan hatlar `L1, L2, L3, P24.32` (hepsi bir cihaza giriyor); atlananlar
`N24.30` ve üç `PE` ağı — her biri gerekçesiyle listede. Ayrıca aynı testte: 3 kutuplu sigorta üç
ayrı tek kutuplu nesne, klemens sırasının her ucu ayrı klemens, eşlenmemiş cihaz ailesi yok.

**Yan bulgu (düzeltildi):** `page_model` düğüm kimliği `pin:` önekliydi, `relations` ham kimlik
veriyordu; bu yüzden cihazlar hiçbir hatta bağlı görünmüyordu. Eşleme düzeltildi.

**Yan temizlik:** sayfa 4'te arayüz denemelerimden kalan 8 işaret ve 2 maske kutusu pasife alındı
(kayıt silinmedi). Maske kutusu sigortanın ray bağlantısını kapatıyordu.

---

## T4 — Ürün kodundan makro yerleştirme

**Kaynak tarafı — TAMAM**
- [x] Ürün kodları belgenin kendi malzeme listesi (Stückliste) sayfalarından okunuyor
      (`analyzer_v3/parts.py`): cihaz, üretici, tip numarası, açıklama.
- [x] Firma iç numarası (6 haneli) koda karışmıyor; tabloda alt satıra taşan hücre birleşiyor.
- [x] Pakete `part_number` + `part_candidates` eklendi; kod yoksa alan boş, uydurulmuyor.
- [x] Liste sayfaları hazırlanmadıysa paket bunu `issues` altında söylüyor.
- [x] Testler: `test_parts_list_reads_device_and_type_number_without_guessing`,
      `test_package_says_when_parts_list_pages_are_not_prepared`.

**Kanıt:** belge genelinde 88 cihazın 83'ünde tip numarası okundu. Sayfa 4 paketinde 18 cihazın
6'sında kod var: `-3F22 → 5SE2316`, `-17K52 → 3RH2122-1BB40`, `-17K53/-17K55 → 3RQ4018-1AB00`.
Klemens sıralarında (`-X1`, `-X4`) kod yok — listede de yazmıyor, sembol yolu kullanılacak.

**EPLAN tarafı — kod tamam, koşu bekliyor**
- [x] Tip numarası parça veritabanında aranıyor (`GetPart`, sonra `ARTICLE_TYPENR` filtresi).
- [x] Parçanın şema makrosu (`ARTICLE_MACRO`) varsa makro yerleştiriliyor; ilk uç kaynak noktasına
      oturtuluyor, ürün kodu cihaza atanıyor.
- [x] Makro varken uç adlarının ÜZERİNE YAZILMIYOR: makronun kendi adı ile kaynak adı
      karşılaştırılıp makbuza yazılıyor.
- [x] Kod yoksa / parça yoksa / makro yoksa sembol yolu sürüyor ve makbuzda nedeni yazılı.
- [x] Özette "Cihaz: makro ile N, sembol ile M" satırı var.

**1. koşu ölçümü:** röle kontağı (`-17K53`, parça 3RQ4018-1AB00) makroyla kondu ama makro TÜM
cihazı getirdiği için kontak yanlış çıktı; geri okumada `-17K52` fonksiyonunun ucu hiç yoktu.

**2. tur değişiklik:** makro yerleştirildikten sonra uç adları kaynakla karşılaştırılıyor; küme
tutmuyorsa **makro geri alınıyor** (`Placement.Remove`) ve sembol yolu kullanılıyor, gerekçe
makbuza yazılıyor. Böylece çok fonksiyonlu parçanın makrosu tek kontağın yerine konmuyor.

**Kanıt bekleniyor:** sigorta (5SE2316) makro ile gelmeli, uç adları (1/2) tutmalı; röle kontağı
sembolle gelmeli ve geçen turdaki gibi doğru görünmeli.

---

## Durum

| İş | Durum | Kanıt |
|---|---|---|
| T1 | 1. koşu: 0/23 otomatik; DynamicConnectionLine elendi. 2. tur kod hazır | makbuz `links_auto`, `links_by_line`, `links_failed` |
| T2 | kod tamam, EPLAN koşusu bekliyor | geri okumada `visible_name`, `cross_reference` |
| T3 | **tamam** | test + sayfa 4 paketi (atlanan PE/N24 gerekçeli) |
| T4 kaynak | **tamam** | 83/88 cihazda kod; 2 test |
| T4 EPLAN | 1. koşu: röle makrosu yanlış kontak üretti. 2. tur: uç doğrulaması + geri alma | makbuzda `macro_pins`, `source`, `macro_error` |

Tüm takım: **142 test geçiyor** (2026-09-12).
