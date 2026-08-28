Architecture
============

High-level overview
--------------------

The plugin is split into a thin QGIS UI layer and a framework-independent
analysis pipeline. The UI layer owns all Qt and QGIS API calls; the
pipeline has no QGIS dependency and could be run from a plain Python
script.

.. code-block:: text

   ┌─────────────────────────────────────────────────┐
   │                   QGIS UI layer                  │
   │                                                  │
   │  WaterQual              (main plugin class)      │
   │  WaterQualDialog        (dialog + getters)       │
   │  ExtentDrawingTool      (rubber-band tool)        │
   └──────────────────────┬──────────────────────────┘
                          │  spawns
                          ▼
   ┌─────────────────────────────────────────────────┐
   │              AnalysisWorker (QThread)            │
   │  emits: progress · message · finished · error   │
   └──────────────────────┬──────────────────────────┘
                          │  calls
                          ▼
   ┌─────────────────────────────────────────────────┐
   │        Water-quality pipeline (pure Python)      │
   │                                                  │
   │  pipeline.run_water_quality()                    │
   │    ├── AOI           (bounding box geometry)     │
   │    ├── SentinelSearch (STAC query)                │
   │    ├── SentinelScene  (band I/O, reproject)       │
   │    ├── indices        (NDCI / NDTI math)          │
   │    └── index GeoTIFF + raw GeoTIFF + report       │
   └─────────────────────────────────────────────────┘

Module reference
----------------

WaterQual.py
~~~~~~~~~~~~

The main QGIS plugin class. Responsible for:

* Registering the toolbar action and menu entry via ``initGui()``
* Creating the dialog once and reusing it across runs
* Connecting all signal handlers (browse, draw, run, help)
* Launching ``AnalysisWorker`` and routing its signals back to the dialog

WaterQual_dialog.py
~~~~~~~~~~~~~~~~~~~

A thin wrapper around the Qt Designer ``.ui`` file. Exposes typed getter
methods for every user input so that ``WaterQual.py`` never has to
touch raw Qt widgets:

* ``get_algorithm()`` → ``"ndci"`` / ``"ndti"`` / ``"oc3"`` / ``"gilerson"``
* ``get_restrict_water()`` → bool
* ``get_also_save_raw()`` → bool
* ``get_excluded_flags()`` → list of SCL class names to mask
* ``get_aoi_coords()`` → ``(xmin, ymin, xmax, ymax)`` validated floats
* ``get_selected_date()`` → date string
* ``get_max_cloud_tile()`` / ``get_max_cloud_tol()`` → ints

It also owns the **Advanced masking options** panel's expand/collapse
behavior: the panel is a plain ``QGroupBox`` positioned to the right of the
dialog's collapsed width, and ``btn_toggle_advanced.toggled`` calls
``setVisible()`` on it plus ``setFixedWidth()`` on the dialog — no custom
collapsible-widget click handling involved.

extent_tool.py
~~~~~~~~~~~~~~

A ``QgsMapTool`` subclass that renders a live rectangle while the user
drags. On mouse release it:

1. Transforms both corners from the canvas CRS to EPSG:4326.
2. Normalises the bounds (handles right-to-left or bottom-to-top drags).
3. Calls the registered callback with ``(xmin, ymin, xmax, ymax)``.

worker.py
~~~~~~~~~

A ``QThread`` subclass. Runs ``pipeline.run_water_quality()`` off the main
thread and translates return values / exceptions into four Qt signals:

+------------+---------------------------------------+
| Signal     | Payload                                |
+============+=========================================+
| progress   | integer 0–100                          |
+------------+---------------------------------------+
| message    | status string                          |
+------------+---------------------------------------+
| finished   | dict with status / paths / index stats |
+------------+---------------------------------------+
| error      | traceback string                       |
+------------+---------------------------------------+

pipeline.py
~~~~~~~~~~~

Orchestrates the water-quality workflow via ``run_water_quality()``:

1. Build AOI geometry (drawn rectangle or layer polygon).
2. Query STAC API for the scene with the largest AOI overlap among
   candidates meeting the cloud threshold.
3. Load the SCL band plus B01, B02, B03, B04, B05 — the union of bands any
   of the four algorithms might need, fetched together as one batch.
4. Build a combined valid-pixel mask: excluded SCL classes, the AOI
   polygon, and (optionally) the SCL "Water" class.
5. Compute cloud/shadow and water-coverage statistics over the AOI.
6. Skip with a report-only result if too cloudy or no valid water pixels
   remain.
7. Compute the selected algorithm (NDCI / NDTI / OC3 / Gilerson), masked
   to NaN outside the valid-pixel mask.
