import os
import requests
from PIL import Image
from io import BytesIO
from utils.config import config
from utils.logging import logger
from data_acquisition.elevation import _calculate_bounds_wgs84

MAPBOX_STYLE = "satellite-v9"
MAPBOX_ZOOM_LEVEL = 15

def download_satellite_texture_tiles(location: tuple, radius_meters: float, output_dir: str, mapbox_api_key: str = None):
	"""
	Downloads satellite texture tiles from Mapbox Static Tiles API for the given location and radius.

	Args:
		location: (latitude, longitude) tuple in WGS84 (EPSG:4326).
		radius_meters: Radius in meters around the location.
		output_dir: Directory to save the downloaded tiles.
		mapbox_api_key: Optional Mapbox API key. If None, it will try to use the one from config.
	"""
	logger.info(f"Downloading satellite texture tiles for location {location} with radius {radius_meters}m to {output_dir}")
	if mapbox_api_key is None:
		mapbox_api_key = config.MAPBOX_API_KEY
		if not mapbox_api_key:
			logger.warning("Mapbox API key not provided in function argument or configuration. Using public access (may be limited).")

	bbox_wgs84 = _calculate_bounds_wgs84(location, radius_meters) # (west, south, east, north)
	west, south, east, north = bbox_wgs84

	tile_size = 256 # Mapbox tile size is 256x256 pixels

	# Calculate tile coordinates (rough approximation for simplicity, consider more precise tile calculations for production)
	def deg2num(lat_deg, lon_deg, zoom):
		lat_rad = lat_deg * (3.141592653589793 / 180.0)
		n = 2.0 ** zoom
		xtile = int((lon_deg + 180.0) / 360.0 * n)
		ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / 3.141592653589793) / 2.0 * n)
		return (xtile, ytile)

	import math

	top_left_tile = deg2num(north, west, MAPBOX_ZOOM_LEVEL)
	bottom_right_tile = deg2num(south, east, MAPBOX_ZOOM_LEVEL)

	tiles_x = range(top_left_tile[0], bottom_right_tile[0] + 1)
	tiles_y = range(top_left_tile[1], bottom_right_tile[1] + 1)

	merged_image = Image.new('RGB', ((tiles_x[-1] - tiles_x[0] + 1) * tile_size, (tiles_y[-1] - tiles_y[0] + 1) * tile_size))

	for x_tile in tiles_x:
		for y_tile in tiles_y:
			tile_url = f"https://api.mapbox.com/styles/v1/mapbox/{MAPBOX_STYLE}/tiles/{MAPBOX_ZOOM_LEVEL}/{x_tile}/{y_tile}?access_token={mapbox_api_key if mapbox_api_key else 'public'}"
			try:
				response = requests.get(tile_url, stream=True)
				response.raise_for_status()

				tile_image = Image.open(BytesIO(response.content))
				x_offset = (x_tile - top_left_tile[0]) * tile_size
				y_offset = (y_tile - top_left_tile[1]) * tile_size
				merged_image.paste(tile_image, (x_offset, y_offset))

				tile_filename = f"tile_{x_tile}_{y_tile}.png"
				tile_output_path = os.path.join(output_dir, tile_filename)
				tile_image.save(tile_output_path)
				logger.debug(f"Downloaded tile {x_tile}_{y_tile} to {tile_output_path}")

			except requests.exceptions.RequestException as e:
				logger.error(f"Error downloading tile {x_tile}_{y_tile}: {e}")
			except Exception as e:
				logger.error(f"Error processing tile {x_tile}_{y_tile}: {e}")

	output_texture_path = os.path.join(output_dir, "satellite_texture.png")
	merged_image.save(output_texture_path)
	logger.info(f"Merged satellite texture saved to {output_texture_path}")
