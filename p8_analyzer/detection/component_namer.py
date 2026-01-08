import logging
from p8_analyzer.detection.device_tagger import DeviceTagger

logger = logging.getLogger(__name__)

class ComponentNamer:
    """
    Handles the automatic naming of manual boxes using DeviceTagger (Top-Left search).
    """
    def __init__(self, text_engine):
        self.text_engine = text_engine
        self.tagger = DeviceTagger(text_engine)

    def name_boxes(self, boxes, logger_func=None):
        """
        Iterates through boxes and updates their IDs using DeviceTagger.
        """
        if not self.text_engine or not boxes:
            return

        if logger_func:
            logger_func("📦 Kutular isimlendiriliyor (Sol-Üst Köşe Taraması)...")

        for box in boxes:
            # Use DeviceTagger to find the tag at the top-left corner
            found_tag = self.tagger.find_tag((
                box.bbox['min_x'], box.bbox['min_y'],
                box.bbox['max_x'], box.bbox['max_y']
            ))
            
            if found_tag:
                # Validate the tag (DeviceTagger already does regex, but we can double check)
                # Reject '---' or invalid formats if DeviceTagger lets them through
                if (found_tag.startswith("-") and 
                    len(found_tag) > 1 and 
                    any(c.isalnum() for c in found_tag)):
                    
                    old_id = box.id
                    box.id = found_tag
                    if logger_func:
                        logger_func(f"   🔄 {old_id} -> {found_tag} olarak güncellendi.")
