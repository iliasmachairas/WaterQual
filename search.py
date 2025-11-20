# search.py
from pystac_client import Client
import planetary_computer as pc

class SentinelSearch:
    def __init__(self, stac_url, collection):
        self.client = Client.open(stac_url)
        self.collection = collection

    def find_best_item(self, aoi_json: dict, datetime_str: str, max_cloud: int = 20):
        search = self.client.search(
            collections=[self.collection],
            intersects=aoi_json,
            datetime=datetime_str,
            query={"eo:cloud_cover": {"lt": max_cloud}},
            limit=1,
        )
        items = list(search.items())
        if not items:
            raise RuntimeError("No Sentinel-2 items found.")
        return pc.sign(items[0])
