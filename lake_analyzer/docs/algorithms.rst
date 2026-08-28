Water Quality Algorithms
=========================

Lake Analyzer offers four algorithms, computed from Sentinel-2 L2A surface
reflectance bands, in two families:

* **Quick proxies** (NDCI, NDTI) — unitless normalized-difference ratios,
  no calibration needed.
* **Calibrated estimates** (OC3, Gilerson) — log-space regressions that
  output an actual mg/m3 chlorophyll-a estimate, but only as accurate as
  their coefficients (see the caveat at the end of this page).

This page explains what each one measures, why it works, and where its
limits are.

Why band-math at all?
-----------------------

Water absorbs and scatters light differently depending on what's dissolved
or suspended in it. Chlorophyll-a (in phytoplankton/algae) and suspended
sediment each leave a distinctive fingerprint on the reflectance spectrum a
satellite sensor measures. Combining two bands — as a normalized
difference, or as a calibrated ratio regression — isolates that
fingerprint while cancelling out illumination and atmospheric effects that
would otherwise swamp the signal.

Chlorophyll-a proxy — NDCI
----------------------------

**Formula**

.. math::

   \mathrm{NDCI} = \frac{B05 - B04}{B05 + B04}

where ``B05`` is Sentinel-2's Red Edge 1 band (~705 nm) and ``B04`` is Red
(~665 nm).

**Why these bands**

Chlorophyll-a has a reflectance peak near 700 nm (the "red edge") caused by
scattering from algal cells, right next to a strong chlorophyll absorption
trough in the red (~665 nm). The contrast between these two closely-spaced
bands tracks chlorophyll-a concentration even in optically complex,
sediment-laden inland water — where earlier blue/green-based ocean-color
algorithms (built for clear open ocean) break down.

**What it indicates**

* Higher NDCI → more chlorophyll-a → greater likelihood of algal activity
  or bloom conditions.
* Lower / negative NDCI → clearer water, low chlorophyll-a signal.

**Reference**

Mishra, S. & Mishra, D.R. (2012). Normalized difference chlorophyll index:
A novel model for remote estimation of chlorophyll-a concentration in
turbid productive waters. *Remote Sensing of Environment*, 117, 394-406.

Turbidity proxy — NDTI
------------------------

**Formula**

.. math::

   \mathrm{NDTI} = \frac{B04 - B03}{B04 + B03}

where ``B04`` is Red (~665 nm) and ``B03`` is Green (~560 nm).

**Why these bands**

Suspended sediment scatters light broadly across the visible spectrum, but
the effect is stronger in the red than in the green, since clear water
absorbs red light much more strongly than green when sediment is absent.
As turbidity rises, red reflectance climbs faster than green, so the
red/green contrast tracks suspended sediment load and, inversely, water
clarity.

**What it indicates**

* Higher NDTI → more suspended sediment → higher turbidity → lower water
  clarity (e.g. after heavy rainfall, runoff, or resuspension events).
* Lower / negative NDTI → clearer water, low sediment load.

**Reference**

Lacaux, J.P. et al. (2007). Classification of ponds from high-spatial
resolution remote sensing: Application to Rift Valley Fever epidemics in
Senegal. *Remote Sensing of Environment*, 106(1), 66-74.

Clear-water chlorophyll — OC3
--------------------------------

**Formula**

.. math::

   X &= \log_{10}\left(\frac{\max(B01, B02)}{B03}\right) \\
   \mathrm{OC3} &= 10^{\,a_0 + a_1 X + a_2 X^2 + a_3 X^3 + a_4 X^4}

where ``B01`` is Coastal Aerosol (~443 nm), ``B02`` is Blue (~490 nm), and
``B03`` is Green (~560 nm).

**Why these bands**

OC3 belongs to NASA's OCx family of ocean-color chlorophyll algorithms,
originally built for open-ocean ("case-1") water where chlorophyll is the
dominant optically-active substance. Chlorophyll absorbs blue light, so as
chlorophyll rises, blue reflectance falls relative to green — a log-space
polynomial regression converts that ratio into an mg/m3 estimate.

**What it indicates**

* An mg/m3 chlorophyll-a estimate, most reliable in clear (low-turbidity,
  low-CDOM) water.
