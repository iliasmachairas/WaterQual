# -*- coding: utf-8 -*-
import os
import numpy as np

from .aoi import AOI
from .search import SentinelSearch
from .scene import SentinelScene
from . import indices as wq


# Below this fraction of AOI-vs-scene overlap, warn that the AOI spans more
# than one tile and part of it is missing from the output.
AOI_COVERAGE_WARN_THRESHOLD = 0.95

STAC_URL   = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

SCL_FLAGS = {
    "No Data": 0, "Saturated or defective": 1, "Dark area pixels": 2,
    "Cloud shadows": 3, "Vegetation": 4, "Not vegetated": 5,
    "Water": 6, "Unclassified": 7, "Cloud medium probability": 8,
    "Cloud high probability": 9, "Thin cirrus": 10, "Snow or ice": 11,
}

# Sentinel-2 band preset for the "also save raw satellite data" companion
# output — a general-purpose visual-monitoring set (true color + NIR/SWIR).
RAW_BANDS = [("B04","Red"), ("B03","Green"), ("B02","Blue"),
             ("B08","NIR"), ("B11","SWIR1"), ("B12","SWIR2")]


def _unique_path(path: str) -> str:
    """Return path unchanged if it doesn't exist, otherwise append (1), (2)… until unique."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}({counter}){ext}"):
        counter += 1
    return f"{base}({counter}){ext}"


def _resolve_scene(aoi, date_str, max_cloud_tile, progress_callback=None):
    """Shared STAC search step for both purposes. Returns (scene, item, props,
    tile_id, datetime_str, cloud_cover_metadata, aoi_coverage, aoi_warning)."""
    def _p(pct, msg=""):
        if progress_callback:
            progress_callback(pct, msg)

    search = SentinelSearch(STAC_URL, COLLECTION)
    _p(15, "Querying Planetary Computer STAC…")
    item, aoi_coverage = search.find_best_item(aoi.to_geojson, date_str,
                                                max_cloud_tile=max_cloud_tile)

    props = item.get("properties", {}) if isinstance(item, dict) \
        else getattr(item, "properties", {})

    datetime_val         = props.get("datetime", "Unknown")
    datetime_str         = datetime_val[:10] if datetime_val != "Unknown" else "Unknown"
    cloud_cover_metadata = props.get("eo:cloud_cover", 0.0)
    tile_id              = props.get("s2:mgrs_tile") or props.get("mgrs:utm_zone", "Unknown")

    _p(30, f"Scene: {tile_id}  ({datetime_str})  cloud={cloud_cover_metadata:.1f}%")
    print(f"[Pipeline] {tile_id} | {datetime_str} | cloud={cloud_cover_metadata}% "
          f"| AOI coverage={aoi_coverage * 100:.1f}%")

    aoi_warning = None
    if aoi_coverage < AOI_COVERAGE_WARN_THRESHOLD:
        aoi_warning = (
            f"Your area of interest extends beyond a single scene's coverage — "
            f"only about {aoi_coverage * 100:.0f}% of it is covered by the selected "
            f"tile ('{tile_id}'), chosen because it has the largest overlap with "
            f"your AOI among scenes meeting the cloud threshold. The rest of your "
            f"AOI is missing from the output."
        )
        _p(32, f"⚠ {aoi_warning}")
        print(f"[Pipeline] WARNING: {aoi_warning}")

    scene = SentinelScene(item, aoi, resolution=10, dtype="float32", fill_value=0.0)
    return scene, tile_id, datetime_str, cloud_cover_metadata, aoi_coverage, aoi_warning


def _cloud_masks(scl_data, excluded_flags):
    """Return (valid_mask, cloud_mask) from an SCL array. valid_mask excludes
    the user-selected SCL classes plus No Data/Saturated always; cloud_mask
    is the fixed cloud/shadow classes used for the report statistics."""
    scl        = scl_data.astype(int)
    base_excl  = {SCL_FLAGS[f] for f in excluded_flags if f in SCL_FLAGS}
    base_excl |= {0, 1}  # always exclude No Data / Saturated
    valid_mask = ~np.isin(scl, sorted(base_excl))
    cloud_mask = np.isin(scl, [3, 8, 9, 10])
    return valid_mask, cloud_mask


def run_water_quality(
    points_list=None, aoi_geojson=None, date_str=None,
    algorithm="ndci", max_cloud_tile=100, max_cloud_tolerance=20,
    excluded_flags=None, restrict_to_water=True, also_save_raw=True,
    output_directory="./output", create_report=True, progress_callback=None,
):
    """Search, mask, and compute a water-quality index (NDCI or NDTI) over
    the AOI. Optionally also downloads a raw RGB+NIR+SWIR GeoTIFF of the
    same scene so the underlying imagery can be inspected alongside the
    index — useful for visually monitoring what's driving a reading."""
    def _p(pct, msg=""):
        if progress_callback:
            progress_callback(pct, msg)

    if algorithm not in wq.ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{algorithm}'. Expected one of {list(wq.ALGORITHMS)}.")
    algo         = wq.ALGORITHMS[algorithm]
    excluded_flags = excluded_flags or []

    aoi = AOI(aoi_geojson) if aoi_geojson is not None else AOI.from_four_points(points_list)
    scene, tile_id, datetime_str, cloud_cover_metadata, aoi_coverage, aoi_warning = \
        _resolve_scene(aoi, date_str, max_cloud_tile, progress_callback)

    # SCL + every band any of the four algorithms might need (cheap to fetch
    # together as one batch, and keeps the dispatch below algorithm-agnostic).
    _p(40, "Loading SCL and spectral bands…")
    bands = scene.load_bands(["SCL", "B01", "B02", "B03", "B04", "B05"])

    valid_mask, cloud_mask = _cloud_masks(bands["SCL"], excluded_flags)
    water_mask = wq.water_mask_from_scl(bands["SCL"])

    aoi_mask = scene.build_aoi_mask(aoi.to_geojson["geometry"], bands["SCL"].shape)
    total_pixels = int(np.sum(aoi_mask))
    if total_pixels == 0:
        raise RuntimeError("The selected area of interest does not overlap this scene.")

    cloud_pixels     = int(np.sum(cloud_mask & aoi_mask))
    cloud_shadow_pct = (cloud_pixels / total_pixels) * 100
    water_pixels     = int(np.sum(water_mask & aoi_mask))
    water_pct        = (water_pixels / total_pixels) * 100

    combined_mask = valid_mask & aoi_mask
    if restrict_to_water:
        combined_mask = combined_mask & water_mask

    valid_pct = (int(np.sum(combined_mask)) / total_pixels) * 100
    _p(55, f"Cloud/shadow: {cloud_shadow_pct:.1f}%  Water: {water_pct:.1f}%  Valid: {valid_pct:.1f}%")

    output_base = f"{tile_id}_{datetime_str}_{algo['short']}"
    report_path = None

    def _write_report(result_str, index_stats=None, warning_extra=None, raw_note=""):
        nonlocal report_path
        if not create_report:
            return
        os.makedirs(output_directory, exist_ok=True)
        report_path = os.path.join(output_directory, f"{output_base}_report.txt")
        with open(report_path, "w") as f:
            f.write(
                f"Lake Analyzer — Water Quality Report\n"
                f"{'=' * 40}\n"
                f"Tile ID: {tile_id}\nDate: {datetime_str}\nPlatform: Sentinel-2 L2A\n"
                f"Algorithm: {algo['label']} ({algo['short']})\n"
                f"Formula: {algo['formula']}\n"
                f"Measures: {algo['measures']}\n"
                f"Reference: {algo['citation']}\n\n"
                f"Metadata Cloud Cover: {cloud_cover_metadata:.2f}%\n"
                f"Calculated Cloud/Shadow (in AOI): {cloud_shadow_pct:.2f}%\n"
                f"Water Pixels (of AOI): {water_pct:.2f}%\n"
                f"Valid Pixels Analysed: {valid_pct:.2f}%\n"
                f"AOI Coverage by Scene: {aoi_coverage * 100:.2f}%\n"
                f"Cloud Tolerance Threshold: {max_cloud_tolerance}%\n"
                f"Restricted to water pixels only: {restrict_to_water}\n"
                f"Result: {result_str}\n"
            )
            if index_stats:
                f.write(
                    f"\n{algo['short']} statistics (over valid pixels)\n"
                    f"{'-' * 40}\n"
                    f"Mean:  {index_stats['mean']:.4f}\n"
                    f"Min:   {index_stats['min']:.4f}\n"
                    f"Max:   {index_stats['max']:.4f}\n"
                    f"StDev: {index_stats['std']:.4f}\n"
                    f"Classification: {index_stats['classification']}\n\n"
                    "Note: this index is a relative remote-sensing screening proxy, "
                    "not a calibrated concentration — pair with in-situ samples "
                    "before using it for management or regulatory decisions.\n"
                )
            if raw_note:
                f.write(f"\n{raw_note}\n")
            if warning_extra:
                f.write(f"\nWARNING: {warning_extra}\n")

    if cloud_shadow_pct > max_cloud_tolerance:
        _write_report("REJECTED (Too Cloudy)", warning_extra=aoi_warning)
        _p(100, f"Skipped — too cloudy ({cloud_shadow_pct:.1f}%)")
        return {"status": "skipped", "report": report_path, "aoi_warning": aoi_warning}

    if int(np.sum(combined_mask)) == 0:
        _write_report("REJECTED (No valid water pixels in AOI)", warning_extra=aoi_warning)
        _p(100, "Skipped — no valid water pixels in the AOI")
        return {"status": "skipped", "report": report_path, "aoi_warning": aoi_warning}

    # 1. Compute the index, masking out everything outside combined_mask.
    _p(65, f"Computing {algo['short']}…")
    index_array = algo["compute"](bands).astype("float32")
    index_array[~combined_mask] = np.nan

    finite = index_array[np.isfinite(index_array)]
    index_stats = {
        "mean": float(np.mean(finite)) if finite.size else float("nan"),
        "min":  float(np.min(finite))  if finite.size else float("nan"),
        "max":  float(np.max(finite))  if finite.size else float("nan"),
        "std":  float(np.std(finite))  if finite.size else float("nan"),
    }
    index_stats["classification"] = algo["classify"](index_stats["mean"])

    index_path = _unique_path(os.path.join(output_directory, f"{output_base}.tif"))
    os.makedirs(output_directory, exist_ok=True)
    _p(80, "Saving index GeoTIFF…")
    scene.save_tiff(index_array, index_path, nodata_value=float("nan"),
                     band_names=[algo["short"]])

    # 2. Optionally also fetch a raw RGB+NIR+SWIR GeoTIFF of the same scene,
    #    cloud-masked but NOT restricted to water only, so it's useful for
    #    visually monitoring the surrounding area too.
    raw_path = None
    raw_note = ""
    if also_save_raw:
        _p(88, "Downloading raw bands for visual monitoring…")
        raw_codes      = [b[0] for b in RAW_BANDS]
        raw_names      = [b[1] for b in RAW_BANDS]
        raw_bands      = scene.load_bands(raw_codes)
        raw_valid_mask = valid_mask & aoi_mask  # cloud-masked, but full AOI (not water-only)
        for code in raw_codes:
            raw_bands[code][~raw_valid_mask] = 0.0
        raw_stacked = np.stack([raw_bands[c] for c in raw_codes], axis=-1)
        raw_path    = _unique_path(
            os.path.join(output_directory, f"{output_base}_rgb_nir_swir.tif"))
        scene.save_tiff(raw_stacked, raw_path, nodata_value=0.0, band_names=raw_names)
        raw_note = f"Raw RGB+NIR+SWIR GeoTIFF also saved: {os.path.basename(raw_path)}"

    _write_report("ACCEPTED", index_stats=index_stats, warning_extra=aoi_warning,
                  raw_note=raw_note)

    _p(100, f"Done — {algo['short']} mean {index_stats['mean']:.3f} "
            f"({index_stats['classification']})")
    return {
        "status": "analyzed", "output_path": index_path, "raw_path": raw_path,
        "report": report_path, "aoi_warning": aoi_warning, "index_stats": index_stats,
        "algorithm": algo["short"],
    }
