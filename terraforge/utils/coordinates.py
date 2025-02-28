
from pyproj import Transformer
import pyproj
from utils.logging import logger


class CoordinateConverter:
    def __init__(self, origin_location_wgs84: tuple):
        self.origin_location_wgs84 = origin_location_wgs84
        self.utm_zone = self._determine_utm_zone(origin_location_wgs84[1])
        self.wgs84_to_utm_transformer = Transformer.from_crs('EPSG:4326', self.utm_crs_string, always_xy=True)
        self.utm_to_wgs84_transformer = Transformer.from_crs(self.utm_crs_string, "EPSG:4326", always_xy=True)

        self.origin_utm_x, self.origin_utm_y = self.wgs84_to_utm_transformer.transform(origin_location_wgs84[1], origin_location_wgs84[0])
        logger.info(f"Coordinate Converter initialized with origin WGS84: {origin_location_wgs84}, UTM Zone: {self.utm_zone}, UTM CRS: {self.utm_crs_string}, Origin UTM: ({self.origin_utm_x}, {self.origin_utm_y})")

    @property
    def utm_crs_string(self):
        return self._get_utm_crs_string(self.utm_zone)
    
    def _get_utm_crs_string(self, utm_zone):
        if utm_zone > 0:
            return f"EPSG:326{utm_zone:02d}" # UTM North
        else:
            return f"EPSG:327{-utm_zone:02d}" # UTM South

    def _determine_utm_zone(self, longitude_degrees):
        utm_zone = int((longitude_degrees + 180) / 6) + 1
        if utm_zone > 60:
            utm_zone = 1
        return utm_zone
    
    def wgs84_to_utm(self, location_wgs84: tuple) -> tuple:
        """ Converts WGS84 (lat, lon) to UTM (x,y) coordinates in the initialized UTM Zone"""
        lon, lat = location_wgs84[1], location_wgs84[0]
        utm_x, utm_y = self.wgs84_to_utm_transformer.transform(lon, lat)
        return utm_x, utm_y
    
    def utm_to_local_gazebo(self, utm_coords: tuple) -> tuple:
        """
        Converts UTM (x,y) coordinates to local Gazebo coordinates (x, y, z=0)
        The origin of the local Gazebo frame is the origin_location_wgs84 specified
        during initialization. Z-coordinate is set to 0 here, elevation is handled
        separately via heightmap.
        """
        utm_x, utm_y = utm_coords
        local_x = utm_x - self.origin_utm_x
        local_y = utm_y - self.origin_utm_y
        local_z = 0.0
        return local_x, local_y, local_z
    
    def wgs84_to_gazebo(self, location_wgs84: tuple) -> tuple:
        """
        Converts WGS84 (lat, lon) directly to local Gazebo coordinates (x, y, z=0).
        This is a convenience function combinding WGS84 to UTM and UTM to local Gazebo
        conversion.
        """
        utm_coords = self.wgs84_to_utm(location_wgs84)
        return self.utm_to_local_gazebo(utm_coords)
    
    def gazebo_to_utm(self, gazebo_cords: tuple) -> tuple:
        """Converts local Gazebo coordinates (x, y) back to UTM (x, y)"""
        local_x, local_y = gazebo_cords
        utm_x = local_x + self.origin_utm_x
        utm_y = local_y + self.origin_utm_y
        return utm_x, utm_y
    
    def utm_to_wgs84(self, utm_coords: tuple) -> tuple:
        """Converts UTM (x, y) coordinates backs to WGS84 (lat, lon)"""
        utm_x, utm_y = utm_coords
        lon, lat = self.utm_to_wgs84_transformer.transform(utm_x, utm_y)
        return lat, lon
    
    def gazebo_to_wgs84(self, gazebo_coords: tuple) -> tuple:
        """
        Converts local Gazebo coordinates (x, y) back to WGS84 (latitude, longitude).
        This is a convenience function combining Gazebo to UTM and UTM to WGS84 conversion.
        """
        utm_coords = self.gazebo_to_utm(gazebo_coords)
        return self.utm_to_wgs84(utm_coords)
    