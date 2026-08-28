WaterQual
=========

.. image:: _static/icon.png
   :width: 120px
   :align: center

A QGIS 3.0+ plugin that monitors lake water quality from **Sentinel-2 L2A**
imagery via Microsoft Planetary Computer's STAC API — chlorophyll-a
(NDCI) and turbidity (NDTI), with no account or API key required.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   usage
   algorithms
   architecture
   troubleshooting

Overview
--------

WaterQual lets you draw a lake's boundary (or pick an existing polygon
layer) on the QGIS map canvas, choose a date, and get back a georeferenced
water-quality index raster plus a plain-text report — all without leaving
QGIS. The search, download, and analysis run in a background thread so the
interface stays responsive throughout.

**What it computes**

* **NDCI** — Normalized Difference Chlorophyll Index, a proxy for
  chlorophyll-a concentration / algal bloom potential.
* **NDTI** — Normalized Difference Turbidity Index, a proxy for suspended
  sediment / water clarity.

See :doc:`algorithms` for the formulas, what they mean, and their
limitations.

**Key capabilities**

* Restricts the analysis to actual water pixels using the Sentinel-2 SCL
  band, so results aren't diluted by surrounding land.
* Optionally also saves the raw RGB+NIR+SWIR imagery for the same scene, so
  you can visually inspect what's driving a reading.
* Cloud/shadow masking and cloud-percentage thresholds are tucked into a
  collapsed "Advanced masking options" panel with sensible defaults —
  visible only if you need to change them.
* Interactive rubber-band AOI drawing directly on the QGIS canvas, or reuse
  an existing polygon layer.

Source code
-----------

https://github.com/iliasmachairas/WaterQual

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`
