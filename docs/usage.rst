Usage
=====

Opening the plugin
------------------

Click the **WaterQual** button in the QGIS toolbar, or navigate to
**Plugins → WaterQual** in the menu bar.

Step 1 — Pick a date
---------------------

Click a date in the calendar widget.

Use the **± days** spin box to widen the search window around that date.
Increasing it improves the chance of finding a low-cloud scene.

Step 2 — Choose an algorithm
------------------------------

+-------------------------------------+----------------------------------------------+----------------+
| Option                              | Measures                                      | Calibration    |
+======================================+================================================+================+
| Chlorophyll-a proxy (NDCI)          | Chlorophyll-a / algal bloom potential         | Not needed     |
+-------------------------------------+----------------------------------------------+----------------+
| Turbidity proxy (NDTI)              | Turbidity / suspended sediment / clarity      | Not needed     |
+-------------------------------------+----------------------------------------------+----------------+
| Clear-water chlorophyll (OC3)       | Chlorophyll-a concentration (mg/m3)           | Recommended    |
+-------------------------------------+----------------------------------------------+----------------+
| Turbid-water chlorophyll (Gilerson) | Chlorophyll-a concentration (mg/m3)           | Recommended    |
+-------------------------------------+----------------------------------------------+----------------+

NDCI/NDTI are quick unitless proxies, usable immediately. OC3/Gilerson
output an mg/m3 estimate but ship with published *example* coefficients,
not calibrated for your lake — see :doc:`algorithms` for the calibration
caveat before trusting their absolute numbers.

Hover the ⓘ icon next to each option for the formula, reference, and
caveats. See :doc:`algorithms` for the full explanation.

Step 3 — Define the area of interest
--------------------------------------

**Option A: Draw on the map**

1. Click **Start drawing** — the dialog minimises and a rubber-band tool
   activates on the QGIS canvas.
2. Click and drag a rectangle over the lake.
3. Release the mouse — coordinates fill automatically and the dialog reopens.

**Option B: From an existing polygon layer**

Select **From layer** and pick a polygon layer from the dropdown. Any CRS
works — it's reprojected to WGS-84 automatically. The output is masked
exactly to the polygon boundary, not just its bounding box.

.. note::
   Each search returns exactly one Sentinel-2 scene (roughly 110×110 km).
   If your AOI is bigger than that or straddles a tile boundary, the plugin
   picks the scene with the largest overlap and warns you if part of your
   AOI is still missing from the output.

Step 4 — Advanced masking options (optional)
-----------------------------------------------

Click **▸ Advanced masking options** to expand a panel to the right of the
dialog. The defaults work for most cases — open this only if you need to
change them.

* **Cloud & shadow types to mask** — which Sentinel-2 SCL classes to
  exclude. Defaults: shadows, medium probability, and high probability
  clouds are checked; low probability and thin cirrus are not.
* **Cloud thresholds** — a tile-level pre-filter (default 100, i.e. no
  pre-filtering) and a stricter AOI-specific tolerance (default 20%) that
  skips the run outright if exceeded.
* **Restrict to water pixels only** — checked by default. Uses the SCL
  "Water" class so the index reflects only the waterbody, not surrounding
  land or vegetation.

Step 5 — Output and run
--------------------------

1. Set the **output directory**.
2. **Create report** (checked by default) writes a ``.txt`` summary
   alongside the GeoTIFF.
3. **Open output folder after run** opens the folder automatically on
   success.
4. **Also download raw satellite data (RGB+NIR+SWIR)** (checked by
   default) additionally saves the underlying imagery for the same scene,
   so you can visually monitor what's driving the index reading — not just
   get a number.
5. Click **Run**. The progress bar tracks each pipeline stage, from STAC
   search through band download, index computation, and GeoTIFF write.

Output files
------------

+------------------------------------------+-------------------------------------------------+
| File                                      | Description                                      |
+============================================+===================================================+
| ``<tile>_<date>_<ALGO>.tif``              | Single-band index GeoTIFF (NaN outside the mask) |
+------------------------------------------+-------------------------------------------------+
| ``<tile>_<date>_<ALGO>_rgb_nir_swir.tif`` | Raw imagery companion (if enabled)               |
+------------------------------------------+-------------------------------------------------+
| ``<tile>_<date>_<ALGO>_report.txt``       | Cloud/water statistics, index mean/min/max/std,  |
|                                            | qualitative classification, and citation         |
+------------------------------------------+-------------------------------------------------+

If the scene is too cloudy, or no valid water pixels remain in the AOI, no
GeoTIFF is written — only the report, explaining why.

Viewing logs
------------

Detailed per-step logging is available in
**View → Panels → Log Messages → WaterQual**.