* In turbid inland lakes, suspended sediment and colored dissolved organic
  matter also affect the blue/green signal, which can bias OC3 —
  use Gilerson for turbid water instead.

**Reference**

O'Reilly, J.E. et al. (1998). Ocean color chlorophyll algorithms for
SeaWiFS. *Journal of Geophysical Research*, 103(C11), 24937-24953.

Turbid-water chlorophyll — Gilerson
--------------------------------------

**Formula**

.. math::

   X &= \log_{10}\left(\frac{B05}{B04}\right) \\
   \mathrm{Gilerson} &= 10^{\,b_0 + b_1 X + b_2 X^2}

where ``B05`` is Red Edge 1 (~705 nm) and ``B04`` is Red (~665 nm) — the
same two bands NDCI uses, but converted through a calibrated regression
into an mg/m3 estimate rather than a unitless ratio.

**Why these bands**

Built specifically for turbid, algae-rich ("case-2") inland and coastal
water. Red sits in chlorophyll's strongest absorption band; the red-edge
band is less absorbed but rises with scattering from algal biomass and
suspended matter, so the ratio isolates the chlorophyll signal even when
sediment is also present — where OC3 would struggle.

**Reference**

Gilerson, A.A. et al. (2010). Algorithms for remote estimation of
chlorophyll-a in coastal and inland waters using red and near infrared
bands. *Optics Express*, 18(23), 24109-24125.

How the plugin computes it
-----------------------------

1. Searches Planetary Computer for the least-cloudy Sentinel-2 L2A scene
   over your AOI and date window.
2. Loads the SCL (Scene Classification Layer) band plus B01, B02, B03, B04,
   B05 (the union of bands any of the four algorithms might need).
3. Builds a combined mask: your selected cloud/shadow SCL classes are
   excluded, the AOI polygon is rasterized and applied, and — if
   **Restrict to water pixels only** is checked (default) — only SCL class
   6 ("Water") pixels are kept.
4. Computes the selected algorithm per-pixel, masking everything outside
   the combined mask to NaN.
5. Writes a single-band GeoTIFF of the result, plus a report with the mean,
   min, max, standard deviation, and a coarse qualitative classification of
   the mean value.
6. If **Also download raw satellite data** is checked, also fetches and
   saves an RGB+NIR+SWIR GeoTIFF of the same scene (cloud-masked, full AOI)
   so you can visually cross-check what the algorithm is responding to.

Qualitative classification
-----------------------------

The report bins the mean value into a coarse Low / Moderate / High label
(see ``indices.py``: ``classify_ndci`` / ``classify_ndti`` for the
unitless proxies, ``classify_chlorophyll_mgm3`` — using commonly-cited
OECD/Carlson trophic-state boundaries — for OC3/Gilerson's mg/m3 output).
These are general screening heuristics from the literature, **not
calibrated scales** — the same value can correspond to different actual
water conditions in different lakes, depending on local optical properties.

Limitations — read before you rely on these numbers
--------------------------------------------------------

* **OC3/Gilerson coefficients are uncalibrated placeholders.** The
  ``OC3_DEFAULT_COEFFS`` and ``GILERSON_DEFAULT_COEFFS`` in ``indices.py``
  are the algorithms' published *example* values, not calibrated for any
  specific lake. Converting to an accurate mg/m3 reading requires a
  site-specific regression against in-situ water samples collected around
  the same time as the satellite pass. Until then, treat OC3/Gilerson
  output as relative, same as NDCI/NDTI.
* **NDCI/NDTI are relative, not absolute.** These are most reliable for
  *comparing* the same waterbody over time (trend monitoring) or between
  similar waterbodies, not for asserting an absolute water-quality state
  from a single reading.
* **Resolution matters.** Sentinel-2's 10 m pixels mean small ponds or
  narrow channels may not have enough clean water pixels for a stable
  result — check the report's "Water Pixels (of AOI)" and "Valid Pixels
  Analysed" percentages.
* **Cloud/shadow contamination.** Misclassified cloud shadow or haze can
  bias any of the four algorithms. The Advanced masking options let you
  tighten or loosen which SCL classes are excluded.
* **Not a substitute for regulatory monitoring.** Use these as a
  screening and monitoring aid — to flag when and where to send someone to
  take a water sample — not as a replacement for laboratory analysis in
  any decision with legal, health, or regulatory consequences.
