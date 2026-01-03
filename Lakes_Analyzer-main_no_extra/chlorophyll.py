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
        print(f"[Chlorophyll] Initializing ChlorophyllEstimator")
        self.scene = scene
        self.water_mask = water_mask.astype(bool)
        self.dtype = dtype
        self.fill_value = np.dtype(dtype).type(fill_value)

        self.a0, self.a1, self.a2, self.a3, self.a4 = oc3_coeffs
        self.b0, self.b1, self.b2 = gilerson_coeffs
        
        # Print water mask statistics
        water_pixels = np.sum(self.water_mask)
        total_pixels = self.water_mask.size
        water_percent = 100 * water_pixels / total_pixels
        print(f"[Chlorophyll] Water mask: {water_pixels}/{total_pixels} pixels ({water_percent:.1f}%)")
        print(f"[Chlorophyll] OC3 coefficients: a0={self.a0}, a1={self.a1}, a2={self.a2}, a3={self.a3}, a4={self.a4}")
        print(f"[Chlorophyll] Gilerson coefficients: b0={self.b0}, b1={self.b1}, b2={self.b2}")

    # ---- OC3 (clear water) ----
    def chla_oc3(self):
        print(f"\n[Chlorophyll] Computing OC3 (clear water) algorithm")
        print(f"[Chlorophyll] Loading bands: B01, B02, B03")
        bands = self.scene.load_bands(["B01", "B02", "B03"])  # at 10 m, B01 resampled
        B01 = bands["B01"].astype("float32")
        B02 = bands["B02"].astype("float32")
        B03 = bands["B03"].astype("float32")
        
        # Print band statistics
        print(f"[Chlorophyll] B01 stats: shape={B01.shape}, min={np.nanmin(B01):.2f}, max={np.nanmax(B01):.2f}, mean={np.nanmean(B01):.2f}")
        print(f"[Chlorophyll] B02 stats: shape={B02.shape}, min={np.nanmin(B02):.2f}, max={np.nanmax(B02):.2f}, mean={np.nanmean(B02):.2f}")
        print(f"[Chlorophyll] B03 stats: shape={B03.shape}, min={np.nanmin(B03):.2f}, max={np.nanmax(B03):.2f}, mean={np.nanmean(B03):.2f}")

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            # Compute ratio
            max_B01_B02 = np.maximum(B01, B02)
            ratio = max_B01_B02 / (B03 + 1e-12)
            print(f"[Chlorophyll] Ratio (max(B01,B02)/B03): min={np.nanmin(ratio):.4f}, max={np.nanmax(ratio):.4f}, mean={np.nanmean(ratio):.4f}")
            
            X = np.log10(ratio)
            print(f"[Chlorophyll] X = log10(ratio): min={np.nanmin(X):.4f}, max={np.nanmax(X):.4f}, mean={np.nanmean(X):.4f}")
            
            log_chl = (
                self.a0
                + self.a1 * X
                + self.a2 * X**2
                + self.a3 * X**3
                + self.a4 * X**4
            )
            print(f"[Chlorophyll] log_chl (before clipping): min={np.nanmin(log_chl):.4f}, max={np.nanmax(log_chl):.4f}, mean={np.nanmean(log_chl):.4f}")
            
            # Clip log_chl to reasonable bounds to prevent overflow
            # Chlorophyll-a typically ranges from 0.01 to 1000 mg/m³
            # So log_chl should be roughly -2 to 3
            log_chl_clipped = np.clip(log_chl, -5, 5)  # Clipping to prevent overflow
            clipped_count = np.sum(log_chl != log_chl_clipped)
            if clipped_count > 0:
                print(f"[Chlorophyll] WARNING: Clipped {clipped_count} log_chl values to prevent overflow")
            
            chl = 10.0 ** log_chl_clipped
            print(f"[Chlorophyll] chl (before masking): min={np.nanmin(chl):.2f}, max={np.nanmax(chl):.2f}, mean={np.nanmean(chl):.2f}")
            
            # Replace any inf/nan with reasonable max value
            inf_nan_count = np.sum(~np.isfinite(chl))
            if inf_nan_count > 0:
                print(f"[Chlorophyll] WARNING: Found {inf_nan_count} inf/nan values, replacing with 10000")
            chl = np.where(np.isfinite(chl), chl, 10000)  # Replace inf/nan with max
            chl = np.clip(chl, 0, 10000)  # Cap at reasonable maximum

        chl[~self.water_mask] = np.nan
        water_chl = chl[self.water_mask]
        if len(water_chl) > 0:
            print(f"[Chlorophyll] Final chl (water pixels only): min={np.nanmin(water_chl):.2f}, max={np.nanmax(water_chl):.2f}, mean={np.nanmean(water_chl):.2f}")
            print(f"[Chlorophyll] Percentiles (5th, 50th, 95th): {np.nanpercentile(water_chl, [5, 50, 95])}")
        else:
            print(f"[Chlorophyll] WARNING: No water pixels found in mask!")
        
        return chl.astype(self.dtype)

    # ---- Gilerson (turbid water) ----
    def chla_gilerson(self):
        print(f"\n[Chlorophyll] Computing Gilerson (turbid water) algorithm")
        print(f"[Chlorophyll] Loading bands: B05, B04")
        bands = self.scene.load_bands(["B05", "B04"])  # 705, 665
        B05 = bands["B05"].astype("float32")
        B04 = bands["B04"].astype("float32")
        
        # Print band statistics
        print(f"[Chlorophyll] B05 stats: shape={B05.shape}, min={np.nanmin(B05):.2f}, max={np.nanmax(B05):.2f}, mean={np.nanmean(B05):.2f}")
        print(f"[Chlorophyll] B04 stats: shape={B04.shape}, min={np.nanmin(B04):.2f}, max={np.nanmax(B04):.2f}, mean={np.nanmean(B04):.2f}")

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            # Compute ratio
            ratio = (B05 + 1e-12) / (B04 + 1e-12)
            print(f"[Chlorophyll] Ratio (B05/B04): min={np.nanmin(ratio):.4f}, max={np.nanmax(ratio):.4f}, mean={np.nanmean(ratio):.4f}")
            
            X = np.log10(ratio)
            print(f"[Chlorophyll] X = log10(B05/B04): min={np.nanmin(X):.4f}, max={np.nanmax(X):.4f}, mean={np.nanmean(X):.4f}")
            
            log_chl = self.b0 + self.b1 * X + self.b2 * X**2
            print(f"[Chlorophyll] log_chl (before clipping): min={np.nanmin(log_chl):.4f}, max={np.nanmax(log_chl):.4f}, mean={np.nanmean(log_chl):.4f}")
            
            # Clip log_chl to reasonable bounds to prevent overflow
            # Chlorophyll-a typically ranges from 0.01 to 1000 mg/m³
            # So log_chl should be roughly -2 to 3
            log_chl_clipped = np.clip(log_chl, -5, 5)  # Clipping to prevent overflow
            clipped_count = np.sum(log_chl != log_chl_clipped)
            if clipped_count > 0:
                print(f"[Chlorophyll] WARNING: Clipped {clipped_count} log_chl values to prevent overflow")
            
            chl = 10.0 ** log_chl_clipped
            print(f"[Chlorophyll] chl (before masking): min={np.nanmin(chl):.2f}, max={np.nanmax(chl):.2f}, mean={np.nanmean(chl):.2f}")
            
            # Replace any inf/nan with reasonable max value
            inf_nan_count = np.sum(~np.isfinite(chl))
            if inf_nan_count > 0:
                print(f"[Chlorophyll] WARNING: Found {inf_nan_count} inf/nan values, replacing with 10000")
            chl = np.where(np.isfinite(chl), chl, 10000)  # Replace inf/nan with max
            chl = np.clip(chl, 0, 10000)  # Cap at reasonable maximum

        chl[~self.water_mask] = np.nan
        water_chl = chl[self.water_mask]
        if len(water_chl) > 0:
            print(f"[Chlorophyll] Final chl (water pixels only): min={np.nanmin(water_chl):.2f}, max={np.nanmax(water_chl):.2f}, mean={np.nanmean(water_chl):.2f}")
            print(f"[Chlorophyll] Percentiles (5th, 50th, 95th): {np.nanpercentile(water_chl, [5, 50, 95])}")
        else:
            print(f"[Chlorophyll] WARNING: No water pixels found in mask!")
        
        return chl.astype(self.dtype)

    def compute(self, lake_type: str):
        lake_type = lake_type.lower()
        print(f"\n[Chlorophyll] ===== Computing chlorophyll for lake_type: {lake_type} =====")
        
        if lake_type == "clear":
            self.chl_array = self.chla_oc3()
        elif lake_type == "turbid":
            self.chl_array = self.chla_gilerson()
        else:
            raise ValueError("lake_type must be 'clear' or 'turbid'.")
        
        print(f"[Chlorophyll] ✓ Chlorophyll computation completed")
        print(f"[Chlorophyll] Final array shape: {self.chl_array.shape}, dtype: {self.chl_array.dtype}")
        
        return self.chl_array

    def save_image(self, out_path):
        print(f"\n[Chlorophyll] Saving image to: {out_path}")
        
        # use stored chlorophyll array
        arr = np.nan_to_num(self.chl_array, nan=0.0)
        
        # Print statistics before saving
        valid_pixels = np.sum(np.isfinite(self.chl_array))
        total_pixels = self.chl_array.size
        print(f"[Chlorophyll] Image stats: {valid_pixels}/{total_pixels} valid pixels ({100*valid_pixels/total_pixels:.1f}%)")
        if valid_pixels > 0:
            print(f"[Chlorophyll] Chl-a range: {np.nanmin(self.chl_array):.2f} - {np.nanmax(self.chl_array):.2f} mg/m³")
            print(f"[Chlorophyll] Chl-a mean: {np.nanmean(self.chl_array):.2f} mg/m³")
        
        plt.imshow(arr, cmap="viridis")
        plt.colorbar(label="Chlorophyll (mg/m³)")
        plt.title("Chlorophyll Estimate")
        plt.axis("off")
        plt.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"[Chlorophyll] ✓ Image saved successfully")