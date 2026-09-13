// =====================================================================================
// UvpPdfToP8Import — PLAN S03 / E04 erken gerçek P8 kanıtı.
//
//   UvpPdfToP8Import /PACKAGE:"<import-request.json>" /MAPPING:"<mapping.json>"
//                    /OUT:"<klasör>" /TEMPLATE:"<.zw9>"
//
// Her çalıştırma şablondan YENİ bir test projesi oluşturur ve yalnız ona yazar. Paket bizim
// sözleşmemizdir (uvp.pdf2p8.import-request 1.0); sembol seçimi ayrı eşleme dosyasındadır.
// Paketteki keyfi komut yürütülmez: yalnız DEVICE / JUNCTION / INTERRUPTION / POTENTIAL_BOUNDARY
// nesne türleri tanınır, diğerleri reddedilip makbuza yazılır.
//
// Sonuç: receipt.json (ne oluşturuldu / ne reddedildi) + readback.json (EPLAN'dan GERİ OKUNAN
// fonksiyon, pin konumu, bağlantı uçları, kesinti noktası). "Aktarım tamamlandı" kararı
// geri okumanın kaynak topolojiyle karşılaştırılmasından verilir, bu dosyadan değil.
// =====================================================================================
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Base;
using Eplan.EplApi.DataModel;
using Eplan.EplApi.DataModel.EObjects;
using Eplan.EplApi.DataModel.Graphics;
using Eplan.EplApi.DataModel.MasterData;
using Eplan.EplApi.HEServices;
using Eplan.EplApi.MasterData;

namespace Uvp.PdfToP8.Host
{
    public class ImportAction : IEplAction
    {
        public bool OnRegister(ref string Name, ref int Ordinal)
        {
            Name = "UvpPdfToP8Import";
            Ordinal = 20;
            return true;
        }

        public void GetActionProperties(ref ActionProperties actionProperties) { }

        static Dictionary<string, object> D(object o) { return (Dictionary<string, object>)o; }
        static ArrayList A(object o) { return o == null ? new ArrayList() : (ArrayList)o; }
        static string S(Dictionary<string, object> d, string k) { return d.ContainsKey(k) && d[k] != null ? Convert.ToString(d[k]) : ""; }
        static double N(object o) { return Convert.ToDouble(o, System.Globalization.CultureInfo.InvariantCulture); }
        static PointD P(object o) { ArrayList a = A(o); return new PointD(N(a[0]), N(a[1])); }
        static double[] XY(PointD p) { return new double[] { Math.Round(p.X, 3), Math.Round(p.Y, 3) }; }

        static SymbolVariant Variant(Project prj, Dictionary<string, object> m, List<string> log)
        {
            SymbolLibrary lib = new SymbolLibrary(prj, S(m, "library"));
            Symbol sym = new Symbol(lib, S(m, "symbol"));
            int nr = m.ContainsKey("variant") ? Convert.ToInt32(m["variant"]) : 0;
            SymbolVariant sv = sym[nr];
            if (sv == null) throw new InvalidOperationException("Sembol varyantı yok: " + S(m, "library") + "/" + S(m, "symbol") + " #" + nr);
            log.Add("sembol " + S(m, "library") + "/" + S(m, "symbol") + " #" + nr + " bağlantı noktası " + sv.ConnectionPoints.Length);
            return sv;
        }

        /// <summary>Ürün kodunu (tip numarası) parça veritabanında ara. Bulunamazsa null.</summary>
        static MDPart FindPart(MDPartsDatabase db, string typeNumber, List<string> log)
        {
            if (db == null || string.IsNullOrEmpty(typeNumber)) return null;
            try
            {
                MDPart direct = db.GetPart(typeNumber);
                if (direct != null) return direct;
            }
            catch (Exception) { }
            try
            {
                MDPartsDatabaseItemPropertyList filter = new MDPartsDatabaseItemPropertyList();
                filter.ARTICLE_TYPENR = typeNumber;
                MDPart[] hits = db.GetParts(filter);
                if (hits != null && hits.Length == 1) return hits[0];
                if (hits != null && hits.Length > 1) log.Add("Belirsiz parça: " + typeNumber + " (" + hits.Length + " sonuç); ilk sonuç seçilmedi.");
            }
            catch (Exception ex) { log.Add("parça arama (" + typeNumber + "): " + ex.Message); }
            return null;
        }

        /// <summary>Parçanın ŞEMA makrosu. Ölçüm: ARTICLE_MACRO 3D makrosunu veriyor
        /// (13/13 '*_3D.ema'); şema makrosu grup sembol makrosu alanındadır.</summary>
        static string MacroOf(MDPart part)
        {
            if (part == null) return "";
            foreach (Func<string> read in new Func<string>[] {
                delegate { return part.Properties.ARTICLE_GROUPSYMBOLMACRO_IEC.ToString(); },
                delegate { return part.Properties.ARTICLE_GROUPSYMBOLMACRO.ToString(); } })
            {
                try
                {
                    string value = read();
                    if (!string.IsNullOrEmpty(value)) return value;
                }
                catch (Exception) { }
            }
            return "";
        }

        // Makro dosyasini her cihaz icin acmak pahali: parca basina bir kez sorulur.
        static readonly Dictionary<string, bool> MultiLineCache = new Dictionary<string, bool>();

        /// <summary>Makroda şema (MultiLine) gösterimi var mı? (parça başına bir kez sorulur)</summary>
        static bool HasMultiLine(string macro, Project project)
        {
            if (MultiLineCache.ContainsKey(macro)) return MultiLineCache[macro];
            bool result = ProbeMultiLine(macro, project);
            MultiLineCache[macro] = result;
            return result;
        }

        static bool ProbeMultiLine(string macro, Project project)
        {
            try
            {
                Eplan.EplApi.DataModel.MasterData.WindowMacro probe =
                    new Eplan.EplApi.DataModel.MasterData.WindowMacro();
                probe.Open(macro, project);
                foreach (Eplan.EplApi.DataModel.MasterData.WindowMacro.Enums.RepresentationType type
                         in probe.RepresentationTypes)
                    if (type == Eplan.EplApi.DataModel.MasterData.WindowMacro.Enums.RepresentationType.MultiLine)
                        return true;
            }
            catch (Exception) { }
            return false;
        }

        /// <summary>Makroyu yerleştir ve İLK UCU hedef noktaya oturt. Makro kendi uçlarını
        /// getirir; sembolde boş kalan uç adları böyle doğru gelir.</summary>
        /// <summary>İki uç adı aynı ucu mu gösteriyor? Kural `analyzer_v3/pins.py` ile aynı:
        /// birebir → gevşek (ayırıcı ve harf büyüklüğü) → varyant (1L1→1, 13/1→13, 3.13→13,
        /// L1intern→L1). Kesme işareti KORUNUR: `2` ile `2'` ayrı terminaldir.</summary>
        static bool PinNamesMatch(string a, string b)
        {
            if (a == null || b == null) return false;
            a = a.Trim(); b = b.Trim();
            if (a.Length == 0 || b.Length == 0) return false;
            if (a == b) return true;
            if (LoosePin(a) == LoosePin(b)) return true;
            foreach (string left in PinVariants(a))
                foreach (string right in PinVariants(b))
                    if (left == right) return true;
            return false;
        }

