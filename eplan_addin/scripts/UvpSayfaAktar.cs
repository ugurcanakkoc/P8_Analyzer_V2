// =====================================================================================
// UvpSayfaAktar.cs — JSON seç, sayfayı EPLAN'da oluştur. Tek adım.
//
// Kullanım: EPLAN > Yardımcı programlar > Script'ler > Çalıştır… > bu dosya
//   1) "Açık projeye yazayım mı?" sorusu (Evet = açık projene yazar)
//   2) Dosya penceresi → PDF analizinden çıkan sayfa paketi (*.json)
//   3) Sayfa(lar) oluşturulur, cihazlar yerleşir, bağlantılar üretilir, sonuç geri okunur
//   4) Kısa özet kutusu: hangi sayfa, kaç nesne, kaç bağlantı, ne reddedildi
//
// Açık projeye yazarken VAR OLAN sayfalar değiştirilmez; yalnız yeni sayfa eklenir ve
// işlem tek bir geri alma adımıdır (Ctrl+Z ile geri alınır).
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpSayfaAktar
{
    const string Kok = @"C:\Users\UVW-U\Desktop\astra 6 test";
    const string Sablon = @"C:\ProgramData\EPLAN\O_Data\Electric P8 Data\2026.0.3\Templates\EPLAN\IEC_bas001.zw9";
    const string Baslik = "UVP · sayfa aktarımı";

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
        string esleme = Path.Combine(Kok, @"output\exchange\proof_s03\mapping.json");
        string cikti = Path.Combine(Kok, @"output\p8test\import");
        if (dll == null || !File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + dll, Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        if (!File.Exists(esleme))
        {
            MessageBox.Show("Sembol eşlemesi yok:\n" + esleme + "\n\nÖnce UvpKatalog.cs çalıştırılmalı.",
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        DialogResult secim = MessageBox.Show(
            "AÇIK projene yazayım mı?\n\n" +
            "Evet : açık projende yeni sayfa oluşturulur (var olan sayfalara dokunulmaz, Ctrl+Z ile geri alınır)\n" +
            "Hayır: ayrı bir test projesi oluşturulur",
            Baslik, MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
        if (secim == DialogResult.Cancel) return;
        bool acikProje = secim == DialogResult.Yes;

        string paket;
        using (OpenFileDialog dialog = new OpenFileDialog())
        {
            dialog.Title = "Sayfa paketi (JSON) seç";
            dialog.Filter = "Sayfa paketi (*.json)|*.json";
            dialog.InitialDirectory = Path.Combine(Kok, @"output\exchange");
            dialog.CheckFileExists = true;
            if (dialog.ShowDialog() != DialogResult.OK) return;
            paket = dialog.FileName;
        }

        // Paketin yanında kendi eşleme dosyası varsa O kullanılır (müşteri profilinden
        // üretilir); yoksa eski ortak eşlemeye düşülür.
        string yanEsleme = Path.Combine(Path.GetDirectoryName(paket),
            Path.GetFileNameWithoutExtension(paket).Replace("_tum_sayfalar", "") + "_mapping.json");
        if (File.Exists(yanEsleme)) esleme = yanEsleme;

        Directory.CreateDirectory(cikti);
        string ozetDosya = Path.Combine(cikti, "ozet.txt");
        if (File.Exists(ozetDosya)) File.Delete(ozetDosya);       // eski özet yeni sonuç sanılmasın

        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi (API Extension lisansı?).\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        // Önce KÜÇÜK dene: 36 sayfa bir anda EPLAN'ı çökertti. Sayfa numarası PDF'in fiziksel
        // sayfasıdır (örn. PLC için 38). Boş bırakılırsa bütün sayfalar aktarılır.
        string sayfalar = "";
        using (Form form = new Form())
        using (Label yazi = new Label())
        using (TextBox kutu = new TextBox())
        using (Button tamam = new Button())
        {
            form.Text = Baslik;
            form.Width = 460; form.Height = 170;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.StartPosition = FormStartPosition.CenterScreen;
            yazi.Text = "Hangi sayfalar? (PDF sayfa no, virgülle — örn. 38 veya 4,5). Boş = hepsi";
            yazi.Left = 12; yazi.Top = 12; yazi.Width = 420;
            kutu.Left = 12; kutu.Top = 40; kutu.Width = 420; kutu.Text = "38";
            tamam.Text = "Aktar"; tamam.Left = 342; tamam.Top = 80; tamam.Width = 90;
            tamam.DialogResult = DialogResult.OK;
            form.Controls.Add(yazi); form.Controls.Add(kutu); form.Controls.Add(tamam);
            form.AcceptButton = tamam;
            if (form.ShowDialog() != DialogResult.OK) return;
            sayfalar = kutu.Text.Replace(" ", "");
        }

        bool ok = cli.Execute("UvpPdfToP8Import /PACKAGE:\"" + paket + "\" /MAPPING:\"" + esleme +
                              "\" /OUT:\"" + cikti + "\" /TEMPLATE:\"" + Sablon + "\"" +
                              (sayfalar != "" ? " /PAGES:\"" + sayfalar + "\"" : "") +
                              (acikProje ? " /TARGET:OPEN" : ""));

        string ozet = File.Exists(ozetDosya) ? File.ReadAllText(ozetDosya) : "(özet dosyası yazılmadı)";
        MessageBox.Show("Paket: " + Path.GetFileName(paket) + "\n\n" + ozet +
                        "\nAyrıntı: " + cikti,
                        Baslik, MessageBoxButtons.OK,
                        ok ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
    }
}
