"""
Terminal grouper module with inheritance logic.
Groups terminals by finding group labels (e.g., -X1, -X2) or inheriting from left neighbor.
"""
import logging
import re
from typing import List, Dict, Optional
from src.text_engine import HybridTextEngine, SearchProfile, SearchDirection

logger = logging.getLogger(__name__)


class TerminalGrouper:
    """
    Groups terminals using smart inheritance logic.
    
    Algorithm:
    1. Sort terminals by Y coordinate (top to bottom)
    2. For each terminal:
       a) Search for -X label on the left (narrow search ~25px)
       b) If not found, find left neighbor terminal and inherit its group
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize terminal grouper with configuration.
        
        Args:
            config: Configuration dictionary with grouping parameters
        """
        self.config = config or {}
        self.search_direction = self.config.get('search_direction', 'left')
        self.search_radius = self.config.get('search_radius', 100.0)  # Increased from 25.0 to 100.0
        self.y_tolerance = self.config.get('y_tolerance', 15.0)  # For finding neighbors
        self.label_pattern = self.config.get('label_pattern', r'^-?X.*') # Allow optional hyphen at start, just in case
        self.neighbor_x_distance = self.config.get('neighbor_x_distance', 50.0)

    def group_terminals(self, terminals: List[Dict], text_engine: HybridTextEngine) -> List[Dict]:
        """
        Group terminals by finding group labels or inheriting from neighbors.
        
        Args:
            terminals: List of terminal dictionaries (already with individual labels)
            text_engine: Hybrid text engine (already loaded with page)
            
        Returns:
            Updated terminals list with group_label and full_label
        """
        if not terminals:
            return terminals
        
        # Step 1: Sort terminals by Y coordinate (top to bottom), then X (left to right)
        sorted_terminals = sorted(terminals, key=lambda t: (t['center'][1], t['center'][0]))
        
        # Step 2: Create search profile for group labels (narrow search)
        profile = SearchProfile(
            search_radius=self.search_radius,
            direction=SearchDirection.LEFT,
            regex_pattern=self.label_pattern,
            use_ocr_fallback=True
        )
        
        # Step 3: Process each terminal
        for i, terminal in enumerate(sorted_terminals):
            cx, cy = terminal['center']
            
            # Try to find group label on the left
            result = text_engine.find_text((cx, cy), profile)
            
            if result:
                # Found group label directly
                terminal['group_label'] = result.text
                terminal['group_source'] = f"{result.source}_direct"
                logger.debug(f"Terminal at ({cx:.0f},{cy:.0f}) -> Direct group: {result.text}")
            else:
                # No direct group label, try to inherit from parent (left or top neighbor)
                parent = self._find_parent_terminal(terminal, sorted_terminals[:i])
                
                if parent and parent.get('group_label'):
                    # Inherit group from neighbor
                    terminal['group_label'] = parent['group_label']
                    terminal['group_source'] = 'inherited'
                    logger.debug(f"Terminal at ({cx:.0f},{cy:.0f}) -> Inherited group: {parent['group_label']}")
                else:
                    # No group found
                    terminal['group_label'] = None
                    terminal['group_source'] = None
                    logger.debug(f"Terminal at ({cx:.0f},{cy:.0f}) -> No group")
            
            # Create full label
            # User request: "Grupadı:Pin adı olacak"
            # We enforce this format even if parts are missing (using 'UNK' or '?')
            group = terminal.get('group_label') or "UNK"
            pin = terminal.get('label') or "?"
            
            terminal['full_label'] = f"{group}:{pin}"
            
            # Log the assignment
            logger.debug(f"Terminal ID assigned: {terminal['full_label']} at {terminal['center']}")
        
        # Statistics
        grouped_count = sum(1 for t in sorted_terminals if t.get('group_label'))
        inherited_count = sum(1 for t in sorted_terminals if t.get('group_source') == 'inherited')
        logger.info(f"Grouped {grouped_count}/{len(sorted_terminals)} terminals ({inherited_count} inherited)")
        
        # Log all generated IDs for verification
        all_ids = [t['full_label'] for t in sorted_terminals]
        logger.info(f"Generated Terminal IDs: {', '.join(all_ids)}")
        
        return sorted_terminals
    
    def _find_parent_terminal(self, terminal: Dict, previous_terminals: List[Dict]) -> Optional[Dict]:
        """
        Find a parent terminal to inherit group from.
        Prioritizes scanning to the LEFT on the same Y level until a labeled terminal is found.
        
        Args:
            terminal: Current terminal
            previous_terminals: Terminals processed before this one (sorted)
            
        Returns:
            Parent terminal or None
        """
        if not previous_terminals:
            return None
        
        cx, cy = terminal['center']
        
        # 1. Horizontal Scan (Left, Same Y)
        # Iterate backwards through previous terminals (nearest first)
        for t in reversed(previous_terminals):
            tx, ty = t['center']
            
            # Strict Y tolerance (Must be on the same line)
            if abs(cy - ty) > self.y_tolerance:
                continue
            
            # Since 'previous_terminals' is sorted by Y then X, 
            # and we are in the same Y range, 't' is guaranteed to be to the left (or same pos).
            
            # Check if this neighbor has a valid group label
            if t.get('group_label'):
                return t
            
            # If this neighbor has NO group label, we ignore it and continue scanning left.
            # "bulana kadarda tarasın" (scan until found)
        
        # 2. Vertical Scan (Top, Same X)
        # Only if no horizontal parent found.
        # User warning: "y hizasında yüksekte varsa onu almamalı aynı y hizsında olmalı"
        # This implies we should be very careful about vertical inheritance.
        # We'll use a very strict X tolerance for vertical inheritance to ensure it's a true vertical strip.
        
        candidates = []
        for t in previous_terminals:
            tx, ty = t['center']
            
            dx = abs(cx - tx)
            dy = abs(cy - ty)
            
            # Must be above (ty < cy)
            if ty >= cy:
                continue
                
            # Strict X alignment for vertical strips (e.g. 5.0 units)
            if dx <= 5.0 and dy <= self.neighbor_x_distance:
                candidates.append((dy, t))
        
        if candidates:
            candidates.sort(key=lambda x: x[0])
            for _, term in candidates:
                if term.get('group_label'):
                    return term
                    
        return None
