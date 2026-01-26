"""
PDF Analyzer - CLI wrapper for the shared analysis engine.

Uses the same AnalysisEngine as the GUI for consistent results.
"""
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

import pymupdf

from p8_analyzer.core.analysis_engine import AnalysisEngine, AnalysisOptions
from p8_analyzer.core.session import (
    AnalysisSession,
    SessionMetadata,
    AnalysisSummary,
)

logger = logging.getLogger(__name__)

# Re-export AnalysisOptions for CLI users
__all__ = ['PDFAnalyzer', 'AnalysisOptions']


class PDFAnalyzer:
    """
    Headless PDF analyzer for P8-format electrical schematics.

    Uses the shared AnalysisEngine for consistency with GUI.

    Usage:
        analyzer = PDFAnalyzer()
        session = analyzer.analyze_document("schematic.pdf", pages=[11, 12])
        session.save("output.json")
    """

    def __init__(self, options: AnalysisOptions = None):
        self.options = options or AnalysisOptions()
        self._engine = AnalysisEngine(self.options)

    def analyze_document(
        self,
        pdf_path: str,
        pages: Optional[List[int]] = None
    ) -> AnalysisSession:
        """
        Analyze a PDF document and return an AnalysisSession.

        Args:
            pdf_path: Path to PDF file
            pages: List of page numbers (1-indexed). If None, analyze all pages.

        Returns:
            AnalysisSession containing all analysis results
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = pymupdf.open(str(pdf_path))
        try:
            total_pages = len(doc)

            # Determine which pages to analyze
            if pages is None:
                pages = list(range(1, total_pages + 1))
            else:
                # Validate page numbers
                pages = [p for p in pages if 1 <= p <= total_pages]

            # Create session metadata
            metadata = SessionMetadata(
                pdf_path=str(pdf_path.absolute()),
                pdf_name=pdf_path.name,
                total_pages=total_pages,
                analyzed_pages=pages,
                created_at=datetime.now(),
                analyzer_version="2.0.0"
            )

            # Create session
            session = AnalysisSession(
                metadata=metadata,
                pages={},
                summary=AnalysisSummary()
            )

            # Analyze each page using the shared engine
            for page_num in pages:
                logger.info(f"Analyzing page {page_num}/{total_pages}")
                try:
                    page = doc.load_page(page_num - 1)  # 0-indexed
                    page_analysis = self._engine.analyze_page(page, page_num)
                    session.pages[page_num] = page_analysis
                except Exception as e:
                    logger.error(f"Error analyzing page {page_num}: {e}")
                    session.summary.pages_with_errors.append(page_num)

            # Compute summary
            session.compute_summary()

            return session

        finally:
            doc.close()
