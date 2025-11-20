# chlorophyll.py
import numpy as np
import matplotlib.pyplot as plt

class ChlorophyllEstimator:
    """
    Implements:
      - OC3 (for clear lakes) using B01, B02, B03
      - Gilerson (for turbid lakes) using B05, B04
    """

    def __init__(
        self,
        scene: "SentinelScene",
        water_mask: np.ndarray,
        dtype="float32",
        fill_value=0.0,
        # OC3 coefficients
        oc3_coeffs=(0.0, 0.283, -2.753, 1.457, 0.659),
        #   (a0, a1, a2, a3, a4) – replace with your calibrated values
        # Gilerson coefficients
        gilerson_coeffs=(0.0, 2.0, 1.0),
        #   (b0, b1, b2) – placeholder; replace with your calibrated values
    ):
        self.scene = scene
        self.water_mask = water_mask.astype(bool)
        self.dtype = dtype
        self.fill_value = np.dtype(dtype).type(fill_value)

        self.a0, self.a1, self.a2, self.a3, self.a4 = oc3_coeffs
        self.b0, self.b1, self.b2 = gilerson_coeffs

    # ---- OC3 (clear water) ----
    def chla_oc3(self):
        bands = self.scene.load_bands(["B01", "B02", "B03"])  # at 10 m, B01 resampled
        B01 = bands["B01"].astype("float32")
        B02 = bands["B02"].astype("float32")
        B03 = bands["B03"].astype("float32")

        with np.errstate(divide="ignore", invalid="ignore"):
            X = np.log10(np.maximum(B01, B02) / (B03 + 1e-12))
            log_chl = (
                self.a0
                + self.a1 * X
                + self.a2 * X**2
                + self.a3 * X**3
                + self.a4 * X**4
            )
            chl = 10 ** log_chl

        chl[~self.water_mask] = np.nan
        return chl.astype(self.dtype)

    # ---- Gilerson (turbid water) ----
    def chla_gilerson(self):
        bands = self.scene.load_bands(["B05", "B04"])  # 705, 665
        B05 = bands["B05"].astype("float32")
        B04 = bands["B04"].astype("float32")

        with np.errstate(divide="ignore", invalid="ignore"):
            X = np.log10((B05 + 1e-12) / (B04 + 1e-12))
            log_chl = self.b0 + self.b1 * X + self.b2 * X**2
            chl = 10 ** log_chl

        chl[~self.water_mask] = np.nan
        return chl.astype(self.dtype)

    def compute(self, lake_type: str):
        lake_type = lake_type.lower()
        if lake_type == "clear":
            self.chl_array = self.chla_oc3()
        elif lake_type == "turbid":
            self.chl_array = self.chla_gilerson()
        else:
            raise ValueError("lake_type must be 'clear' or 'turbid'.")
        return self.chl_array

    def save_image(self, out_path):
        # use stored chlorophyll array
        arr = np.nan_to_num(self.chl_array, nan=0.0)
        plt.imshow(arr, cmap="viridis")
        plt.colorbar(label="Chlorophyll (mg/m³)")
        plt.title("Chlorophyll Estimate")
        plt.axis("off")
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close()