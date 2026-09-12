// =====================================================================================
// UvpPdfToP8Catalog — K1: sembol kataloğunu ızgara sayfalarına basar ve PDF'e verir.
//
//   UvpPdfToP8Catalog /OUT:"<klasör>" /TEMPLATE:"<.zw9>"
//                     [/LIB:IEC_symbol,SPECIAL] [/MAX:0] [/CELL:24] [/MARGIN:15] [/PDF:1]
//
// Neden: PDF'teki şekli EPLAN sembolüyle eşleştirmek için sembolün VEKTÖRÜ gerekir.
// Kataloğu aynı çizim dünyasında (PDF) üretirsek kendi çıkarıcımız onu müşteri belgesiyle
// birebir aynı biçimde okur.
//
// AÇIK PROJEYE DOKUNMAZ: şablondan yeni bir katalog projesi kurar, PDF'i yazar, kapatır.
//
// Her hücreye kısa bir KOD metni (C0001…) basılır. Eşleştirici hücreyi bu kodun PDF'teki
// konumundan bulur; böylece mm ↔ PDF nokta dönüşümünü tahmin etmek gerekmez.
// =====================================================================================
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Base;
using Eplan.EplApi.DataModel;
using Eplan.EplApi.DataModel.Graphics;
using Eplan.EplApi.DataModel.MasterData;
using Eplan.EplApi.HEServices;

namespace Uvp.PdfToP8.Host
{
    public class CatalogAction : IEplAction
    {
        public bool OnRegister(ref string Name, ref int Ordinal)
        {
            Name = "UvpPdfToP8Catalog";
            Ordinal = 20;
            return true;
        }

        public void GetActionProperties(ref ActionProperties actionProperties) { }

        static double Num(string text, double fallback)
        {
            double value;
            return double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value) && value > 0
                ? value : fallback;
        }

        static double[] XY(PointD p) { return new double[] { Math.Round(p.X, 3), Math.Round(p.Y, 3) }; }

        /// <summary>Yerleştirilmiş nesnenin sayfa üzerindeki kutusu. Okunamazsa null.
        /// ÖLÇÜM: `SymbolVariant.GetBoundingBox()` bu sürümde her sembolde NULL erişimi
        /// hatası veriyor (10850/10850). Kutu ancak yerleştirilmiş nesneden okunuyor.</summary>
        static PointD[] Box(Placement placement)
        {
            try
            {
                PointD[] box = placement.GetBoundingBox();
                return box != null && box.Length == 2 ? box : null;
            }
            catch (Exception) { return null; }
        }