        static string LoosePin(string name)
        {
            System.Text.StringBuilder builder = new System.Text.StringBuilder();
            foreach (char ch in name.ToLowerInvariant())
                if (char.IsLetterOrDigit(ch) || ch == '\'') builder.Append(ch);
            return builder.ToString();
        }

        static List<string> PinVariants(string name)
        {
            List<string> out_ = new List<string>();
            out_.Add(name);
            if (name.Length > 6 && name.ToLowerInvariant().EndsWith("intern"))
                out_.Add(name.Substring(0, name.Length - 6));
            int slash = name.IndexOf('/');
            if (slash > 0) out_.Add(name.Substring(0, slash));
            System.Text.RegularExpressions.Match phase =
                System.Text.RegularExpressions.Regex.Match(name, @"^(\d+)[Ll]\d+$");
            if (phase.Success) out_.Add(phase.Groups[1].Value);
            System.Text.RegularExpressions.Match prefix =
                System.Text.RegularExpressions.Regex.Match(name, @"^\d+\.(\d+)$");
            if (prefix.Success) out_.Add(prefix.Groups[1].Value);
            return out_;
        }

        /// <summary>Cihazı PARÇADAN kur ve yalnız kaynak uçlarına karşılık gelen fonksiyonları
        /// yerleştir. Ailede "placement": "DEVICE_FROM_PART" yoksa ya da ürün kodu yoksa false döner
        /// ve eski yol (makro/sembol) sürer.</summary>
        static bool TryPlaceFromPart(Dictionary<string, object> o, Dictionary<string, object> familyEntry,
                                     Project prj, Page pg, SymbolVariant sv, MDPartsDatabase partsDb,
                                     Dictionary<string, Function[]> devices,
                                     Dictionary<string, PointD> nodePoint, Dictionary<string, Page> nodePage,
                                     Dictionary<string, object> row, List<string> log)
        {
            if (S(familyEntry, "placement") != "DEVICE_FROM_PART") return false;
            string partNumber = S(o, "part_number");
            string tag = S(o, "device_tag");
            string id = S(o, "id");
            if (partNumber == "" || tag == "") return false;

            Function[] functions;
            if (!devices.TryGetValue(tag, out functions))
            {
                MDPart part = FindPart(partsDb, partNumber, log);
                if (part == null) { row["part_lookup"] = "bulunamadı: " + partNumber; return false; }
                functions = new DeviceService().CreateDevice(prj, part.PartNr, part.Variant ?? "",
                                                             new FunctionPropertyList());
                if (functions == null || functions.Length == 0)
                    throw new InvalidOperationException("Parçadan cihaz oluşmadı: " + partNumber);
                // Ölçüm: yalnız ana fonksiyonu adlandırmak yetmiyor; bağlantı noktaları eski adda
                // ('-K1') kalıyor. Her fonksiyon ayrı adlandırılır.
                foreach (Function fn in functions)
                {
                    string only = fn.Pins.Length == 1 ? fn.Pins[0].Name : "";
                    try { fn.Name = (fn.IsMainFunction || only == "") ? tag : tag + ":" + only; }
                    catch (Exception ex) { log.Add("ad yazılamadı (" + tag + "): " + ex.Message); }
                }
                devices[tag] = functions;
                log.Add("parçadan cihaz " + tag + " <- " + partNumber + " (" + functions.Length + " fonksiyon)");
            }

            row["source"] = "DEVICE_FROM_PART";
            row["part_number"] = partNumber;
            List<object> pinLog = new List<object>();
            List<string> missing = new List<string>();
            foreach (object pr in A(o["pins"]))
            {
                Dictionary<string, object> pinRow = D(pr);
                string want = S(pinRow, "name");
                PointD target = P(pinRow["point_mm"]);
                Function chosen = null;
                foreach (Function fn in functions)
                    if (!fn.IsPlaced && fn.Pins.Length == 1 && PinNamesMatch(want, fn.Pins[0].Name))
                    {
                        chosen = fn;
                        break;
                    }
                if (chosen == null) { missing.Add(want); continue; }
                chosen.PlaceAt(pg, target, DocumentTypeManager.DocumentType.Circuit, sv);
                Pin pin = chosen.Pins[0];
                PointD absolute = new PointD(chosen.Location.X + pin.Location.X, chosen.Location.Y + pin.Location.Y);
                chosen.Location = new PointD(chosen.Location.X + target.X - absolute.X,
                                             chosen.Location.Y + target.Y - absolute.Y);
                PointD real = new PointD(chosen.Location.X + pin.Location.X, chosen.Location.Y + pin.Location.Y);
                nodePoint[id + "#" + want] = real;
                nodePage[id + "#" + want] = pg;
                pinLog.Add(new Dictionary<string, object> {
                    { "pin", want }, { "eplan_pin", pin.Name }, { "name", chosen.Name },
                    { "real_point", XY(real) },
                    { "shift_mm", Math.Round(Math.Abs(real.X - target.X) + Math.Abs(real.Y - target.Y), 2) } });
            }
            row["pins"] = pinLog;
            if (missing.Count > 0) row["unmatched_pins"] = missing.ToArray();
            return true;
        }

        static void RemoveAll(StorableObject[] placed)
        {
            if (placed == null) return;
            foreach (StorableObject item in placed)
            {
                Placement placement = item as Placement;
                if (placement == null) continue;
                try { placement.Remove(); } catch (Exception) { }
            }
        }

