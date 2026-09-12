// =====================================================================================
// UvpPdfToP8Panel — aracın EPLAN'IN İÇİNDE açılan penceresi (tarayıcı değil).
//
//   UvpPdfToP8Panel [/ROOT:"<proje klasörü>"] [/PORT:<port>] [/PYTHON:"<python.exe>"]
//
// Pencere WebView2 ile YEREL motora bağlanır (127.0.0.1, yalnız bu makine). Motor yoksa
// add-in başlatır; pencere kapanınca yalnız KENDİ başlattığı motoru kapatır.
//
// Sayfadan gelen mesajlar (WebView2 köprüsü) SINIRLIDIR: 'ping', 'pickPdf', 'catalog', 'import'. Sayfadan gelen
// keyfi komut yürütülmez. 'import' yalnız `UvpPdfToP8Import` action'ını çağırır; o da her
// çalıştırmada ŞABLONDAN YENİ test projesi oluşturur, açık/canlı projeye yazmaz.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Uvp.PdfToP8.Host
{
    public class PanelAction : IEplAction
    {
        public bool OnRegister(ref string Name, ref int Ordinal)
        {
            Name = "UvpPdfToP8Panel";
            Ordinal = 20;
            return true;
        }

        public void GetActionProperties(ref ActionProperties actionProperties) { }

        public bool Execute(ActionCallingContext ctx)
        {
            string root = Io.Param(ctx, "ROOT"), port = Io.Param(ctx, "PORT"), python = Io.Param(ctx, "PYTHON");
            if (root == "") root = PanelForm.GuessRoot();
            if (python == "") python = PanelForm.GuessPython();
            int number;
            if (!int.TryParse(port, out number)) number = 8791;
            // MODELESS: pencere açıkken EPLAN kullanılmaya devam eder. Modal ShowDialog
            // EPLAN'ın arayüz iş parçacığını kilitliyordu.
            if (PanelForm.Instance != null && !PanelForm.Instance.IsDisposed)
            {
                PanelForm.Instance.BringToFront();
                PanelForm.Instance.Activate();
                return true;
            }
            PanelForm.Instance = new PanelForm(root, number, python);
            PanelForm.Instance.Show();
            return true;
        }
    }

    public class PanelForm : Form
    {
        public static PanelForm Instance;
        readonly string _root, _python;
        readonly int _port;
        readonly WebView2 _web = new WebView2();
        readonly Label _status = new Label();
        Process _engine;                     // yalnız bizim başlattığımız motor

        public PanelForm(string root, int port, string python)
        {
            _root = root; _port = port; _python = python;
            Text = "UVP · PDF → EPLAN P8";
            StartPosition = FormStartPosition.CenterScreen;
            Width = 1400; Height = 900;
            _status.Dock = DockStyle.Bottom; _status.Height = 22; _status.TextAlign = ContentAlignment.MiddleLeft;
            _status.Text = "Motor başlatılıyor…";
            _web.Dock = DockStyle.Fill;
            Controls.Add(_web); Controls.Add(_status);
            Load += OnLoaded;
            FormClosed += OnClosed;
        }

        public static string GuessRoot()
        {
            // DLL <kök>\output\eplan_addin_bin altında durur.
            string dll = Path.GetDirectoryName(new Uri(typeof(PanelForm).Assembly.CodeBase).LocalPath);
            DirectoryInfo dir = new DirectoryInfo(dll);
            while (dir != null && !File.Exists(Path.Combine(dir.FullName, "analyzer_v3", "server.py")))
                dir = dir.Parent;
            return dir == null ? dll : dir.FullName;
        }

        public static string GuessPython()
        {
            foreach (string dir in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
            {
                if (dir.Trim() == "") continue;
                try
                {
                    string candidate = Path.Combine(dir.Trim(), "python.exe");
                    if (File.Exists(candidate)) return candidate;
                }
                catch (ArgumentException) { }
            }
            // EPLAN süreci PATH'i kullanıcının kabuğundan farklı olabilir: bilinen kurulum
            // klasörleri de denenir. Bulunamazsa panel bunu açıkça yazar.
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            List<string> roots = new List<string> { Path.Combine(local, "Programs", "Python"),
                                                    @"C:\Program Files\Python312",
                                                    @"C:\Program Files\Python311",
                                                    @"C:\Program Files\Python310" };
            foreach (string root in roots)
            {
                if (!Directory.Exists(root)) continue;
                string direct = Path.Combine(root, "python.exe");
                if (File.Exists(direct)) return direct;
                try
                {
                    foreach (string sub in Directory.GetDirectories(root))
                    {
                        string candidate = Path.Combine(sub, "python.exe");
                        if (File.Exists(candidate)) return candidate;
                    }
                }
                catch (IOException) { }
            }
            return "python";
        }

        bool EngineAnswers()
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + _port + "/api/pages");
                request.Timeout = 2000;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                    return response.StatusCode == HttpStatusCode.OK;
            }
            catch (WebException) { return false; }
        }

        void Status(string text)
        {
            if (IsDisposed) return;
            if (InvokeRequired) BeginInvoke((MethodInvoker)delegate { if (!IsDisposed) _status.Text = text; });
            else _status.Text = text;
        }

        /// <summary>Motoru AYRI iş parçacığında başlatır: EPLAN'ın arayüzü beklemez.</summary>
        void StartEngineAsync()
        {
            System.Threading.Thread worker = new System.Threading.Thread(delegate()
            {
                try
                {
                    if (!EngineAnswers())
                    {
                        if (!File.Exists(_python) && _python != "python")
                            Status("Python bulunamadı: " + _python);
                        ProcessStartInfo info = new ProcessStartInfo(_python, "-m analyzer_v3.server --port " + _port);
                        info.WorkingDirectory = _root;
                        info.UseShellExecute = false;
                        info.CreateNoWindow = true;
                        Status("Motor başlatılıyor: " + _python + " (klasör: " + _root + ")");
                        _engine = Process.Start(info);
                        for (int i = 0; i < 40 && !EngineAnswers(); i++)
                            System.Threading.Thread.Sleep(500);
                    }
                    if (EngineAnswers())
                    {
                        Status("Motor hazır (port " + _port + ", yalnız bu bilgisayar).");
                        BeginInvoke((MethodInvoker)delegate { Navigate(); });
                    }
                    else
                    {
                        Status("Motor yanıt vermedi: " + _python + " -m analyzer_v3.server --port " + _port
                               + " (klasör: " + _root + ")");
                    }
                }
                catch (Exception ex)
                {
                    Status("Motor başlatılamadı: " + ex.GetType().Name + ": " + ex.Message);
                }
            });
            worker.IsBackground = true;
            worker.Start();
        }

        void Navigate()
        {
            if (_web.CoreWebView2 != null) _web.CoreWebView2.Navigate("http://127.0.0.1:" + _port + "/");
        }

        async void OnLoaded(object sender, EventArgs e)
        {
            try
            {
                string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                           "UVP", "PdfToP8", "WebView2");
                Directory.CreateDirectory(data);
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, data, null);
                await _web.EnsureCoreWebView2Async(env);
                _web.CoreWebView2.Settings.AreDevToolsEnabled = false;
                _web.CoreWebView2.Settings.IsStatusBarEnabled = false;
                _web.CoreWebView2.WebMessageReceived += OnMessage;
                StartEngineAsync();                       // motor hazır olunca sayfa yüklenir
            }
            catch (Exception ex)
            {
                _status.Text = "Panel açılamadı: " + ex.GetType().Name + ": " + ex.Message;
            }
        }

        void Reply(object value)
        {
            _web.CoreWebView2.PostWebMessageAsJson(new JavaScriptSerializer().Serialize(value));
        }

        /// <summary>Sayfadan gelen mesaj. YALNIZ bilinen işler: durum, PDF seçme, aktarım.</summary>
        void OnMessage(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            Dictionary<string, object> message;
            try { message = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(e.WebMessageAsJson); }
            catch (Exception ex) { Reply(new Dictionary<string, object> { { "ok", false }, { "error", ex.Message } }); return; }
            string action = message != null && message.ContainsKey("action") ? Convert.ToString(message["action"]) : "";
            Dictionary<string, object> answer = new Dictionary<string, object>();
            answer["action"] = action;
            try
            {
                if (action == "ping")
                {
                    answer["ok"] = true;
                    answer["host"] = "EPLAN";
                    answer["eplan_version"] = Process.GetCurrentProcess().MainModule.FileVersionInfo.FileVersion;
                }
                else if (action == "pickPdf")
                {
                    // Dosya seçme penceresi EPLAN'ın içinde açılır; sayfa dosya sistemine erişmez.
                    using (OpenFileDialog dialog = new OpenFileDialog())
                    {
                        dialog.Title = "Şema PDF'i seç";
                        dialog.Filter = "PDF (*.pdf)|*.pdf";
                        dialog.CheckFileExists = true;
                        bool chosen = dialog.ShowDialog(this) == DialogResult.OK;
                        answer["ok"] = chosen;
                        answer["path"] = chosen ? dialog.FileName : "";
                        if (chosen) _status.Text = "PDF: " + dialog.FileName;
                    }
                }
                else if (action == "catalog")
                {
                    // Sembol kataloğu: şablondan YENİ test projesi açar, kataloğu yazar, kapatır.
                    string outDir = message.ContainsKey("out") ? Convert.ToString(message["out"])
                                                               : Path.Combine(_root, "output", "p8test", "probe");
                    string template = message.ContainsKey("template") ? Convert.ToString(message["template"]) : "";
                    ActionCallingContext call = new ActionCallingContext();
                    call.AddParameter("OUT", outDir);
                    call.AddParameter("TEMPLATE", template);
                    Eplan.EplApi.ApplicationFramework.Action probe =
                        new ActionManager().FindAction("UvpPdfToP8Probe");
                    if (probe == null) throw new InvalidOperationException("UvpPdfToP8Probe action bulunamadı.");
                    _status.Text = "Katalog alınıyor…";
                    bool done = probe.Execute(call);
                    answer["ok"] = done;
                    answer["catalog"] = Path.Combine(outDir, "capabilities.json");
                    _status.Text = done ? "Katalog yazıldı: " + outDir : "Katalog alınamadı.";
                }
                else if (action == "import")
                {
                    string package = Convert.ToString(message["package"]);
                    string mapping = message.ContainsKey("mapping") ? Convert.ToString(message["mapping"]) : "";
                    string outDir = message.ContainsKey("out") ? Convert.ToString(message["out"])
                                                              : Path.Combine(_root, "output", "p8test", "panel");
                    string template = message.ContainsKey("template") ? Convert.ToString(message["template"]) : "";
                    if (!File.Exists(package)) throw new FileNotFoundException("Paket bulunamadı: " + package);
                    if (mapping == "" || !File.Exists(mapping))
                        throw new InvalidOperationException("Sembol eşlemesi yok: önce katalog alınıp eşleme yazılmalı.");
                    ActionCallingContext call = new ActionCallingContext();
                    call.AddParameter("PACKAGE", package);
                    call.AddParameter("MAPPING", mapping);
                    call.AddParameter("OUT", outDir);
                    call.AddParameter("TEMPLATE", template);
                    Eplan.EplApi.ApplicationFramework.Action importer =
                        new ActionManager().FindAction("UvpPdfToP8Import");
                    if (importer == null)
                        throw new InvalidOperationException("UvpPdfToP8Import action bulunamadı; add-in yüklü mü?");
                    bool ok = importer.Execute(call);
                    answer["ok"] = ok;
                    answer["receipt"] = Path.Combine(outDir, "receipt.json");
                    answer["readback"] = Path.Combine(outDir, "readback.json");
                    _status.Text = ok ? "Aktarım çalıştı; makbuz ve geri okuma yazıldı." : "Aktarım başarısız.";
                }
                else
                {
                    answer["ok"] = false;
                    answer["error"] = "Bilinmeyen istek: " + action;
                }
            }
            catch (Exception ex)
            {
                answer["ok"] = false;
                answer["error"] = ex.GetType().Name + ": " + ex.Message;
                _status.Text = "Hata: " + ex.Message;
            }
            Reply(answer);
        }

        void OnClosed(object sender, FormClosedEventArgs e)
        {
            // Kullanıcının kendi başlattığı motora dokunulmaz; yalnız bizimki kapatılır.
            if (_engine != null && !_engine.HasExited)
            {
                try { _engine.Kill(); } catch (InvalidOperationException) { }
            }
            _web.Dispose();
        }
    }
}
