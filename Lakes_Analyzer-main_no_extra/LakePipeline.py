# pipeline.py (could be inside chlorophyll.py or its own file)
import numpy as np
from aoi import AOI
from search import SentinelSearch
from scene import SentinelScene
from masking import WaterMaskBuilder
from chlorophyll import ChlorophyllEstimator
import os
from config import (
    output_directory, 
    base_name, 
    suffix_chlorophyll_png, 
    suffix_rgb_tiff, 
    suffix_chlorophyll_tiff,
    mode,
    band_selection
)

# Sentinel-2 band mapping: (Band Code, Band Name)
BAND_MAPPING = {
    "B01": "Coastal_Aerosol",
    "B02": "Blue",
    "B03": "Green", 
    "B04": "Red",
    "B05": "Red_Edge_1",
    "B06": "Red_Edge_2",
    "B07": "Red_Edge_3",
    "B08": "NIR",
    "B09": "Narrow_NIR",
    "B09": "Water_Vapor",
    "B11": "SWIR1",
    "B12": "SWIR2",
}

# Band selections for get_data mode
BAND_SELECTIONS = {
    "rgb_only": [("B04", "Red"), ("B03", "Green"), ("B02", "Blue")],
    "rgb_nir_swir": [("B04", "Red"), ("B03", "Green"), ("B02", "Blue"), ("B08", "NIR"), ("B11", "SWIR1"), ("B12", "SWIR2")],
    "all_bands": [
        ("B01", "Coastal_Aerosol"),
        ("B02", "Blue"),
        ("B03", "Green"),
        ("B04", "Red"),
        ("B05", "Red_Edge_1"),
        ("B06", "Red_Edge_2"),
        ("B07", "Red_Edge_3"),
        ("B08", "NIR"),
        ("B09", "Narrow_NIR"),
        ("B09", "Water_Vapor"),
        ("B11", "SWIR1"),
        ("B12", "SWIR2"),
    ],
}