        /// <summary>Makro yerleştir; uçları kaynaktakiyle TUTMUYORSA geri al.
        /// Röle gibi çok fonksiyonlu parçaların makrosu tek bir kontağın yerine konamaz. </summary>
        static Function PlaceMacro(string macro, Page page, PointD target, string firstPin,
                                   List<string> wanted, Dictionary<string, object> row, List<string> log)
        {
            // Şema sayfasına ŞEMA gösterimi konur. Varsayılan gösterim montaj görünümü
            // olabiliyor: ölçümde motor koruma ve sigorta kutusu 'PANP' sembollü, yüzlerce
            // çizgilik montaj çizimi olarak geliyordu.
            bool multiLine = HasMultiLine(macro, page.Project);
            StorableObject[] placed = multiLine
                ? new Insert().WindowMacro(macro,
                      Eplan.EplApi.DataModel.MasterData.WindowMacro.Enums.RepresentationType.MultiLine,
                      0, page, target, Insert.MoveKind.Absolute)
                : new Insert().WindowMacro(macro, 0, page, target, Insert.MoveKind.Absolute);
            row["macro_representation"] = multiLine ? "MultiLine" : "Default";
            if (!multiLine)
            {
                RemoveAll(placed);
                throw new InvalidOperationException("Makroda şema (MultiLine) gösterimi yok; "
                    + "montaj görünümü şema sayfasına konmaz.");
            }
            if (placed == null || placed.Length == 0) throw new InvalidOperationException("Makro hiçbir nesne üretmedi.");

            // Şema makrosu genelde TEK fonksiyon değildir: ölçümde SIE.3RQ4018-1AB00
            // BoxedDevice(DC) + 5 x DCP getiriyor. Bütün fonksiyonların uçları toplanır.
            List<Function> functions = new List<Function>();
            foreach (StorableObject item in placed)
            {
                Function candidate = item as Function;
                if (candidate != null) functions.Add(candidate);
            }
            if (functions.Count == 0)
            {
                RemoveAll(placed);
                throw new InvalidOperationException("Makroda fonksiyon yok (yalnız grafik).");
            }
            List<string> actual = new List<string>();
            List<Pin> actualPins = new List<Pin>();
            foreach (Function each in functions)
                foreach (Pin pin in each.Pins)
                    if (!string.IsNullOrEmpty(pin.Name))
                    {
                        actual.Add(pin.Name);
                        actualPins.Add(pin);
                    }
            row["macro_pins"] = actual.ToArray();
            row["macro_functions"] = functions.Count;

            // Kaynağın her ucu makroda karşılık bulmalı; makroda FAZLA uç olması normaldir.
            List<Pin> matchedPins = new List<Pin>();
            List<string> missing = new List<string>();
            List<bool> used = new List<bool>();
            for (int i = 0; i < actualPins.Count; i++) used.Add(false);
            foreach (string want in wanted)
            {
                int hit = -1;
                for (int i = 0; i < actualPins.Count && hit < 0; i++)
                    if (!used[i] && PinNamesMatch(want, actual[i])) hit = i;
                if (hit < 0) { missing.Add(want); continue; }
                used[hit] = true;
                matchedPins.Add(actualPins[hit]);
            }
            if (missing.Count > 0)
            {
                RemoveAll(placed);
                throw new InvalidOperationException("Makroda karşılığı olmayan uç: ["
                    + string.Join(",", missing.ToArray()) + "] · makro uçları ["
                    + string.Join(",", actual.ToArray()) + "]");
            }
            Function function = functions[0];
            foreach (Function each in functions)
                if (each.Pins.Length > function.Pins.Length) function = each;

            Pin anchor = matchedPins.Count > 0 ? matchedPins[0] : null;
            foreach (Pin pin in actualPins)
                if (PinNamesMatch(firstPin, pin.Name)) { anchor = pin; break; }
            if (anchor != null)
            {
                Function owner = anchor.ParentFunction != null ? anchor.ParentFunction : function;
                PointD absolute = new PointD(owner.Location.X + anchor.Location.X,
                                             owner.Location.Y + anchor.Location.Y);
                PointD delta = new PointD(target.X - absolute.X, target.Y - absolute.Y);
                foreach (StorableObject item in placed)
                {
                    Placement placement = item as Placement;
                    if (placement == null) continue;
                    try { placement.Location = new PointD(placement.Location.X + delta.X,
                                                          placement.Location.Y + delta.Y); }
                    catch (Exception) { }
                }
                row["anchor_pin"] = anchor.Name;
                row["shift"] = XY(delta);
            }
            row["placed_objects"] = placed.Length;
            log.Add("makro " + macro + " → " + placed.Length + " nesne");
            return function;
        }

        /// <summary>Karşı uca BAKAN bağlantı noktasının indeksi. EPLAN iki bağlantı noktasını
        /// ancak birbirine bakıyorlarsa otomatik bağlar; yanlış yön seçilirse hat oluşmaz.</summary>
        static int FacingIndex(SymbolVariant sv, PointD here, List<PointD> targets)
        {
            PinBase[] cps = sv.ConnectionPoints;
            if (cps == null || cps.Length == 0 || targets == null || targets.Count == 0) return 0;
            for (int i = 0; i < cps.Length; i++)
            {
                string want = cps[i].Direction.ToString();
                foreach (PointD t in targets)
                {
                    double dx = t.X - here.X, dy = t.Y - here.Y;
                    if (Math.Abs(dx) < 0.01 && Math.Abs(dy) < 0.01) continue;
                    bool horizontal = Math.Abs(dx) >= Math.Abs(dy);
                    string side = horizontal ? (dx > 0 ? "Right" : "Left") : (dy > 0 ? "Up" : "Down");
                    if (want == side) return i;
                }
            }
            return 0;
        }

        // Nesneyi, seçilen bağlantı noktası hedef noktaya düşecek şekilde konumlandır.
        static PointD Anchor(SymbolVariant sv, int index, PointD target)
        {
            PinBase[] cps = sv.ConnectionPoints;
            if (cps == null || index < 0 || index >= cps.Length)
                throw new InvalidOperationException("Sembol pin indeksi geçersiz: " + index);
            PointD off = cps[index].Location;
            return new PointD(target.X - off.X, target.Y - off.Y);
        }

        // PinBase.Location sembole GÖRELİDİR (yerel 2026 SDK sözleşmesi).
        // Bağlantı uçları da fonksiyon envanteri gibi aynı mutlak koordinatla okunmalıdır.
        static PointD Absolute(SymbolReference parent, PinBase pin)
        {
            if (parent == null || pin == null) throw new InvalidOperationException("Pin sahibi/konumu okunamadı.");
            return new PointD(parent.Location.X + pin.Location.X, parent.Location.Y + pin.Location.Y);
        }

