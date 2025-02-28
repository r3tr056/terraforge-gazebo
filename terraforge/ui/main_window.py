

import sys
import os
import logging
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QApplication
from PyQt6.uic import loadUi
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import pyqtSlot, QThread, pyqtSignal, QUrl
from utils.config import config
from utils.logging import setup_logger
from utils.coordinates import CoordinateConverter
from data_acquisition import elevation, osm, textures
from data_processing import elevation_processor, building_processor, texture_processor
from data_processing.sdf_builder import SDFWorldBuilder
import shutil
import json
import shapely.geometry

logger = setup_logger('gui_app', log_level=logging.DEBUG)

class WorldGeneratorThread(QThread):
    # Threads for running the world generation process to avoid blocking the UI
    generation_started = pyqtSignal()
    generation_progress = pyqtSignal(str)
    generation_finished = pyqtSignal(str)
    generation_error = pyqtSignal(str)

    def __init__(self, latitude, longitude, radius, output_dir, world_name):
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude
        self.radius = radius
        self.output_dir = output_dir
        self.world_name = world_name

    def run(self):
        self.generation_started.emit()
        origin_location = (self.latitude, self.longitude)
        location_name = f"loc_{self.latitude:.4f}_{self.longitude:.4f}"

        self.generation_progress.emit("Starting Data Acquisition...")
        dem_output_path = os.path.join(config.DEM_OUTPUT_DIR, f"{location_name}_dem.tif")
        osm_output_path = os.path.join(config.OSM_OUTPUT_DIR, f"{location_name}_buildings.geojson")
        texture_output_dir = os.path.join(config.TEXTURE_OUTPUT_DIR, f"{location_name}_texture")
        os.makedirs(texture_output_dir, exist_ok=True)

        try:
            elevation.download_dem(origin_location, self.radius, dem_output_path)
            self.generation_progress.emit("DEM data downloaded.")
            osm.download_osm_buildings(origin_location, self.radius, osm_output_path)
            self.generation_progress.emit("OSM building data downloaded.")
            textures.download_satellite_texture_tiles(origin_location, self.radius, texture_output_dir, mapbox_api_key=config.MAPBOX_API_KEY)
            self.generation_progress.emit("Satellite textures downloaded.")
        except Exception as e:
            error_msg = f"Data acquisition failed: {e}"
            logger.error(error_msg)
            self.generation_error.emit(error_msg)
            return

        # --- Data Processing ---
        self.generation_progress.emit("Starting Data Processing...")
        heightmap_output_path = os.path.join(config.DEM_OUTPUT_DIR, f"{location_name}_heightmap.png")
        building_sdf_output_dir = os.path.join(config.OSM_OUTPUT_DIR, f"{location_name}_building_models_sdf")
        processed_texture_output_dir = os.path.join(config.TEXTURE_OUTPUT_DIR, "processed_textures")
        processed_texture_output_path = os.path.join(processed_texture_output_dir, "satellite_texture.png")

        try:
            elevation_processor.process_dem_to_heightmap(dem_output_path, heightmap_output_path)
            self.generation_progress.emit("DEM processed to heightmap.")
            building_processor.process_osm_buildings_to_sdf(osm_output_path, building_sdf_output_dir)
            self.generation_progress.emit("OSM buildings processed to SDF models.")
            texture_processor.process_satellite_texture(texture_output_dir, processed_texture_output_path)
            self.generation_progress.emit("Satellite texture processed.")
        except Exception as e:
            error_msg = f"Data processing failed: {e}"
            logger.error(error_msg)
            self.generation_error.emit(error_msg)
            return

        # --- Coordinate Conversion ---
        self.generation_progress.emit("Setting up Coordinate Conversion...")
        converter = CoordinateConverter(origin_location)

        # --- SDF World Generation ---
        self.generation_progress.emit("Starting SDF World Generation...")
        template_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdf_generation', 'templates')
        sdf_builder = SDFWorldBuilder(template_directory)

        building_model_paths = [os.path.join(building_sdf_output_dir, f) for f in os.listdir(building_sdf_output_dir) if f.endswith('.sdf')] if os.path.exists(building_sdf_output_dir) else []

        building_poses_gazebo = []
        if os.path.exists(osm_output_path):
            with open(osm_output_path, 'r') as f:
                osm_data = json.load(f)
            features = osm_data['features']
            for feature in features:
                if feature['geometry']['type'] in ['Polygon', 'MultiPolygon']:
                    polygon = shapely.geometry.shape(feature['geometry'])
                    centroid = polygon.centroid
                    wgs84_centroid = (centroid.y, centroid.x)
                    gazebo_pose = converter.wgs84_to_gazebo(wgs84_centroid)
                    building_poses_gazebo.append(gazebo_pose[:2])

        output_sdf_world_path = os.path.join(self.output_dir, f"{self.world_name}.world")
        output_media_dir = os.path.join(self.output_dir, "media")
        output_materials_dir = os.path.join(output_media_dir, "materials")
        output_scripts_dir = os.path.join(output_materials_dir, "scripts")
        output_textures_dir = os.path.join(output_materials_dir, "textures")
        os.makedirs(output_scripts_dir, exist_ok=True)
        os.makedirs(output_textures_dir, exist_ok=True)

        texture_path_for_sdf = None
        texture_path_processed = os.path.join(processed_texture_output_dir, "satellite_texture.png")
        output_texture_file_in_media = os.path.join(output_textures_dir, "satellite_texture.png")
        if os.path.exists(texture_path_processed):
            shutil.copy2(texture_path_processed, output_texture_file_in_media)
            texture_path_for_sdf = os.path.relpath(output_texture_file_in_media, os.path.dirname(output_sdf_world_path))

        template_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdf_generation', 'templates')
        material_script_path = os.path.join(template_directory, 'gazebo.material')
        output_material_script_path = os.path.join(output_scripts_dir, 'gazebo.material')
        if os.path.exists(material_script_path):
            shutil.copy2(material_script_path, output_material_script_path)

        try:
            sdf_content = sdf_builder.render_world_template(
                heightmap_path=heightmap_output_path,
                texture_path=texture_path_for_sdf,
                building_model_paths=building_model_paths,
                building_poses=building_poses_gazebo
            )
            sdf_builder.save_sdf_world_file(sdf_content, output_sdf_world_path)
            self.generation_progress.emit("SDF world file generated.")
            self.generation_finished.emit(self.output_dir) # Emit output directory on success
        except Exception as e:
            error_msg = f"SDF world generation failed: {e}"
            logger.error(error_msg)
            self.generation_error.emit(error_msg)
            return
        
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi(os.path.join(os.path.dirname(__file__), 'main_window.ui'), self)
        self.setWindowTitle("Gazebo World Builder")

        self.map_view = self.findChild(QWebEngineView, 'webEngineView')
        map_url = QUrl.fromLocalFile(os.path.abspath(os.path.join(os.path.dirname(__file__), 'web', 'public.html')))
        self.browseOutputDirButton.clicked.connect(self.browse_output_directory)
        self.generateWorldButton.clicked.connect(self.start_world_generation)
        self.outputDirLineEdit.setText(os.path.abspath('generated_worlds_gui'))
        self.world_gen_thread = None

    @pyqtSlot()
    def browse_output_directory(self):
        """Opens a directory dialog to choose the output directory."""
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        output_dir = dialog.getExistingDirectory(self, "Select Output Directory", self.outputDirLineEdit.text())
        if output_dir:
            self.outputDirLineEdit.setText(output_dir)

    @pyqtSlot()
    def start_world_generation(self):
        """Starts the world generation process in a separate thread."""
        latitude_text = self.latitudeLineEdit.text()
        longitude_text = self.longitudeLineEdit.text()
        radius_text = self.radiusLineEdit.text()
        output_dir = self.outputDirLineEdit.text()
        world_name = self.worldNameLineEdit.text()

        try:
            latitude = float(latitude_text)
            longitude = float(longitude_text)
            radius = float(radius_text)

            if not world_name:
                QMessageBox.warning(self, "Warning", "World name cannot be empty.")
                return

            os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists

            # Disable UI elements during generation
            self.generateWorldButton.setEnabled(False)
            self.progressBar.setValue(0)
            self.logPlainTextEdit.clear()

            # Initialize and start the worker thread
            self.world_gen_thread = WorldGeneratorThread(latitude, longitude, radius, output_dir, world_name)
            self.world_gen_thread.generation_started.connect(self.on_generation_started)
            self.world_gen_thread.generation_progress.connect(self.on_generation_progress)
            self.world_gen_thread.generation_finished.connect(self.on_generation_finished)
            self.world_gen_thread.generation_error.connect(self.on_generation_error)
            self.world_gen_thread.start()


        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numeric values for Latitude, Longitude, and Radius.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            logger.exception("Unexpected error during world generation initiation:")
            self.generateWorldButton.setEnabled(True) # Re-enable button in case of error

    def on_generation_started(self):
        """Actions to perform when world generation starts."""
        self.progressBar.setValue(5) # Initial progress

    def on_generation_progress(self, message):
        """Updates the log output with progress messages."""
        current_text = self.logPlainTextEdit.toPlainText()
        self.logPlainTextEdit.setPlainText(current_text + message + "\n")
        self.logPlainTextEdit.verticalScrollBar().setValue(self.logPlainTextEdit.verticalScrollBar().maximum()) # Scroll to bottom

    def on_generation_finished(self, output_dir):
        """Actions to perform when world generation is successfully finished."""
        self.progressBar.setValue(100)
        self.generateWorldButton.setEnabled(True) # Re-enable button
        QMessageBox.information(self, "Success", f"Gazebo world generated successfully in:\n{output_dir}")

    def on_generation_error(self, error_message):
        """Actions to perform when world generation encounters an error."""
        self.progressBar.setValue(0) # Reset progress
        self.generateWorldButton.setEnabled(True) # Re-enable button
        QMessageBox.critical(self, "Error", f"World generation failed:\n{error_message}")
        current_text = self.logPlainTextEdit.toPlainText()
        self.logPlainTextEdit.setPlainText(current_text + "Error: " + error_message + "\n") # Add error to log
        self.logPlainTextEdit.verticalScrollBar().setValue(self.logPlainTextEdit.verticalScrollBar().maximum()) # Scroll to bottom

        
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()