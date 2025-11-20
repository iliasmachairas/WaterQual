# masking.py
import numpy as np

class WaterMaskBuilder:
    def __init__(
        self,
        ndwi_thresh=0.05,
        mndwi_thresh=0.0,
        clean_size=0,        # optional connected-component cleaning
    ):
        self.ndwi_thresh = ndwi_thresh
        self.mndwi_thresh = mndwi_thresh
        self.clean_size = clean_size  # you can plug in scipy later

    def compute_indices(self, scene: "SentinelScene"):
        # NDWI uses Green (B03) and NIR (B08)
        # MNDWI uses Green (B03) and SWIR (B11)
        bands = scene.load_bands(["B03", "B08", "B11"])
        green = bands["B03"].astype("float32")
        nir   = bands["B08"].astype("float32")
        swir  = bands["B11"].astype("float32")

        with np.errstate(divide="ignore", invalid="ignore"):
            ndwi  = (green - nir) / (green + nir + 1e-12)
            mndwi = (green - swir) / (green + swir + 1e-12)

        return ndwi, mndwi

    def build_mask(self, scene: "SentinelScene"):
        ndwi, mndwi = self.compute_indices(scene)
        # basic thresholding (same logic as in the notebook)
        water = (ndwi > self.ndwi_thresh) | (mndwi > self.mndwi_thresh)

        # Optional: area filter / morphology if you want (currently no-op)
        if self.clean_size > 0:
            # placeholder: implement connected-component filtering with scipy if desired
            pass

        return water.astype(bool), ndwi, mndwi

    def apply_mask_to_rgb(self, rgb, water_mask, mask_land=True):
        """
        rgb: array [y, x, 3]
        water_mask: bool [y, x]
        mask_land: if True, set non-water to gray; if False, set water to gray.
        """
        rgb = rgb.copy()
        h, w, _ = rgb.shape
        gray = np.nanpercentile(rgb.reshape(-1, 3), 50, axis=0)

        if mask_land:
            mask = ~water_mask
        else:
            mask = water_mask

        rgb[mask] = gray
        return rgb
