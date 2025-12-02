import logging

logger = logging.getLogger(__name__)

class ComponentNamer:
    """
    Handles the automatic naming of manual boxes based on the text found inside them.
    """
    def __init__(self, matcher):
        self.matcher = matcher

    def name_boxes(self, boxes, logger_func=None):
        """
        Iterates through boxes and updates their IDs if a suitable label is found inside.
        """
        if not self.matcher or not boxes:
            return

        if logger_func:
            logger_func("📦 Kutular isimlendiriliyor...")

        for box in boxes:
            # Find text inside the box
            box_texts = self.matcher.find_text_objects_in_rect((
                box.bbox['min_x'], box.bbox['min_y'],
                box.bbox['max_x'], box.bbox['max_y']
            ))
            
            candidate_name = None
            for obj in box_texts:
                txt = obj['text'].strip()
                
                # Validation Logic:
                # 1. Must start with '-'
                # 2. Must be > 1 char (not just '-')
                # 3. Must contain at least one alphanumeric char (reject '---')
                # 4. Length limit
                if (txt.startswith("-") and 
                    len(txt) > 1 and 
                    len(txt) < 15 and
                    any(c.isalnum() for c in txt)):
                    
                    candidate_name = txt
                    break # Take the first valid one
            
            if candidate_name:
                old_id = box.id
                box.id = candidate_name
                if logger_func:
                    logger_func(f"   🔄 {old_id} -> {candidate_name} olarak güncellendi.")
