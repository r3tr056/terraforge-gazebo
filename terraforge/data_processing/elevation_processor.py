import os
from osgeo import gdal
from utils.logging import logger

def process_dem_to_heightmap(dem_filepath: str, output_heightmap_path: str):
    logger.info(f"Processing DEM {dem_filepath} to heightmap {output_heightmap_path}")
    try:
        dem_dataset = gdal.Open(dem_filepath)
        if dem_dataset is None:
            raise Exception(f"Failed to open DEM file: {dem_filepath}")
        
        band = dem_dataset.GetRasterBand(1)
        if band is None:
            raise Exception("Failed to get raster band from DEM")
        
        raster_array = band.ReadAsArray()

        min_val = raster_array.min()
        max_val = raster_array.max()

        if max_val > min_val:
            normalized_array = ((raster_array - min_val) / (max_val - min_val) * 255).astype('uint8')
        else:
            normalized_array = (raster_array - min_val).astype('uint8')

        # create the output image
        driver = gdal.GetDriverByName('PNG')
        output_dataset = driver.Create(output_heightmap_path, dem_dataset.RasterXSize, dem_dataset.RasterYSize, 1, gdal.GDT_Byte)
        if output_dataset is None:
            raise Exception(f"Failed to create output heightmap file: {output_heightmap_path}")
        
        output_band = output_dataset.GetRasterBand(1)
        output_band.WriteArray(normalized_array)

        # copy geotransform and projection from the source DEM
        output_dataset.SetGeoTransform(dem_dataset.GetGeoTransform())
        output_dataset.SetProjection(dem_dataset.GetProjection())

        # flush data and close datasets
        output_band.FlushCache()
        output_dataset = None
        dem_dataset = None

        logger.info(f"DEM processed and heightmap saved to {output_heightmap_path}")
    except Exception as e:
        logger.error(f"Error processing DEM to heightmap: {e}")
        raise
