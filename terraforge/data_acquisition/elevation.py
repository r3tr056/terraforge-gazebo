import elevation
import os
import pyproj
from pyproj import Transformer
from shapely.geometry import box
from utils.config import config
from utils.logging import logger

def download_dem(location: tuple, radius_meters: float, output_path: str):
	"""
	Downloads DEM data for the given location and radius.

	Args:
		location: (latitude, longitude) tuple in WGS84 (EPSG:4326)
		radius_meters: Radius in meters around the location to download DEM data.
		output_path: Path to save the GeoTIFF file.
	"""
	logger.info(f"Downloading DEM for location {location} with radius {radius_meters}m to {output_path}")
	try:
		bounds = _calculate_bounds_wgs84(location, radius_meters)
		elevation.clip(bounds=bounds, output=output_path, product='SRTM3')
		elevation.clean()
		logger.info(f"DEM data downloaded successfully to {output_path}")
	except Exception as e:
		logger.error(f"Failed to download DEM: {e}")
		raise

def _calculate_bounds_wgs84(location: tuple, radius_meters: float) -> tuple:
	"""
	Calculates bounding box in WGS84 (EPSG:4326) coordinates for a given location and radius in meters.

	Args:
		location: (latitude, longitude) in WGS84.
		radius_meters: Radius in meters.

	Returns:
		Tuple (west, south, east, north) in WGS84.
	"""
	lat, lon = location
	transformer_wgs_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
	transformer_utm_to_wgs = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

	center_x_utm, center_y_utm = transformer_wgs_to_utm.transform(lon, lat)

	minx_utm = center_x_utm - radius_meters
	miny_utm = center_y_utm - radius_meters
	maxx_utm = center_x_utm + radius_meters
	maxy_utm = center_y_utm + radius_meters

	west_lon, south_lat = transformer_utm_to_wgs.transform(minx_utm, miny_utm)
	east_lon, north_lat = transformer_utm_to_wgs.transform(maxx_utm, maxy_utm)

	return (west_lon, south_lat, east_lon, north_lat)
