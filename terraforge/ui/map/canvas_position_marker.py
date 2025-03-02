
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QPainter, QFontMetrics
from PyQt6.QtCore import Qt, QPointF, QRectF

class CanvasPositionMarkerQt(QGraphicsItem):
    def __init__(self, map_widget, coordinates: tuple, text: str = None, color_inner="black", color_outer="white", marker_diameter=12, font_size=12, text_color="black"):
        super().__init__()
        self.map_widget = map_widget
        self.coordinates = coordinates
        self.text = text
        self.color_inner = QColor(color_inner)
        self.color_outer = QColor(color_outer)
        self.marker_diameter = marker_diameter
        self.font_size = font_size
        self.text_color = QColor(text_color)
        self.canvas_position = QPointF(0, 0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        self.marker_path = QPainterPath()
        self.marker_path.addEllipse(QRectF(-self.marker_diameter / 2, -self.marker_diameter / 2, self.marker_diameter, self.marker_diameter))

        self.text_item = None

    def boundingRect(self):
        bounding_rect = QRectF(-self.marker_diameter, -self.marker_diameter, self.marker_diameter * 2, self.marker_diameter * 2)
        if self.text:
            font = QFont()
            font.setPointSize(self.font_size)
            fm = QFontMetrics(font)
            text_rect = fm.boundingRect(self.text)
            bounding_rect = bounding_rect.united(QRectF(0, self.marker_diameter / 2, text_rect.width(), text_rect.height()))
        return bounding_rect.normalized()
    
    def paint(self, painter, option, widget = None):
        painter.setPen(QPen(self.color_outer, 2))
        painter.setBrush(QBrush(self.color_inner))
        painter.drawPath(self.marker_path)

        if self.text:
            painter.setPen(QPen(self.text_color))
            font = QFont()
            font.setPointSize(self.font_size)
            painter.setFont(font)
            painter.drawText(QPointF(0, self.marker_diameter + self.font_size), self.text)

    def draw(self):
        tile_position = self.map_widget.decimal_to_tile_position(*self.coordinates)
        if tile_position is not None:
            canvas_x = (tile_position[0] - self.map_widget.upper_left_tile_pos[0]) * self.map_widget.tile_size
            canvas_y = (tile_position[1] - self.map_widget.upper_left_tile_pos[1]) * self.map_widget.tile_size
            self.setPos(QPointF(canvas_x, canvas_y))

    def delete(self):
        self.map_widget.scene_qt.removeItem(self)
        del self

    def get_canvas_position(self):
        return self.pos()
    
    def get_decimal_position(self):
        return self.coordinates