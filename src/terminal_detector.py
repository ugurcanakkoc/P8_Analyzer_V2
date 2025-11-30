"""
Terminal (Klemens) detection module.
Detects terminal blocks as small filled circles in vector analysis.
"""
import logging
from typing import List, Dict, Optional
from external.uvp.src.models import VectorAnalysisResult, Circle

logger = logging.getLogger(__name__)


class TerminalDetector:
    """
    Detects terminal blocks from vector analysis results.
    Terminals are identified as small filled circles with specific characteristics.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize terminal detector with configuration.
        
        Args:
            config: Configuration dictionary with detection parameters
        """
        self.config = config or {}
        self.min_radius = self.config.get('min_radius', 2.5)
        self.max_radius = self.config.get('max_radius', 3.5)
        self.max_cv = self.config.get('max_cv', 0.01)
        self.only_unfilled = self.config.get('only_unfilled', True)
    
    def detect(self, vector_analysis: VectorAnalysisResult) -> List[Dict]:
        """
        Detect terminals from vector analysis result.
        
        Args:
            vector_analysis: Result from UVP vector analysis
            
        Returns:
            List of terminal dictionaries with center, radius, etc.
        """
        terminals = []
        
        if not vector_analysis or not vector_analysis.structural_groups:
            logger.warning("No structural groups found in vector analysis")
            return terminals
        
        # Search through all circles in structural groups
        for group in vector_analysis.structural_groups:
            for circle in group.circles:
                if self._is_terminal(circle):
                    terminal = {
                        'center': (circle.center.x, circle.center.y),
                        'radius': circle.radius,
                        'cv': circle.coefficient_of_variation,
                        'is_filled': circle.is_filled,
                        'group_id': group.group_id,
                        'label': None,  # Will be filled by TerminalReader
                        'group_label': None  # Will be filled by TerminalGrouper
                    }
                    terminals.append(terminal)
        
        logger.info(f"Detected {len(terminals)} terminal candidates")
        return terminals
    
    def _is_terminal(self, circle: Circle) -> bool:
        """
        Check if a circle matches terminal characteristics.
        
        Args:
            circle: Circle object from vector analysis
            
        Returns:
            True if circle is likely a terminal
        """
        # Check radius
        if not (self.min_radius <= circle.radius <= self.max_radius):
            return False
        
        # Check coefficient of variation (roundness)
        if circle.coefficient_of_variation > self.max_cv:
            return False
        
        # Check if filled (terminals are usually unfilled/hollow)
        if self.only_unfilled and circle.is_filled:
            return False
        
        return True
