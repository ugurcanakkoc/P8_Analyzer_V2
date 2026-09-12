// =====================================================================================
// UvpKatalog.cs — EPLAN sembol kataloğunu dosyaya yazar. Tek adım, panel/motor yok.
//
// Kullanım: EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//
// Ne yapar: add-in'i kaydeder, `UvpPdfToP8Probe` action'ını çalıştırır. Action ŞABLONDAN
// YENİ bir test projesi açar, IEC_symbol + SPECIAL kataloğunu JSON'a yazar ve projeyi kapatır.
// AÇIK PROJENE DOKUNMAZ.
//
// Çıktı: <Cikti>\capabilities.json
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpKatalog
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Sablon = @"C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9";
    const string Baslik = "UVP · EPLAN kataloğu";

    // EPLAN aynı adlı assembly'yi tek oturumda ikinci kez yükleyemez: her derleme ayrı isimli
    // DLL üretir. En YENİSİ kaydedilir, eskilerin kaydı düşürülür (EPLAN kapatmaya gerek yok).
    static string EnYeniDll(string klasor, CommandLineInterpreter cli)
    {
        string[] dosyalar = Directory.GetFiles(klasor, "Uvp.PdfToP8.Host*.dll");
        if (dosyalar.Length == 0) return null;
        string yeni = dosyalar[0];
        foreach (string d in dosyalar)
            if (File.GetLastWriteTimeUtc(d) > File.GetLastWriteTimeUtc(yeni)) yeni = d;
        foreach (string d in dosyalar)
        {
            if (d == yeni) continue;
            try { cli.Execute("EplApiModuleAction /unregister:\"" + Path.GetFileNameWithoutExtension(d) + "\""); }
            catch (Exception) { }
        }
        return yeni;
    }

    [Start]
    public void Basla()
    {
        string bin = Path.Combine(Kok, @"output\eplan_addin_bin");
        CommandLineInterpreter cliBul = new CommandLineInterpreter();
        string dll = Directory.Exists(bin) ? EnYeniDll(bin, cliBul) : null;
        string cikti = Path.Combine(Kok, @"output\p8test\probe");
        if (dll == null || !File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + dll, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (!File.Exists(Sablon))
        {
            MessageBox.Show("Proje şablonu bulunamadı:\n" + Sablon, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        Directory.CreateDirectory(cikti);
        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        bool ok = cli.Execute("UvpPdfToP8Probe /OUT:\"" + cikti + "\" /TEMPLATE:\"" + Sablon + "\"");
        string dosya = Path.Combine(cikti, "capabilities.json");
        string bilgi = ok && File.Exists(dosya)
            ? "Katalog yazıldı:\n" + dosya + "\n\nBoyut: " + new FileInfo(dosya).Length + " bayt"
            : "Action çalıştı ama dosya yok.\nBeklenen: " + dosya;
        MessageBox.Show(bilgi, Baslik, MessageBoxButtons.OK,
                        ok && File.Exists(dosya) ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
