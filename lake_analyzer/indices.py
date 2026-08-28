# -*- coding: utf-8 -*-
"""
Water-quality algorithms computed from Sentinel-2 L2A surface reflectance
bands. Four algorithms are offered, in two families:

Quick proxies (unitless, no calibration needed)
  * NDCI — Normalized Difference Chlorophyll Index (chlorophyll-a proxy).
  * NDTI — Normalized Difference Turbidity Index (turbidity proxy).

Calibrated estimates (mg/m3 chlorophyll-a, need local calibration)
  * OC3      — blue/green ratio, for clear ("case-1") water.
  * Gilerson — red/red-edge ratio, for turbid, algae-rich ("case-2") water.

IMPORTANT — the OC3/Gilerson regression coefficients below are the
algorithms' published DEFAULT/EXAMPLE coefficients, not calibrated for any
specific lake. Treating their output as an accurate mg/m3 reading without
first calibrating against in-situ water samples from your own lake(s) will
give misleading numbers. All four algorithms should be treated as relative
screening/trend signals, not lab-grade measurements, until calibrated —
see each algorithm's tooltip and docs/algorithms.rst.
"""
import numpy as np

# SCL (Scene Classification Layer) class code for "Water", per the
# Sentinel-2 L2A product spec.
SCL_WATER = 6

# a0..a4 for OC3's log-space polynomial. Standard NASA OCx-family example
# coefficients (tuned historically for open-ocean SeaWiFS/MODIS data) —
# NOT calibrated for any particular lake.
OC3_DEFAULT_COEFFS = (0.0, 0.283, -2.753, 1.457, 0.659)

# b0..b2 for Gilerson's log-space quadratic. Placeholder example
# coefficients — NOT calibrated for any particular lake.
GILERSON_DEFAULT_COEFFS = (0.0, 2.0, 1.0)

NDCI_CITATION = (
    "Mishra, S. & Mishra, D.R. (2012). Normalized difference chlorophyll "
    "index: A novel model for remote estimation of chlorophyll-a "
    "concentration in turbid productive waters. Remote Sensing of "
    "Environment, 117, 394-406."
)
NDTI_CITATION = (
    "Lacaux, J.P. et al. (2007). Classification of ponds from high-spatial "
    "resolution remote sensing: Application to Rift Valley Fever epidemics "
    "in Senegal. Remote Sensing of Environment, 106(1), 66-74."
)
OC3_CITATION = (
    "O'Reilly, J.E. et al. (1998). Ocean color chlorophyll algorithms for "
    "SeaWiFS. Journal of Geophysical Research, 103(C11), 24937-24953."
)
GILERSON_CITATION = (
    "Gilerson, A.A. et al. (2010). Algorithms for remote estimation of "
    "chlorophyll-a in coastal and inland waters using red and near "
    "infrared bands. Optics Express, 18(23), 24109-24125."
)

_LOG_CHL_CLIP = 5.0      # keeps 10**log_chl within a sane numeric range
_CHL_MAX      = 10000.0  # mg/m3 ceiling for physically implausible outliers

_CALIBRATION_CAVEAT = (
    "Coefficients are published example values, not calibrated for a "
    "specific lake — treat this as a relative screening signal, not an "
    "accurate mg/m3 reading, until calibrated against in-situ samples."
)


# ── Quick proxies (unitless) ────────────────────────────────────────────────

def compute_ndci(b05: np.ndarray, b04: np.ndarray) -> np.ndarray:
    """Normalized Difference Chlorophyll Index — (B05-B04)/(B05+B04).

    B05 is Sentinel-2's Red Edge 1 band (~705 nm), sensitive to
    chlorophyll-a reflectance; B04 is Red (~665 nm), where chlorophyll
    absorbs strongly. Higher values indicate higher chlorophyll-a
    concentration / greater algal bloom potential.
    """
    denom = b05 + b04
    with np.errstate(divide="ignore", invalid="ignore"):
        ndci = np.where(denom != 0, (b05 - b04) / denom, np.nan)
    return ndci.astype("float32")


def compute_ndti(b04: np.ndarray, b03: np.ndarray) -> np.ndarray:
    """Normalized Difference Turbidity Index — (B04-B03)/(B04+B03).

    B04 is Red (~665 nm), which brightens with suspended sediment; B03 is
    Green (~560 nm). Higher values indicate higher turbidity / suspended
    sediment load and lower water clarity.
    """
    denom = b04 + b03
    with np.errstate(divide="ignore", invalid="ignore"):
        ndti = np.where(denom != 0, (b04 - b03) / denom, np.nan)
    return ndti.astype("float32")


