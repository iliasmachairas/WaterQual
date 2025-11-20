# pipeline.py (could be inside chlorophyll.py or its own file)
import numpy as np
from aoi import AOI
from search import SentinelSearch
from scene import SentinelScene
from masking import WaterMaskBuilder
from chlorophyll import ChlorophyllEstimator
from config import chlorophyl_img_path

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

    def run(self, points_list: list, date_str: str, lake_type: str, max_cloud: int = 20):
        # 1) AOI + search
        aoi = AOI.from_four_points(points_list)
        print(aoi.bounds)
        item = self.search.find_best_item(aoi.to_geojson, date_str, max_cloud=max_cloud)

        # 2) Scene + water mask
        scene = SentinelScene(
            item,
            aoi,
            resolution=self.resolution,
            dtype=self.dtype,
            fill_value=self.fill_value,
        )
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
        chl_est.save_image(chlorophyl_img_path)



        return {
            "item": item,
            "scene": scene,
            "water_mask": water_mask,
            "ndwi": ndwi,
            "mndwi": mndwi,
            "chl": chl,
        }
