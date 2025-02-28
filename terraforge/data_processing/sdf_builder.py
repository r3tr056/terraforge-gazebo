
import os
from jinja2 import Environment, FileSystemLoader
from utils.logging import logger

from utils.coordinates import CoordinateConverter

class SDFWorldBuilder:
    def __init__(self, template_dir='./templates'):
        self.template_env = Environment(loader=FileSystemLoader(template_dir))
        logger.info(f"SDF World Builder initialized with template directory: {template_dir}")

    def render_world_template(self, heightmap_path=None, texture_path=None, building_model_paths=None, building_poses=None):
        # Renders the world_template.sdf.j2 template with provided data
        template = self.template_env.get_template('world_template.sdf.j2')
        rendered_sdf = template.render(
            heightmap_path=heightmap_path,
            texture_path=texture_path,
            building_model_paths=building_model_paths if building_model_paths else [],
            building_poses=building_poses if building_poses else []
        )
        logger.info("SDF world template rendered.")
        return rendered_sdf
    
    def save_sdf_world_file(self, sdf_content, output_path):
        # Saves the rendered SDF content to a file
        try:
            with open(output_path, 'w') as sdf_file:
                sdf_file.write(sdf_content)
            logger.info(f"SDF world file saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving SDF world file: {e}")
            raise
        