def classify_ndci(value) -> str:
    """Coarse qualitative bin for a mean NDCI value. General screening
    guidance from the literature, not a calibrated concentration scale —
    validate against local ground-truth data before using this for any
    management or regulatory decision."""
    if value is None or np.isnan(value):
        return "Unknown (no valid water pixels)"
    if value < 0.0:
        return "Low — clear water, minimal chlorophyll signal"
    if value < 0.2:
        return "Moderate — some chlorophyll present, worth monitoring"
    return "High — elevated chlorophyll-a, possible algal bloom risk"


def classify_ndti(value) -> str:
    """Coarse qualitative bin for a mean NDTI value — same caveats as
    classify_ndci()."""
    if value is None or np.isnan(value):
        return "Unknown (no valid water pixels)"
    if value < 0.0:
        return "Low — clear water, low suspended sediment"
    if value < 0.2:
        return "Moderate — some turbidity/sediment present"
    return "High — significant turbidity, low water clarity"


# ── Calibrated estimates (mg/m3) ────────────────────────────────────────────

def compute_oc3(b01: np.ndarray, b02: np.ndarray, b03: np.ndarray,
                 coeffs=OC3_DEFAULT_COEFFS) -> np.ndarray:
    """OC3 chlorophyll-a (mg/m3) for clear water — a blue/green ratio.

    X = log10(max(B01,B02)/B03); chl = 10**(a0 + a1*X + a2*X^2 + a3*X^3 + a4*X^4).
    B01 (Coastal Aerosol, ~443nm) and B02 (Blue, ~490nm) both sit in
    chlorophyll's absorption band; B03 (Green, ~560nm) does not, so the
    ratio falls as chlorophyll rises.
    """
    a0, a1, a2, a3, a4 = coeffs
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        ratio    = np.maximum(b01, b02) / (b03 + 1e-12)
        x        = np.log10(np.clip(ratio, 1e-6, None))
        log_chl  = a0 + a1 * x + a2 * x**2 + a3 * x**3 + a4 * x**4
        log_chl  = np.clip(log_chl, -_LOG_CHL_CLIP, _LOG_CHL_CLIP)
        chl      = 10.0 ** log_chl
        chl      = np.where(np.isfinite(chl), chl, _CHL_MAX)
        chl      = np.clip(chl, 0, _CHL_MAX)
    return chl.astype("float32")


def compute_gilerson(b05: np.ndarray, b04: np.ndarray,
                      coeffs=GILERSON_DEFAULT_COEFFS) -> np.ndarray:
    """Gilerson chlorophyll-a (mg/m3) for turbid water — a red/red-edge ratio.

    X = log10(B05/B04); chl = 10**(b0 + b1*X + b2*X^2).
    B04 (Red, ~665nm) sits in chlorophyll's strongest absorption band;
    B05 (Red Edge 1, ~705nm) is less absorbed but rises with scattering
    from algal biomass, so the ratio tracks chlorophyll even when
    suspended sediment also affects the water's optical properties.
    """
    b0, b1, b2 = coeffs
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        ratio    = (b05 + 1e-12) / (b04 + 1e-12)
        x        = np.log10(np.clip(ratio, 1e-6, None))
        log_chl  = b0 + b1 * x + b2 * x**2
        log_chl  = np.clip(log_chl, -_LOG_CHL_CLIP, _LOG_CHL_CLIP)
        chl      = 10.0 ** log_chl
        chl      = np.where(np.isfinite(chl), chl, _CHL_MAX)
        chl      = np.clip(chl, 0, _CHL_MAX)
    return chl.astype("float32")


def classify_chlorophyll_mgm3(value) -> str:
    """Coarse trophic-state bin for a mean chlorophyll-a (mg/m3) value,
    following commonly-cited OECD/Carlson boundaries. General screening
    guidance, not a precise trophic classification — and only as reliable
    as the algorithm's calibration (see module docstring)."""
    if value is None or np.isnan(value):
        return "Unknown (no valid water pixels)"
    if value < 2.6:
        return "Low — oligotrophic range, minimal algal activity expected"
    if value < 20:
        return "Moderate — meso/eutrophic range, some algal activity"
    return "High — eutrophic range, elevated bloom risk"


def water_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    """Boolean mask, True where the Sentinel-2 SCL band classifies the pixel
    as class 6 ('Water')."""
    return scl.astype(int) == SCL_WATER