        public bool Execute(ActionCallingContext ctx)
        {
            string pkgPath = "", mapPath = "", outDir = "", template = "", target = "";
            ctx.GetParameter("PACKAGE", ref pkgPath);
            ctx.GetParameter("MAPPING", ref mapPath);
            ctx.GetParameter("OUT", ref outDir);
            ctx.GetParameter("TEMPLATE", ref template);
            ctx.GetParameter("TARGET", ref target);
            bool toOpenProject = (target ?? "").ToUpperInvariant() == "OPEN";
            Directory.CreateDirectory(outDir);
            JavaScriptSerializer js = new JavaScriptSerializer();
            js.MaxJsonLength = int.MaxValue;
            Dictionary<string, object> receipt = new Dictionary<string, object>();
            Dictionary<string, object> readback = new Dictionary<string, object>();
            List<string> log = new List<string>();
            List<object> created = new List<object>();
            List<object> rejected = new List<object>();
            List<string> validationErrors = new List<string>();
            receipt["contract"] = "uvp.pdf2p8.receipt";
            receipt["contract_version"] = "1.0";
            receipt["utc"] = DateTime.UtcNow.ToString("o");
            receipt["writes_live_project"] = false;
            Project prj = null;
            bool createdProject = false;
            UndoManager undoManager = null;
            UndoStep undo = null;
            List<string> pageNames = new List<string>();
            int connectionCount = 0;
            try
            {
                Dictionary<string, object> pkg = js.Deserialize<Dictionary<string, object>>(File.ReadAllText(pkgPath));
                Dictionary<string, object> map = js.Deserialize<Dictionary<string, object>>(File.ReadAllText(mapPath));
                if (S(pkg, "contract") != "uvp.pdf2p8.import-request" || S(pkg, "contract_version") != "1.0")
                    throw new InvalidOperationException("Beklenmeyen paket sözleşmesi: " + S(pkg, "contract") + " " + S(pkg, "contract_version"));
                receipt["package_sha256"] = S(pkg, "payload_sha256");
                readback["package_sha256"] = S(pkg, "payload_sha256");
                readback["document_sha256"] = S(pkg, "document_sha256");
                Dictionary<string, object> families = D(map["families"]);
                // Eski paketlerde 'L1' gibi ortak adlar farklı devamları yanlış eşleştirebilir.
                foreach (object po in A(pkg["pages"]))
                    foreach (object oo in A(D(po)["objects"]))
                        if (S(D(oo), "kind") == "INTERRUPTION" && S(D(oo), "import_name") == "")
                            throw new InvalidOperationException("Devam kimliği olmayan eski paket. Güncel motorla yeniden üretin.");
                string importNamespace = "UVP" + Guid.NewGuid().ToString("N").Substring(0, 10) + "_";

                if (toOpenProject)
                {
                    // AÇIK projeye yazma: kullanıcı bunu açıkça istedi. VAR OLAN sayfalar değiştirilmez,
                    // yalnız yeni sayfa eklenir; işlem tek bir geri alma adımıdır.
                    SelectionSet selection = new SelectionSet();
                    selection.LockProjectByDefault = true;
                    prj = selection.GetCurrentProject(true);
                    if (prj == null) throw new InvalidOperationException("Açık proje yok. EPLAN'da bir proje açın.");
                    createdProject = false;
                    receipt["target_project"] = prj.ProjectLinkFilePath;
                    receipt["writes_live_project"] = true;
                    log.Add("Hedef: AÇIK proje " + prj.ProjectName);
                }
                else
                {
                    string elk = Path.Combine(outDir, "UVP_PDF2P8_S03_" + Io.Stamp() + ".elk");
                    prj = new ProjectManager().CreateProject(elk, template);
                    createdProject = true;
                    receipt["test_project"] = prj.ProjectLinkFilePath;
                    receipt["target_project"] = prj.ProjectLinkFilePath;
                    log.Add("Hedef: YENİ test projesi " + prj.ProjectLinkFilePath);
                }
                prj.LockAllObjects(); // Kilit alınamadıysa yazmaya devam edilmez.

                // Her düğümün karşı uçları: bağlantı noktası YÖNÜ buna göre seçilir.
                Dictionary<string, List<PointD>> partners = new Dictionary<string, List<PointD>>();
                Dictionary<string, PointD> declared = new Dictionary<string, PointD>();
                foreach (object lo in A(pkg["pages"]))
                    foreach (object oo in A(D(lo)["objects"]))
                    {
                        Dictionary<string, object> o = D(oo);
                        if (o.ContainsKey("point_mm")) declared[S(o, "id")] = P(o["point_mm"]);
                        foreach (object pr in A(o.ContainsKey("pins") ? o["pins"] : null))
                            declared[S(o, "id") + "#" + S(D(pr), "name")] = P(D(pr)["point_mm"]);
                    }
                foreach (object lo in A(pkg["expected_links"]))
                {
                    Dictionary<string, object> link = D(lo);
                    string a = S(link, "a"), b = S(link, "b");
                    if (!declared.ContainsKey(a) || !declared.ContainsKey(b)) continue;
                    if (!partners.ContainsKey(a)) partners[a] = new List<PointD>();
                    if (!partners.ContainsKey(b)) partners[b] = new List<PointD>();
                    partners[a].Add(declared[b]);
                    partners[b].Add(declared[a]);
                }

                // Makro yolu ACIKCA istenmedikce calismaz: son kosuda EPLAN kapandi ve
                // makbuz hic yazilamadi. Once /MACRO:1 ile kucuk bir sayfa kumesinde denenir.
                bool useMacros = Io.Param(ctx, "MACRO") == "1";
                receipt["macro_enabled"] = useMacros;
                log.Add(useMacros ? "makro yolu ACIK (/MACRO:1)" : "makro yolu kapalı (sembol yolu)");

                // Sayfa suzgeci: /PAGES:4,5 verilirse yalniz o fiziksel sayfalar aktarilir.
                List<string> onlyPages = new List<string>();
                foreach (string piece in Io.Param(ctx, "PAGES").Split(','))
                    if (piece.Trim() != "") onlyPages.Add(piece.Trim());
                receipt["pages_filter"] = onlyPages.ToArray();

                // Parça veritabanı her zaman açılır: parçadan cihaz yolu (PLC) makro yolundan
                // bağımsızdır. Çökme makro dosyasını 326 kez açıp kapatmaktan geliyordu.
                Dictionary<string, Function[]> devicesFromPart = new Dictionary<string, Function[]>();
                MDPartsDatabase partsDb = null;
                try { partsDb = new MDPartsManagement().OpenDatabase(); }
                catch (Exception ex) { log.Add("Parça veritabanı açılamadı: " + ex.Message); }

                List<Page> pages = new List<Page>();
                Dictionary<Page, int> physical = new Dictionary<Page, int>();
                // Paketteki düğüm kimliği -> yerleştirilen gerçek nokta (mm) ve sayfa.
                Dictionary<string, PointD> nodePoint = new Dictionary<string, PointD>();
                Dictionary<string, Page> nodePage = new Dictionary<string, Page>();
                using (LockingStep step = new LockingStep())
                {
                    try
                    {
                        undoManager = new UndoManager();
                        undo = undoManager.CreateUndoStep();
                        undo.SetUndoDescription("UVP · PDF sayfa aktarımı");
                    }
                    catch (Exception ex) { throw new InvalidOperationException("Geri alma adımı açılamadı; aktarım durdu.", ex); }
                    foreach (object po in A(pkg["pages"]))
                    {
                        Dictionary<string, object> pd = D(po);
                        if (onlyPages.Count > 0
                            && !onlyPages.Contains(Convert.ToString(pd["physical_page"])))
                            continue;
                        PagePropertyList names = new PagePropertyList();
                        names.DESIGNATION_PLANT = S(pd, "anlage");
                        names.DESIGNATION_LOCATION = S(pd, "einbauort");
                        names.PAGE_COUNTER = S(pd, "blatt");
                        Page pg = new Page();
                        string counter = S(pd, "blatt");
                        Exception last = null;
                        for (int attempt = 0; attempt < 5; attempt++)
                        {
                            names.PAGE_COUNTER = attempt == 0 ? counter : counter + "_UVP" + attempt;
                            try { pg.Create(prj, DocumentTypeManager.DocumentType.Circuit, names); last = null; break; }
                            catch (Exception ex) { last = ex; pg = new Page(); }   // ad çakıştı: yeni sayfa adı dene
                        }
                        if (last != null) throw last;
                        pages.Add(pg);
                        physical[pg] = Convert.ToInt32(pd["physical_page"]);
                        pageNames.Add(pg.Name);
                        log.Add("sayfa " + pg.Name + " <- fiziksel " + pd["physical_page"]);

                        foreach (object oo in A(pd["objects"]))
                        {
                            Dictionary<string, object> o = D(oo);
                            string kind = S(o, "kind"), family = S(o, "family"), id = S(o, "id");
                            Dictionary<string, object> row = new Dictionary<string, object>();
                            row["id"] = id; row["kind"] = kind; row["family"] = family;
                            try
                            {
                                if (!families.ContainsKey(family)) throw new InvalidOperationException("Eşleme yok: " + family);
                                SymbolVariant sv = Variant(prj, D(families[family]), log);
                                if (kind == "DEVICE")
                                {
                                    // PARÇADAN CİHAZ: Cihaz Gezgini ile aynı yol. Olursa makro/sembol
                                    // yolu hiç denenmez.
                                    if (TryPlaceFromPart(o, D(families[family]), prj, pg, sv, partsDb,
                                                         devicesFromPart, nodePoint, nodePage, row, log))
                                    {
                                        row["eplan_type"] = "parçadan cihaz";
                                        created.Add(row);
                                        continue;
                                    }
                                    ArrayList pinRowsAll = A(o["pins"]);
                                    string firstPinName = S(D(pinRowsAll[0]), "name");
                                    PointD firstPoint = P(D(pinRowsAll[0])["point_mm"]);
                                    // ÖNCE ürün kodu: makro gerçek uç adlarını getirir. Kod yoksa
                                    // veya makro bulunamazsa sembole düşülür ve makbuza yazılır.
                                    Function macroFunction = null;
                                    // ÖNCE etiket listesinden gelen KESİN kod denenir; o yoksa
                                    // belgenin malzeme listesinden çıkan adaylar. Ölçüm: etiket
                                    // kodlarıyla 13/13 parça bulunuyor, tip numarasıyla 0.
                                    List<string> tryNumbers = new List<string>();
                                    string labelPart = S(o, "part_number");
                                    if (labelPart != "") tryNumbers.Add(labelPart);
                                    ArrayList candidates = A(o.ContainsKey("part_candidates") ? o["part_candidates"] : null);
                                    if (tryNumbers.Count == 0 && candidates.Count > 1)
                                    {
                                        row["part_lookup"] = "Birden çok ürün/aksesuar adayı; otomatik makro seçilmedi.";
                                        candidates = new ArrayList();
                                    }
                                    foreach (object co in candidates)
                                    {
                                        string number = S(D(co), "type_number");
                                        if (number != "" && !tryNumbers.Contains(number)) tryNumbers.Add(number);
                                    }
                                    row["part_tried"] = tryNumbers.ToArray();
                                    if (!useMacros) tryNumbers.Clear();
                                    foreach (string typeNumber in tryNumbers)
                                    {
                                        MDPart part = FindPart(partsDb, typeNumber, log);
                                        string macro = MacroOf(part);
                                        if (part == null) { row["part_lookup"] = "bulunamadı: " + typeNumber; continue; }
                                        if (macro == "") { row["part_lookup"] = "makrosuz parça: " + typeNumber; continue; }
                                        try
                                        {
                                            List<string> wantedPins = new List<string>();
                                            foreach (object pr in pinRowsAll) wantedPins.Add(S(D(pr), "name"));
                                            macroFunction = PlaceMacro(macro, pg, firstPoint, firstPinName,
                                                                       wantedPins, row, log);
                                            row["part_number"] = part.PartNr;
                                            row["part_type_number"] = typeNumber;
                                            row["macro"] = macro;
                                            row["source"] = "PART_MACRO";
                                            try { macroFunction.AddArticleReference(part.PartNr, part.Variant, 1); }
                                            catch (Exception ex) { row["article_reference_error"] = ex.Message; }
                                            break;
                                        }
                                        catch (Exception ex)
                                        {
                                            row["macro_error"] = ex.GetType().Name + ": " + ex.Message;
                                            macroFunction = null;
                                        }
                                    }
                                    Function f = macroFunction;
                                    if (f == null)
                                    {
                                        f = family == "terminal" ? new Terminal() : new Function();
                                        f.Create(pg, sv);
                                        row["source"] = "SYMBOL";
                                        if (!row.ContainsKey("part_lookup")) row["part_lookup"] = "ürün kodu yok";
                                    }
                                    string tag = S(o, "device_tag");
                                    f.Name = family == "terminal" ? tag + ":" + S(o, "terminal") : tag;
                                    ArrayList pinRows = A(o["pins"]);
                                    Dictionary<string, object> pin0 = D(pinRows[0]);
                                    if (macroFunction == null)                    // makro kendi yerine oturdu
                                        f.Location = Anchor(sv, Convert.ToInt32(pin0["index"]), P(pin0["point_mm"]));
                                    row["eplan_type"] = f.GetType().Name;
                                    row["name_written"] = f.Name;
                                    row["location"] = XY(f.Location);
                                    // Uç adı (#20022, 1 tabanlı indeks): çıplak sembolde pin adı boş gelir.
                                    List<object> pinLog = new List<object>();
                                    for (int i = 0; i < pinRows.Count; i++)
                                    {
                                        Dictionary<string, object> pr = D(pinRows[i]);
                                        string pinName = S(pr, "name");
                                        int index = pr.ContainsKey("index") ? Convert.ToInt32(pr["index"]) : i;
                                        // Düğüm noktası GERÇEK bağlantı noktasıdır: sembolün uç
                                        // aralığı kaynaktakiyle aynı olmak zorunda değil. Kaynak
                                        // koordinatı kullanılırsa çizilen çizgi hiçbir bağlantı
                                        // noktasına değmez ve bağlantı oluşmaz (ölçüm: 361/370).
                                        PointD real = P(pr["point_mm"]);
                                        bool realKnown = false;
                                        try
                                        {
                                            if (index < f.Pins.Length)
                                            {
                                                real = new PointD(f.Location.X + f.Pins[index].Location.X,
                                                                  f.Location.Y + f.Pins[index].Location.Y);
                                                realKnown = true;
                                            }
                                        }
                                        catch (Exception) { }
                                        nodePoint[id + "#" + pinName] = real;
                                        nodePage[id + "#" + pinName] = pg;
                                        Dictionary<string, object> pl = new Dictionary<string, object>();
                                        pl["pin"] = pinName;
                                        pl["source_point"] = XY(P(pr["point_mm"]));
                                        pl["real_point"] = XY(real);
                                        pl["real_point_known"] = realKnown;
                                        pl["shift_mm"] = Math.Round(Math.Abs(real.X - P(pr["point_mm"]).X)
                                                                    + Math.Abs(real.Y - P(pr["point_mm"]).Y), 2);
                                        if (macroFunction != null)
                                        {
                                            // Makronun kendi uç adları vardır: ÜZERİNE YAZILMAZ, karşılaştırılır.
                                            string actual = index < f.Pins.Length ? f.Pins[index].Name : "";
                                            pl["macro_pin"] = actual;
                                            pl["matches_source"] = actual == pinName;
                                        }
                                        else
                                        {
                                            try { f.Properties[20022, index + 1] = pinName; pl["written"] = true; }
                                            catch (Exception ex) { pl["written"] = false; pl["error"] = ex.Message; validationErrors.Add(id + ": pin yazılamadı " + pinName); }
                                        }
                                        Pin matched = null;
                                        foreach (Pin actualPin in f.Pins)
                                            if (actualPin.Name == pinName) { matched = actualPin; break; }
                                        if (matched == null || !Near(Absolute(f, matched), P(pr["point_mm"])))
                                        {
                                            pl["source_alignment_ok"] = false;
                                            validationErrors.Add(id + ": kaynak pin adı/konumu eşleşmedi " + pinName);
                                        }
                                        else pl["source_alignment_ok"] = true;
                                        pinLog.Add(pl);
                                    }
                                    row["pins"] = pinLog;
                                }
                                else if (kind == "JUNCTION" || kind == "INTERRUPTION" || kind == "POTENTIAL_BOUNDARY")
                                {
                                    SymbolReference sr = SymbolReference.Create(sv, pg);
                                    PointD here = P(o["point_mm"]);
                                    int facing = FacingIndex(sv, here,
                                        partners.ContainsKey(id) ? partners[id] : null);
                                    sr.Location = Anchor(sv, facing, here);
                                    row["connection_point"] = facing;
                                    InterruptionPoint ip = sr as InterruptionPoint;
                                    PotentialDefinition pdef = sr as PotentialDefinition;
                                    if (kind == "INTERRUPTION")
                                    {
                                        if (ip == null) throw new InvalidOperationException("Sembol kesinti noktası üretmedi: " + sr.GetType().Name);
                                        // Ad DÜZ etiket olmalı: Name setter'ı yapı ön eki üretiyor (=+-L1).
                                        ip.Name = importNamespace + S(o, "import_name");
                                        // VisibleName'a L1 yazmak kimliği tekrar ortak L1 yapabilir.
                                        // Özgün potansiyel/referans kayıtta ayrı korunur.
                                        row["source_potential"] = S(o, "name");
                                        row["source_reference"] = S(o, "reference");
                                        row["name_written"] = ip.Name;
                                        try { row["visible_name"] = ip.VisibleName; } catch (Exception) { }
                                    }
                                    if (kind == "POTENTIAL_BOUNDARY")
                                    {
                                        if (pdef == null) throw new InvalidOperationException("Sembol potansiyel tanımı üretmedi: " + sr.GetType().Name);
                                        pdef.PotentialName = S(o, "name");
                                    }
                                    row["eplan_type"] = sr.GetType().Name;
                                    row["location"] = XY(P(o["point_mm"]));
                                    // Kaynak nokta değil, sembolün KENDİ bağlantı noktası.
                                    PointD real = P(o["point_mm"]);
                                    try
                                    {
                                        PinBase[] points = sv.ConnectionPoints;
                                        if (points != null && facing < points.Length)
                                            real = Absolute(sr, points[facing]);
                                    }
                                    catch (Exception ex) { row["real_point_error"] = ex.Message; }
                                    row["real_point"] = XY(real);
                                    row["shift_mm"] = Math.Round(Math.Abs(real.X - P(o["point_mm"]).X)
                                                                 + Math.Abs(real.Y - P(o["point_mm"]).Y), 2);
                                    nodePoint[id] = real;
                                    nodePage[id] = pg;
                                }
                                else throw new InvalidOperationException("Tanınmayan nesne türü: " + kind);
                                created.Add(row);
                            }
                            catch (Exception ex)
                            {
                                row["error"] = ex.GetType().Name + ": " + ex.Message;
                                rejected.Add(row);
                            }
                        }
                    }
                    // ÖNCE otomatik bağlama: hizalı ve birbirine bakan bağlantı noktaları EPLAN
                    // tarafından kendiliğinden bağlanır; çizgi çizmeye gerek yoktur.
                    new Generate().Connections(pages.ToArray(), true);
                    int connectionsBeforeLines = 0;
                    {
                        DMObjectsFinder beforeFinder = new DMObjectsFinder(prj);
                        foreach (Page countPage in pages)
                        {
                            ConnectionsFilter countFilter = new ConnectionsFilter();
                            countFilter.Page = countPage;
                            foreach (Connection ignored in beforeFinder.GetConnections(countFilter))
                                connectionsBeforeLines++;
                        }
                    }
                    log.Add("Generate.Connections(" + pages.Count + " sayfa) — otomatik");

                    // SONRA yalnız oluşmayan bağlar için çizgi. Böylece sayfada başıboş mavi çizgi
                    // kalmaz; çizilen her çizgi "otomatik bağlanmadı" kanıtıdır ve makbuzda yazılır.
                    DMObjectsFinder finderPass = new DMObjectsFinder(prj);
                    List<object> drawn = new List<object>();
                    List<object[]> pending = new List<object[]>();
                    int autoLinked = 0;
                    foreach (object lo in A(pkg["expected_links"]))
                    {
                        Dictionary<string, object> link = D(lo);
                        string a = S(link, "a"), b = S(link, "b");
                        Dictionary<string, object> lr = new Dictionary<string, object>();
                        lr["a"] = a; lr["b"] = b; lr["ok"] = false;
                        if (!nodePoint.ContainsKey(a) || !nodePoint.ContainsKey(b))
                        {
                            lr["ok"] = false; lr["error"] = "Düğüm yerleştirilmedi.";
                            drawn.Add(lr); continue;
                        }
                        if (Linked(finderPass, nodePage[a], nodePoint[a], nodePoint[b]))
                        {
                            lr["auto"] = true; lr["ok"] = true; autoLinked++; drawn.Add(lr); continue;
                        }
                        try
                        {
                            // EPLAN'ın KENDİ bağlantı çizgisi kullanılır: grafik çizgi ölçümde
                            // hiç bağlantı üretmedi (316/316). Noktalar GERÇEK bağlantı
                            // noktalarıdır; hizalı değillerse tek köşeyle iki parça çizilir —
                            // diyagonal bağlantı uydurulmaz.
                            PointD pa = nodePoint[a], pb = nodePoint[b];
                            List<Placement> segments = new List<Placement>();
                            if (Math.Abs(pa.X - pb.X) <= 0.01 || Math.Abs(pa.Y - pb.Y) <= 0.01)
                            {
                                DynamicConnectionLine line = new DynamicConnectionLine();
                                line.Create(nodePage[a]);
                                line.SetGraphics(pa, pb);
                                segments.Add(line);
                                lr["route"] = "düz";
                            }
                            else
                            {
                                PointD corner = new PointD(pb.X, pa.Y);
                                DynamicConnectionLine first = new DynamicConnectionLine();
                                first.Create(nodePage[a]);
                                first.SetGraphics(pa, corner);
                                DynamicConnectionLine second = new DynamicConnectionLine();
                                second.Create(nodePage[a]);
                                second.SetGraphics(corner, pb);
                                segments.Add(first); segments.Add(second);
                                lr["route"] = "köşeli";
                                lr["corner"] = XY(corner);
                            }
                            lr["auto"] = false; lr["line"] = true;
                            lr["from"] = XY(pa); lr["to"] = XY(pb);
                            pending.Add(new object[] { lr, segments, nodePage[a], pa, pb });
                        }
                        catch (Exception ex)
                        {
                            lr["auto"] = false; lr["line"] = false;
                            lr["error"] = ex.GetType().Name + ": " + ex.Message;
                        }
                        drawn.Add(lr);
                    }
                    log.Add("otomatik bağlanan: " + autoLinked + " / " + drawn.Count);
                    if (pending.Count > 0)
                    {
                        new Generate().Connections(pages.ToArray(), true);
                        log.Add("Generate.Connections — çizgilerden sonra");
                        DMObjectsFinder after = new DMObjectsFinder(prj);
                        // Bağlantı SAYISI ölçülür: Linked() bağlantıyı koordinatla arar ve
                        // EPLAN başka uçlarla kurduysa göremez; o zaman İYİ çizgiyi silerdik.
                        int totalAfter = 0;
                        foreach (Page countPage in pages)
                        {
                            ConnectionsFilter countFilter = new ConnectionsFilter();
                            countFilter.Page = countPage;
                            foreach (Connection ignored in after.GetConnections(countFilter)) totalAfter++;
                        }
                        receipt["connections_after_lines"] = totalAfter;
                        receipt["connections_before_lines"] = connectionsBeforeLines;
                        bool linesHelped = totalAfter > connectionsBeforeLines;
                        receipt["lines_helped"] = linesHelped;
                        log.Add("bağlantı sayısı: çizgiden önce " + connectionsBeforeLines
                                + ", sonra " + totalAfter);
                        int byLine = 0, dropped = 0;
                        foreach (object[] item in pending)
                        {
                            Dictionary<string, object> lr = (Dictionary<string, object>)item[0];
                            List<Placement> segments = (List<Placement>)item[1];
                            if (Linked(after, (Page)item[2], (PointD)item[3], (PointD)item[4]))
                            {
                                lr["connected_by"] = "CONNECTION_LINE"; lr["ok"] = true; byLine++;
                            }
                            else if (linesHelped)
                            {
                                // Toplam bağlantı sayısı arttıysa çizgiler işe yaramış demektir;
                                // tek tek doğrulayamasak da SİLMEYİZ (silmek işi geri alırdı).
                                lr["connected_by"] = "CONNECTION_LINE (sayı arttı, uç doğrulanamadı)";
                                byLine++;
                            }
                            else
                            {
                                foreach (Placement segment in segments)
                                    try { segment.Remove(); } catch (Exception) { }
                                lr["line"] = false;
                                lr["connected_by"] = null;
                                lr["note"] = "Bağlantı oluşmadı; çizgi silindi.";
                                dropped++;
                            }
                        }
                        log.Add("çizgiyle bağlanan: " + byLine + ", silinen çizgi: " + dropped);
                        receipt["links_by_line"] = byLine;
                        receipt["links_failed"] = dropped;
                        if (dropped > 0) new Generate().Connections(pages.ToArray(), true);
                    }
                    receipt["links"] = drawn;
                    receipt["links_auto"] = autoLinked;
                    int failedLinks = 0;
                    foreach (object item in drawn) if (!Convert.ToBoolean(D(item)["ok"])) failedLinks++;
                    receipt["links_failed"] = failedLinks;
                    if (failedLinks > 0) validationErrors.Add(failedLinks + " beklenen bağ EPLAN'da doğrulanamadı.");
                }

                // ------------------------------------------------------------ GERİ OKUMA
                DMObjectsFinder finder = new DMObjectsFinder(prj);
                List<object> rbPages = new List<object>();
                List<object> rbConnections = new List<object>();
                connectionCount = 0;
                foreach (Page pg in pages)
                {
                    Dictionary<string, object> rp = new Dictionary<string, object>();
                    rp["physical_page"] = physical[pg];
                    rp["name"] = pg.Name;
                    List<object> fs = new List<object>();
                    foreach (Function f in pg.Functions)
                    {
                        Dictionary<string, object> fr = new Dictionary<string, object>();
                        fr["name"] = f.Name;
                        fr["visible_name"] = f.VisibleName;
                        fr["type"] = f.GetType().Name;
                        fr["location"] = XY(f.Location);
                        List<object> pins = new List<object>();
                        foreach (Pin pin in f.Pins)
                        {
                            Dictionary<string, object> pr = new Dictionary<string, object>();
                            pr["name"] = pin.Name;
                            // Pin.Location sembole GÖRELİdir; karşılaştırma mutlak konum ister.
                            pr["offset"] = XY(pin.Location);
                            pr["location"] = new double[] { Math.Round(f.Location.X + pin.Location.X, 3),
                                                            Math.Round(f.Location.Y + pin.Location.Y, 3) };
                            List<string> targets = new List<string>();
                            foreach (Pin t in pin.TargetPins)
                                targets.Add((t.ParentFunction != null ? t.ParentFunction.Name : "?") + ":" + t.Name);
                            pr["target_pins"] = targets;
                            pins.Add(pr);
                        }
                        fr["pins"] = pins;
                        fs.Add(fr);
                    }
                    rp["functions"] = fs;
                    List<object> placements = new List<object>();
                    foreach (Placement pl in pg.AllPlacements)
                    {
                        Dictionary<string, object> r = new Dictionary<string, object>();
                        r["type"] = pl.GetType().Name;
                        try { r["location"] = XY(pl.Location); } catch { }
                        InterruptionPoint ip = pl as InterruptionPoint;
                        if (ip != null)
                        {
                            r["name"] = ip.Name;
                            try { r["visible_name"] = ip.VisibleName; } catch (Exception) { }
                        }
                        PotentialDefinition pdef = pl as PotentialDefinition;
                        if (pdef != null) r["potential"] = pdef.PotentialName;
                        placements.Add(r);
                    }
                    rp["placements"] = placements;
                    rbPages.Add(rp);

                    ConnectionsFilter cf = new ConnectionsFilter();
                    cf.Page = pg;
                    foreach (Connection c in finder.GetConnections(cf))
                    {
                        Dictionary<string, object> cr = new Dictionary<string, object>();
                        cr["physical_page"] = physical[pg];
                        cr["start"] = End(c.StartPin);
                        cr["end"] = End(c.EndPin);
                        // T düğümü / kesinti noktası ucu bir fonksiyon pini değildir: sembol bağlantı
                        // noktası ve sembol türüyle okunur (konum eşlemesi için).
                        try { if (c.StartPin == null) Ref(D(cr["start"]), c.StartSymbolReference, c.StartSymbolConnPoint); } catch (Exception ex) { D(cr["start"])["ref_error"] = ex.Message; }
                        try { if (c.EndPin == null) Ref(D(cr["end"]), c.EndSymbolReference, c.EndSymbolConnPoint); } catch (Exception ex) { D(cr["end"])["ref_error"] = ex.Message; }
                        List<string> pots = new List<string>();
                        try { foreach (PotentialDefinition p in c.PotentialDefinitions) pots.Add(p.PotentialName); } catch { }
                        cr["potentials"] = pots;
                        rbConnections.Add(cr);
                        connectionCount++;
                    }
                }
                List<object> ips = new List<object>();
                foreach (InterruptionPoint ip in finder.GetInterruptionPoints(new InterruptionPointsFilter()))
                {
                    Dictionary<string, object> r = new Dictionary<string, object>();
                    r["name"] = ip.Name;
                    try { r["visible_name"] = ip.VisibleName; } catch (Exception) { }
                    try { r["cross_reference"] = ip.Properties.INTERRUPTIONPOINT_CROSSREFERENCE.ToString(); }
                    catch (Exception) { }
                    r["page"] = ip.Page != null ? ip.Page.Name : "";
                    r["location"] = XY(ip.Location);
                    ips.Add(r);
                }
                readback["contract"] = "uvp.pdf2p8.readback";
                readback["contract_version"] = "1.0";
                readback["test_project"] = prj.ProjectLinkFilePath;
                readback["pages"] = rbPages;
                readback["connections"] = rbConnections;
                readback["interruption_points"] = ips;
                receipt["ok"] = rejected.Count == 0 && validationErrors.Count == 0;
                readback["import_ok"] = receipt["ok"];
            }
            catch (Exception ex)
            {
                receipt["ok"] = false;
                receipt["error"] = ex.GetType().FullName + ": " + ex.Message;
                receipt["stack"] = ex.StackTrace;
            }
            finally
            {
                receipt["created"] = created;
                receipt["rejected"] = rejected;
                receipt["pages"] = pageNames;
                receipt["log"] = log;
                receipt["validation_errors"] = validationErrors;
                receipt["verification_state"] = "SOURCE_COMPARISON_REQUIRED";
                Io.WriteJson(Path.Combine(outDir, "receipt.json"), receipt);
                Io.WriteJson(Path.Combine(outDir, "readback.json"), readback);
                // Kısa özet: script bunu doğrudan kullanıcıya gösterir, JSON açmaya gerek kalmaz.
                StringBuilder summary = new StringBuilder();
                summary.AppendLine(toOpenProject ? "Hedef: AÇIK PROJE" : "Hedef: yeni test projesi");
                summary.AppendLine("Proje    : " + (receipt.ContainsKey("target_project") ? receipt["target_project"] : "-"));
                summary.AppendLine("Sayfalar : " + (pageNames.Count == 0 ? "-" : string.Join(", ", pageNames.ToArray())));
                int byMacro = 0, bySymbol = 0;
                foreach (object row in created)
                {
                    string how = Convert.ToString(D(row).ContainsKey("source") ? D(row)["source"] : "");
                    if (how == "PART_MACRO") byMacro++;
                    else if (how == "SYMBOL") bySymbol++;
                }
                summary.AppendLine("Konan nesne: " + created.Count + "   reddedilen: " + rejected.Count);
                summary.AppendLine("Cihaz: makro ile " + byMacro + ", sembol ile " + bySymbol);
                summary.AppendLine("Beklenen bağ: " + (receipt.ContainsKey("links")
                                   ? ((List<object>)receipt["links"]).Count : 0)
                                   + " · otomatik: " + (receipt.ContainsKey("links_auto") ? receipt["links_auto"] : 0)
                                   + " · çizgiyle: " + (receipt.ContainsKey("links_by_line") ? receipt["links_by_line"] : 0)
                                   + " · bağlanamayan: " + (receipt.ContainsKey("links_failed") ? receipt["links_failed"] : 0));
                summary.AppendLine("Geri okunan bağlantı: " + connectionCount);
                if (receipt.ContainsKey("error")) summary.AppendLine("HATA: " + receipt["error"]);
                foreach (string error in validationErrors) summary.AppendLine("DOĞRULAMA: " + error);
                foreach (object row in rejected)
                {
                    Dictionary<string, object> r = (Dictionary<string, object>)row;
                    summary.AppendLine("  reddedildi " + r["id"] + ": " + (r.ContainsKey("error") ? r["error"] : ""));
                }
                summary.AppendLine();
                summary.AppendLine("Kaynakla geri okuma karşılaştırılmadan aktarım tamamlanmış sayılmaz.");
                if (undo != null) summary.AppendLine("Aktarım için bir geri alma adımı oluşturuldu; mevcut nesneler silinmedi.");
                File.WriteAllText(Path.Combine(outDir, "ozet.txt"), summary.ToString(), new UTF8Encoding(false));
                try { if (undo != null) undo.CloseUndo(); } catch (Exception) { }
                try { if (undoManager != null) undoManager.Dispose(); } catch (Exception) { }
                if (prj != null && createdProject) { try { prj.Close(); } catch { } }
            }
            return receipt.ContainsKey("ok") && Convert.ToBoolean(receipt["ok"]);
        }

