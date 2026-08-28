# -*- coding: utf-8 -*-
import time
import email.utils
from datetime import datetime, timezone
import requests
from shapely.geometry import shape as shapely_shape

TOO_MANY_REQUESTS_MSG = (
    "Too many requests to Planetary Computer — please wait a few minutes "
    "and try again."
)


class SentinelSearch:
    """Searches Microsoft Planetary Computer's STAC API for Sentinel-2 L2A
    scenes and signs their asset URLs for anonymous access."""

    def __init__(self, stac_url, collection="sentinel-2-l2a"):
        self.stac_url   = stac_url.rstrip('/')
        self.collection = collection
        self.sign_url   = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
        self.max_retries = 3
        self.retry_delay = 5    # seconds between retries for 503/504
        self.rate_limit_wait = 60  # default wait for 429 if no Retry-After header

    def _wait_seconds(self, response):
        """Seconds to wait before retrying, from the Retry-After header if present."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return self.rate_limit_wait
        try:
            return max(1, int(retry_after))
        except ValueError:
            pass
        try:
            dt = email.utils.parsedate_to_datetime(retry_after)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(1, int((dt - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError):
            return self.rate_limit_wait

    def _sign_asset_url(self, href):
        for attempt in range(1, self.max_retries + 1):
            try:
                r = requests.get(self.sign_url, params={"href": href}, timeout=30)
                if r.status_code == 429:
                    if attempt < self.max_retries:
                        wait = self._wait_seconds(r)
                        print(f"[Search] Rate limited while signing an asset URL — "
                              f"waiting {wait}s before retry {attempt + 1}/"
                              f"{self.max_retries}…")
                        time.sleep(wait)
                        continue
                    raise RuntimeError(TOO_MANY_REQUESTS_MSG)
                r.raise_for_status()
                return r.json().get("href", href)
            except RuntimeError:
                raise
            except Exception:
                return href
        return href

    def _sign_item_assets(self, item):
        for asset_data in item.get("assets", {}).values():
            if "href" in asset_data:
                asset_data["href"] = self._sign_asset_url(asset_data["href"])
        return item

    @staticmethod
    def _pick_best_overlap(items, aoi_geom):
        """Among candidate scenes (already filtered by cloud threshold), pick the one
        covering the largest fraction of the AOI; break ties by lower cloud cover.
        Returns (item, coverage_fraction)."""
        aoi_area = aoi_geom.area
        scored = []
        for item in items:
            footprint = item.get("geometry")
            if not footprint:
                continue
            try:
                fraction = (aoi_geom.intersection(shapely_shape(footprint)).area / aoi_area
                            if aoi_area > 0 else 0.0)
            except Exception:
                fraction = 0.0
            cloud = item.get("properties", {}).get("eo:cloud_cover", 100.0)
            scored.append((fraction, -cloud, item))

        if not scored:
            return items[0], 0.0
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        best_fraction, _, best_item = scored[0]
        return best_item, best_fraction

    def find_best_item(self, aoi_json: dict, datetime_str: str, max_cloud_tile: int = 100):
        endpoint = f"{self.stac_url}/search"
        geom     = aoi_json.get("geometry", aoi_json)
        aoi_geom = shapely_shape(geom)
        body     = {
            "collections": [self.collection],
            "intersects":  geom,
            "datetime":    datetime_str,
            "query":       {"eo:cloud_cover": {"lt": max_cloud_tile}},
            "limit":       50,
            "sortby":      [{"field": "eo:cloud_cover", "direction": "asc"}],
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"[Search] STAC query attempt {attempt}/{self.max_retries}…")
                r = requests.post(endpoint, json=body, timeout=60)
                r.raise_for_status()
                items = r.json().get("features", [])
                if not items:
                    raise RuntimeError(
                        "No scenes found for the given AOI, date range, and cloud threshold.")
                best_item, coverage = self._pick_best_overlap(items, aoi_geom)
                return self._sign_item_assets(best_item), coverage

            except requests.exceptions.HTTPError as e:
                if r.status_code == 429:
                    if attempt < self.max_retries:
                        wait = self._wait_seconds(r)
                        print(f"[Search] Rate limited, waiting {wait}s before "
                              f"retry {attempt + 1}/{self.max_retries}…")
                        time.sleep(wait)
                        last_error = e
                    else:
                        raise RuntimeError(TOO_MANY_REQUESTS_MSG) from e
                # 504 / 503 are transient — retry; anything else fail immediately
                elif r.status_code in (503, 504) and attempt < self.max_retries:
                    print(f"[Search] Server timeout ({r.status_code}), "
                          f"retrying in {self.retry_delay}s…")
                    time.sleep(self.retry_delay)
                    last_error = e
                else:
                    raise RuntimeError(
                        f"STAC API error {r.status_code}: {r.text}") from e

            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    print(f"[Search] Request timed out, retrying in {self.retry_delay}s…")
                    time.sleep(self.retry_delay)
                else:
                    raise RuntimeError("STAC API timed out after all retries.")

        raise RuntimeError("STAC API failed after all retries.") from last_error
