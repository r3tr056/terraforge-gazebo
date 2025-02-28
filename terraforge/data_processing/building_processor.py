
import os
import json
import shapely.geometry

from utils.logging import logger

DEFAULT_BUILDING_HEIGHT = 10.0

def process_osm_buildings_to_sdf(osm_filepath: str, output_sdf_dir: str):
    """
    Process OSM building footprints from a GeoJSON file and generates SDF model files for each building
    """
    logger.info(f"Processing OSM buildings from {osm_filepath} to SDF models in {output_sdf_dir}")
    os.makedirs(output_sdf_dir, exist_ok=True)

    try:
        with open(osm_filepath, 'r') as f:
            osm_data = json.load(f)

        features = osm_data['features']
        for feature_idx, feature in enumerate(features):
            if feature['geometry']['type'] == 'Polygon' or feature['geometry']['type'] == 'MultiPolygon':
                building_id = feature['properties'].get('osmid', f"building_{feature_idx}")
                building_name = feature['properties'].get('name', f"Building {feature_idx}")
                height = feature['properties'].get('height', DEFAULT_BUILDING_HEIGHT)

                # create shapely geometry object
                if feature['geometry']['type'] == 'Polygon':
                    polygon = shapely.geometry.Polygon(feature['geometry']['coordinates'][0])
                elif feature['geometry']['type'] == 'MultiPolygon':
                    polygon = shapely.geometry.MultiPolygon([shapely.geometry.Polygon(p[0]) for p in feature['geometry']['coordinates']])
                else:
                    logger.warning(f"Unsupported geometry type: {feature['geometry']['type']} for building {building_id}. Skipping.")
                    continue

                centroid = polygon.centroid
                center_x = centroid.x
                center_y = centroid.y

                bounds = polygon.bounds
                size_x = bounds[2] - bounds[0]
                size_y = bounds[3] - bounds[1]
                size_z = float(height)

                sdf_content = f"""<?xml version='1.0'?>
<sdf version='1.7'>
  <model name='{building_name.replace(" ", "_")}'>
    <static>true</static>
    <pose>{center_x} {center_y} {size_z/2.0} 0 0 0</pose> <!-- Position at centroid, base at Z=0 -->
    <link name='link'>
      <collision name='collision'>
        <geometry>
          <box>
            <size>{size_x} {size_y} {size_z}</size>
          </box>
        </geometry>
      </collision>
      <visual name='visual'>
        <geometry>
          <box>
            <size>{size_x} {size_y} {size_z}</size>
          </box>
        </geometry>
        <material>
          <ambient>0.7 0.7 0.7 1</ambient>
          <diffuse>0.7 0.7 0.7 1</diffuse>
          <specular>0.1 0.1 0.1 1</specular>
          <emissive>0 0 0 1</emissive>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""
                sdf_filename = f"building_{building_id.replace(':', '_')}.sdf"
                sdf_filepath = os.path.join(output_sdf_dir, sdf_filename)
                with open(sdf_filepath, 'w') as sdf_file:
                    sdf_file.write(sdf_content)
                logger.debug(f"Generated SDF model for building {building_id} to {sdf_filepath}")
            else:
                logger.warning(f"Feature with type {feature['geometry']['type']} is not a building polygon. Skipping.")

        logger.info(f"OSM buildings processed and SDF models saved to {output_sdf_dir}")
    except Exception as e:
        logger.error(f"Error processing OSM buildings to SDF models: {e}")
        raise
