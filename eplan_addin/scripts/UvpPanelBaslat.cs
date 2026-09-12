// =====================================================================================
// UvpPanelBaslat.cs — EPLAN'da TEK ADIM: add-in'i kaydeder ve UVP panelini açar.
//
// Kullanım (EPLAN içinde):
//   Yardımcı programlar > Script'ler > Çalıştır…  →  bu dosyayı seç
//
// Ne yapar:
//   1) `Uvp.PdfToP8.Host.dll` add-in'ini kaydeder (EplApiModuleAction /register)
//   2) `UvpPdfToP8Panel` action'ını çalıştırır → EPLAN içinde UVP penceresi açılır
//
// Script'in kendisi lisans istemez; açtığı add-in API Extension (#725) ister.
// Depo taşınırsa yalnız aşağıdaki `Klasor` sabitini güncelleyin.
// =====================================================================================
using System;
using System.IO;
using System.Windows.Forms;
using Eplan.EplApi.ApplicationFramework;
using Eplan.EplApi.Scripting;

public class UvpPanelBaslat
{
    const string Klasor = @"C:\Users\UVW-U\Desktop\astra 6 test\output\eplan_addin_bin";
    const string DllAdi = "Uvp.PdfToP8.Host.dll";
    const string Baslik = "UVP · PDF → EPLAN P8";

    [Start]
    public void Basla()
    {
        string dll = Path.Combine(Klasor, DllAdi);
        if (!File.Exists(dll))
        {
            MessageBox.Show("Add-in bulunamadı:\n" + dll +
                            "\n\nÖnce derleyin: eplan_addin\\build\\build.bat",
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        CommandLineInterpreter cli = new CommandLineInterpreter();
        if (!cli.Execute("EplApiModuleAction /register:\"" + dll + "\""))
        {
            MessageBox.Show("Add-in kaydedilemedi. API Extension lisansı ve DLL yolunu kontrol edin:\n" + dll,
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }
        if (!cli.Execute("UvpPdfToP8Panel"))
            MessageBox.Show("Panel açılamadı. Add-in yüklendi ama action çalışmadı.",
                            Baslik, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
