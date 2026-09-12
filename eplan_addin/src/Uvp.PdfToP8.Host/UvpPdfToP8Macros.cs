// =====================================================================================
// UvpPdfToP8Macros — ürün kodlarının MAKROLARINI ve makro UÇLARINI dosyaya yazar.
//
//   UvpPdfToP8Macros /PACKAGE:"<import-request.json>" /OUT:"<klasör>" [/TEMPLATE:"<.zw9>"]
//
// Neden: müşteri şemasında uç adı `1 2 3`, makroda `L1 L2 L3` olabiliyor. Eşlemeyi
// yapabilmek için önce makronun GERÇEK uçlarını bilmek gerekir — tahminle değil, makroyu
// açıp okuyarak.
//
// Nasıl: paketteki her ürün kodu parça veritabanında aranır; parçanın şema makrosu geçici
// bir projede boş sayfaya konur, fonksiyonların uçları okunur, sonra proje kapatılır.
// AÇIK PROJEYE DOKUNULMAZ.
//
// Çıktı: <klasör>\makro_pinleri.json
// =====================================================================================
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Base;
using Eplan.EplApi.DataModel;
using Eplan.EplApi.DataModel.Filters;
using Eplan.EplApi.HEServices;
using Eplan.EplApi.MasterData;

namespace Uvp.PdfToP8.Host
{
    public class MacroDumpAction : IEplAction
    {
        public bool OnRegister(ref string Name, ref int Ordinal)
        {
            Name = "UvpPdfToP8Macros";
            Ordinal = 20;
            return true;
        }

        public void GetActionProperties(ref ActionProperties actionProperties) { }

        static Dictionary<string, object> D(object o) { return (Dictionary<string, object>)o; }
        static ArrayList A(object o) { return o == null ? new ArrayList() : (ArrayList)o; }
        static string S(Dictionary<string, object> d, string k)
        {
            return d.ContainsKey(k) && d[k] != null ? Convert.ToString(d[k]) : "";
        }

        /// <summary>Paketteki ürün kodları: kod → onu kullanan cihaz etiketleri.</summary>
        static Dictionary<string, List<object>> PartNumbers(Dictionary<string, object> package)
        {
            Dictionary<string, List<object>> out_ = new Dictionary<string, List<object>>();
            foreach (object po in A(package["pages"]))
            {
                Dictionary<string, object> page = D(po);
                foreach (object oo in A(page["objects"]))
                {
                    Dictionary<string, object> o = D(oo);
                    if (S(o, "kind") != "DEVICE") continue;
                    string part = S(o, "part_number");
                    if (part == "") continue;
                    if (!out_.ContainsKey(part)) out_[part] = new List<object>();
                    List<string> pins = new List<string>();
                    foreach (object pr in A(o["pins"])) pins.Add(S(D(pr), "name"));
                    out_[part].Add(new Dictionary<string, object> {
                        { "device_tag", S(o, "device_tag") }, { "family", S(o, "family") },
                        { "source_pins", pins.ToArray() } });
                }
            }
            return out_;
        }

        static MDPart FindPart(MDPartsDatabase db, string number, List<string> log)
        {
            if (db == null || string.IsNullOrEmpty(number)) return null;
            try
            {
                MDPart direct = db.GetPart(number);
                if (direct != null) return direct;
            }
            catch (Exception) { }
            try
            {
                MDPartsDatabaseItemPropertyList filter = new MDPartsDatabaseItemPropertyList();
                filter.ARTICLE_TYPENR = number;
                MDPart[] hits = db.GetParts(filter);
                if (hits != null && hits.Length > 0) return hits[0];
            }
            catch (Exception ex) { log.Add("parça arama (" + number + "): " + ex.Message); }
            return null;
        }

        static string Text(Func<string> read)
        {
            try { string v = read(); return v ?? ""; }
            catch (Exception) { return ""; }
        }

