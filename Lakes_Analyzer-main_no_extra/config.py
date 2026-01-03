
# Bounding box coordinates
xmin = 22.68
xmax = 22.82
ymin = 39.493
ymax = 39.573

selected_date = "2024-06-15" 

# Output directory and file naming
#output_directory = "./output"
output_directory = "./output"
base_name = "lake_analysis"

# Processing mode: "get_data" or "estimate_water_quality"
mode = "get_data"  # Options: "get_data" or "estimate_water_quality"

# Lake type for "estimate_water_quality" mode: "clear" or "turbid" (None if not using water quality estimation)
lake_type = "turbid"  # Options: "clear" or "turbid" (only used when mode = "estimate_water_quality")

# Band selection for "get_data" mode: "all_bands", "rgb_only", or "rgb_nir_swir"
band_selection = "all_bands"  # Only used when mode = "get_data"

# File suffixes for the three output files (used in estimate_water_quality mode)
suffix_chlorophyll_png = "_chlorophyll.png"
suffix_rgb_tiff = "_rgb.tif"
suffix_chlorophyll_tiff = "_chlorophyll.tif"

