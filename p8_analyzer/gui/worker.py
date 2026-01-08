from PyQt5.QtCore import QThread, pyqtSignal
import pymupdf
import traceback

# P8 Analyzer modules
from p8_analyzer.core import analyze_page_vectors, DEFAULT_CONFIG

class AnalysisWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, pdf_path, page_num):
        """
        Thread Safety için 'doc' nesnesi yerine dosya yolu (pdf_path) alır.
        """
        super().__init__()
        self.pdf_path = pdf_path
        self.page_num = page_num

    def run(self):
        doc = None
        try:
            # Thread içinde dosyayı güvenli şekilde aç
            doc = pymupdf.open(self.pdf_path)
            page_index = self.page_num - 1
            page = doc.load_page(page_index)
            
            drawings = page.get_drawings()
            if not drawings:
                self.error.emit("Bu sayfada vektör verisi bulunamadı.")
                return

            # Vektör Analizi
            analysis_result = analyze_page_vectors(drawings, page.rect, self.page_num, DEFAULT_CONFIG)
            
            # --- TERMINAL ANALİZİ ---
            try:
                from p8_analyzer.detection import TerminalDetector, TerminalReader, TerminalGrouper
                from p8_analyzer.text import HybridTextEngine

                # 1. Tespit
                detector = TerminalDetector()
                terminals = detector.detect(analysis_result)

                if terminals:
                    # 2. Okuma (TextEngine bu thread'deki page nesnesini kullanmalı)
                    text_engine = HybridTextEngine(languages=['en'])
                    text_engine.load_page(page)

                    reader = TerminalReader()
                    terminals = reader.read_labels(terminals, text_engine)

                    # 3. Gruplama
                    grouper = TerminalGrouper()
                    terminals = grouper.group_terminals(terminals, text_engine)

                    # 4. Sonucu modele ekle
                    analysis_result.terminals = terminals

            except ImportError:
                print("Terminal modülleri bulunamadı, bu adım atlanıyor.")
            except Exception as e:
                print(f"Terminal analizi hatası: {e}")
                traceback.print_exc()

            # --- CLUSTER-BASED COMPONENT DETECTION ---
            try:
                from p8_analyzer.detection import ClusterDetector, get_default_settings

                settings = get_default_settings()
                cluster_detector = ClusterDetector(
                    vertical_weight=settings.vertical_weight,
                    absolute_min_gap=settings.absolute_min_gap,
                    density_factor=settings.density_factor,
                    max_gap=settings.max_gap,
                    label_max_distance=settings.label_max_distance,
                    label_cluster_size_factor=settings.label_cluster_size_factor,
                    cross_color_penalty=settings.cross_color_penalty,
                    label_subsume_threshold=settings.label_subsume_threshold
                )

                clusters, labels, gap_fills, circle_pins, line_ends = cluster_detector.detect_clusters(
                    page,
                    analysis_result.broken_connections,
                    analysis_result.structural_groups
                )

                # Store results on analysis_result
                analysis_result.component_clusters = clusters
                analysis_result.cluster_labels = labels
                analysis_result.cluster_gap_fills = gap_fills
                analysis_result.cluster_circle_pins = circle_pins
                analysis_result.cluster_line_ends = line_ends

                print(f"Cluster detection: {len(clusters)} clusters, {sum(1 for c in clusters if c.label)} labeled")

            except ImportError as e:
                print(f"Cluster detection modules not found: {e}")
            except Exception as e:
                print(f"Cluster detection error: {e}")
                traceback.print_exc()

            # Sonucu gönder
            self.finished.emit(analysis_result)

        except Exception as e:
            self.error.emit(f"Kritik Hata:\n{str(e)}\n{traceback.format_exc()}")
        finally:
            if doc:
                doc.close()