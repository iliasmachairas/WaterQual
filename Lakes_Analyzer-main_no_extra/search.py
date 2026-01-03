# search.py
import requests
import json

class SentinelSearch:
    def __init__(self, stac_url, collection):
        self.stac_url = stac_url.rstrip('/')
        self.collection = collection
        self.sign_url = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

    def _sign_asset_url(self, href):
        """Sign a single asset URL using Planetary Computer's signing API"""
        try:
            response = requests.get(self.sign_url, params={"href": href})
            response.raise_for_status()
            return response.json().get("href", href)
        except Exception:
            # If signing fails, return original URL
            return href

    def _sign_item_assets(self, item):
        """Sign all asset URLs in a STAC item"""
        if "assets" in item:
            for asset_key, asset_data in item["assets"].items():
                if "href" in asset_data:
                    item["assets"][asset_key]["href"] = self._sign_asset_url(asset_data["href"])
        #print(item)
        return item

    def find_best_item(self, aoi_json: dict, datetime_str: str, max_cloud: int = 20):
        # Build STAC search request
        search_endpoint = f"{self.stac_url}/search"
        
        # Extract geometry from GeoJSON Feature if needed
        # STAC API expects just the geometry object, not the full Feature
        if "geometry" in aoi_json:
            intersects_geom = aoi_json["geometry"]
        else:
            # Assume it's already a geometry object
            intersects_geom = aoi_json
        
        # Create search request body
        search_body = {
            "collections": [self.collection],
            "intersects": intersects_geom,
            "datetime": datetime_str,
            "query": {
                "eo:cloud_cover": {"lt": max_cloud}
            },
            "limit": 1,
            "sortby": [{"field": "datetime", "direction": "desc"}]
        }
        
        # Make POST request to STAC search endpoint
        try:
            response = requests.post(search_endpoint, json=search_body)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Print more detailed error information
            error_msg = f"HTTP {response.status_code} Error: {response.text}"
            print(f"Request body: {json.dumps(search_body, indent=2)}")
            raise RuntimeError(f"STAC API request failed: {error_msg}") from e
        
        search_result = response.json()
        #print(search_result)
        
        # Extract items from the response
        items = search_result.get("features", [])
        #print(items)
        if not items:
            raise RuntimeError("No Sentinel-2 items found.")
        
        # Get the first item
        item = items[0]
        
        # Sign all asset URLs for Planetary Computer access
        item = self._sign_item_assets(item)
        
        return item
