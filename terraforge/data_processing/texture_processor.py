
import os
import shutil
from utils.logging import logger

def process_satellite_texture(texture_dir: str, output_texture_path: str):
    """
    Processes the downloaded satellite texture. In this version
    it mainly copies the merged texture to a specified output path.
    TODO : this could include tiling, georeferencing adjustments, material file creation, etc.
    """
    logger.info(f"Processing satellite texture from {texture_dir} to {output_texture_path}")
    try:
        input_texture_file = os.path.join(texture_dir, "satellite_texture.png")
        if not os.path.exists(input_texture_file):
            raise FileNotFoundError(f"Merged texture file not found: {input_texture_file}. Make sure to run data acquisition first.")
        
        output_dir = os.path.dirname(output_texture_path)
        os.makedirs(output_dir, exist_ok=True)

        shutil.copy2(input_texture_file, output_texture_path)

        logger.info(f"Satellite texture coped to {output_texture_path}")
    except FileNotFoundError as e:
        logger.error(f"Texture processing failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing statellite texture: {e}")
        raise