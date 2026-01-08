"""
Terminal label reader module.
Reads terminal labels from PDF text layer using the hybrid text engine.
"""
import logging
from typing import List, Dict, Optional, Tuple
from p8_analyzer.text import HybridTextEngine, SearchProfile, SearchDirection

logger = logging.getLogger(__name__)


class TerminalReader:
    """
    Reads terminal labels from PDF text layer.
    Uses directional search around terminal centers.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize terminal reader with configuration.
        
        Args:
            config: Configuration dictionary with search parameters
        """
        self.config = config or {}
        self.direction = self.config.get('direction', 'top_right')
        self.search_radius = self.config.get('search_radius', 20.0)
        self.y_tolerance = self.config.get('y_tolerance', 15.0)
        
        # Map string to SearchDirection enum
        self.direction_map = {
            'any': SearchDirection.ANY,
            'top': SearchDirection.TOP,
            'bottom': SearchDirection.BOTTOM,
            'right': SearchDirection.RIGHT,
            'left': SearchDirection.LEFT,
            'top_right': SearchDirection.TOP_RIGHT,
            'top_left': SearchDirection.TOP_LEFT,
            'bottom_right': SearchDirection.BOTTOM_RIGHT,
            'bottom_left': SearchDirection.BOTTOM_LEFT
        }
    
    def read_labels(self, terminals: List[Dict], text_engine: HybridTextEngine) -> List[Dict]:
        """
        Read labels for all terminals using the text engine.
        
        Args:
            terminals: List of terminal dictionaries
            text_engine: Hybrid text engine (already loaded with page)
            
        Returns:
            Updated terminals list with labels
        """
        if not terminals:
            return terminals
        
        # Create search profile - accept alphanumeric labels (PE, 5, L1, N, etc.)
        direction_enum = self.direction_map.get(self.direction, SearchDirection.TOP_RIGHT)
        profile = SearchProfile(
            search_radius=self.search_radius,
            direction=direction_enum,
            regex_pattern=r'^[a-zA-Z0-9\.\-\/]+$',  # Alphanumeric + dots/hyphens/slashes + lowercase
            use_ocr_fallback=True  # Enable OCR fallback for better detection
        )
        
        for terminal in terminals:
            center = terminal['center']
            
            # Search for label (try PDF first, then OCR)
            result = text_engine.find_text(center, profile)
            
            if result:
                terminal['label'] = result.text
                terminal['label_source'] = result.source  # Track if from PDF or OCR
                logger.debug(f"Terminal at {center} -> Label: {result.text} (source: {result.source})")
            else:
                terminal['label'] = '?'
                terminal['label_source'] = None
                logger.debug(f"Terminal at {center} -> No label found")
        
        labeled_count = sum(1 for t in terminals if t['label'] != '?')
        logger.info(f"Labeled {labeled_count}/{len(terminals)} terminals")
        
        return terminals
