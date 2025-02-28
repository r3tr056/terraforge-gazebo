
import math
from fsspec import Callback
import requests
import io
import sqlite3
import threading

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, QMenu, QMessageBox, QGraphicsPixmapItem
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QPointF, QRectF, QUrl, QTimer, pyqtSignal, QObject
from PIL import Image, ImageTk 

import pyperclip
import geocoder
from typing import Callable, List, Dict, Union, Tuple, Optional
from functools import partial

from PyQt6.QtWebEngineWidgets import QWebEngineView

class MapTileItemQt(QGraphicsPixmapItem):
    def __init__(self, tile_name_position: Tuple[int, int], parent=None):
        super().__init__(parent)
        self.tile_name_position = tile_name_position
        self.image = None
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def set_image(self, image: QPixmap):
        self.setPixmap(image)
        self.image = image

    def set_position(self, pos: QPointF):
        self.setPos(pos)

    def __del__(self):
        pass


class MapViewWidgetQt(QGraphicsView):
    map_clicked = pyqtSignal(tuple)

    def __init__(self, parent=None, width: int = 300, height: int = 200, corner_radius: int = 0, bg_color: str = None, database_path: str = None, use_database_only: bool = False, max_zoom: int = 19, **kwargs):
        super().__init__(parent)

        self.running = True

        self.width = width
        self.height = height
        self.corner_radius = corner_radius if corner_radius <= 30 else 30
        self.setFixedSize(self.width, self.height)

        self.bg_color = bg_color if bg_color else QColor("#F1EFEA")
        self.setBackgroundBrush(QBrush(self.bg_color))
        self.setSceneRect(QRectF(0, 0, self.width, self.height))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scene_qt = QGraphicsScene(self)
        self.setScene(self.scene_qt)

        # zoom buttons
        self.last_mouse_pos = QPointF()
        self.mouse_click_pos = QPointF()
        self.map_click_callback: Optional[Callback] = None

        self.fading_possible: bool = True
