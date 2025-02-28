
import os

class Config:
	ELEVATION_DATA_SOURCE = os.getenv("ELEVATION_DATA_SOURCE", "earthexplorer")

	OSM_DATA_SOURCE = os.getenv("OSM_DATA_SOURCE", "overpass")
	SATELLITE_TEXTURE_SOURCE = os.getenv("SATELLITE_TEXTURE_SOURCE", "mapbox")

	EARTH_EXPLORER_API_KEY = os.getenv("EARTH_EXPLORER_API_KEY", "")
	MAPBOX_API_KEY = os.getenv("MAPBOX_API_KEY", "")
	SENTINEL_HUB_API_KEY = os.getenv("SENTINEL_HUB_API_KEY", "")

	DEM_OUTPUT_DIR = os.getenv("DEM_OUTPUT_DIR", "data/dem")
	OSM_OUTPUT_DIR = os.getenv("OSM_OUTPUT_DIR", "data/osm")
	TEXTURE_OUTPUT_DIR = os.getenv("TEXTURE_OUTPUT_DIR", "data/textures")

	def __init__(self):
		os.makedirs(self.DEM_OUTPUT_DIR, exist_ok=True)
		os.makedirs(self.OSM_OUTPUT_DIR, exist_ok=True)
		os.makedirs(self.TEXTURE_OUTPUT_DIR, exist_ok=True)

config = Config()