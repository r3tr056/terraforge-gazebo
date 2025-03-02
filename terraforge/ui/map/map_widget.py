
from gc import enable
import math
import time
from click import Option
from fsspec import Callback
import requests
import io
import sqlite3
import threading

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QVBoxLayout, QWidget, QMenu, QMessageBox, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsPolygonItem
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QBrush, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF, QUrl, QTimer, pyqtSignal, QObject
from PIL import Image, ImageTk 

import pyperclip
import geocoder
from typing import Callable, List, Dict, Union, Tuple, Optional
from functools import partial

from PyQt6.QtWebEngineWidgets import QWebEngineView
from sympy import Q

from terraforge.ui.map.canvas_path import CanvasPathQt
from terraforge.ui.map.canvas_polygon import CanvasPolygonQt
from terraforge.ui.map.canvas_position_marker import CanvasPositionMarkerQt
from terraforge.ui.map.utils import osm_to_decimal_qt, decimal_to_osm_qt

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
	area_selected = pyqtSignal(list)
	polgon_area_selected = pyqtSignal(list)

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
		self.move_velocity: Tuple[float, float] = (0, 0)
		self.last_move_time: Optional[float] = None

		# Tile layout
		self.zoom: float = 0
		self.upper_left_tile_pos: Tuple[float, float] = (0, 0)
		self.lower_right_tile_pos: Tuple[float, float] = (0, 0)
		self.tile_size: int = 256
		self.last_zoom: float = self.zoom

		# Canvas objects, image cache
		self.canvas_tile_array: List[List[MapTileItemQt]] = []
		self.canvas_marker_list: List[CanvasPositionMarkerQt] = []
		self.canvas_path_list: List[CanvasPathQt] = []
		self.canvas_polygon_list: List[CanvasPolygonQt] = []

		self.tile_image_cache: Dict[str, QPixmap] = {}
		self.empty_tile_image = self._create_empty_tile_pixmap(QColor(190, 190, 190))
		self.not_loaded_tile_image = self._create_empty_tile_pixmap(QColor(250, 250, 250))

		# Tile server and database
		self.tile_server = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
		self.database_path = database_path
		self.use_database_only = use_database_only
		self.overlay_tile_server: Optional[str] = None
		self.max_zoom = max_zoom
		self.min_zoom: int = math.ceil(math.log2(math.ceil(self.width / self.tile_size)))

		# Pre-Caching (implement later if needed, start with basic functionality)
		self.pre_cache_position: Optional[Tuple[float, float]] = None
		self.pre_cache_thread = threading.Thread(daemon=True, target=self._pre_cache)
		self.pre_cache_thread.start()

		# Image loading in background threads
		# TODO : Upgrade to using QThreadPool and QT threads
		self.image_load_queue_tasks: List[tuple] = []
		self.image_load_queue_results: List[tuple] = []
		self.update_timer = QTimer(self)
		self.update_timer.timeout.connect(self._update_canvas_tile_images)
		self.update_timer.start(10)
		self.image_load_thread_pool: List[threading.Thread] = []

		for _ in range(25):
			image_load_thread = threading.Thread(daemon=True, target=self._load_images_background)
			image_load_thread.start()
			self.image_load_thread_pool.append(image_load_thread)

		self.set_zoom(17)
		self.set_position(52.516268, 13.377695)

		self.right_click_menu_commands: List[dict] = []

		self.is_selecting_area = False
		self.selection_start_point = QPointF()
		self.selection_rect_item = None

		self.is_drawing_polygon = False
		self.polygon_points_scene = []
		self.drawing_polygon_item = None

	def destroy(self):
		self.running = False
		super().deleteLater()

	def _create_empty_tile_pixmap(self, color: QColor) -> QPixmap:
		image = QImage(self.tile_size, self.tile_size, QImage.Format.Format_RGB32)
		image.fill(color)
		return QPixmap.fromImage(image)
	
	def add_right_click_menu_command(self, label: str, command: Callable, pass_coords: bool = False) -> None:
		self.right_click_menu_commands.append({"label": label, "command": command, "pass_coords": pass_coords})

	def add_left_click_map_command(self, callback_function):
		self.map_click_callback = callback_function

	def convert_canvas_coords_to_decimal_coords(self, canvas_x: int, canvas_y: int) -> tuple:
		relative_mouse_x = canvas_x / self.width
		relative_mouse_y = canvas_y / self.height

		tile_mouse_x = self.upper_left_tile_pos[0] + (self.lower_right_tile_pos[0] - self.upper_left_tile_pos[0]) * relative_mouse_x
		tile_mouse_y = self.upper_left_tile_pos[1] + (self.lower_right_tile_pos[1] - self.upper_left_tile_pos[1]) * relative_mouse_y

		coordinates_mouse_pos = osm_to_decimal_qt(tile_mouse_x, tile_mouse_y, round(self.zoom))
		return coordinates_mouse_pos
	
	def contextMenuEvent(self, event):
		menu = QMenu(self)
		coordinate_mouse_pos = self.convert_canvas_coords_to_decimal_coords(event.pos().x(), event.pos().y())

		copy_coords_action = menu.addAction(f"{coordinate_mouse_pos[0]:.7f} {coordinate_mouse_pos[1]:.7f}")
		copy_coords_action.triggered.connect(lambda: self._copy_coordinates_to_clipboard(coordinate_mouse_pos))

		if len(self.right_click_menu_commands) > 0:
			menu.addSeparator()

		for command in self.right_click_menu_commands:
			action = menu.addAction(command["label"])
			if command["pass_coords"]:
				action.triggered.connect(partial(command["command"], coordinate_mouse_pos))
			else:
				action.triggered.connect(command["command"])

		menu.popup(self.mapToGlobal(event.pos()))

	def _copy_coordinates_to_clipboard(self, coords):
		try:
			pyperclip.copy(f"{coords[0]:.7f} {coords[1]:.7f}")
			QMessageBox.information(self, "", "Coordinates copied to clipboard!")
		except Exception as e:
			QMessageBox.warning(self, "", f"Error copying to clipboard: {e}")

	def set_overlay_tile_server(self, overlay_server: str):
		self.overlay_tile_server = overlay_server

	def set_tile_server(self, tile_server: str, tile_size: int = 256, max_zoom: int = 19):
		self.image_load_queue_tasks = []
		self.max_zoom = max_zoom
		self.tile_size = tile_size
		self.min_zoom = math.ceil(math.log2(math.ceil(self.width / self.tile_size)))
		self.tile_server = tile_server
		self.tile_image_cache: Dict[str, QPixmap] = {}
		self.scene_qt.clear() # Clear scene to remove old tiles
		self.canvas_tile_array = [] # Reset tile array
		self.image_load_queue_results = []
		self._draw_initial_array() # Correct method name

	def get_position(self) -> tuple:
		""" returns current middle position of map widget in decimal coordinates """
		return osm_to_decimal_qt((self.lower_right_tile_pos[0] + self.upper_left_tile_pos[0]) / 2,
							  (self.lower_right_tile_pos[1] + self.upper_left_tile_pos[1]) / 2,
							  round(self.zoom))

	def fit_bounding_box(self, position_top_left: Tuple[float, float], position_bottom_right: Tuple[float, float]):
		QTimer.singleShot(100, partial(self._fit_bounding_box, position_top_left, position_bottom_right)) # Use QTimer

	def _fit_bounding_box(self, position_top_left: Tuple[float, float], position_bottom_right: Tuple[float, float]):
		""" Fit the map to contain a bounding box with the maximum zoom level possible. """
		# ... (Bounding box fitting logic - adapt from TkinterMapView, using Qt coordinate conversions) ...
		if not (position_top_left[0] > position_bottom_right[0] and position_top_left[1] < position_bottom_right[1]):
			raise ValueError("incorrect bounding box positions, <must be top_left_position> <bottom_right_position>")

		last_fitting_zoom_level = self.min_zoom
		middle_position_lat, middle_position_long = (position_bottom_right[0] + position_top_left[0]) / 2, (position_bottom_right[1] + position_top_left[1]) / 2

		for zoom in range(self.min_zoom, self.max_zoom + 1):
			middle_tile_position = decimal_to_osm_qt(middle_position_lat, middle_position_long, zoom)
			top_left_tile_position = decimal_to_osm_qt(*position_top_left, zoom)
			bottom_right_tile_position = decimal_to_osm_qt(*position_bottom_right, zoom)

			calc_top_left_tile_position = (middle_tile_position[0] - ((self.width / 2) / self.tile_size),
										   middle_tile_position[1] - ((self.height / 2) / self.tile_size))
			calc_bottom_right_tile_position = (middle_tile_position[0] + ((self.width / 2) / self.tile_size),
											   middle_tile_position[1] + ((self.height / 2) / self.tile_size))

			if calc_top_left_tile_position[0] < top_left_tile_position[0] and calc_top_left_tile_position[1] < top_left_tile_position[1] \
					and calc_bottom_right_tile_position[0] > bottom_right_tile_position[0] and calc_bottom_right_tile_position[1] > bottom_right_tile_position[1]:
				last_fitting_zoom_level = zoom
			else:
				break

		self.set_zoom(last_fitting_zoom_level)
		self.set_position(middle_position_lat, middle_position_long)

	def set_position(self, deg_x, deg_y, text=None, marker=False, **kwargs) -> Optional[CanvasPositionMarkerQt]:
		""" set new middle position of map in decimal coordinates """

		current_tile_position = decimal_to_osm_qt(deg_x, deg_y, round(self.zoom))
		self.upper_left_tile_pos = (current_tile_position[0] - ((self.width / 2) / self.tile_size),
									current_tile_position[1] - ((self.height / 2) / self.tile_size))

		self.lower_right_tile_pos = (current_tile_position[0] + ((self.width / 2) / self.tile_size),
									 current_tile_position[1] + ((self.height / 2) / self.tile_size))

		marker_object = None
		if marker is True:
			marker_object = self.set_marker(deg_x, deg_y, text, **kwargs)

		self._check_map_border_crossing() # Correct method name
		self._draw_initial_array() # Correct method name

		return marker_object

	def set_address(self, address_string: str, marker: bool = False, text: str = None, **kwargs) -> Union[CanvasPositionMarkerQt, bool]:
		""" Function uses geocode service of OpenStreetMap (Nominatim). """
		result = geocoder.osm(address_string)

		if result.ok:
			if hasattr(result, "bbox"):
				zoom_not_possible = True
				for zoom in range(self.min_zoom, self.max_zoom + 1):
					lower_left_corner = decimal_to_osm_qt(*result.bbox['southwest'], zoom)
					upper_right_corner = decimal_to_osm_qt(*result.bbox['northeast'], zoom)
					tile_width = upper_right_corner[0] - lower_left_corner[0]

					if tile_width > math.floor(self.width / self.tile_size):
						zoom_not_possible = False
						self.set_zoom(zoom)
						break
				if zoom_not_possible:
					self.set_zoom(self.max_zoom)
			else:
				self.set_zoom(10)

			if text is None:
				try:
					text = result.geojson['features'][0]['properties']['address']
				except:
					text = address_string

			return self.set_position(*result.latlng, marker=marker, text=text, **kwargs)
		else:
			return False

	def set_marker(self, deg_x: float, deg_y: float, text: str = None, **kwargs) -> CanvasPositionMarkerQt:
		marker = CanvasPositionMarkerQt(self, (deg_x, deg_y), text=text, **kwargs)
		marker.draw()
		self.canvas_marker_list.append(marker)
		return marker

	def set_path(self, position_list: list, **kwargs) -> CanvasPathQt:
		path = CanvasPathQt(self, position_list, **kwargs)
		path.draw()
		self.canvas_path_list.append(path)
		return path

	def set_polygon(self, position_list: list, **kwargs) -> CanvasPolygonQt:
		polygon = CanvasPolygonQt(self, position_list, **kwargs)
		polygon.draw()
		self.canvas_polygon_list.append(polygon)
		return polygon
	
	def set_area_selection_mode(self, enabled: bool):
		self.is_selecting_area = enabled
		self.is_drawing_polygon = False
		if enabled:
			self.setDragMode(QGraphicsView.DragMode.NoDrag)
		else:
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
		if self.drawing_polygon_item:
			self.scene_qt.removeItem(self.drawing_polygon_item)
			self.drawing_polygon_item = None
			self.polygon_points_scene = []

	def set_polygon_selection_mode(self, enabled: bool):
		self.is_drawing_polygon = enabled
		self.is_selecting_area = False
		if enabled:
			self.setDragMode(QGraphicsView.DragMode.NoDrag)
		else:
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
		if self.selection_rect_item:
			self.scene_qt.removeItem(self.selection_rect_item)
			self.selection_rect_item = None

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			if self.is_selecting_area:
				self.selection_start_point = self.mapToScene(event.pos())
				if self.selection_rect_item is None:
					self.selection_rect_item = QGraphicsRectItem()
					self.selection_rect_item.setPen(QPen(QColor("red"), 2, Qt.PenStyle.DashLine))
					self.scene_qt.addItem(self.selection_rect_item)
				self.update_selection_rect(event.pos())
				return
			
			if self.is_drawing_polygon:
				scene_pos = self.mapToScene(event.pos())
				self.polygon_points_scene.append(scene_pos)
				self.update_drawing_polygon()
				return
			
			self.fading_possible = False
			self.mouse_click_pos = event.pos()
			self.last_mouse_pos = event.pos()
		super().mousePressEvent(event)

	def mouseMoveEvent(self, event):
		if self.is_selecting_area and event.buttns() == Qt.MouseButton.LeftButton:
			self.update_selection_rect(event.pos())
			return
		
		if self.is_drawing_polygon and event.buttons() == Qt.MouseButton.LeftButton:
			self.update_drawing_polygon(event.pos())
			return
		
		if event.buttons() == Qt.MouseButton.LeftButton:
			delta = event.pos() - self.last_mouse_pos
			self._move_map_by(delta)
			self.last_mouse_pos = event.pos()
		super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			if self.is_selecting_area:
				self.finalize_area_selection(event.pos())
				return
			
			if self.is_drawing_polygon:
				self.finalize_polygon_selection(event.pos())
				return
			
			self.fading_possible = True
			self.last_move_time = time.time()
			if event.pos() == self.mouse_click_pos:
				coordinate_mouse_pos = self.convert_canvas_coords_to_decimal_coords(event.pos().x(), event.pos().y())
				self.map_clicked.emit(coordinate_mouse_pos)
				if self.map_click_callback:
					self.map_click_callback(coordinate_mouse_pos)
			else:
				self.after(1, self._fading_move)
		super().mouseReleaseEvent(event)

	def update_selection_rect(self, mouse_pos_viewport):
		end_point_scene = self.mapToScene(mouse_pos_viewport)
		rect = QRectF(self.selection_start_point, end_point_scene).normalized()
		self.selection_rect_item.setRect(rect)

	def finalize_area_selection(self, mouse_pos_viewport):
		if self.selection_rect_item:
			bounding_rect_scene = self.selection_rect_item.rect()
			top_left_scene = bounding_rect_scene.topLeft()
			bottom_right_scene = bounding_rect_scene.bottomRight()

			# convert scene coordinates to decimal coordinates
			top_left_viewport = self.mapFromScene(top_left_scene)
			bottom_right_viewport = self.mapFromScene(bottom_right_scene)

			top_left_decimal = self.convert_canvas_coords_to_decimal_coords(top_left_viewport.x(), top_left_viewport.y())
			bottom_right_decimal = self.convert_canvas_coords_to_decimal_coords(bottom_right_viewport.x(), bottom_right_viewport.y())

			# emit signal with bounding box coordinates (top-left, bottom-right decimal coords)
			self.area_selected.emit([top_left_decimal, bottom_right_decimal])

			# Remove the selection rectangle after selection
			self.scene_qt.removeItem(self.selection_rect_item)
			self.selection_rect_item = None
			self.is_selecting_area = False
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

	def update_drawing_polygon(self, mouse_pos_viewport=None):
		polygon = QPolygonF()
		for point in self.polygon_points_scene:
			polygon.append(point)
		if mouse_pos_viewport:
			polygon.append(self.mapToScene(mouse_pos_viewport))

		if self.drawing_polygon_item is None:
			self.drawing_polygon_item = QGraphicsPolygonItem()
			self.drawing_polygon_item.setPen(QPen(QColor("green"), 2, Qt.PenStyle.SolidLine))
			self.drawing_polygon_item.setBrush(QBrush(QColor(0, 255, 0, 50)))
			self.scene_qt.addItem(self.drawing_polygon_item)

		self.drawing_polygon_item.setPolygon(polygon)

	def finalize_polygon_selection(self, mouse_pos_viewport):
		if self.drawing_polygon_item:
			polygon_scene = self.drawing_polygon_item.polygon()
			polygon_coords_decimal = []

			for point_scene in polygon_scene:
				point_viewport = self.mapFromScene(point_scene)
				decimal_coods = self.convert_canvas_coords_to_decimal_coords(point_viewport.x(), point_viewport.y())
				polygon_coords_decimal.append(decimal_coods)

			self.polygon_area_selected.emit(polygon_coords_decimal)

			self.scene_qt.removeItem(self.drawing_polygon_item)
			self.drawing_polygon_item = None
			self.polygon_poinst	 = []
			self.is_drawing_polygon = False
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

	def delete(self, map_object: any):
		if isinstance(map_object, (CanvasPathQt, CanvasPositionMarkerQt, CanvasPolygonQt)):
			map_object.delete()

	def delete_all_marker(self):
		for i in range(len(self.canvas_marker_list) - 1, -1, -1):
			self.canvas_marker_list[i].delete()
		self.canvas_marker_list = []

	def delete_all_path(self):
		for i in range(len(self.canvas_path_list) - 1, -1, -1):
			self.canvas_path_list[i].delete()
		self.canvas_path_list = []

	def delete_all_polygon(self):
		for i in range(len(self.canvas_polygon_list) - 1, -1, -1):
			self.canvas_polygon_list[i].delete()
		self.canvas_polygon_list = []

	def _manage_z_order(self): # Correct method name, consider if needed in Qt GraphicsView
		pass # Z-order management in QGraphicsView is different, items are drawn in order added to scene

	def _pre_cache(self): # Correct method name
		""" single threaded pre-chache tile images in area of self.pre_cache_position """
		# ... (Pre-caching logic - adapt from TkinterMapView, using QPixmap and QImage) ...
		last_pre_cache_position = None
		radius = 1
		zoom = round(self.zoom)

		if self.database_path is not None:
			db_connection = sqlite3.connect(self.database_path)
			db_cursor = db_connection.cursor()
		else:
			db_cursor = None

		while self.running:
			if last_pre_cache_position != self.pre_cache_position:
				last_pre_cache_position = self.pre_cache_position
				zoom = round(self.zoom)
				radius = 1

			if last_pre_cache_position is not None and radius <= 8:
				for x in range(self.pre_cache_position[0] - radius, self.pre_cache_position[0] + radius + 1):
					if f"{zoom}{x}{self.pre_cache_position[1] + radius}" not in self.tile_image_cache:
						self._request_image(zoom, x, self.pre_cache_position[1] + radius, db_cursor=db_cursor)
					if f"{zoom}{x}{self.pre_cache_position[1] - radius}" not in self.tile_image_cache:
						self._request_image(zoom, x, self.pre_cache_position[1] - radius, db_cursor=db_cursor)

				for y in range(self.pre_cache_position[1] - radius, self.pre_cache_position[1] + radius + 1):
					if f"{zoom}{self.pre_cache_position[0] + radius}{y}" not in self.tile_image_cache:
						self._request_image(zoom, self.pre_cache_position[0] + radius, y, db_cursor=db_cursor)
					if f"{zoom}{self.pre_cache_position[0] - radius}{y}" not in self.tile_image_cache:
						self._request_image(zoom, self.pre_cache_position[0] - radius, y, db_cursor=db_cursor)
				radius += 1
			else:
				threading.Event().wait(0.1) # Use threading.Event().wait instead of time.sleep

			if len(self.tile_image_cache) > 10_000:
				keys_to_delete = []
				for key in list(self.tile_image_cache.keys()): # Iterate over a copy to allow deletion
					if len(self.tile_image_cache) - len(keys_to_delete) > 10_000:
						keys_to_delete.append(key)
				for key in keys_to_delete:
					del self.tile_image_cache[key]

	def _request_image(self, zoom: int, x: int, y: int, db_cursor=None) -> Optional[QPixmap]: # Correct method name
		# ... (Image request logic - adapt from TkinterMapView, using QPixmap and QImage) ...
		if db_cursor is not None:
			try:
				db_cursor.execute("SELECT t.tile_image FROM tiles t WHERE t.zoom=? AND t.x=? AND t.y=? AND t.server=?;",
								  (zoom, x, y, self.tile_server))
				result = db_cursor.fetchone()
				if result is not None:
					image = QImage.fromData(result[0]) # Load QImage from byte array
					pixmap = QPixmap.fromImage(image)
					self.tile_image_cache[f"{zoom}{x}{y}"] = pixmap
					return pixmap
				elif self.use_database_only:
					return self.empty_tile_image
				else:
					pass
			except sqlite3.OperationalError:
				if self.use_database_only:
					return self.empty_tile_image
				else:
					pass
			except Exception:
				return self.empty_tile_image

		try:
			url = self.tile_server.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(zoom))
			response = requests.get(url, stream=True, headers={"User-Agent": "TkinterMapView"})
			response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
			image_data = response.content
			image = QImage.fromData(image_data) # Load QImage directly from bytes
			if image.isNull(): # Check if image loading failed
				return self.empty_tile_image

			if self.overlay_tile_server is not None:
				url_overlay = self.overlay_tile_server.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(zoom))
				response_overlay = requests.get(url_overlay, stream=True, headers={"User-Agent": "TkinterMapView"})
				response_overlay.raise_for_status()
				overlay_image_data = response_overlay.content
				overlay_image = QImage.fromData(overlay_image_data)
				if not overlay_image.isNull():
					image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied) # Ensure alpha channel
					overlay_image = overlay_image.scaled(self.tile_size, self.tile_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied) # Resize and ensure alpha
					painter = QPainter(image)
					painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver) # Alpha blending
					painter.drawImage(0, 0, overlay_image)
					painter.end()

			pixmap = QPixmap.fromImage(image)
			self.tile_image_cache[f"{zoom}{x}{y}"] = pixmap
			return pixmap

		except requests.exceptions.RequestException: # Catch connection errors, timeouts, etc.
			return self.empty_tile_image
		except Exception: # Catch other potential errors like PIL errors
			return self.empty_tile_image

	def _get_tile_image_from_cache(self, zoom: int, x: int, y: int) -> Union[QPixmap, bool]: # Correct method name
		if f"{zoom}{x}{y}" not in self.tile_image_cache:
			return False
		else:
			return self.tile_image_cache[f"{zoom}{x}{y}"]

	def _load_images_background(self): # Correct method name
		# ... (Background image loading logic - adapt from TkinterMapView, using QPixmap and QImage) ...
		if self.database_path is not None:
			db_connection = sqlite3.connect(self.database_path)
			db_cursor = db_connection.cursor()
		else:
			db_cursor = None

		while self.running:
			if self.image_load_queue_tasks: # Check if queue is not empty
				task = self.image_load_queue_tasks.pop(0) # FIFO for queue

				zoom = task[0][0]
				x, y = task[0][1], task[0][2]
				canvas_tile = task[1]

				image = self._get_tile_image_from_cache(zoom, x, y) # Correct method name
				if image is False:
					image = self._request_image(zoom, x, y, db_cursor=db_cursor) # Correct method name
					if image is None:
						self.image_load_queue_tasks.append(task) # Re-queue if image load failed
						continue # Skip to next iteration

				self.image_load_queue_results.append(((zoom, x, y), canvas_tile, image)) # Append to results queue

			else:
				threading.Event().wait(0.01) # Use threading.Event().wait instead of time.sleep

	def _update_canvas_tile_images(self): # Correct method name
		# ... (Canvas tile image update logic - adapt from TkinterMapView, using QPixmap and QImage for Qt) ...
		while self.image_load_queue_results: # Process all available results
			result = self.image_load_queue_results.pop(0)

			zoom, x, y = result[0][0], result[0][1], result[0][2]
			canvas_tile = result[1]
			image = result[2]

			if zoom == round(self.zoom): # Check zoom level
				canvas_tile.set_image(image)

	def _insert_row(self, insert: int, y_name_position: int): # Correct method name
		# ... (Row insertion logic - adapt from TkinterMapView, for Qt) ...
		for x_pos in range(len(self.canvas_tile_array)):
			tile_name_position = self.canvas_tile_array[x_pos][0].tile_name_position[0], y_name_position

			image = self._get_tile_image_from_cache(round(self.zoom), *tile_name_position) # Correct method name
			if image is False:
				canvas_tile = MapTileItemQt(tile_name_position)
				canvas_tile.set_image(self.not_loaded_tile_image)
				self.image_load_queue_tasks.append(((round(self.zoom), *tile_name_position), canvas_tile))
			else:
				canvas_tile = MapTileItemQt(tile_name_position)
				canvas_tile.set_image(image)

			self.scene_qt.addItem(canvas_tile) # Add tile to scene
			self.canvas_tile_array[x_pos].insert(insert, canvas_tile)

	def _insert_column(self, insert: int, x_name_position: int): # Correct method name
		# ... (Column insertion logic - adapt from TkinterMapView, for Qt) ...
		canvas_tile_column = []

		for y_pos in range(len(self.canvas_tile_array[0])):
			tile_name_position = x_name_position, self.canvas_tile_array[0][y_pos].tile_name_position[1]

			image = self._get_tile_image_from_cache(round(self.zoom), *tile_name_position) # Correct method name
			if image is False:
				canvas_tile = MapTileItemQt(tile_name_position)
				canvas_tile.set_image(self.not_loaded_tile_image)
				self.image_load_queue_tasks.append(((round(self.zoom), *tile_name_position), canvas_tile))
			else:
				canvas_tile = MapTileItemQt(tile_name_position)
				canvas_tile.set_image(image)

			self.scene_qt.addItem(canvas_tile) # Add tile to scene
			canvas_tile_column.append(canvas_tile)

		self.canvas_tile_array.insert(insert, canvas_tile_column)

	def _draw_initial_array(self): # Correct method name
		# ... (Initial array drawing logic - adapt from TkinterMapView, for Qt) ...
		self.image_load_queue_tasks = []
		self.scene_qt.clear() # Clear the scene

		x_tile_range = math.ceil(self.lower_right_tile_pos[0]) - math.floor(self.upper_left_tile_pos[0])
		y_tile_range = math.ceil(self.lower_right_tile_pos[1]) - math.floor(self.upper_left_tile_pos[1])

		upper_left_x = math.floor(self.upper_left_tile_pos[0])
		upper_left_y = math.floor(self.upper_left_tile_pos[1])

		self.canvas_tile_array = [] # Reset tile array

		for x_pos in range(x_tile_range):
			canvas_tile_column = []
			for y_pos in range(y_tile_range):
				tile_name_position = upper_left_x + x_pos, upper_left_y + y_pos

				image = self._get_tile_image_from_cache(round(self.zoom), *tile_name_position) # Correct method name
				if image is False:
					canvas_tile = MapTileItemQt(tile_name_position)
					canvas_tile.set_image(self.not_loaded_tile_image) # Set placeholder image
					self.image_load_queue_tasks.append(((round(self.zoom), *tile_name_position), canvas_tile))
				else:
					canvas_tile = MapTileItemQt(tile_name_position)
					canvas_tile.set_image(image)

				canvas_tile_column.append(canvas_tile)
				self.scene_qt.addItem(canvas_tile) # Add tile to scene

			self.canvas_tile_array.append(canvas_tile_column)

		for x_pos in range(len(self.canvas_tile_array)):
			for y_pos in range(len(self.canvas_tile_array[0])):
				tile = self.canvas_tile_array[x_pos][y_pos]
				tile_pos_x = (x_pos / x_tile_range) * self.width
				tile_pos_y = (y_pos / y_tile_range) * self.height
				tile.set_position(QPointF(tile_pos_x, tile_pos_y)) # Position tile in scene

		for marker in self.canvas_marker_list: # Draw markers on top of tiles
			marker.draw()
		for path in self.canvas_path_list:
			path.draw()
		for polygon in self.canvas_polygon_list:
			polygon.draw()

		self.pre_cache_position = (round((self.upper_left_tile_pos[0] + self.lower_right_tile_pos[0]) / 2),
								   round((self.upper_left_tile_pos[1] + self.lower_right_tile_pos[1]) / 2))

	def _draw_move(self, called_after_zoom: bool = False): # Correct method name
		# ... (Move drawing logic - adapt from TkinterMapView, for Qt) ...
		if self.canvas_tile_array:
			top_y_name_position = self.canvas_tile_array[0][0].tile_name_position[1]
			top_y_diff = self.upper_left_tile_pos[1] - top_y_name_position
			if top_y_diff <= 0:
				for y_diff in range(1, math.ceil(-top_y_diff) + 1):
					self._insert_row(insert=0, y_name_position=top_y_name_position - y_diff) # Correct method name
			elif top_y_diff >= 1:
				for y_diff in range(1, math.ceil(top_y_diff)):
					for x in range(len(self.canvas_tile_array) - 1, -1, -1):
						if len(self.canvas_tile_array[x]) > 1:
							self.scene_qt.removeItem(self.canvas_tile_array[x][0]) # Remove from scene
							del self.canvas_tile_array[x][0]

			left_x_name_position = self.canvas_tile_array[0][0].tile_name_position[0]
			left_x_diff = self.upper_left_tile_pos[0] - left_x_name_position
			if left_x_diff <= 0:
				for x_diff in range(1, math.ceil(-left_x_diff) + 1):
					self._insert_column(insert=0, x_name_position=left_x_name_position - x_diff) # Correct method name
			elif left_x_diff >= 1:
				for x_diff in range(1, math.ceil(left_x_diff)):
					if len(self.canvas_tile_array) > 1:
						for y in range(len(self.canvas_tile_array[0]) - 1, -1, -1):
							self.scene_qt.removeItem(self.canvas_tile_array[0][y]) # Remove from scene
							del self.canvas_tile_array[0][y]
						del self.canvas_tile_array[0]

			bottom_y_name_position = self.canvas_tile_array[0][-1].tile_name_position[1]
			bottom_y_diff = self.lower_right_tile_pos[1] - bottom_y_name_position
			if bottom_y_diff >= 1:
				for y_diff in range(1, math.ceil(bottom_y_diff)):
					self._insert_row(insert=len(self.canvas_tile_array[0]), y_name_position=bottom_y_name_position + y_diff) # Correct method name
			elif bottom_y_diff <= 1:
				for y_diff in range(1, math.ceil(-bottom_y_diff) + 1):
					for x in range(len(self.canvas_tile_array) - 1, -1, -1):
						if len(self.canvas_tile_array[x]) > 1:
							self.scene_qt.removeItem(self.canvas_tile_array[x][-1]) # Remove from scene
							del self.canvas_tile_array[x][-1]

			right_x_name_position = self.canvas_tile_array[-1][0].tile_name_position[0]
			right_x_diff = self.lower_right_tile_pos[0] - right_x_name_position
			if right_x_diff >= 1:
				for x_diff in range(1, math.ceil(right_x_diff)):
					self._insert_column(insert=len(self.canvas_tile_array), x_name_position=right_x_name_position + x_diff) # Correct method name
			elif right_x_diff <= 1:
				for x_diff in range(1, math.ceil(-right_x_diff) + 1):
					if len(self.canvas_tile_array) > 1:
						for y in range(len(self.canvas_tile_array[-1]) - 1, -1, -1):
							self.scene_qt.removeItem(self.canvas_tile_array[-1][y]) # Remove from scene
							del self.canvas_tile_array[-1][y]
						del self.canvas_tile_array[-1]

		x_tile_range = math.ceil(self.lower_right_tile_pos[0]) - math.floor(self.upper_left_tile_pos[0])
		y_tile_range = math.ceil(self.lower_right_tile_pos[1]) - math.floor(self.upper_left_tile_pos[1])

		for x_pos in range(len(self.canvas_tile_array)):
			for y_pos in range(len(self.canvas_tile_array[0])):
				tile = self.canvas_tile_array[x_pos][y_pos]
				tile_pos_x = (x_pos / x_tile_range) * self.width
				tile_pos_y = (y_pos / y_tile_range) * self.height
				tile.set_position(QPointF(tile_pos_x, tile_pos_y))

		for marker in self.canvas_marker_list:
			marker.draw()
		for path in self.canvas_path_list:
			path.draw(move=not called_after_zoom)
		for polygon in self.canvas_polygon_list:
			polygon.draw(move=not called_after_zoom)

		self.pre_cache_position = (round((self.upper_left_tile_pos[0] + self.lower_right_tile_pos[0]) / 2),
								   round((self.upper_left_tile_pos[1] + self.lower_right_tile_pos[1]) / 2))

	def _draw_zoom(self): # Correct method name
		# ... (Zoom drawing logic - adapt from TkinterMapView, for Qt) ...
		if self.canvas_tile_array:
			self.image_load_queue_tasks = []
			upper_left_x = math.floor(self.upper_left_tile_pos[0])
			upper_left_y = math.floor(self.upper_left_tile_pos[1])

			x_tile_range = math.ceil(self.lower_right_tile_pos[0]) - math.floor(self.upper_left_tile_pos[0])
			y_tile_range = math.ceil(self.lower_right_tile_pos[1]) - math.floor(self.upper_left_tile_pos[1])

			for x_pos in range(len(self.canvas_tile_array)):
				for y_pos in range(len(self.canvas_tile_array[0])):
					tile = self.canvas_tile_array[x_pos][y_pos]
					tile_name_position = upper_left_x + x_pos, upper_left_y + y_pos

					image = self._get_tile_image_from_cache(round(self.zoom), *tile_name_position) # Correct method name
					if image is False:
						image = self.not_loaded_tile_image
						self.image_load_queue_tasks.append(((round(self.zoom), *tile_name_position), tile))

					tile.set_image(image)
					tile_pos_x = (x_pos / x_tile_range) * self.width
					tile_pos_y = (y_pos / y_tile_range) * self.height
					tile.set_position(QPointF(tile_pos_x, tile_pos_y))


			self.pre_cache_position = (round((self.upper_left_tile_pos[0] + self.lower_right_tile_pos[0]) / 2),
									   round((self.upper_left_tile_pos[1] + self.lower_right_tile_pos[1]) / 2))

			self._draw_move(called_after_zoom=True) # Correct method name

	def mousePressEvent(self, event): # Override mouse press event
		if event.button() == Qt.MouseButton.LeftButton:
			self.fading_possible = False
			self.mouse_click_pos = event.pos()
			self.last_mouse_pos = event.pos()
		super().mousePressEvent(event)

	def mouseMoveEvent(self, event): # Override mouse move event
		if event.buttons() == Qt.MouseButton.LeftButton:
			delta = event.pos() - self.last_mouse_pos
			self._move_map_by(delta) # Call internal move function
			self.last_mouse_pos = event.pos()
		super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event): # Override mouse release event
		if event.button() == Qt.MouseButton.LeftButton:
			self.fading_possible = True
			self.last_move_time = time.time()
			if event.pos() == self.mouse_click_pos: # Check for click vs drag
				coordinate_mouse_pos = self.convert_canvas_coords_to_decimal_coords(event.pos().x(), event.pos().y())
				self.map_clicked.emit(coordinate_mouse_pos) # Emit signal with coordinates
				if self.map_click_callback: # Also call callback if set for compatibility
					self.map_click_callback(coordinate_mouse_pos)
			else:
				self.after(1, self._fading_move) # Start fading animation
		super().mouseReleaseEvent(event)

	def _move_map_by(self, pixel_delta: QPointF): # Internal move function
		mouse_move_x = pixel_delta.x()
		mouse_move_y = pixel_delta.y()

		delta_t = 1.0/60.0 # Assume 60 FPS, for velocity calculation. Not used for fading in this basic version.
		self.move_velocity = (mouse_move_x / delta_t, mouse_move_y / delta_t)

		tile_x_range = self.lower_right_tile_pos[0] - self.upper_left_tile_pos[0]
		tile_y_range = self.lower_right_tile_pos[1] - self.upper_left_tile_pos[1]

		tile_move_x = (mouse_move_x / self.width) * tile_x_range
		tile_move_y = (mouse_move_y / self.height) * tile_y_range

		self.lower_right_tile_pos = (self.lower_right_tile_pos[0] + tile_move_x, self.lower_right_tile_pos[1] + tile_move_y)
		self.upper_left_tile_pos = (self.upper_left_tile_pos[0] + tile_move_x, self.upper_left_tile_pos[1] + tile_move_y)

		self._check_map_border_crossing() # Correct method name
		self._draw_move() # Correct method name

	def wheelEvent(self, event): # Override mouse wheel event
		relative_mouse_x = event.pos().x() / self.width
		relative_mouse_y = event.pos().y() / self.height

		delta = event.angleDelta().y() # Get wheel delta
		new_zoom = self.zoom + delta * 0.001 # Adjust zoom speed as needed, smaller value = slower zoom

		self.set_zoom(new_zoom, relative_mouse_x, relative_mouse_y) # Call zoom function

	def _fading_move(self): # Correct method name
		# ... (Fading move logic - adapt from TkinterMapView, for Qt, using QTimer for animation) ...
		delta_t = 1.0/60.0 # Assume 60 FPS for fading animation

		if self.fading_possible:
			mouse_move_x = self.move_velocity[0] * delta_t
			mouse_move_y = self.move_velocity[1] * delta_t

			lowering_factor = 2 ** (-9 * delta_t)
			self.move_velocity = (self.move_velocity[0] * lowering_factor, self.move_velocity[1] * lowering_factor)

			tile_x_range = self.lower_right_tile_pos[0] - self.upper_left_tile_pos[0]
			tile_y_range = self.lower_right_tile_pos[1] - self.upper_left_tile_pos[1]

			tile_move_x = (mouse_move_x / self.width) * tile_x_range
			tile_move_y = (mouse_move_y / self.height) * tile_y_range

			self.lower_right_tile_pos = (self.lower_right_tile_pos[0] + tile_move_x, self.lower_right_tile_pos[1] + tile_move_y)
			self.upper_left_tile_pos = (self.upper_left_tile_pos[0] + tile_move_x, self.upper_left_tile_pos[1] + tile_move_y)

			self._check_map_border_crossing() # Correct method name
			self._draw_move() # Correct method name

			if abs(self.move_velocity[0]) > 1 or abs(self.move_velocity[1]) > 1:
				QTimer.singleShot(1, self._fading_move) # Re-trigger fading animation
		else:
			self.move_velocity = (0, 0) # Reset velocity if fading is no longer possible (mouse pressed)

	def set_zoom(self, zoom: int, relative_pointer_x: float = 0.5, relative_pointer_y: float = 0.5):
		# ... (Zoom setting logic - adapt from TkinterMapView, for Qt) ...
		mouse_tile_pos_x = self.upper_left_tile_pos[0] + (self.lower_right_tile_pos[0] - self.upper_left_tile_pos[0]) * relative_pointer_x
		mouse_tile_pos_y = self.upper_left_tile_pos[1] + (self.lower_right_tile_pos[1] - self.upper_left_tile_pos[1]) * relative_pointer_y

		current_deg_mouse_position = osm_to_decimal_qt(mouse_tile_pos_x,
													mouse_tile_pos_y,
													round(self.zoom))
		self.zoom = zoom

		if self.zoom > self.max_zoom:
			self.zoom = self.max_zoom
		if self.zoom < self.min_zoom:
			self.zoom = self.min_zoom

		current_tile_mouse_position = decimal_to_osm_qt(*current_deg_mouse_position, round(self.zoom))

		self.upper_left_tile_pos = (current_tile_mouse_position[0] - relative_pointer_x * (self.width / self.tile_size),
									current_tile_mouse_position[1] - relative_pointer_y * (self.height / self.tile_size))

		self.lower_right_tile_pos = (current_tile_mouse_position[0] + (1 - relative_pointer_x) * (self.width / self.tile_size),
									 current_tile_mouse_position[1] + (1 - relative_pointer_y) * (self.height / self.tile_size))

		if round(self.zoom) != round(self.last_zoom):
			self._check_map_border_crossing() # Correct method name
			self._draw_zoom() # Correct method name
			self.last_zoom = round(self.zoom)

	def _check_map_border_crossing(self): # Correct method name
		# ... (Border crossing check logic - adapt from TkinterMapView, for Qt) ...
		diff_x, diff_y = 0, 0
		if self.upper_left_tile_pos[0] < 0:
			diff_x += 0 - self.upper_left_tile_pos[0]
		if self.upper_left_tile_pos[1] < 0:
			diff_y += 0 - self.upper_left_tile_pos[1]
		if self.lower_right_tile_pos[0] > 2 ** round(self.zoom):
			diff_x -= self.lower_right_tile_pos[0] - (2 ** round(self.zoom))
		if self.lower_right_tile_pos[1] > 2 ** round(self.zoom):
			diff_y -= self.lower_right_tile_pos[1] - (2 ** round(self.zoom))

		self.upper_left_tile_pos = self.upper_left_tile_pos[0] + diff_x, self.upper_left_tile_pos[1] + diff_y
		self.lower_right_tile_pos = self.lower_right_tile_pos[0] + diff_x, self.lower_right_tile_pos[1] + diff_y

	def button_zoom_in(self): # Correct method name, not using canvas buttons for now
		self.set_zoom(self.zoom + 1, relative_pointer_x=0.5, relative_pointer_y=0.5)

	def button_zoom_out(self): # Correct method name, not using canvas buttons for now
		self.set_zoom(self.zoom - 1, relative_pointer_x=0.5, relative_pointer_y=0.5)

	
	def decimal_to_tile_position(self, decimal_latitude: float, decimal_longitude: float) -> Union[tuple, None]:
		""" converts decimal coordinates to canvas position depending on current zoom and map position """

		if not (-90 <= decimal_latitude <= 90 and -180 <= decimal_longitude <= 180):
			return None # coordinates out of range

		tile_x, tile_y = decimal_to_osm_qt(decimal_latitude, decimal_longitude, round(self.zoom))

		x_pos = (tile_x - self.upper_left_tile_pos[0]) * self.tile_size
		y_pos = (tile_y - self.upper_left_tile_pos[1]) * self.tile_size

		return x_pos, y_pos


