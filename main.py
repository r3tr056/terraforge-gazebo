
import os
import click
import logging
import shutil
from terraforge.utils.config import config
from terraforge.utils.logging import setup_logger
from terraforge.data_acquisition import elevation, osm, textures
from terraforge.data_processing import elevation_processor, building_processor, texture_processor, sdf_builder
from terraforge.utils.coordinates import CoordinateConverter

logger = setup_logger('cli_app')

@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging.')
@click.pass_context
def cli(ctx, debug):
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")
    else:
        logger.setLevel(logging.INFO)


@cli.command()
@click.option('--latitude', required=True, type=float, help='Latitude of the location.')
@click.option('--longitude', required=True, type=float, help='Longitude of the location.')
@click.option('--radius', required=True, type=float, help='Radius in meters around the location.')
@click.option('--output-dir', default='generated_world', help='Output directory for the generated world.', type=click.Path())
@click.option('--world-name', default='generated_world', help='Name of the generated Gazebo world.')
@click.pass_context
def generate_world(ctx, latitude, longitude, radius, output_dir, world_name):
    """
    Generates a Gazebo SDF world for a given location and radius.
    """
    logger.info(f"Starting world generation for location ({latitude}, {longitude}), radius: {radius}m, output to: {output_dir}")

    origin_location = (latitude, longitude)
    location_name = f"loc_{latitude:.4f}_{longitude:.4f}" # Create a name based on location

    # --- Data Acquisition ---
    logger.info("--- Data Acquisition ---")
    dem_output_path = os.path.join(config.DEM_OUTPUT_DIR, f"{location_name}_dem.tif")
    osm_output_path = os.path.join(config.OSM_OUTPUT_DIR, f"{location_name}_buildings.geojson")
    texture_output_dir = os.path.join(config.TEXTURE_OUTPUT_DIR, f"{location_name}_texture")
    os.makedirs(texture_output_dir, exist_ok=True) # Ensure texture output dir exists

    try:
        elevation.download_dem(origin_location, radius, dem_output_path)
        osm.download_osm_buildings(origin_location, radius, osm_output_path)
        textures.download_satellite_texture_tiles(origin_location, radius, texture_output_dir, mapbox_api_key=config.MAPBOX_API_KEY)
    except Exception as e:
        logger.error(f"Data acquisition failed: {e}")
        if ctx.obj['DEBUG']: raise # Re-raise exception in debug mode for full traceback
        return

    # --- Data Processing ---
    logger.info("--- Data Processing ---")
    heightmap_output_path = os.path.join(config.DEM_OUTPUT_DIR, f"{location_name}_heightmap.png")
    building_sdf_output_dir = os.path.join(config.OSM_OUTPUT_DIR, f"{location_name}_building_models_sdf")
    processed_texture_output_dir = os.path.join(config.TEXTURE_OUTPUT_DIR, "processed_textures") # Using fixed processed textures dir
    processed_texture_output_path = os.path.join(processed_texture_output_dir, "satellite_texture.png") # Assuming merged texture is named this

    try:
        elevation_processor.process_dem_to_heightmap(dem_output_path, heightmap_output_path)
        building_processor.process_osm_buildings_to_sdf(osm_output_path, building_sdf_output_dir)
        texture_processor.process_satellite_texture(texture_output_dir, processed_texture_output_path) # Process to a fixed output path for now
    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        if ctx.obj['DEBUG']: raise
        return

    # --- Coordinate Conversion ---
    logger.info("--- Coordinate Conversion ---")
    converter = CoordinateConverter(origin_location)

    # --- SDF World Generation ---
    logger.info("--- SDF World Generation ---")
    template_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sdf_generation', 'templates') # Path to templates from cli/main.py
    sdf_builder = sdf_builder.SDFWorldBuilder(template_directory)

    building_model_paths = [os.path.join(building_sdf_output_dir, f) for f in os.listdir(building_sdf_output_dir) if f.endswith('.sdf')] if os.path.exists(building_sdf_output_dir) else []

    # Generate building poses in Gazebo frame
    building_poses_gazebo = []
    if os.path.exists(osm_output_path):
        import json
        import shapely.geometry
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

    output_sdf_world_path = os.path.join(output_dir, f"{world_name}.world") # Output world file path
    output_media_dir = os.path.join(output_dir, "media") # Media directory in output
    output_materials_dir = os.path.join(output_media_dir, "materials")
    output_scripts_dir = os.path.join(output_materials_dir, "scripts")
    output_textures_dir = os.path.join(output_materials_dir, "textures")
    os.makedirs(output_scripts_dir, exist_ok=True)
    os.makedirs(output_textures_dir, exist_ok=True)

    texture_path_for_sdf = None # Initialize to None
    texture_path_processed = os.path.join(processed_texture_output_dir, "satellite_texture.png")
    output_texture_file_in_media = os.path.join(output_textures_dir, "satellite_texture.png")
    if os.path.exists(texture_path_processed):
        shutil.copy2(texture_path_processed, output_texture_file_in_media)
        texture_path_for_sdf = os.path.relpath(output_texture_file_in_media, os.path.dirname(output_sdf_world_path))

    material_script_path = os.path.join(template_directory, 'gazebo.material') # Assuming material template is in the same template dir
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
        logger.info(f"World generation complete. SDF world file saved to: {output_sdf_world_path}")
    except Exception as e:
        logger.error(f"SDF world generation failed: {e}")
        if ctx.obj['DEBUG']: raise
        return

    logger.info(f"Gazebo world generated successfully in: {output_dir}")


if __name__ == '__main__':
    cli()