        public bool Execute(ActionCallingContext ctx)
        {
            string packagePath = Io.Param(ctx, "PACKAGE");
            string outDir = Io.Param(ctx, "OUT");
            string template = Io.Param(ctx, "TEMPLATE");
            if (outDir == "") outDir = Path.Combine(Path.GetTempPath(), "uvp_p8macros");
            Directory.CreateDirectory(outDir);

            List<string> log = new List<string>();
            List<object> rows = new List<object>();
            Dictionary<string, object> report = new Dictionary<string, object>();
            report["contract"] = "uvp.pdf2p8.macro-pins";
            report["contract_version"] = "1.0";
            report["utc"] = DateTime.UtcNow.ToString("o");
            report["writes_live_project"] = false;

            Project scratch = null;
            try
            {
                if (packagePath == "" || !File.Exists(packagePath))
                    throw new InvalidOperationException("Paket dosyası yok: " + packagePath);
                JavaScriptSerializer js = new JavaScriptSerializer();
                js.MaxJsonLength = int.MaxValue;
                // DeserializeObject dizileri object[] verir; Deserialize<T> ArrayList verir.
                // Import ile aynı yol kullanılır ki A() yardımcısı ikisinde de çalışsın.
                Dictionary<string, object> package =
                    js.Deserialize<Dictionary<string, object>>(File.ReadAllText(packagePath));
                Dictionary<string, List<object>> parts = PartNumbers(package);
                report["part_numbers"] = parts.Count;
                log.Add("pakette " + parts.Count + " farklı ürün kodu");

                MDPartsDatabase db = null;
                try { db = new MDPartsManagement().OpenDatabase(); }
                catch (Exception ex) { log.Add("Parça veritabanı açılamadı: " + ex.Message); }

                // Makro ancak bir sayfaya konunca uçlarını gösterir: geçici proje, sonra kapatılır.
                ProjectManager pm = new ProjectManager();
                if (template == "") throw new InvalidOperationException("/TEMPLATE gerekli (geçici proje).");
                string elk = Path.Combine(outDir, "UVP_MAKRO_" + Io.Stamp() + ".elk");
                scratch = pm.CreateProject(elk, template);
                PagePropertyList names = new PagePropertyList();
                names.DESIGNATION_PLANT = "UVPMAK";
                names.PAGE_COUNTER = "1";
                Page page = new Page();
                page.Create(scratch, DocumentTypeManager.DocumentType.Circuit, names);

                double x = 20.0, y = 250.0;
                int pageNumber = 1;
                foreach (KeyValuePair<string, List<object>> entry in parts)
                {
                    Dictionary<string, object> row = new Dictionary<string, object>();
                    row["part_number"] = entry.Key;
                    row["used_by"] = entry.Value;
                    MDPart part = FindPart(db, entry.Key, log);
                    if (part == null)
                    {
                        row["found"] = false;
                        row["reason"] = "parça veritabanında bulunamadı";
                        rows.Add(row);
                        continue;
                    }
                    row["found"] = true;
                    row["part_nr"] = Text(delegate { return part.PartNr; });
                    row["type_nr"] = Text(delegate { return part.Properties.ARTICLE_TYPENR.ToString(); });
                    row["description"] = Text(delegate { return part.Properties.ARTICLE_DESCR1.ToString(); });
                    // Parçada birden çok makro alanı var. ŞEMA makrosu ayrıdır:
                    // ARTICLE_MACRO ölçümde 3D makrosunu veriyordu (13/13 '*_3D.ema').
                    string schematic = Text(delegate { return part.Properties.ARTICLE_GROUPSYMBOLMACRO_IEC.ToString(); });
                    string generic = Text(delegate { return part.Properties.ARTICLE_GROUPSYMBOLMACRO.ToString(); });
                    string any = Text(delegate { return part.Properties.ARTICLE_MACRO.ToString(); });
                    row["macro_iec"] = schematic;
                    row["macro_group"] = generic;
                    row["macro_any"] = any;
                    row["macro_3d"] = Text(delegate { return part.Properties.ARTICLE_3DMACRO.ToString(); });
                    row["macro_name"] = Text(delegate { return part.Properties.ARTICLE_MACRONAME.ToString(); });
                    // Parçanın kendi SEMBOLÜ de kayıtlı: aile→sembol kararını bu çözebilir.
                    row["symbol_file"] = Text(delegate { return part.Properties.ARTICLE_SYMBOLFILE.ToString(); });
                    row["symbol_number"] = Text(delegate { return part.Properties.ARTICLE_SYMBOLNUMBER.ToString(); });

                    string macro = schematic != "" ? schematic : (generic != "" ? generic : any);
                    row["macro"] = macro;
                    row["macro_source"] = schematic != "" ? "ARTICLE_GROUPSYMBOLMACRO_IEC"
                        : (generic != "" ? "ARTICLE_GROUPSYMBOLMACRO" : "ARTICLE_MACRO");
                    if (macro == "")
                    {
                        row["reason"] = "parçanın şema makrosu yok";
                        rows.Add(row);
                        continue;
                    }

                    List<object> functions = new List<object>();
                    StorableObject[] placed = null;
                    // Her makro AYRI noktaya konur: aynı noktaya ikinci kez koymak
                    // "aynı semboller üst üste yerleştirilir" hatası veriyordu (12/13).
                    x += 60.0;
                    if (x > 380.0) { x = 20.0; y -= 60.0; }
                    if (y < 20.0)
                    {
                        names.PAGE_COUNTER = Convert.ToString(++pageNumber);
                        page = new Page();
                        page.Create(scratch, DocumentTypeManager.DocumentType.Circuit, names);
                        x = 20.0; y = 250.0;
                    }
                    row["at"] = new double[] { x, y };
                    try
                    {
                        placed = new Insert().WindowMacro(macro, 0, page, new PointD(x, y),
                                                          Insert.MoveKind.Absolute);
                        // Konan nesne türleri kayda geçer: uç bulunamazsa nerede olduğu görünsün.
                        Dictionary<string, int> kinds = new Dictionary<string, int>();
                        foreach (StorableObject item in placed)
                        {
                            string kind = item.GetType().Name;
                            kinds[kind] = (kinds.ContainsKey(kind) ? kinds[kind] : 0) + 1;
                        }
                        row["placed_types"] = kinds;

                        // Üst düzey nesneler yetmiyor: makronun İÇİNDEKİ fonksiyonlar da
                        // sayfada durur. Sayfadaki bütün fonksiyonlar taranır ve yalnız bu
                        // makronun konduğu bölgedekiler alınır.
                        List<Function> found = new List<Function>();
                        foreach (StorableObject item in placed)
                        {
                            Function direct = item as Function;
                            if (direct != null) found.Add(direct);
                        }
                        try
                        {
                            DMObjectsFinder finder = new DMObjectsFinder(scratch);
                            FunctionsFilter filter = new FunctionsFilter();
                            filter.SetFilteredPropertyList(new FunctionPropertyList());
                            foreach (Function candidate in finder.GetFunctions(filter))
                            {
                                if (candidate.Page == null || !candidate.Page.Equals(page)) continue;
                                if (Math.Abs(candidate.Location.X - x) > 55.0
                                    || Math.Abs(candidate.Location.Y - y) > 55.0) continue;
                                if (!found.Contains(candidate)) found.Add(candidate);
                            }
                        }
                        catch (Exception ex) { row["scan_error"] = ex.Message; }

                        foreach (Function function in found)
                        {
                            if (function == null) continue;
                            List<object> pins = new List<object>();
                            foreach (Pin pin in function.Pins)
                                pins.Add(new Dictionary<string, object> {
                                    { "name", pin.Name },
                                    { "index", pin.Index },
                                    { "direction", Text(delegate { return pin.Direction.ToString(); }) },
                                    { "offset", new double[] { Math.Round(pin.Location.X - function.Location.X, 3),
                                                               Math.Round(pin.Location.Y - function.Location.Y, 3) } } });
                            functions.Add(new Dictionary<string, object> {
                                { "type", function.GetType().Name },
                                { "name", Text(delegate { return function.Name; }) },
                                { "visible_name", Text(delegate { return function.VisibleName; }) },
                                { "symbol", Text(delegate { return function.SymbolVariant == null ? ""
                                                            : function.SymbolVariant.SymbolName; }) },
                                { "pins", pins } });
                        }
                        row["objects"] = placed.Length;
                    }
                    catch (Exception ex)
                    {
                        row["reason"] = "makro açılamadı: " + ex.GetType().Name + ": " + ex.Message;
                    }
                    finally
                    {
                        if (placed != null)
                            foreach (StorableObject item in placed)
                            {
                                Placement placement = item as Placement;
                                if (placement == null) continue;
                                try { placement.Remove(); } catch (Exception) { }
                            }
                    }
                    row["functions"] = functions;
                    rows.Add(row);
                }
                report["ok"] = true;
            }
            catch (Exception ex)
            {
                report["ok"] = false;
                report["error"] = ex.GetType().FullName + ": " + ex.Message;
                report["stack"] = ex.StackTrace;
            }
            finally
            {
                if (scratch != null) { try { scratch.Close(); log.Add("geçici proje kapatıldı."); } catch (Exception) { } }
            }
            report["parts"] = rows;
            report["log"] = log;
            Io.WriteJson(Path.Combine(outDir, "makro_pinleri.json"), report);
            return true;
        }
    }
}
