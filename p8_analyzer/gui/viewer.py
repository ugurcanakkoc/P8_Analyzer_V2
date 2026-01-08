from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsEllipseItem
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont, QPixmap, QImage
import pymupdf
import tempfile
import os

# P8 Analyzer modules
from p8_analyzer.circuit import CircuitComponent

class InteractiveGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        
        self.mode = "NAVIGATE"
        self.temp_rect = None
        self.start_pos = None
        self.drawn_boxes = [] 
        self.tagger_callback = None

    def set_tagger_callback(self, callback):
        self.tagger_callback = callback

    def set_background_image(self, page):
        self.scene.clear()
        self.drawn_boxes = [] 
        
        mat = pymupdf.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        fmt = QImage.Format_RGB888 if pix.alpha == 0 else QImage.Format_RGBA8888
        qt_img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        
        pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_img))
        pixmap_item.setOpacity(0.4)
        pixmap_item.setScale(0.5)
        self.scene.setSceneRect(0, 0, page.rect.width, page.rect.height)

    def draw_analysis_result(self, result, page=None):
        """
        Draw analysis result using PIL-based visualization for consistency with CLI output.

        Args:
            result: Analysis result with structural_groups, component_clusters, etc.
            page: PyMuPDF page object (required for cluster visualization)
        """
        # Always use PIL-based visualization when page is available
        if page is not None:
            clusters = getattr(result, 'component_clusters', None) or []
            labels = getattr(result, 'cluster_labels', None) or []
            gap_fills = getattr(result, 'cluster_gap_fills', None) or []
            circle_pins = getattr(result, 'cluster_circle_pins', None) or []
            line_ends = getattr(result, 'cluster_line_ends', None) or []

            self._draw_cluster_visualization(
                page,
                clusters,
                labels,
                gap_fills,
                circle_pins,
                line_ends,
                result.structural_groups
            )
        else:
            # Fallback to Qt-based drawing only if no page
            for i, group in enumerate(result.structural_groups):
                display_id = f"NET-{i+1:03d}"
                self._draw_group(group, display_id)

    def _draw_cluster_visualization(self, page, clusters, labels, gap_fills, circle_pins, line_ends, structural_groups):
        """
        Use the PIL-based visualize_clusters function for consistent output.
        Renders to a temp file, then displays in scene.
        """
        from p8_analyzer.detection import visualize_clusters

        # Clear scene and render using PIL
        self.scene.clear()
        self.drawn_boxes = []

        # Create temp file for visualization
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Use same scale as CLI visualization (scale=2.0)
            visualize_clusters(
                page, clusters, labels, gap_fills, circle_pins, line_ends,
                tmp_path, scale=2.0, structural_groups=structural_groups
            )

            # Load the rendered image
            qt_img = QImage(tmp_path)
            if not qt_img.isNull():
                pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_img))
                # Scale down to match PDF coordinates (rendered at 2x, display at 1x)
                pixmap_item.setScale(0.5)
                self.scene.setSceneRect(0, 0, page.rect.width, page.rect.height)
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _draw_group(self, group, label_text):
        path = QPainterPath()
        for elem in group.elements:
            path.moveTo(elem.start_point.x, elem.start_point.y)
            path.lineTo(elem.end_point.x, elem.end_point.y)
            
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor(group.color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path_item.setToolTip(f"ID: {label_text}")
        self.scene.addItem(path_item)

    def _draw_terminal(self, terminal):
        cx, cy = terminal['center']
        radius = terminal['radius']
        ellipse = QGraphicsEllipseItem(cx - radius, cy - radius, radius * 2, radius * 2)
        ellipse.setPen(QPen(Qt.blue, 1.0))
        ellipse.setBrush(QBrush(QColor(0, 0, 255, 50)))
        self.scene.addItem(ellipse)

        label = terminal.get('full_label') or terminal.get('label')
        if label and label != '?':
            text = QGraphicsSimpleTextItem(str(label))
            text.setPos(cx + radius + 2, cy - radius - 5)
            text.setFont(QFont("Arial", 6))
            text.setBrush(QBrush(Qt.blue))
            self.scene.addItem(text)

    def _draw_detected_elements(self, detected_elements):
        """Draw detected circuit elements (wire breaks, junctions)."""
        for elem in detected_elements:
            bbox = elem.bounding_box
            x0, y0 = bbox['min_x'], bbox['min_y']
            w = bbox['max_x'] - bbox['min_x']
            h = bbox['max_y'] - bbox['min_y']

            # Color based on element type
            if elem.element_type == "wire_break":
                color = QColor(255, 100, 0, 120)  # Orange for wire breaks
                pen_color = QColor(255, 100, 0)
            elif elem.element_type == "junction":
                color = QColor(0, 200, 100, 120)  # Green for junctions
                pen_color = QColor(0, 200, 100)
            else:
                color = QColor(128, 128, 128, 120)  # Gray for unknown
                pen_color = QColor(128, 128, 128)

            # Draw rectangle
            rect_item = QGraphicsRectItem(x0, y0, w, h)
            rect_item.setPen(QPen(pen_color, 1.5, Qt.DashLine))
            rect_item.setBrush(QBrush(color))
            rect_item.setToolTip(f"{elem.element_type}: {elem.label}")
            self.scene.addItem(rect_item)

            # Draw label
            if elem.label:
                text = QGraphicsSimpleTextItem(elem.label)
                text.setPos(x0, y0 - 12)
                text.setFont(QFont("Arial", 6, QFont.Bold))
                text.setBrush(QBrush(pen_color))
                self.scene.addItem(text)

    def _draw_clusters(self, clusters, labels, gap_fills, circle_pins, line_ends):
        """Draw cluster-based component detection results."""
        import math

        # Build label-to-cluster-color map
        label_to_color = {}
        assigned_labels = set()
        for cluster in clusters:
            if cluster.label:
                color_hex = cluster.primary_color.lstrip('#')
                r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
                label_to_color[id(cluster.label)] = QColor(r, g, b)
                assigned_labels.add(id(cluster.label))

        # Draw cluster bounding boxes
        for cluster in clusters:
            color_hex = cluster.primary_color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            color = QColor(r, g, b)

            bbox = cluster.bbox
            x0, y0, x1, y1 = bbox
            w, h = x1 - x0, y1 - y0

            rect_item = QGraphicsRectItem(x0, y0, w, h)
            if cluster.label:
                # Labeled cluster: solid outline
                rect_item.setPen(QPen(color, 2.0, Qt.SolidLine))
                rect_item.setBrush(QBrush(QColor(r, g, b, 40)))
                tooltip = f"{cluster.label.text}: {len(cluster.objects)} objects"
            else:
                # Unlabeled cluster: dashed outline
                rect_item.setPen(QPen(color, 1.0, Qt.DashLine))
                rect_item.setBrush(QBrush(QColor(r, g, b, 20)))
                tooltip = f"Unlabeled: {len(cluster.objects)} objects"

            rect_item.setToolTip(tooltip)
            self.scene.addItem(rect_item)

        # Draw gap fills (small rectangles along the gap)
        for gap in gap_fills:
            color_hex = gap.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            color = QColor(r, g, b)

            sx, sy = gap.gap_start
            ex, ey = gap.gap_end
            cx, cy = gap.center

            # Draw a small marker at the center
            marker = QGraphicsEllipseItem(cx - 3, cy - 3, 6, 6)
            marker.setPen(QPen(color, 1.5))
            marker.setBrush(QBrush(QColor(r, g, b, 150)))
            marker.setToolTip(f"Gap fill")
            self.scene.addItem(marker)

        # Draw circle pins
        for circ in circle_pins:
            color_hex = circ.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            color = QColor(r, g, b)

            cx, cy = circ.center
            radius = circ.radius

            ellipse = QGraphicsEllipseItem(cx - radius, cy - radius, radius * 2, radius * 2)
            ellipse.setPen(QPen(color, 2.0))
            ellipse.setBrush(QBrush(Qt.transparent))
            ellipse.setToolTip(f"Circle pin")
            self.scene.addItem(ellipse)

        # Draw line ends (diamond markers)
        for end in line_ends:
            color_hex = end.color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            color = QColor(r, g, b)

            ex, ey = end.position
            size = 4.0

            # Draw diamond shape
            path = QPainterPath()
            path.moveTo(ex, ey - size)
            path.lineTo(ex + size, ey)
            path.lineTo(ex, ey + size)
            path.lineTo(ex - size, ey)
            path.closeSubpath()

            diamond = QGraphicsPathItem(path)
            diamond.setPen(QPen(color, 1.5))
            diamond.setBrush(QBrush(QColor(r, g, b, 150)))
            diamond.setToolTip(f"Line end")
            self.scene.addItem(diamond)

        # Draw labels with matching colors
        for label in labels:
            x0, y0, x1, y1 = label.bbox
            w, h = x1 - x0, y1 - y0

            if id(label) in assigned_labels:
                # Assigned label: use cluster's color
                color = label_to_color[id(label)]
                rect_item = QGraphicsRectItem(x0, y0, w, h)
                rect_item.setPen(QPen(color, 2.0))
                rect_item.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 80)))
            else:
                # Unassigned label: orange
                rect_item = QGraphicsRectItem(x0, y0, w, h)
                rect_item.setPen(QPen(QColor(255, 140, 0), 2.0))
                rect_item.setBrush(QBrush(QColor(255, 200, 0, 80)))

            rect_item.setToolTip(label.text)
            self.scene.addItem(rect_item)

            # Draw label text
            text = QGraphicsSimpleTextItem(label.text)
            text.setPos(x0 + 2, y0 + 2)
            text.setFont(QFont("Arial", 7, QFont.Bold))
            if id(label) in assigned_labels:
                text.setBrush(QBrush(label_to_color[id(label)].darker(150)))
            else:
                text.setBrush(QBrush(QColor(180, 100, 0)))
            self.scene.addItem(text)

    def set_mode(self, mode):
        self.mode = mode
        if mode == "DRAW":
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if self.mode == "DRAW" and event.button() == Qt.LeftButton:
            self.start_pos = self.mapToScene(event.pos())
            self.temp_rect = QGraphicsRectItem()
            self.temp_rect.setPen(QPen(Qt.red, 2, Qt.DashLine))
            self.scene.addItem(self.temp_rect)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "DRAW" and self.temp_rect:
            curr_pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_pos, curr_pos).normalized()
            self.temp_rect.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode == "DRAW" and self.temp_rect:
            rect = self.temp_rect.rect()
            self.scene.removeItem(self.temp_rect)
            self.temp_rect = None
            
            box_id = f"BOX-{len(self.drawn_boxes)+1}"
            
            if self.tagger_callback:
                bbox = (rect.left(), rect.top(), rect.right(), rect.bottom())
                found_tag = self.tagger_callback(bbox)
                if found_tag: box_id = found_tag
            
            final_item = QGraphicsRectItem(rect)
            final_item.setPen(QPen(Qt.red, 2))
            final_item.setBrush(QBrush(QColor(255, 0, 0, 40)))
            self.scene.addItem(final_item)
            
            text = self.scene.addSimpleText(box_id)
            text.setPos(rect.left(), rect.top() - 15)
            text.setBrush(QColor("red"))
            text.setFont(QFont("Arial", 8, QFont.Bold))
            
            component = CircuitComponent(
                id=box_id, label="Manual",
                bbox={"min_x": rect.left(), "min_y": rect.top(), "max_x": rect.right(), "max_y": rect.bottom()}
            )
            self.drawn_boxes.append(component)
        else:
            super().mouseReleaseEvent(event)

    def get_drawn_components(self):
        return self.drawn_boxes

    def draw_debug_rect(self, rect, color=Qt.green, label=None):
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0
        rect_item = QGraphicsRectItem(x0, y0, w, h)
        rect_item.setPen(QPen(color, 1, Qt.DashLine))
        self.scene.addItem(rect_item)
        if label:
            text_item = QGraphicsSimpleTextItem(label)
            text_item.setPos(x0, y0 - 10)
            text_item.setFont(QFont("Arial", 6))
            text_item.setBrush(QBrush(color))
            self.scene.addItem(text_item)

    # --- YENİ EKLENEN METOD ---
    def draw_debug_point(self, point, color=Qt.red, radius=5.0):
        """
        Verilen (x, y) noktasına belirgin bir daire çizer.
        """
        x, y = point
        # Daireyi oluştur (merkezi x,y olacak şekilde)
        ellipse = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
        
        # Kenar çizgisi (Siyah olsun ki belli olsun)
        ellipse.setPen(QPen(Qt.black, 1))
        # İç dolgusu (İstenen renk)
        ellipse.setBrush(QBrush(color))
        # Her zaman üstte görünsün diye z-value verilebilir
        ellipse.setZValue(100) 
        
        self.scene.addItem(ellipse)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0: self.scale(1.25, 1.25)
            else: self.scale(0.8, 0.8)
        else:
            super().wheelEvent(event)