class LakePipeline:
    def __init__(
        self,
        stac_url: str,
        collection: str,
        resolution: int = 10,
        dtype: str = "float32",
        fill_value: float = 0.0,
        ndwi_thresh: float = 0.05,
        mndwi_thresh: float = 0.0,
        clean_size: int = 0,
        oc3_coeffs=(0.0, 0.283, -2.753, 1.457, 0.659),
        gilerson_coeffs=(0.0, 2.0, 1.0),
    ):
        self.search = SentinelSearch(stac_url, collection)
        self.resolution = resolution
        self.dtype = dtype
        self.fill_value = fill_value

        self.mask_builder = WaterMaskBuilder(
            ndwi_thresh=ndwi_thresh,
            mndwi_thresh=mndwi_thresh,
            clean_size=clean_size,
        )
        self.oc3_coeffs = oc3_coeffs
        self.gilerson_coeffs = gilerson_coeffs

    def run(self, points_list: list, date_str: str, lake_type: str = None, max_cloud: int = 20):
        # 1) AOI + search
        aoi = AOI.from_four_points(points_list)
        print(f"[Pipeline] AOI bounds: {aoi.bounds}")
        item = self.search.find_best_item(aoi.to_geojson, date_str, max_cloud=max_cloud)
        
        # Print tile information
        if isinstance(item, dict):
            item_id = item.get("id", "Unknown")
            properties = item.get("properties", {})
            tile_id = properties.get("s2:mgrs_tile") or properties.get("mgrs:utm_zone") or properties.get("s2:product_uri", "Unknown")
            datetime_str = properties.get("datetime", "Unknown")
            cloud_cover = properties.get("eo:cloud_cover", "Unknown")
        else:
            item_id = getattr(item, "id", "Unknown")
            properties = getattr(item, "properties", {})
            tile_id = properties.get("s2:mgrs_tile") if isinstance(properties, dict) else getattr(properties, "s2:mgrs_tile", "Unknown")
            datetime_str = properties.get("datetime", "Unknown") if isinstance(properties, dict) else getattr(properties, "datetime", "Unknown")
            cloud_cover = properties.get("eo:cloud_cover", "Unknown") if isinstance(properties, dict) else getattr(properties, "eo:cloud_cover", "Unknown")
        
        print(f"[Pipeline] Found Sentinel-2 tile:")
        print(f"[Pipeline]   - Item ID: {item_id}")
        print(f"[Pipeline]   - MGRS Tile: {tile_id}")
        print(f"[Pipeline]   - Date/Time: {datetime_str}")
        print(f"[Pipeline]   - Cloud Cover: {cloud_cover}%")
        
        # Create scene
        scene = SentinelScene(
            item,
            aoi,
            resolution=self.resolution,
            dtype=self.dtype,
            fill_value=self.fill_value,
        )
        
        # Route to appropriate processing mode
        if mode == "get_data":
            return self._run_get_data(scene)
        elif mode == "estimate_water_quality":
            if lake_type is None:
                raise ValueError("lake_type must be specified for 'estimate_water_quality' mode")
            return self._run_estimate_water_quality(scene, lake_type)
        else:
            raise ValueError(f"Unknown mode: {mode}. Must be 'get_data' or 'estimate_water_quality'")
    
    def _run_get_data(self, scene):
        """Handle get_data mode: load and save selected bands as TIFF files"""
        print(f"\n[Pipeline] Mode: get_data")
        print(f"[Pipeline] Band selection: {band_selection}")
        
        if band_selection not in BAND_SELECTIONS:
            raise ValueError(f"Unknown band_selection: {band_selection}. Must be one of: {list(BAND_SELECTIONS.keys())}")
        
        selected_bands = BAND_SELECTIONS[band_selection]
        band_codes = [band_code for band_code, band_name in selected_bands]
        band_names = [band_name for band_code, band_name in selected_bands]
        
        print(f"[Pipeline] Loading bands: {band_codes}")
        print(f"[Pipeline] Band names: {band_names}")
        
        # Load bands
        bands_dict = scene.load_bands(band_codes)
        
        # Stack bands into multi-band array (height, width, n_bands)
        bands_list = [bands_dict[code] for code in band_codes]
        stacked_array = np.stack(bands_list, axis=-1)
        
        # Build output file path
        os.makedirs(output_directory, exist_ok=True)
        output_filename = f"{base_name}_{band_selection}.tif"
        output_path = os.path.join(output_directory, output_filename)
        
        print(f"\n[Pipeline] Saving bands to: {output_path}")
        scene.save_tiff(stacked_array, output_path, nodata_value=self.fill_value, band_names=band_names)
        
        # Print band information
        print(f"[Pipeline] ✓ Saved {len(band_codes)} bands:")
        for code, name in zip(band_codes, band_names):
            print(f"[Pipeline]   - {code} ({name})")
        
        return {"bands": bands_dict, "output_path": output_path}
    
    def _run_estimate_water_quality(self, scene, lake_type: str):
        """Handle estimate_water_quality mode: compute chlorophyll and save outputs"""
        print(f"\n[Pipeline] Mode: estimate_water_quality")
        print(f"[Pipeline] Lake type: {lake_type}")
        
        # 2) Water mask
        water_mask, ndwi, mndwi = self.mask_builder.build_mask(scene)

        # 3) Chlorophyll
        chl_est = ChlorophyllEstimator(
            scene,
            water_mask,
            dtype=self.dtype,
            fill_value=self.fill_value,
            oc3_coeffs=self.oc3_coeffs,
            gilerson_coeffs=self.gilerson_coeffs,
        )
        chl = chl_est.compute(lake_type)
        
        # 4) Save output files
        os.makedirs(output_directory, exist_ok=True)
        chlorophyll_png_path = os.path.join(output_directory, base_name + suffix_chlorophyll_png)
        rgb_tiff_path = os.path.join(output_directory, base_name + suffix_rgb_tiff)
        chlorophyll_tiff_path = os.path.join(output_directory, base_name + suffix_chlorophyll_tiff)
        
        print(f"\n[Pipeline] Saving output files to: {output_directory}")
        
        # Save chlorophyll PNG
        chl_est.save_image(chlorophyll_png_path)
        
        # Save RGB TIFF
        print(f"\n[Pipeline] Saving RGB TIFF...")
        rgb_array = scene.load_rgb(bands=("B04", "B03", "B02"))  # Red, Green, Blue
        rgb_band_names = ["Red", "Green", "Blue"]
        scene.save_tiff(rgb_array, rgb_tiff_path, nodata_value=self.fill_value, band_names=rgb_band_names)
        
        # Save chlorophyll TIFF
        print(f"\n[Pipeline] Saving chlorophyll TIFF...")
        scene.save_tiff(chl, chlorophyll_tiff_path, nodata_value=np.nan, band_names=["Chlorophyll"])
        
        # Calculate and print chlorophyll statistics
        print(f"\n[Pipeline] Calculating chlorophyll statistics...")
        valid_chl = chl[np.isfinite(chl)]
        if len(valid_chl) > 0:
            percentiles = np.nanpercentile(valid_chl, [5, 50, 95])
            print(f"\n[Pipeline] Chl-a over water (mg m^-3), percentiles:")
            print(f"[Pipeline]   5th percentile: {percentiles[0]:.2f}")
            print(f"[Pipeline]   50th percentile (median): {percentiles[1]:.2f}")
            print(f"[Pipeline]   95th percentile: {percentiles[2]:.2f}")
        else:
            print("[Pipeline] WARNING: No valid chlorophyll values found!")

        print(f"\n[Pipeline] Preparing results...")
        
        # Extract only essential data - don't return scene/item objects that hold GDAL references
        # This prevents GDAL cleanup issues when Python exits
        print(f"[Pipeline] Extracting result data...")
        
        # Clean up before returning - explicitly close any GDAL references
        import gc
        gc.collect()
        
        print(f"[Pipeline] Results prepared successfully")
        print(f"[Pipeline] Returning: water_mask, ndwi, mndwi, chl (not returning scene/item to avoid GDAL cleanup issues)")
        
        try:
            result = {
                # Don't return 'scene' or 'item' - they hold GDAL references that cause crashes on cleanup
                # "item": item,  # Commented out - large dict with GDAL references
                # "scene": scene,  # Commented out - holds GDAL dataset references
                "water_mask": water_mask,
                "ndwi": ndwi,
                "mndwi": mndwi,
                "chl": chl,
            }
            print(f"[Pipeline] ✓ Results dictionary created successfully")
            
            # Final cleanup
            gc.collect()
            
            return result
        except Exception as e:
            print(f"[Pipeline] ERROR creating results dictionary: {e}")
            import traceback
            traceback.print_exc()
            raise