8. Save the index as a single-band GeoTIFF; write a report with summary
   statistics and a qualitative classification.
9. If enabled, also download and save an RGB+NIR+SWIR GeoTIFF of the same
   scene for visual monitoring.

**SCL flag mapping (Sentinel-2)**

+-------+---------------------------+
| Code  | Class                     |
+=======+===========================+
| 0     | No data                   |
+-------+---------------------------+
| 1     | Saturated / defective     |
+-------+---------------------------+
| 2     | Dark area pixels          |
+-------+---------------------------+
| 3     | Cloud shadows             |
+-------+---------------------------+
| 4     | Vegetation                |
+-------+---------------------------+
| 5     | Not vegetated             |
+-------+---------------------------+
| 6     | Water                     |
+-------+---------------------------+
| 7     | Unclassified              |
+-------+---------------------------+
| 8     | Clouds — medium prob.     |
+-------+---------------------------+
| 9     | Clouds — high probability |
+-------+---------------------------+
| 10    | Thin cirrus               |
+-------+---------------------------+
| 11    | Snow / ice                |
+-------+---------------------------+

indices.py
~~~~~~~~~~

Pure NumPy math with no QGIS or network dependency. Four algorithms in two
families:

* ``compute_ndci(b05, b04)`` / ``compute_ndti(b04, b03)`` — unitless
  normalized-difference proxies, no calibration needed.
* ``compute_oc3(b01, b02, b03, coeffs=...)`` /
  ``compute_gilerson(b05, b04, coeffs=...)`` — calibrated log-space
  regressions outputting mg/m3 chlorophyll-a; ``OC3_DEFAULT_COEFFS`` /
  ``GILERSON_DEFAULT_COEFFS`` are the algorithms' published example
  values, not calibrated for any specific lake (see :doc:`algorithms`).
* ``classify_ndci(value)`` / ``classify_ndti(value)`` — coarse qualitative
  bins for the unitless proxies' reports.
* ``classify_chlorophyll_mgm3(value)`` — coarse trophic-state bins for the
  OC3/Gilerson mg/m3 output.
* ``water_mask_from_scl(scl)`` — boolean mask for SCL class 6.
* ``ALGORITHMS`` — a single dict keyed by ``"ndci"``/``"ndti"``/``"oc3"``/
  ``"gilerson"`` that both the dialog's tooltips and the pipeline's report
  draw from, so the UI text and the backend explanation never drift apart.
  Every entry's ``"compute"`` takes the full ``{band_code: array}`` dict
  loaded by the pipeline, so ``pipeline.py`` dispatches uniformly
  regardless of which bands a given algorithm actually needs.

search.py
~~~~~~~~~

Sends a POST request to the Planetary Computer STAC ``/search`` endpoint:

* Filters by AOI geometry, date range, and ``eo:cloud_cover``.
* Picks the scene with the **largest AOI overlap** among candidates
  (not simply the least cloudy one).
* Signs all asset URLs using the Planetary Computer SAS token service.
* Retries up to 3 times (5-second back-off) on HTTP 503/504 and timeouts,
  and respects ``Retry-After`` on HTTP 429.

scene.py
~~~~~~~~

Handles all raster I/O:

* Opens remote Cloud-Optimised GeoTIFFs via GDAL ``/vsicurl/``.
* Reprojects and resamples to a common 10 m grid with ``gdal.Warp()``
  (bilinear resampling).
* ``build_aoi_mask()`` rasterizes the AOI polygon onto the established
  raster grid, so output is clipped to the polygon itself, not just its
  bounding box.
* Saves the final stack as a GTiff with band descriptions and a properly
  set geotransform and CRS.

aoi.py
~~~~~~

Wraps a GeoJSON polygon in a Shapely geometry object and exposes
``.bounds``, ``.centroid``, and ``.to_geojson`` properties.

External dependencies
---------------------

+----------------------------------------------+----------------------------------------------------+
| Dependency                                   | Used for                                           |
+==============================================+====================================================+
| Planetary Computer STAC API                  | Scene search and asset discovery                   |
+----------------------------------------------+----------------------------------------------------+
| Planetary Computer SAS signing service       | Authenticating COG download URLs                   |
+----------------------------------------------+----------------------------------------------------+
| GDAL ``/vsicurl/``                           | Streaming remote GeoTIFF reads without full copy   |
+----------------------------------------------+----------------------------------------------------+
| Shapely                                      | AOI polygon geometry and bounds extraction         |
+----------------------------------------------+----------------------------------------------------+
| NumPy                                        | Band array masking, index math, and stacking       |
+----------------------------------------------+----------------------------------------------------+
