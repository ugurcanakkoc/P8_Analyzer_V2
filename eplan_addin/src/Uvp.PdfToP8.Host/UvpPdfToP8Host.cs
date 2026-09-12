// =====================================================================================
// Uvp.PdfToP8.Host — EPLAN P8 2026.0.3 ince host adaptörü (PLAN S03 / EPLAN_ADDIN_PLAN E00–E04)
//
// Bu dosya YALNIZ AYRI TEST PROJESİNE yazar: her action kendi yeni projesini şablondan
// oluşturur (`/OUT` klasörü altında). Açık/canlı kullanıcı projesini açmaz, değiştirmez, silmez.
//
// Actions:
//   UvpPdfToP8Probe  /OUT:"<klasör>" /TEMPLATE:"<.zw9>"
//       E00/E02/E03: ortam raporu + yeni test projesi + sembol kataloğu (IEC_symbol, SPECIAL).
//
// Derleme: eplan_addin/build/build.bat (yerel P8 Bin'e karşı; DLL'ler repoya girmez).
// C# 5 sözdizimi: Windows'un .NET Framework csc'si ile derlenir (SemaKopru ile aynı yol).
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Base;
using Eplan.EplApi.DataModel;
using Eplan.EplApi.DataModel.MasterData;

namespace Uvp.PdfToP8.Host
{
    public class AddInModule : IEplAddIn
    {
        public bool OnRegister(ref bool bLoadOnStart) { bLoadOnStart = true; return true; }
        public bool OnUnregister() { return true; }
        public bool OnInit() { return true; }
        public bool OnInitGui() { return true; }
        public bool OnExit() { return true; }
    }

    internal static class Io
    {
        public static string Param(ActionCallingContext ctx, string name)
        {
            string v = "";
            ctx.GetParameter(name, ref v);
            return v ?? "";
        }

        public static void WriteJson(string path, object value)
        {
            JavaScriptSerializer js = new JavaScriptSerializer();
            js.MaxJsonLength = int.MaxValue;
            File.WriteAllText(path, js.Serialize(value), new UTF8Encoding(false));
        }

        public static string Stamp()
        {
            return DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
        }
    }

    public class ProbeAction : IEplAction
    {
        public bool OnRegister(ref string Name, ref int Ordinal)
        {
            Name = "UvpPdfToP8Probe";
            Ordinal = 20;
            return true;
        }

        public void GetActionProperties(ref ActionProperties actionProperties) { }

        static string Text(Func<string> read)
        {
            try { string value = read(); return value ?? ""; }
            catch (Exception) { return ""; }
        }

        public bool Execute(ActionCallingContext ctx)
        {
            string outDir = Io.Param(ctx, "OUT");
            string template = Io.Param(ctx, "TEMPLATE");
            if (outDir == "") outDir = Path.Combine(Path.GetTempPath(), "uvp_p8probe");
            Directory.CreateDirectory(outDir);
            List<string> log = new List<string>();
            Dictionary<string, object> report = new Dictionary<string, object>();
            report["contract"] = "uvp.pdf2p8.capabilities";
            report["contract_version"] = "1.0";
            report["utc"] = DateTime.UtcNow.ToString("o");
            report["writes_live_project"] = false;
            try
            {
                Process me = Process.GetCurrentProcess();
                report["eplan_exe"] = me.MainModule.FileName;
                report["eplan_file_version"] = me.MainModule.FileVersionInfo.FileVersion;
                report["clr"] = Environment.Version.ToString();

                ProjectManager pm = new ProjectManager();
                List<string> open = new List<string>();
                foreach (Project p in pm.OpenProjects) open.Add(p.ProjectLinkFilePath);
                report["open_projects_before"] = open;

                string elk = Path.Combine(outDir, "UVP_PDF2P8_PROBE_" + Io.Stamp() + ".elk");
                log.Add("CreateProject " + elk + " <- " + template);
                Project prj = pm.CreateProject(elk, template);
                report["test_project"] = prj.ProjectLinkFilePath;

                List<object> libraries = new List<object>();
                foreach (SymbolLibrary lib in prj.SymbolLibraries)
                {
                    string libName = lib.Name;
                    List<object> symbols = new List<object>();
                    if (libName == "IEC_symbol" || libName == "SPECIAL")
                    {
                        foreach (Symbol s in lib.Symbols)
                        {
                            Dictionary<string, object> row = new Dictionary<string, object>();
                            row["name"] = s.Name;
                            row["type"] = s.Type.ToString();
                            // Sembol ADI seçim için yeterli değildir: açıklama ve fonksiyon türü de
                            // yazılır, eşleme tahminle değil katalog kanıtıyla kurulsun.
                            row["description"] = Text(delegate { return s.Properties.SYMB_DESC.ToString(); });
                            row["function_type"] = Text(delegate { return s.Properties.SYMB_SYBMOLFUNCTIONTYPE_NAME.ToString(); });
                            row["function_description"] = Text(delegate { return s.Properties.FUNC_DESC.ToString(); });
                            row["logic_model"] = Text(delegate { return s.Properties.SYMB_LOGICMODEL.ToString(); });
                            int variants = 0;
                            try { variants = s.Variants.Length; } catch (Exception ex) { row["variants_error"] = ex.Message; }
                            row["variants"] = variants;
                            try
                            {
                                SymbolVariant v0 = s[0];
                                PinBase[] points = v0 == null ? null : v0.ConnectionPoints;
                                row["connection_points_v0"] = points == null ? 0 : points.Length;
                                if (points != null)
                                {
                                    List<object> list = new List<object>();
                                    foreach (PinBase cp in points)
                                        list.Add(new Dictionary<string, object> {
                                            { "index", cp.Index },
                                            { "direction", cp.Direction.ToString() },
                                            { "offset", new double[] { Math.Round(cp.Location.X, 3), Math.Round(cp.Location.Y, 3) } } });
                                    row["points_v0"] = list;
                                }
                            }
                            catch (Exception ex) { row["variant0_error"] = ex.Message; }
                            symbols.Add(row);
                        }
                    }
                    Dictionary<string, object> l = new Dictionary<string, object>();
                    l["name"] = libName;
                    l["symbols"] = symbols;
                    libraries.Add(l);
                }
                report["symbol_libraries"] = libraries;
                prj.Close();
                log.Add("Closed test project.");
                report["ok"] = true;
            }
            catch (Exception ex)
            {
                report["ok"] = false;
                report["error"] = ex.GetType().FullName + ": " + ex.Message;
                report["stack"] = ex.StackTrace;
            }
            report["log"] = log;
            Io.WriteJson(Path.Combine(outDir, "capabilities.json"), report);
            return true;
        }
    }
}
