# scene.py
from osgeo import gdal, osr
import numpy as np
import gc
from aoi import AOI

class SentinelScene:
    def __init__(self, item, aoi: AOI, resolution=10, dtype="float32", fill_value=0.0):
        self.item = item
        self.aoi = aoi
        self.resolution = resolution
        self.dtype = dtype
        self.fill_value = np.dtype(dtype).type(fill_value)
        self._epsg = None  # lazy
        self._bounds_ll = None
        self._geotransform = None  # stored after first band load
        self._projection = None  # stored after first band load

    def _get_epsg_and_bounds(self):
        if self._epsg is None or self._bounds_ll is None:
            # Handle both dict-based items and object-based items
            if isinstance(self.item, dict):
                properties = self.item.get("properties", {})
                assets = self.item.get("assets", {})
            else:
                properties = getattr(self.item, "properties", {})
                assets = getattr(self.item, "assets", {})
            
            self._epsg = properties.get("proj:epsg", 32632)  # fallback
            self._bounds_ll = self.aoi.bounds  # (minx, miny, maxx, maxy) in lon/lat
            
            print(f"[Scene] EPSG from STAC item: {properties.get('proj:epsg', 'NOT FOUND')}, using EPSG:{self._epsg}")
            print(f"[Scene] AOI bounds (lat/lon): {self._bounds_ll}")
        
        return self._epsg, self._bounds_ll

    def _get_asset_url(self, band_name):
        """Get the URL for a band asset from the STAC item"""
        if isinstance(self.item, dict):
            assets = self.item.get("assets", {})
        else:
            assets = getattr(self.item, "assets", {})
        
        print(f"[Scene] Looking for band '{band_name}' in {len(assets)} available assets")
        print(f"[Scene] Available bands: {list(assets.keys())[:10]}...")  # Show first 10 bands
        
        if band_name not in assets:
            raise ValueError(f"Band {band_name} not found in item assets. Available: {list(assets.keys())}")
        
        asset = assets[band_name]
        if isinstance(asset, dict):
            url = asset.get("href")
        else:
            url = getattr(asset, "href", None)
        
        if url:
            print(f"[Scene] Found URL for {band_name}: {url[:80]}...")  # Show first 80 chars
        else:
            print(f"[Scene] WARNING: No URL found for band {band_name}")
        
        return url


    def _transform_bounds(self, src_epsg, dst_epsg, minx, miny, maxx, maxy):
        """Transform bounding box from one CRS to another using GDAL (axis-safe)"""

        print(f"[Scene] Transforming bounds from EPSG:{src_epsg} to EPSG:{dst_epsg}")
        print(f"[Scene] Source bounds: minx={minx:.6f}, miny={miny:.6f}, "
            f"maxx={maxx:.6f}, maxy={maxy:.6f}")

        # Enable exceptions (future-safe)
        osr.UseExceptions()

        src_srs = osr.SpatialReference()
        src_srs.ImportFromEPSG(src_epsg)
        src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        dst_srs = osr.SpatialReference()
        dst_srs.ImportFromEPSG(dst_epsg)
        dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        transform = osr.CoordinateTransformation(src_srs, dst_srs)

        # Transform all four corners
        corners = [
            (minx, miny),
            (maxx, miny),
            (maxx, maxy),
            (minx, maxy),
        ]

        transformed = [transform.TransformPoint(x, y)[:2] for x, y in corners]

        xs = [p[0] for p in transformed]
        ys = [p[1] for p in transformed]

        bounds_result = (min(xs), min(ys), max(xs), max(ys))

        print(f"[Scene] Transformed bounds: "
            f"minx={bounds_result[0]:.2f}, miny={bounds_result[1]:.2f}, "
            f"maxx={bounds_result[2]:.2f}, maxy={bounds_result[3]:.2f}")

        return bounds_result



    def load_bands(self, band_names, res=None):
        """Load and process bands using GDAL"""
        print(f"[Scene] load_bands() called for bands: {band_names} (requesting {len(band_names)} bands)")
        print(f"[Scene] Target resolution: {res or self.resolution} meters")

        print(f"[Scene] Loading bands: {band_names}")
        epsg, bounds_ll = self._get_epsg_and_bounds()
        res = res or self.resolution
        
        # Convert lat/lon bounds to target CRS bounds
        minx, miny, maxx, maxy = bounds_ll
        bounds_target = self._transform_bounds(4326, epsg, minx, miny, maxx, maxy)
        
        result = {}
        
        for band_name in band_names:
            print(f"\n[Scene] ===== Processing band: {band_name} =====")
            
            src_ds = None
            
            try:
                # Get asset URL
                asset_url = self._get_asset_url(band_name)
                if not asset_url:
                    raise ValueError(f"Could not find URL for band {band_name}")
                
                # Stream directly from Azure using GDAL's VSICURL virtual file system
                # GDAL will use HTTP range requests to read only the needed data
                vsicurl_path = f"/vsicurl/{asset_url}"
                print(f"[Scene] Streaming directly from Azure: {asset_url[:80]}...")
                print(f"[Scene] Using GDAL VSICURL: /vsicurl/...")
                
                src_ds = gdal.Open(vsicurl_path, gdal.GA_ReadOnly)
                if src_ds is None:
                    error_msg = gdal.GetLastErrorMsg()
                    raise RuntimeError(f"Failed to open file from Azure. GDAL error: {error_msg}")
                
                # Print source dataset info
                print(f"[Scene] Source dataset opened successfully")
                print(f"[Scene] Source size: {src_ds.RasterXSize} x {src_ds.RasterYSize}")
                src_geo = src_ds.GetGeoTransform()
                print(f"[Scene] Source geotransform: {src_geo}")
                
                # Calculate source bounds from geotransform
                # geotransform = [x_origin, pixel_width, rotation, y_origin, rotation, -pixel_height]
                src_minx = src_geo[0]
                src_maxx = src_geo[0] + src_ds.RasterXSize * src_geo[1]
                src_maxy = src_geo[3]
                src_miny = src_geo[3] + src_ds.RasterYSize * src_geo[5]  # geo[5] is negative
                print(f"[Scene] Source bounds (in source CRS): minx={src_minx:.2f}, miny={src_miny:.2f}, maxx={src_maxx:.2f}, maxy={src_maxy:.2f}")
                
                # Check if target bounds overlap with source bounds
                print(f"[Scene] Target bounds (in target CRS): minx={bounds_target[0]:.2f}, miny={bounds_target[1]:.2f}, maxx={bounds_target[2]:.2f}, maxy={bounds_target[3]:.2f}")
                
                # Read a sample of source data to check if it has valid values
                src_band = src_ds.GetRasterBand(1)
                src_nodata = src_band.GetNoDataValue()
                print(f"[Scene] Source NoData value: {src_nodata}")
                
                # Read a small sample from center of source image
                sample_size = min(100, src_ds.RasterXSize, src_ds.RasterYSize)
                x_off = (src_ds.RasterXSize - sample_size) // 2
                y_off = (src_ds.RasterYSize - sample_size) // 2
                sample_data = src_band.ReadAsArray(x_off, y_off, sample_size, sample_size)
                if sample_data is not None:
                    valid_mask = sample_data != src_nodata if src_nodata is not None else np.ones_like(sample_data, dtype=bool)
                    if src_nodata is not None:
                        valid_mask = valid_mask & ~np.isnan(sample_data) if np.isnan(src_nodata) else valid_mask
                    valid_data = sample_data[valid_mask] if np.any(valid_mask) else np.array([])
                    if len(valid_data) > 0:
                        print(f"[Scene] Source sample (center {sample_size}x{sample_size}): min={np.min(valid_data):.2f}, max={np.max(valid_data):.2f}, mean={np.mean(valid_data):.2f}")
                        print(f"[Scene] Source sample has {np.sum(valid_mask)} valid pixels out of {sample_data.size}")
                    else:
                        print(f"[Scene] WARNING: Source sample has NO valid data!")
                else:
                    print(f"[Scene] WARNING: Could not read source sample data!")
                
                src_srs = src_ds.GetSpatialRef()
                if src_srs:
                    src_epsg = src_srs.GetAuthorityCode(None)
                    print(f"[Scene] Source CRS: EPSG:{src_epsg}")
                # Check if source and target CRS match
                src_epsg_code = src_srs.GetAuthorityCode(None) if src_srs else None
                needs_reprojection = (src_epsg_code != str(epsg))
                
                # Create output SRS
                dst_srs = osr.SpatialReference()
                error_code = dst_srs.ImportFromEPSG(epsg)
                if error_code != 0:
                    raise RuntimeError(f"Failed to create destination SRS for EPSG:{epsg}")
                
                # If source and target CRS are the same, check bounds overlap
                if not needs_reprojection:
                    # Same CRS - check if bounds overlap
                    tgt_minx, tgt_miny, tgt_maxx, tgt_maxy = bounds_target
                    
                    # Calculate intersection
                    intersect_minx = max(src_minx, tgt_minx)
                    intersect_miny = max(src_miny, tgt_miny)
                    intersect_maxx = min(src_maxx, tgt_maxx)
                    intersect_maxy = min(src_maxy, tgt_maxy)
                    
                    if intersect_minx < intersect_maxx and intersect_miny < intersect_maxy:
                        # Use intersection
                        bounds_to_use = (intersect_minx, intersect_miny, intersect_maxx, intersect_maxy)
                        print(f"[Scene] Using intersection of source and target bounds")
                        print(f"[Scene] Intersection bounds: ({intersect_minx:.2f}, {intersect_miny:.2f}, {intersect_maxx:.2f}, {intersect_maxy:.2f})")
                    else:
                        # No overlap - use source bounds (the actual data extent)
                        bounds_to_use = (src_minx, src_miny, src_maxx, src_maxy)
                        print(f"[Scene] WARNING: Target bounds don't overlap with source! Using source bounds instead.")
                        print(f"[Scene] This means your AOI is outside the Sentinel-2 tile coverage.")
                        print(f"[Scene] Source bounds: ({src_minx:.2f}, {src_miny:.2f}, {src_maxx:.2f}, {src_maxy:.2f})")
                        print(f"[Scene] Target bounds: ({tgt_minx:.2f}, {tgt_miny:.2f}, {tgt_maxx:.2f}, {tgt_maxy:.2f})")
                else:
                    # Different CRS - use transformed bounds
                    bounds_to_use = bounds_target
                    print(f"[Scene] Reprojecting from EPSG:{src_epsg_code} to EPSG:{epsg}")
                
                print(f"[Scene] Warping to EPSG:{epsg}, resolution: {res}m, bounds: {bounds_to_use}")
                
                # Use gdal.Warp to reproject, resample, and crop
                warp_options = gdal.WarpOptions(
                    outputBounds=bounds_to_use,  # [minx, miny, maxx, maxy]
                    outputBoundsSRS=f"EPSG:{epsg}",
                    xRes=res,
                    yRes=res,
                    dstSRS=dst_srs if needs_reprojection else None,  # Only reproject if needed
                    resampleAlg=gdal.GRA_Bilinear,
                    format='MEM',  # In-memory dataset
                    outputType=gdal.GDT_Float32
                )
                
                # Warp (reproject, resample, crop)
                print(f"[Scene] Executing gdal.Warp...")
                print(f"[Scene] Warp options: bounds={bounds_target}, resolution={res}m, CRS=EPSG:{epsg}")
                warped_ds = gdal.Warp('', src_ds, options=warp_options)
                
                if warped_ds is None:
                    error_msg = gdal.GetLastErrorMsg()
                    raise RuntimeError(f"Failed to warp band {band_name}. GDAL error: {error_msg}")
                
                print(f"[Scene] Warp completed successfully")
                print(f"[Scene] Warped size: {warped_ds.RasterXSize} x {warped_ds.RasterYSize}")
                
                # Check warped geotransform
                warped_geo = warped_ds.GetGeoTransform()
                print(f"[Scene] Warped geotransform: {warped_geo}")
                warped_minx = warped_geo[0]
                warped_maxx = warped_geo[0] + warped_ds.RasterXSize * warped_geo[1]
                warped_maxy = warped_geo[3]
                warped_miny = warped_geo[3] + warped_ds.RasterYSize * warped_geo[5]
                print(f"[Scene] Warped bounds: minx={warped_minx:.2f}, miny={warped_miny:.2f}, maxx={warped_maxx:.2f}, maxy={warped_maxy:.2f}")
                
                # Read band data
                band = warped_ds.GetRasterBand(1)
                nodata = band.GetNoDataValue()
                print(f"[Scene] NoData value: {nodata}")
                
                # Read as numpy array - make a copy to ensure data persists after dataset is closed
                print(f"[Scene] Reading band data as numpy array...")
                band_data = band.ReadAsArray().copy()  # Copy to ensure data persists
                print(f"[Scene] Array shape: {band_data.shape}, dtype: {band_data.dtype}")
                print(f"[Scene] Data range: min={np.nanmin(band_data):.2f}, max={np.nanmax(band_data):.2f}")
                
                # Handle nodata values
                if nodata is not None:
                    if np.isnan(nodata):
                        nodata_mask = np.isnan(band_data)
                    else:
                        nodata_mask = (band_data == nodata)
                    
                    nodata_count = np.sum(nodata_mask)
                    nodata_percent = 100*nodata_count/band_data.size
                    print(f"[Scene] Found {nodata_count} nodata pixels ({nodata_percent:.1f}%)")
                    
                    # Warning if all data is nodata
                    if nodata_percent >= 99.9:
                        print(f"[Scene] WARNING: {nodata_percent:.1f}% of pixels are nodata! Check bounds or data availability.")
                    
                    if self.fill_value is not None:
                        band_data[nodata_mask] = self.fill_value
                        print(f"[Scene] Replaced nodata with fill_value: {self.fill_value}")
                    else:
                        band_data[nodata_mask] = np.nan
                        print(f"[Scene] Replaced nodata with NaN")
                
                # Convert dtype
                band_data = band_data.astype(self.dtype)
                print(f"[Scene] Converted to dtype: {self.dtype}")
                
                # Store geotransform and projection info from first band (they're the same for all bands)
                if self._geotransform is None:
                    self._geotransform = warped_geo
                    warped_srs = warped_ds.GetSpatialRef()
                    if warped_srs:
                        self._projection = warped_srs.ExportToWkt()
                        print(f"[Scene] Stored geotransform and projection for TIFF export")
                
                # Store band data
                result[band_name] = band_data
                print(f"[Scene] ✓ Successfully loaded band {band_name}")
                
                # Clean up GDAL objects immediately - close datasets properly
                band = None
                if warped_ds:
                    warped_ds.FlushCache()  # Ensure all data is written/flushed
                    warped_ds = None
                gc.collect()  # Force garbage collection to free memory
                
            except Exception as e:
                print(f"[Scene] ERROR processing band {band_name}: {type(e).__name__}: {str(e)}")
                raise
            finally:
                # Clean up GDAL dataset - close properly to avoid crashes
                if src_ds:
                    src_ds.FlushCache()  # Ensure all operations are complete
                    src_ds = None
                    print(f"[Scene] Closed source dataset")
                
                # Force garbage collection after each band
                gc.collect()
        
        # Show actual bands loaded vs requested
        requested_count = len(band_names)
        loaded_count = len(result)
        print(f"\n[Scene] ✓ Successfully loaded {loaded_count} of {requested_count} requested bands")
        if loaded_count != requested_count:
            print(f"[Scene] WARNING: Expected {requested_count} bands but got {loaded_count}")
            print(f"[Scene] Requested: {band_names}")
            print(f"[Scene] Loaded: {list(result.keys())}")
        
        return result

    def load_rgb(self, bands=("B04", "B03", "B02")):
        rgb = self.load_bands(list(bands))
        # stack into (y,x,3)
        arr = np.stack([rgb[b] for b in bands], axis=-1)
        return arr
    
    def save_tiff(self, array, output_path, nodata_value=None, band_names=None):
        """
        Save a numpy array as a georeferenced TIFF file.
        
        Parameters:
        -----------
        array : np.ndarray
            Array to save. Can be 2D (single band) or 3D (multi-band, shape: height, width, bands)
        output_path : str
            Path to output TIFF file
        nodata_value : float, optional
            NoData value to use (default: self.fill_value)
        band_names : list of str, optional
            Names for each band (will be set as band descriptions)
        """
        import os
        
        if self._geotransform is None or self._projection is None:
            raise ValueError("Geotransform and projection not available. Load at least one band first.")
        
        if nodata_value is None:
            nodata_value = self.fill_value
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Determine number of bands and array shape
        if array.ndim == 2:
            height, width = array.shape
            n_bands = 1
            arrays = [array]
        elif array.ndim == 3:
            height, width, n_bands = array.shape
            arrays = [array[:, :, i] for i in range(n_bands)]
        else:
            raise ValueError(f"Array must be 2D or 3D, got {array.ndim}D")
        
        # Create output dataset
        driver = gdal.GetDriverByName('GTiff')
        dtype_map = {
            'uint8': gdal.GDT_Byte,
            'uint16': gdal.GDT_UInt16,
            'int16': gdal.GDT_Int16,
            'uint32': gdal.GDT_UInt32,
            'int32': gdal.GDT_Int32,
            'float32': gdal.GDT_Float32,
            'float64': gdal.GDT_Float64,
        }
        
        gdal_dtype = dtype_map.get(str(array.dtype), gdal.GDT_Float32)
        
        dst_ds = driver.Create(output_path, width, height, n_bands, gdal_dtype)
        if dst_ds is None:
            raise RuntimeError(f"Failed to create TIFF file: {output_path}")
        
        # Set geotransform and projection
        dst_ds.SetGeoTransform(self._geotransform)
        dst_ds.SetProjection(self._projection)
        
        # Write bands
        for i, band_data in enumerate(arrays, 1):
            band = dst_ds.GetRasterBand(i)
            band.WriteArray(band_data)
            if nodata_value is not None:
                band.SetNoDataValue(nodata_value)
            # Set band description if provided
            if band_names is not None and i <= len(band_names):
                band.SetDescription(band_names[i-1])
            band.FlushCache()
        
        dst_ds = None  # Close dataset
        print(f"[Scene] ✓ Saved TIFF: {output_path} ({n_bands} band(s), {width}x{height})")
