// =====================================================================================
// UvpKatalogPdf.cs — K1: sembol kataloğunu ızgara sayfalarına basar, PDF'e verir.
//
// Kullanım: EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//
// Ne yapar: `UvpPdfToP8Catalog` action'ını çalıştırır. Action ŞABLONDAN yeni bir katalog
// projesi kurar, sembolleri hücrelere basar, PDF'i ve yerleşim kaydını yazar, projeyi kapatır.
// AÇIK PROJENE DOKUNMAZ.
//
// Çıktı: <Kök>\output\catalog\katalog.pdf  ve  yerlesim.json
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpKatalogPdf
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Sablon = @"C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9";
    const string Baslik = "UVP · Katalog PDF";

    // EPLAN aynı adlı assembly'yi tek oturumda ikinci kez yükleyemez: en yeni DLL kaydedilir,
    // eskilerin kaydı düşürülür (EPLAN kapatmaya gerek yok).
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
        string cikti = Path.Combine(Kok, @"output\catalog");
        if (dll == null || !File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + bin, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (!File.Exists(Sablon))
        {
            MessageBox.Show("Proje şablonu bulunamadı:\n" + Sablon, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        // Tam katalog 10850 varyanttır ve uzun sürer. Önce küçük bir deneme koşusu
        // yapılabilsin: PDF dışa aktarımı çalışmıyorsa bunu 200 sembolde görmek ucuzdur.
        DialogResult secim = MessageBox.Show(
            "EVET = deneme koşusu (200 sembol)\nHAYIR = tam katalog (10850 varyant, uzun sürer)\n\nAçık projene dokunulmaz.",
            Baslik, MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
        if (secim == DialogResult.Cancel) return;
        string maxParam = secim == DialogResult.Yes ? " /MAX:200" : "";

        Directory.CreateDirectory(cikti);
        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        bool ok = cli.Execute("UvpPdfToP8Catalog /OUT:\"" + cikti + "\" /TEMPLATE:\"" + Sablon + "\"" + maxParam);
        string kayit = Path.Combine(cikti, "yerlesim.json");
        string pdf = Path.Combine(cikti, "katalog.pdf");
        string bilgi = !File.Exists(kayit)
            ? "Action çalıştı ama kayıt yok.\nBeklenen: " + kayit
            : "Yerleşim: " + kayit + "\nPDF: " + (File.Exists(pdf) ? pdf : "YOK — yerlesim.json içindeki pdf_error'a bak");
        MessageBox.Show(bilgi, Baslik, MessageBoxButtons.OK,
                        ok && File.Exists(pdf) ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
