Installation
============

Prerequisites
-------------

+---------------------+-------------------------------------------+
| Requirement         | Notes                                     |
+=====================+===========================================+
| QGIS ≥ 3.0          | Bundled with Python 3 and GDAL            |
+---------------------+-------------------------------------------+
| Python 3.x          | Provided by the QGIS installer            |
+---------------------+-------------------------------------------+
| GDAL                | Provided by the QGIS installer            |
+---------------------+-------------------------------------------+
| ``shapely``         | Must be installed separately (see below)  |
+---------------------+-------------------------------------------+
| ``numpy``           | Bundled with QGIS                         |
+---------------------+-------------------------------------------+
| ``requests``        | Must be installed separately (see below)  |
+---------------------+-------------------------------------------+

Installing Python dependencies
-------------------------------

Open the **OSGeo4W Shell** (available in the Start Menu after installing QGIS)
and run:

.. code-block:: bash

   pip install shapely requests

.. note::
   Do **not** use a regular terminal or Anaconda environment — the packages
   must be installed into the Python that QGIS uses.

Deploying the plugin
--------------------

Option 1 — Install from ZIP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Download a release ZIP from the
   `GitHub repository <https://github.com/iliasmachairas/Lakes_Analyzer>`_.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the ZIP and click **Install Plugin**.

Option 2 — Copy manually
~~~~~~~~~~~~~~~~~~~~~~~~~

Copy the ``lake_analyzer/`` folder to the QGIS plugins directory:

.. code-block:: text

   C:\Users\<your-username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\

Enabling the plugin
-------------------

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins**.
3. Select the **Installed** tab.
4. Tick the checkbox next to **Lake Analyzer**.

The plugin icon (a lake) appears in the QGIS toolbar.