        public bool Execute(ActionCallingContext ctx)
        {
            string outDir = Io.Param(ctx, "OUT");
            string template = Io.Param(ctx, "TEMPLATE");
            if (outDir == "") outDir = Path.Combine(Path.GetTempPath(), "uvp_p8catalog");
            Directory.CreateDirectory(outDir);

            string libParam = Io.Param(ctx, "LIB");
            if (libParam == "") libParam = "IEC_symbol,SPECIAL";
            List<string> wantedLibs = new List<string>(libParam.Split(','));
            for (int i = 0; i < wantedLibs.Count; i++) wantedLibs[i] = wantedLibs[i].Trim();

            int max = (int)Num(Io.Param(ctx, "MAX"), 0);
            double cell = Num(Io.Param(ctx, "CELL"), 24);
            double margin = Num(Io.Param(ctx, "MARGIN"), 15);
            bool wantPdf = Io.Param(ctx, "PDF") != "0";

            List<string> log = new List<string>();
            List<object> cells = new List<object>();
            List<object> skipped = new List<object>();
            Dictionary<string, object> report = new Dictionary<string, object>();
            report["contract"] = "uvp.pdf2p8.catalog-layout";
            report["contract_version"] = "1.0";
            report["utc"] = DateTime.UtcNow.ToString("o");
            report["writes_live_project"] = false;
            report["cell_mm"] = cell;
            report["libraries_requested"] = wantedLibs;

            Project prj = null;
            ProjectManager pm = new ProjectManager();
            try
            {
                string elk = Path.Combine(outDir, "UVP_KATALOG_" + Io.Stamp() + ".elk");
                prj = pm.CreateProject(elk, template);
                report["catalog_project"] = prj.ProjectLinkFilePath;
                log.Add("katalog projesi: " + elk);

                List<Page> pages = new List<Page>();
                Page page = null;
                int columns = 0, rows = 0, index = 0, pageNumber = 0, placed = 0;
                double originX = 0, originY = 0;

                using (new LockingStep())
                {
                    foreach (SymbolLibrary lib in prj.SymbolLibraries)
                    {
                        if (!wantedLibs.Contains(lib.Name)) continue;
                        int libCount = 0;
                        foreach (Symbol symbol in lib.Symbols)
                        {
                            int variants = 0;
                            try { variants = symbol.Variants.Length; }
                            catch (Exception ex)
                            {
                                skipped.Add(new Dictionary<string, object> {
                                    { "library", lib.Name }, { "symbol", symbol.Name },
                                    { "reason", "varyant listesi okunamadı: " + ex.Message } });
                                continue;
                            }
                            for (int nr = 0; nr < variants; nr++)
                            {
                                if (max > 0 && placed >= max) break;
                                SymbolVariant sv = null;
                                try { sv = symbol[nr]; }
                                catch (Exception ex)
                                {
                                    skipped.Add(new Dictionary<string, object> {
                                        { "library", lib.Name }, { "symbol", symbol.Name }, { "variant", nr },
                                        { "reason", "varyant okunamadı: " + ex.Message } });
                                    continue;
                                }
                                if (sv == null)
                                {
                                    skipped.Add(new Dictionary<string, object> {
                                        { "library", lib.Name }, { "symbol", symbol.Name }, { "variant", nr },
                                        { "reason", "varyant yok" } });
                                    continue;
                                }

                                if (page == null || index >= columns * rows)
                                {
                                    PagePropertyList names = new PagePropertyList();
                                    names.DESIGNATION_PLANT = "UVPKAT";
                                    names.PAGE_COUNTER = (++pageNumber).ToString(CultureInfo.InvariantCulture);
                                    page = new Page();
                                    page.Create(prj, DocumentTypeManager.DocumentType.Circuit, names);
                                    pages.Add(page);
                                    PointD size = page.Size;
                                    columns = (int)Math.Floor((size.X - 2 * margin) / cell);
                                    rows = (int)Math.Floor((size.Y - 2 * margin) / cell);
                                    if (columns < 1 || rows < 1)
                                        throw new InvalidOperationException("Sayfa hücre için küçük: "
                                            + size.X + "x" + size.Y + " mm, hücre " + cell + " mm");
                                    originX = margin;
                                    originY = size.Y - margin - cell;     // sol ÜST hücreden başla
                                    index = 0;
                                    log.Add("sayfa " + page.Name + " ızgara " + columns + "x" + rows);
                                }

                                int col = index % columns, row = index / columns;
                                double x0 = originX + col * cell, y0 = originY - row * cell;
                                double centerX = x0 + cell / 2, centerY = y0 + cell / 2 + 1.5;   // metne yer bırak
                                string code = "C" + (placed + 1).ToString("0000", CultureInfo.InvariantCulture);

                                SymbolReference reference;
                                try
                                {
                                    reference = SymbolReference.Create(sv, page);
                                    reference.Location = new PointD(centerX, centerY);
                                }
                                catch (Exception ex)
                                {
                                    skipped.Add(new Dictionary<string, object> {
                                        { "library", lib.Name }, { "symbol", symbol.Name }, { "variant", nr },
                                        { "reason", "yerleştirilemedi: " + ex.GetType().Name + ": " + ex.Message } });
                                    continue;
                                }

                                // Kutu ancak yerleştirdikten sonra okunuyor: önce koy, ölç, sığmıyorsa
                                // GERİ AL. Kutusu okunamayan sembol konulur ama `box_unknown` ile
                                // işaretlenir — komşu hücreye taşma riski gizlenmez.
                                PointD[] box = Box(reference);
                                double width = 0, height = 0;
                                if (box != null)
                                {
                                    width = box[1].X - box[0].X; height = box[1].Y - box[0].Y;
                                    if (width > cell - 2 || height > cell - 4)
                                    {
                                        try { reference.Remove(); } catch (Exception) { }
                                        skipped.Add(new Dictionary<string, object> {
                                            { "library", lib.Name }, { "symbol", symbol.Name }, { "variant", nr },
                                            { "reason", "hücreye sığmıyor" },
                                            { "size_mm", new double[] { Math.Round(width, 2), Math.Round(height, 2) } } });
                                        continue;
                                    }
                                    reference.Location = new PointD(
                                        reference.Location.X + centerX - (box[0].X + box[1].X) / 2,
                                        reference.Location.Y + centerY - (box[0].Y + box[1].Y) / 2);
                                }

                                Text label = new Text();
                                label.Create(page, code, 1.5);
                                label.Location = new PointD(x0 + 0.8, y0 + 0.8);

                                List<object> points = new List<object>();
                                try
                                {
                                    PinBase[] connectionPoints = sv.ConnectionPoints;
                                    if (connectionPoints != null)
                                        foreach (PinBase cp in connectionPoints)
                                            points.Add(new Dictionary<string, object> {
                                                { "index", cp.Index },
                                                { "direction", cp.Direction.ToString() },
                                                { "offset", XY(cp.Location) } });
                                }
                                catch (Exception) { }

                                cells.Add(new Dictionary<string, object> {
                                    { "code", code },
                                    { "library", lib.Name },
                                    { "symbol", symbol.Name },
                                    { "variant", nr },
                                    { "symbol_type", symbol.Type.ToString() },
                                    { "page", page.Name },
                                    { "page_number", pageNumber },
                                    { "cell_box_mm", new double[] { Math.Round(x0, 3), Math.Round(y0, 3),
                                                                    Math.Round(x0 + cell, 3), Math.Round(y0 + cell, 3) } },
                                    { "label_point_mm", new double[] { Math.Round(x0 + 0.8, 3), Math.Round(y0 + 0.8, 3) } },
                                    { "size_mm", box == null ? null
                                        : new double[] { Math.Round(width, 3), Math.Round(height, 3) } },
                                    { "box_unknown", box == null },
                                    { "connection_points", points } });
                                index++; placed++; libCount++;
                            }
                            if (max > 0 && placed >= max) break;
                        }
                        log.Add("kütüphane " + lib.Name + ": " + libCount + " varyant kondu");
                        if (max > 0 && placed >= max) break;
                    }
                }

                report["pages"] = pages.Count;
                report["placed"] = placed;
                report["skipped"] = skipped;

                if (wantPdf && pages.Count > 0)
                {
                    string pdf = Path.Combine(outDir, "katalog.pdf");
                    ArrayList list = new ArrayList();
                    foreach (Page p in pages) list.Add(p);
                    try
                    {
                        new Export().PdfPages(list, "", pdf, Export.DegreeOfColor.BlackAndWhite, false, "", false);
                        report["pdf"] = File.Exists(pdf) ? pdf : null;
                        if (!File.Exists(pdf)) report["pdf_error"] = "Export çalıştı ama dosya yok.";
                    }
                    catch (Exception ex)
                    {
                        report["pdf"] = null;
                        report["pdf_error"] = ex.GetType().Name + ": " + ex.Message;
                    }
                }

                report["cells"] = cells;
                report["ok"] = true;
            }
            catch (Exception ex)
            {
                report["ok"] = false;
                report["error"] = ex.GetType().FullName + ": " + ex.Message;
                report["stack"] = ex.StackTrace;
                report["cells"] = cells;
                report["skipped"] = skipped;
            }
            finally
            {
                if (prj != null) { try { prj.Close(); log.Add("katalog projesi kapatıldı."); } catch (Exception) { } }
            }
            report["log"] = log;
            Io.WriteJson(Path.Combine(outDir, "yerlesim.json"), report);
            return true;
        }
    }
}