        static void Ref(Dictionary<string, object> r, SymbolReference sr, PinBase cp)
        {
            if (sr != null)
            {
                r["symbol_type"] = sr.GetType().Name;
                InterruptionPoint ip = sr as InterruptionPoint;
                if (ip != null) r["name"] = ip.Name;
            }
            if (cp != null && sr != null) r["location"] = XY(Absolute(sr, cp));
        }

        /// <summary>Bu iki nokta arasında EPLAN'ın kendi ürettiği bir bağlantı var mı?</summary>
        static bool Linked(DMObjectsFinder finder, Page page, PointD a, PointD b)
        {
            ConnectionsFilter filter = new ConnectionsFilter();
            filter.Page = page;
            foreach (Connection c in finder.GetConnections(filter))
            {
                PointD[] ends = new PointD[2];
                int found = 0;
                if (c.StartPin != null) ends[found++] = Absolute(c.StartPin.ParentFunction, c.StartPin);
                else if (c.StartSymbolConnPoint != null) ends[found++] = Absolute(c.StartSymbolReference, c.StartSymbolConnPoint);
                if (c.EndPin != null) ends[found++] = Absolute(c.EndPin.ParentFunction, c.EndPin);
                else if (c.EndSymbolConnPoint != null) ends[found++] = Absolute(c.EndSymbolReference, c.EndSymbolConnPoint);
                if (found < 2) continue;
                bool hit = (Near(ends[0], a) && Near(ends[1], b)) || (Near(ends[0], b) && Near(ends[1], a));
                if (hit) return true;
            }
            return false;
        }

        static bool Near(PointD a, PointD b)
        {
            return Math.Abs(a.X - b.X) <= 0.6 && Math.Abs(a.Y - b.Y) <= 0.6;
        }

        static Dictionary<string, object> End(Pin pin)
        {
            Dictionary<string, object> r = new Dictionary<string, object>();
            if (pin == null) { r["pin"] = null; return r; }
            r["function"] = pin.ParentFunction != null ? pin.ParentFunction.Name : null;
            r["function_type"] = pin.ParentFunction != null ? pin.ParentFunction.GetType().Name : null;
            r["pin"] = pin.Name;
            if (pin.ParentFunction != null) r["location"] = XY(Absolute(pin.ParentFunction, pin));
            return r;
        }
    }
}
