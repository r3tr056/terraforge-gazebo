
import math
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QPointF, QRectF

def decimal_to_osm_qt(decimal_lat: float, decimal_lon: float, zoom: int) -> tuple:
    tile_x = ((decimal_lon + 180) / 360) * (2 ** zoom)
    tile_y = (1 - (math.log(math.tan(math.radians(decimal_lat)) + 1 / math.cos(math.radians(decimal_lat))) / math.pi)) / 2 * (2 ** zoom)
    return tile_x, tile_y

def osm_to_decimal_qt(tile_x: float, tile_y: float, zoom: int) -> tuple:
    n = 2.0 ** zoom
    decimal_lon = tile_x / n * 360.0 - 180.0
    decimal_lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * tile_y / n)))
    decimal_lat = math.degrees(decimal_lat_rad)
    return decimal_lat, decimal_lon



