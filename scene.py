# scene.py
import stackstac
import numpy as np
from aoi import AOI

class SentinelScene:
    def __init__(self, item, aoi: AOI, resolution=10, dtype="float32", fill_value=0.0):
        self.item = item
        self.aoi = aoi
        self.resolution = resolution
        self.dtype = dtype
        self.fill_value = np.dtype(dtype).type(fill_value)
        self._epsg = None  # lazy
        self._bounds_ll = None

    def _get_epsg_and_bounds(self):
        if self._epsg is None or self._bounds_ll is None:
            self._epsg = self.item.properties.get("proj:epsg", 32632)  # fallback
            self._bounds_ll = self.aoi.bounds  # (minx, miny, maxx, maxy) in lon/lat
        return self._epsg, self._bounds_ll

    def load_bands(self, band_names, res=None):
        epsg, bounds_ll = self._get_epsg_and_bounds()
        res = res or self.resolution
        da = stackstac.stack(
            [self.item],
            assets=band_names,
            resolution=res,
            epsg=epsg,
            bounds_latlon=bounds_ll,
            rescale=False,
            dtype=self.dtype,
            fill_value=self.fill_value,
        ).compute().squeeze("time")  # dims: band, y, x

        return {b: da.sel(band=b).values for b in band_names}

    def load_rgb(self, bands=("B04", "B03", "B02")):
        rgb = self.load_bands(list(bands))
        # stack into (y,x,3)
        arr = np.stack([rgb[b] for b in bands], axis=-1)
        return arr
