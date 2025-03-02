

from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QPointF

class CanvasPathQt(QGraphicsItem):
    def __init__(self, map_widget, coordinates: list, color="blue", width=3, **kwargs):
        super().__init__()
        self.map_widget = map_widget
        self.coordinates = coordinates
        self.color = QColor(color)
        self.width = width
        self.canvas_postions = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.path = QPainterPath()

    def boundingRect(self):
        return self.path.boundingRect()
    
    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(self.color, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(self.path)

    def draw(self, move=False):
        self.path = QPainterPath()
        self.canvas_postions = []

        first_point = True
        for coordinates in self.coordinates:
            tile_position = self.map_widget.decimal_to_tile_position(*coordinates)
            if tile_position is not None:
                canvas_x = (tile_position[0] - self.map_widget.upper_left_tile_pos[0]) * self.map_widget.tile_size
                canvas_y = (tile_position[1] - self.map_widget.upper_left_tile_pos[1]) * self.map_widget.tile_size
                self.canvas_postions.append((canvas_x, canvas_y))
                if first_point:
                    self.path.moveTo(QPointF(canvas_x, canvas_y))
                    first_point = False
                else:
                    self.path.lineTo(QPointF(canvas_x, canvas_y))
        self.setPath(self.path)
        if not move:
            self.map_widget.scene_qt.addItem(self)

    def delete(self):
        self.map_widget.scene_qt.removeItem(self)
        del self

    def get_canvas_position(self):
        return [QPointF(x, y) for x, y in self.canvas_postions]

    def get_decimal_positions(self):
        return self.coordinates
