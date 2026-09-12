// =====================================================================================
// UvpSembolOku.cs — sembol geometrisini kütüphaneden doğrudan okur (PDF'e basmadan).
//
// Kullanım: EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//
// Ne yapar: `UvpPdfToP8Symbols` action'ını çalıştırır. Açık proje varsa ONUN kütüphanelerini
// YALNIZ OKUR (hiçbir şey yazmaz, sayfa açmaz); açık proje yoksa şablondan geçici bir proje
// açıp sonunda kapatır.
//
// Çıktı: <Kök>\output\catalog\semboller.json
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpSembolOku
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Sablon = @"C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9";
    const string Baslik = "UVP · Sembol geometrisi";

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
        // Önce küçük bir deneme: SubPlacements okunmuyorsa bunu 50 sembolde görmek ucuzdur.
        DialogResult secim = MessageBox.Show(
            "EVET = deneme (50 sembol)\nHAYIR = tüm kütüphaneler\n\nAçık projene YAZILMAZ, yalnız okunur.",
            Baslik, MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
        if (secim == DialogResult.Cancel) return;
        string maxParam = secim == DialogResult.Yes ? " /MAX:50" : "";
        // Projede hangi kütüphane varsa hepsi okunur (IEC_symbol, SPECIAL, firma kütüphanesi…).
        maxParam += " /LIB:*";
        // Sembol kütüphanelerinin kendi klasörü: projeye kayıtlı olmayanlar da okunsun.
        string[] semboller = new string[] {
            @"C:\Users\Public\Eplan\Data\Semboller",
            @"C:\Users\Public\EPLAN\Data\Symbols" };
        foreach (string k in semboller)
            if (Directory.Exists(k)) { maxParam += " /DIR:\"" + k + "\""; break; }

        Directory.CreateDirectory(cikti);
        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        bool ok = cli.Execute("UvpPdfToP8Symbols /OUT:\"" + cikti + "\" /TEMPLATE:\"" + Sablon + "\"" + maxParam);
        string dosya = Path.Combine(cikti, "semboller.json");
        string bilgi = File.Exists(dosya)
            ? "Yazıldı: " + dosya + "\nBoyut: " + new FileInfo(dosya).Length + " bayt"
            : "Action çalıştı ama dosya yok.\nBeklenen: " + dosya;
        MessageBox.Show(bilgi, Baslik, MessageBoxButtons.OK,
                        ok && File.Exists(dosya) ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
