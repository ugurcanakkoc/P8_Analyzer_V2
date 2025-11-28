from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGraphicsRectItem, QGraphicsSimpleTextItem
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont, QPixmap, QImage
import pymupdf
from .circuit_logic import CircuitComponent

class InteractiveGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        
        self.mode = "NAVIGATE"
        self.temp_rect = None
        self.start_pos = None
        self.drawn_boxes = [] # Çizilen kutular burada saklanır

    def set_background_image(self, page):
        self.scene.clear()
        self.drawn_boxes = [] # Sayfa değişince kutuları temizle
        
        mat = pymupdf.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        fmt = QImage.Format_RGB888 if pix.alpha == 0 else QImage.Format_RGBA8888
        qt_img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        
        pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qt_img))
        pixmap_item.setOpacity(0.4)
        pixmap_item.setScale(0.5)
        self.scene.setSceneRect(0, 0, page.rect.width, page.rect.height)

    def draw_analysis_result(self, result):
        for i, group in enumerate(result.structural_groups):
            display_id = f"NET-{i+1:03d}"
            self._draw_group(group, display_id)

    def _draw_group(self, group, label_text):
        path = QPainterPath()
        for elem in group.elements:
            path.moveTo(elem.start_point.x, elem.start_point.y)
            path.lineTo(elem.end_point.x, elem.end_point.y)
            
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor(group.color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path_item.setToolTip(f"ID: {label_text}")
        self.scene.addItem(path_item)

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
            
            # Kutu ID'si
            box_id = f"BOX-{len(self.drawn_boxes)+1}"
            
            # Kalıcı Kutu Çiz
            final_item = QGraphicsRectItem(rect)
            final_item.setPen(QPen(Qt.red, 2))
            final_item.setBrush(QBrush(QColor(255, 0, 0, 40)))
            self.scene.addItem(final_item)
            
            # ID Yazısı Ekle
            text = self.scene.addSimpleText(box_id)
            text.setPos(rect.left(), rect.top() - 15)
            text.setBrush(QColor("red"))
            text.setFont(QFont("Arial", 8, QFont.Bold))
            
            # LİSTEYE KAYDET (Logic'in kullanacağı yer burası)
            component = CircuitComponent(
                id=box_id,
                label="Manual",
                bbox={
                    "min_x": rect.left(), "min_y": rect.top(),
                    "max_x": rect.right(), "max_y": rect.bottom()
                }
            )
            self.drawn_boxes.append(component)
        else:
            super().mouseReleaseEvent(event)

    def get_drawn_components(self):
        return self.drawn_boxes

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0: self.scale(1.25, 1.25)
            else: self.scale(0.8, 0.8)
        else:
            super().wheelEvent(event)