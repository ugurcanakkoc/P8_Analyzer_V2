"""
Internationalization (i18n) module for P8 Analyzer GUI.

Provides multi-language support for UI labels.
Supported languages: English (en), German (de), Turkish (tr)
"""

from typing import Dict

# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Window
        "window_title": "P8 Analyzer - Professional Vector Analyzer",

        # Toolbar
        "toolbar_name": "Tools",
        "btn_open_pdf": "Open PDF",
        "btn_prev": "Previous",
        "btn_next": "Next",
        "btn_analyze": "Analyze",
        "btn_ocr_test": "OCR vs PDF",
        "btn_navigate": "Navigate",
        "btn_draw_box": "Draw Box",
        "btn_connection_check": "Check Connections",

        # Page label
        "page_label": "Page: {current} / {total}",
        "page_label_empty": "Page: -/-",

        # Dock panels
        "dock_logs": "Logs",
        "dock_connections": "Connection List",

        # Table headers
        "header_line_bus": "Line/Bus",
        "header_pin_end": "Pin/End",
        "header_target": "Target",
        "header_pin": "Pin",

        # Messages
        "msg_auto_loading": "Auto loading: {path}",
        "msg_file_not_found": "'{path}' not found.",
        "msg_select_pdf": "Select PDF",
        "msg_error": "Error",
        "msg_page_error": "Page error: {error}",
        "msg_mode": "Mode: {mode}",
        "msg_analyzing": "Analyzing page {page}...",
        "msg_analysis_complete": "Analysis complete. {count} lines found.",
        "msg_connection_report": "====== CONNECTION REPORT ======",
        "msg_warning_no_pin": "WARNING: No pin detected in device/terminal '{comp}' (Line: {net}).",
        "msg_no_valid_connections": "No valid connections found for table.",
        "msg_no_vector_data": "No vector data found on this page.",

        # Page Classification
        "btn_classify_mode": "Classify Pages",
        "btn_save_classifications": "Save Classifications",
        "classify_schematic": "Schematic [S]",
        "classify_non_schematic": "Non-Schematic [N]",
        "classify_skip": "Skip [Space]",
        "msg_classified_schematic": "Page {page} marked as SCHEMATIC",
        "msg_classified_non_schematic": "Page {page} marked as NON-SCHEMATIC",
        "msg_classification_mode_on": "Classification Mode ON - Press S (schematic), N (non-schematic), Space (skip)",
        "msg_classification_mode_off": "Classification Mode OFF",
        "msg_classifications_saved": "Classifications saved to: {path}",
        "msg_classification_stats": "Classified: {schematic} schematic, {non_schematic} non-schematic, {total} total",
        "msg_export_complete": "Exported {count} images to: {path}",
        "lbl_classification_status": "[{status}]",

        # Schematic Filter
        "btn_schematic_filter": "Schematics Only",
        "msg_filter_scanning": "Scanning pages for schematics...",
        "msg_filter_complete": "Found {count} schematic pages out of {total}",
        "msg_filter_on": "Schematic filter ON - Showing {count} pages",
        "msg_filter_off": "Schematic filter OFF - Showing all pages",
        "page_label_filtered": "Page: {current} / {total} (Schematic {idx}/{count})",
        "msg_model_not_found": "Page classifier model not found. Please train the model first.",
        "msg_model_loaded": "Page classifier model loaded",
    },

    "de": {
        # Window
        "window_title": "P8 Analyzer - Professioneller Vektor-Analysator",

        # Toolbar
        "toolbar_name": "Werkzeuge",
        "btn_open_pdf": "PDF öffnen",
        "btn_prev": "Zurück",
        "btn_next": "Weiter",
        "btn_analyze": "Analysieren",
        "btn_ocr_test": "OCR vs PDF",
        "btn_navigate": "Navigieren",
        "btn_draw_box": "Box zeichnen",
        "btn_connection_check": "Verbindungen prüfen",

        # Page label
        "page_label": "Seite: {current} / {total}",
        "page_label_empty": "Seite: -/-",

        # Dock panels
        "dock_logs": "Protokoll",
        "dock_connections": "Verbindungsliste",

        # Table headers
        "header_line_bus": "Leitung/Bus",
        "header_pin_end": "Pin/Ende",
        "header_target": "Ziel",
        "header_pin": "Pin",

        # Messages
        "msg_auto_loading": "Automatisches Laden: {path}",
        "msg_file_not_found": "'{path}' nicht gefunden.",
        "msg_select_pdf": "PDF auswählen",
        "msg_error": "Fehler",
        "msg_page_error": "Seitenfehler: {error}",
        "msg_mode": "Modus: {mode}",
        "msg_analyzing": "Seite {page} wird analysiert...",
        "msg_analysis_complete": "Analyse abgeschlossen. {count} Leitungen gefunden.",
        "msg_connection_report": "====== VERBINDUNGSBERICHT ======",
        "msg_warning_no_pin": "WARNUNG: Kein Pin erkannt bei Geraet/Klemme '{comp}' (Leitung: {net}).",
        "msg_no_valid_connections": "Keine gueltigen Verbindungen fuer Tabelle gefunden.",
        "msg_no_vector_data": "Keine Vektordaten auf dieser Seite gefunden.",

        # Page Classification
        "btn_classify_mode": "Seiten klassifizieren",
        "btn_save_classifications": "Klassifizierungen speichern",
        "classify_schematic": "Schaltplan [S]",
        "classify_non_schematic": "Kein Schaltplan [N]",
        "classify_skip": "Ueberspringen [Leertaste]",
        "msg_classified_schematic": "Seite {page} als SCHALTPLAN markiert",
        "msg_classified_non_schematic": "Seite {page} als KEIN SCHALTPLAN markiert",
        "msg_classification_mode_on": "Klassifizierungsmodus AN - Druecke S (Schaltplan), N (kein Schaltplan), Leertaste (ueberspringen)",
        "msg_classification_mode_off": "Klassifizierungsmodus AUS",
        "msg_classifications_saved": "Klassifizierungen gespeichert unter: {path}",
        "msg_classification_stats": "Klassifiziert: {schematic} Schaltplaene, {non_schematic} keine Schaltplaene, {total} gesamt",
        "msg_export_complete": "{count} Bilder exportiert nach: {path}",
        "lbl_classification_status": "[{status}]",

        # Schematic Filter
        "btn_schematic_filter": "Nur Schaltplaene",
        "msg_filter_scanning": "Seiten werden nach Schaltplaenen durchsucht...",
        "msg_filter_complete": "{count} Schaltplaene von {total} Seiten gefunden",
        "msg_filter_on": "Schaltplan-Filter AN - Zeige {count} Seiten",
        "msg_filter_off": "Schaltplan-Filter AUS - Zeige alle Seiten",
        "page_label_filtered": "Seite: {current} / {total} (Schaltplan {idx}/{count})",
        "msg_model_not_found": "Seitenklassifizierer-Modell nicht gefunden. Bitte zuerst trainieren.",
        "msg_model_loaded": "Seitenklassifizierer-Modell geladen",
    },

    "tr": {
        # Window
        "window_title": "P8 Analyzer - Profesyonel Vektör Analizörü",

        # Toolbar
        "toolbar_name": "Araçlar",
        "btn_open_pdf": "PDF Aç",
        "btn_prev": "Önceki",
        "btn_next": "Sonraki",
        "btn_analyze": "Analiz Et",
        "btn_ocr_test": "OCR vs PDF",
        "btn_navigate": "Gezin",
        "btn_draw_box": "Kutu Çiz",
        "btn_connection_check": "Bağlantı Kontrol",

        # Page label
        "page_label": "Sayfa: {current} / {total}",
        "page_label_empty": "Sayfa: -/-",

        # Dock panels
        "dock_logs": "Loglar",
        "dock_connections": "Bağlantı Listesi",

        # Table headers
        "header_line_bus": "Hat/Bus",
        "header_pin_end": "Pin/Uç",
        "header_target": "Hedef",
        "header_pin": "Pin",

        # Messages
        "msg_auto_loading": "Otomatik yükleme: {path}",
        "msg_file_not_found": "'{path}' bulunamadı.",
        "msg_select_pdf": "PDF Seç",
        "msg_error": "Hata",
        "msg_page_error": "Sayfa hatası: {error}",
        "msg_mode": "Mod: {mode}",
        "msg_analyzing": "Sayfa {page} analiz ediliyor...",
        "msg_analysis_complete": "Analiz Bitti. {count} hat bulundu.",
        "msg_connection_report": "====== BAĞLANTI RAPORU ======",
        "msg_warning_no_pin": "DİKKAT: '{comp}' cihazında/klemensinde pin tespit edilemedi (Hat: {net}).",
        "msg_no_valid_connections": "Tabloya eklenecek geçerli bağlantı bulunamadı.",
        "msg_no_vector_data": "Bu sayfada vektör verisi bulunamadı.",

        # Page Classification
        "btn_classify_mode": "Sayfa Siniflandir",
        "btn_save_classifications": "Siniflandirmalari Kaydet",
        "classify_schematic": "Sema [S]",
        "classify_non_schematic": "Sema Degil [N]",
        "classify_skip": "Atla [Bosluk]",
        "msg_classified_schematic": "Sayfa {page} SEMA olarak isaretlendi",
        "msg_classified_non_schematic": "Sayfa {page} SEMA DEGIL olarak isaretlendi",
        "msg_classification_mode_on": "Siniflandirma Modu ACIK - S (sema), N (sema degil), Bosluk (atla)",
        "msg_classification_mode_off": "Siniflandirma Modu KAPALI",
        "msg_classifications_saved": "Siniflandirmalar kaydedildi: {path}",
        "msg_classification_stats": "Siniflandirildi: {schematic} sema, {non_schematic} sema degil, {total} toplam",
        "msg_export_complete": "{count} gorsel disari aktarildi: {path}",
        "lbl_classification_status": "[{status}]",

        # Schematic Filter
        "btn_schematic_filter": "Sadece Semalar",
        "msg_filter_scanning": "Sayfalar sema icin taraniyor...",
        "msg_filter_complete": "{total} sayfadan {count} sema bulundu",
        "msg_filter_on": "Sema filtresi ACIK - {count} sayfa gosteriliyor",
        "msg_filter_off": "Sema filtresi KAPALI - Tum sayfalar gosteriliyor",
        "page_label_filtered": "Sayfa: {current} / {total} (Sema {idx}/{count})",
        "msg_model_not_found": "Sayfa siniflandirici modeli bulunamadi. Lutfen once modeli egitin.",
        "msg_model_loaded": "Sayfa siniflandirici modeli yuklendi",
    },
}

# Default language
_current_language = "en"


def set_language(lang: str) -> bool:
    """
    Set the current language.

    Args:
        lang: Language code ('en', 'de', 'tr')

    Returns:
        True if language was set, False if not supported
    """
    global _current_language
    if lang in TRANSLATIONS:
        _current_language = lang
        return True
    return False


def get_language() -> str:
    """Get the current language code."""
    return _current_language


def get_supported_languages() -> list:
    """Get list of supported language codes."""
    return list(TRANSLATIONS.keys())


def t(key: str, **kwargs) -> str:
    """
    Get translated string for key.

    Args:
        key: Translation key
        **kwargs: Format arguments for the string

    Returns:
        Translated string, or key if not found
    """
    translations = TRANSLATIONS.get(_current_language, TRANSLATIONS["en"])
    text = translations.get(key, key)

    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Return unformatted if format args don't match

    return text


# Convenience aliases
_ = t  # Common alias for translation function
