// =====================================================================================
// UvpCihazDene.cs — bir ürün kodundan EPLAN'ın hangi fonksiyonları oluşturduğunu ölçer.
//
// Kullanım: EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//   Ürün kodunu sorar (varsayılan PLC: SIE.6ES7131-6BF01-0BA0). Geçici projede cihazı
//   parçadan oluşturur (Cihaz Gezgini ile aynı iş), her fonksiyonu ayrı noktaya yerleştirmeyi
//   dener, sonucu yazar ve geçici projeyi kapatır. AÇIK PROJENE DOKUNMAZ.
//
// Çıktı: output\p8test\device_probe\cihaz_deneme.json
// =====================================================================================
using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpCihazDene
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Sablon = @"C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9";
    const string Baslik = "UVP · cihaz denemesi";

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

    static string KodSor()
    {
        using (Form form = new Form())
        using (TextBox kutu = new TextBox())
        using (Button tamam = new Button())
        {
            form.Text = Baslik;
            form.ClientSize = new Size(420, 90);
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.StartPosition = FormStartPosition.CenterScreen;
            kutu.SetBounds(12, 14, 396, 24);
            kutu.Text = "SIE.6ES7131-6BF01-0BA0";
            tamam.Text = "Dene";
            tamam.SetBounds(318, 50, 90, 28);
            tamam.DialogResult = DialogResult.OK;
            form.Controls.Add(kutu);
            form.Controls.Add(tamam);
            form.AcceptButton = tamam;
            return form.ShowDialog() == DialogResult.OK ? kutu.Text.Trim() : null;
        }
    }

    [Start]
    public void Basla()
    {
        string bin = Path.Combine(Kok, @"output\eplan_addin_bin");
        CommandLineInterpreter cliBul = new CommandLineInterpreter();
        string dll = Directory.Exists(bin) ? EnYeniDll(bin, cliBul) : null;
        string cikti = Path.Combine(Kok, @"output\p8test\device_probe");
        if (dll == null || !File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + bin, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        string kod = KodSor();
        if (string.IsNullOrEmpty(kod)) return;

        Directory.CreateDirectory(cikti);
        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        bool ok = cli.Execute("UvpPdfToP8DeviceProbe /PART:\"" + kod + "\" /OUT:\"" + cikti +
                              "\" /TEMPLATE:\"" + Sablon + "\"");
        string dosya = Path.Combine(cikti, "cihaz_deneme.json");
        string bilgi = File.Exists(dosya)
            ? "Yazıldı: " + dosya + "\nBoyut: " + new FileInfo(dosya).Length + " bayt"
            : "Action çalıştı ama dosya yok.\nBeklenen: " + dosya;
        MessageBox.Show(bilgi, Baslik, MessageBoxButtons.OK,
                        ok && File.Exists(dosya) ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
