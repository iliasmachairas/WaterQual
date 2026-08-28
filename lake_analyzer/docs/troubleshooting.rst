Troubleshooting
===============

Common issues
-------------

"No scenes found for the given date and AOI"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The STAC search returned no results.

**Possible causes and fixes:**

* The date is before Sentinel-2's launch (June 2015).
* The AOI is outside Sentinel-2's coverage.
* The **Max tile cloud cover** threshold (in Advanced masking options) is
  too strict — try raising it to 80 or 100 to check whether *any* scene
  exists at all.
* Try widening the search window with the **± days** spin box.

"Your area of interest extends beyond a single scene's coverage"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each search returns exactly **one** Sentinel-2 scene — roughly 110×110 km.
If your AOI is larger than that, or straddles the boundary between two
tiles, one scene cannot fully cover it.

Among the scenes meeting your cloud threshold, the plugin picks the one
with the **largest overlap with your AOI** (not simply the least cloudy
one). If the best match still doesn't cover the whole AOI, you'll see this
warning in the message bar, the log, and the report file, and the part of
the AOI outside that scene's footprint will be missing from the output.

This isn't a bug to fix by retrying — it's inherent to downloading a
single scene. If you need full coverage of a large lake, split your AOI
into smaller pieces that each fit within one scene and mosaic the results
yourself in QGIS.

"Skipped — cloud cover exceeded tolerance or no water pixels"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Either:

* Cloud/shadow pixels over your AOI exceeded the **Max AOI cloud
  tolerance** threshold, or
* **Restrict to water pixels only** is checked and the SCL band found no
  "Water"-classified pixels in your AOI for this scene.

**Fixes:**

* Raise the cloud tolerance, or pick a different date.
* If your waterbody is small or the SCL band is misclassifying it, try
  unchecking **Restrict to water pixels only** and inspect the raw
  companion GeoTIFF to see what the scene actually looks like.

HTTP 503 / 504 errors
~~~~~~~~~~~~~~~~~~~~~

The Planetary Computer API is temporarily unavailable. The plugin retries
automatically up to 3 times with a 5-second delay. If all retries fail,
wait a few minutes and try again, or check the
`Planetary Computer status page <https://planetarycomputer.microsoft.com>`_.

``ImportError: No module named 'shapely'`` / ``'requests'``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The package is not installed in QGIS's Python environment. Open the
**OSGeo4W Shell** and run:

.. code-block:: bash

   pip install shapely requests

Then restart QGIS.

Plugin not visible after installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Go to **Plugins → Manage and Install Plugins → Installed**.
2. Make sure **Lake Analyzer** is ticked.
3. If it does not appear, restart QGIS and check again.

Output GeoTIFF is empty / all NaN
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All pixels were masked out. This can happen when:

* The cloud tolerance is very high but the SCL band incorrectly classifies
  land as cloud (common over bright surfaces such as snow or desert).
* **Restrict to water pixels only** excludes everything because the SCL
  band's "Water" class doesn't extend to the AOI's edges — try a slightly
  larger AOI or a different date.

Check the report's "Water Pixels (of AOI)" and "Valid Pixels Analysed"
percentages to see what happened.

Coordinates appear swapped (X / Y transposed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make sure you are entering coordinates in the correct fields:

* **Left / Right** = longitude (−180 to +180)
* **Bottom / Top** = latitude (−90 to +90)

If you used the Draw on map tool the coordinates are filled automatically
and should be correct.

The "Advanced masking options" panel doesn't show my content / clips off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The panel expands the dialog's *width* to the right when you click
**▸ Advanced masking options**. If your screen resolution is narrow and the
expanded dialog runs off the edge, drag the dialog window to the left
first, then expand the panel.

Reading the log
---------------

All plugin events are written to the QGIS log:

**View → Panels → Log Messages → Lake_Analyzer**

The log includes the STAC query, the selected scene ID, per-band download
progress, and full Python tracebacks for any errors.

Reporting bugs
--------------

Please open an issue at:
https://github.com/iliasmachairas/Lakes_Analyzer/issues

Include:

* QGIS version (Help → About)
* Operating system
* The full error message from the log panel
* The AOI coordinates and date you used
