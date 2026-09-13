// =====================================================================================
// UvpSayfaDok.cs — açık sayfadaki her nesneyi, sayfa çerçevesini ve katmanları dosyaya döker.
//
// Kullanım: şablon sayfasını aç ('U' ile taslak yerleri görünen sayfa), sonra
//   EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//   Taslak yerleri (Sigorta/MKŞ, PLC IO, Klemens ...) sayfada mı, çerçevede mi, hangi
//   katmanda — bu döküm gösterir; cihazları sayfaya yaymak için bu veri kullanılacak.
//   PROJEYİ DEĞİŞTİRMEZ, yalnız okur.
//
// Çıktı: output\p8test\page_probe\sayfa_dokum.json
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpSayfaDok
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Baslik = "UVP · sayfa dökümü";

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
        CommandLineInterpreter cli = new CommandLineInterpreter();
        string dll = Directory.Exists(bin) ? EnYeniDll(bin, cli) : null;
        if (dll == null || !File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + bin, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        string cikti = Path.Combine(Kok, @"output\p8test\page_probe");
        Directory.CreateDirectory(cikti);
        bool ok = cli.Execute("UvpPdfToP8PageProbe /OUT:\"" + cikti + "\"");
        string dosya = Path.Combine(cikti, "sayfa_dokum.json");
        string bilgi = File.Exists(dosya)
            ? "Yazıldı: " + dosya + "\nBoyut: " + new FileInfo(dosya).Length + " bayt"
            : "Action çalıştı ama dosya yok.\nBeklenen: " + dosya;
        MessageBox.Show(bilgi, Baslik, MessageBoxButtons.OK,
                        ok && File.Exists(dosya) ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
