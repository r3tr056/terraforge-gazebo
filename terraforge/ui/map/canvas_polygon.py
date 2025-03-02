from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QPointF

class CanvasPolygonQt(QGraphicsItem):
    def __init__(self, map_widget, coordinates: list, color="red", border_width=2, **kwargs):
        super().__init__()
        self.map_widget = map_widget
        self.coordinates = coordinates
        self.color = QColor(color)
        self.border_width = border_width
        self.canvas_positions = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.polygon_path = QPainterPath()

    def boundingRect(self):
        return self.polygon_path.boundingRect()
    
    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(self.color, self.border_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QBrush(self.color))
        painter.drawPath(self.polygon_path)

    def draw(self, move=False):
        self.polygon_path = QPainterPath()
        self.canvas_positions = []

        first_point = True
        for coordinates in self.coordinates:
            tile_position = self.map_widget.decimal_to_tile_position(*coordinates)
            if tile_position is not None:
                canvas_x = (tile_position[0] - self.map_widget.upper_left_tile_pos[0]) * self.map_widget.tile_size
                canvas_y = (tile_position[1] - self.map_widget.upper_left_tile_pos[1]) * self.map_widget.tile_size
                self.canvas_positions.append((canvas_x, canvas_y))
                if first_point:
                    self.polygon_path.moveTo(QPointF(canvas_x, canvas_y))
                    first_point = False
                else:
                    self.polygon_path.lineTo(QPointF(canvas_x, canvas_y))
        self.polygon_path.closeSubpath()
        self.setPath(self.polygon_path)
        if not move:
            self.map_widget.scene_qt.addItem(self)

    def delete(self):
        self.map_widget.scene_qt.removeItem(self)
        del self

    def get_canvas_positions(self):
        return [QPointF(x, y) for x, y in self.canvas_positions]
    
    def get_decimal_positions(self):
        return self.coordinates