# Single source of truth for both the dialog's tooltips and the
# pipeline/report — avoids the UI and backend explanations drifting apart.
# Every "compute" callable takes the full {band_code: array} dict loaded by
# the pipeline, so pipeline.py can dispatch uniformly regardless of which
# bands a given algorithm actually needs.
ALGORITHMS = {
    "ndci": {
        "key":          "ndci",
        "label":        "Chlorophyll-a proxy (NDCI)",
        "short":        "NDCI",
        "formula":      "(B05 - B04) / (B05 + B04)",
        "measures":     "chlorophyll-a proxy (unitless, no calibration needed)",
        "bands_needed": ("B05", "B04"),
        "compute":      lambda bands: compute_ndci(bands["B05"], bands["B04"]),
        "classify":     classify_ndci,
        "citation":     NDCI_CITATION,
        "tooltip": (
            "NDCI — Normalized Difference Chlorophyll Index, a quick "
            "unitless chlorophyll-a proxy needing no calibration.\n\n"
            "(B05-B04)/(B05+B04) — Red Edge vs. Red reflectance contrast. "
            "Higher values suggest more chlorophyll-a and greater algal "
            "bloom potential.\n\n"
            f"Reference: {NDCI_CITATION}\n\n"
            "Relative screening proxy, not a calibrated mg/m3 concentration "
            "— for an absolute estimate see Gilerson below."
        ),
    },
    "ndti": {
        "key":          "ndti",
        "label":        "Turbidity proxy (NDTI)",
        "short":        "NDTI",
        "formula":      "(B04 - B03) / (B04 + B03)",
        "measures":     "turbidity proxy (unitless, no calibration needed)",
        "bands_needed": ("B04", "B03"),
        "compute":      lambda bands: compute_ndti(bands["B04"], bands["B03"]),
        "classify":     classify_ndti,
        "citation":     NDTI_CITATION,
        "tooltip": (
            "NDTI — Normalized Difference Turbidity Index, a quick "
            "unitless turbidity proxy needing no calibration.\n\n"
            "(B04-B03)/(B04+B03) — Red vs. Green reflectance contrast; Red "
            "brightens as suspended sediment increases. Higher values "
            "suggest higher turbidity and lower water clarity.\n\n"
            f"Reference: {NDTI_CITATION}\n\n"
            "Relative screening proxy, not a calibrated NTU value."
        ),
    },
    "oc3": {
        "key":          "oc3",
        "label":        "Clear-water chlorophyll (OC3)",
        "short":        "OC3",
        "formula":      "10^(a0+a1X+a2X^2+a3X^3+a4X^4), X=log10(max(B01,B02)/B03)",
        "measures":     "chlorophyll-a concentration (mg/m3) in clear, low-turbidity water",
        "bands_needed": ("B01", "B02", "B03"),
        "compute":      lambda bands: compute_oc3(bands["B01"], bands["B02"], bands["B03"]),
        "classify":     classify_chlorophyll_mgm3,
        "citation":     OC3_CITATION,
        "tooltip": (
            "OC3 — a blue/green band-ratio chlorophyll-a algorithm for "
            "clear, low-turbidity water.\n\n"
            "Uses max(B01,B02)/B03 (Blue vs. Green): chlorophyll absorbs "
            "blue light, so the ratio falls as chlorophyll-a rises.\n\n"
            "Best for clear lakes — sediment/CDOM in turbid water can "
            "throw this off; use Gilerson for turbid lakes instead.\n\n"
            f"Reference: {OC3_CITATION}\n\n"
            f"{_CALIBRATION_CAVEAT}"
        ),
    },
    "gilerson": {
        "key":          "gilerson",
        "label":        "Turbid-water chlorophyll (Gilerson)",
        "short":        "Gilerson",
        "formula":      "10^(b0+b1X+b2X^2), X=log10(B05/B04)",
        "measures":     "chlorophyll-a concentration (mg/m3) in turbid, algae-rich water",
        "bands_needed": ("B05", "B04"),
        "compute":      lambda bands: compute_gilerson(bands["B05"], bands["B04"]),
        "classify":     classify_chlorophyll_mgm3,
        "citation":     GILERSON_CITATION,
        "tooltip": (
            "Gilerson — a red/red-edge band-ratio chlorophyll-a algorithm "
            "for turbid, algae-rich water.\n\n"
            "Uses B05/B04 (Red Edge vs. Red): Red sits in chlorophyll's "
            "strongest absorption band, while Red Edge rises with algal "
            "biomass scattering — the ratio tracks chlorophyll-a even "
            "when suspended sediment is also present.\n\n"
            "Best for turbid inland/coastal lakes — for clear open water "
            "use OC3 instead.\n\n"
            f"Reference: {GILERSON_CITATION}\n\n"
            f"{_CALIBRATION_CAVEAT}"
        ),
    },
}
