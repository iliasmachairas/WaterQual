# scripts/run_lake_chla.py
import json
import numpy as np
from LakePipeline import LakePipeline
from config import selected_coords, selected_date
from aoi import AOI 


def main():
    pipeline = LakePipeline(
        stac_url="https://planetarycomputer.microsoft.com/api/stac/v1",
        collection="sentinel-2-l2a",
    )
    
    result = pipeline.run(
        points_list=selected_coords,
        date_str="2024-07-01/2024-07-31",
        lake_type="turbid",  # or "clear"
        max_cloud=20,
    )

    chl = result["chl"]
    print(
        "Chl-a over water (mg m^-3), percentiles:",
        np.nanpercentile(chl[np.isfinite(chl)], [5, 50, 95]),
    )

if __name__ == "__main__":
    main()
