// =====================================================================================
// UvpP8Remote — EPLAN'ı dışarıdan süren küçük araç (resmi EplanRemoteClient API'si).
//
// Neden: `EplApiModuleAction /register:` EPLAN'ın komut YORUMLAYICISINDA çalışır; açılış
// komut satırında çalışmıyor (denendi: EPLAN açıldı, action işlemedi). RemoteClient ise
// çalışan EPLAN'a bağlanıp action yürütür.
//
//   UvpP8Remote.exe --args "/Variant:\"Pro Panel\" /NoSplash"
//                   --action "EplApiModuleAction /register:\"...dll\""
//                   --action "UvpPdfToP8Probe /OUT:\"...\" /TEMPLATE:\"...\""
//                   --action "EplApiModuleAction /unregister:\"Uvp.PdfToP8.Host\""
//                   --stop
//
// Varsayılan: KENDİ EPLAN örneğini başlatır. Zaten açık bir EPLAN varsa DOKUNMAZ; ona
// bağlanmak için açıkça `--attach` gerekir (kullanıcının oturumu korunur).
// =====================================================================================
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Eplan.EplApi.RemoteClient;

namespace Uvp.PdfToP8.Remote
{
    public static class RemoteRunner
    {
        static string _bin = @"C:\Program Files\EPLAN\Platform\2026.0.3\Bin";

        /// <summary>Bağımlılıklar EPLAN kurulumundan çözülür; hiçbir DLL kopyalanmaz.
        /// Grpc.Core'un istediği System.Memory, EPLAN'ın Common\IdentityClient klasöründedir.</summary>
        static List<string> ProbeDirs()
        {
            List<string> dirs = new List<string>();
            dirs.Add(_bin);
            DirectoryInfo dir = new DirectoryInfo(_bin).Parent;                 // 2026.0.3
            if (dir != null) dir = dir.Parent;                                  // Platform
            if (dir != null) dir = dir.Parent;                                  // EPLAN
            if (dir != null) dirs.Add(Path.Combine(dir.FullName, "Common", "IdentityClient"));
            return dirs;
        }

        public static int Main(string[] args)
        {
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs e)
            {
                string name = new AssemblyName(e.Name).Name;
                foreach (string dir in ProbeDirs())
                {
                    string path = Path.Combine(dir, name + ".dll");
                    if (File.Exists(path)) return Assembly.LoadFrom(path);
                }
                return null;
            };
            return Run(args);
        }

        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        static int Run(string[] args)
        {
            string exe = Path.Combine(_bin, "EPLAN.exe"), startArgs = "/Variant:\"Pro Panel\" /NoSplash";
            List<string> actions = new List<string>();
            bool attach = false, stop = false;
            for (int i = 0; i < args.Length; i++)
            {
                string key = args[i];
                string value = i + 1 < args.Length ? args[i + 1] : "";
                if (key == "--exe") { exe = value; i++; }
                else if (key == "--bin") { _bin = value; i++; }
                else if (key == "--args") { startArgs = value; i++; }
                else if (key == "--action") { actions.Add(value); i++; }
                // Tırnaklı yolları kabuk kaçışına kurban etmemek için: her satır bir action.
                else if (key == "--actions-file")
                {
                    foreach (string line in File.ReadAllLines(value, System.Text.Encoding.UTF8))
                        if (line.Trim() != "" && !line.TrimStart().StartsWith("#")) actions.Add(line.Trim());
                    i++;
                }
                else if (key == "--attach") attach = true;
                else if (key == "--stop") stop = true;
                else { Console.Error.WriteLine("Bilinmeyen argüman: " + key); return 2; }
            }
            // Yerel grpc yerel kütüphanesi EPLAN Bin'de; süreç onu bulabilsin.
            Environment.SetEnvironmentVariable("PATH", _bin + ";" + Environment.GetEnvironmentVariable("PATH"));

            EplanRemoteClient client = new EplanRemoteClient();
            client.SynchronousMode = true;
            List<EplanServerData> active = new List<EplanServerData>();
            client.GetActiveEplanServersOnLocalMachine(out active);
            Console.WriteLine("Açık EPLAN sunucusu: " + active.Count);
            EplanServerData server = null;
            bool started = false;
            try
            {
                if (active.Count > 0 && attach)
                {
                    server = active[0];
                    Console.WriteLine("Açık oturuma bağlanılıyor: " + server.ServerName + ":" + server.ServerPort
                                      + " (PID " + server.EplanProcessID + ")");
                }
                else if (active.Count > 0)
                {
                    Console.Error.WriteLine("Açık bir EPLAN var; kullanıcının oturumuna dokunulmaz. "
                                            + "Bilerek bağlanmak için --attach verin.");
                    return 3;
                }
                else
                {
                    Console.WriteLine("EPLAN başlatılıyor: " + exe + " " + startArgs);
                    server = client.StartEplan(exe, startArgs);
                    started = true;
                    Console.WriteLine("Başladı: " + server.ServerName + ":" + server.ServerPort
                                      + " sürüm " + server.EplanVersion + " PID " + server.EplanProcessID
                                      + (string.IsNullOrEmpty(server.ErrorMsg) ? "" : " hata: " + server.ErrorMsg));
                }
                client.Connect(server.ServerName, server.ServerPort.ToString());
                Console.WriteLine("Bağlandı. Ping: " + client.Ping());
                int failed = 0;
                foreach (string action in actions)
                {
                    bool ok = client.ExecuteAction(action);
                    Console.WriteLine((ok ? "TAMAM  " : "HATA   ") + action);
                    if (!ok) failed++;
                }
                if (stop && started)
                {
                    Console.WriteLine("EPLAN kapatılıyor (StopEplan): " + client.StopEplan());
                }
                else if (stop)
                {
                    Console.WriteLine("Açık oturum bizim değil; kapatılmadı.");
                }
                return failed == 0 ? 0 : 1;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.GetType().FullName + ": " + ex.Message);
                return 4;
            }
            finally
            {
                try { client.Disconnect(); } catch (Exception) { }
            }
        }
    }
}
