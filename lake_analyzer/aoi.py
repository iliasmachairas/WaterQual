# -*- coding: utf-8 -*-
from shapely.geometry import shape


class AOI:
    def __init__(self, geojson: dict):
        if "geometry" not in geojson:
            raise ValueError("GeoJSON must contain a 'geometry' field.")
        geom = geojson["geometry"]
        if geom["type"] == "Polygon":
            self._close_rings(geom["coordinates"])
        elif geom["type"] == "MultiPolygon":
            for polygon in geom["coordinates"]:
                self._close_rings(polygon)
        self.geojson  = geojson
        self.geometry = shape(geom)

    @staticmethod
    def _close_rings(rings):
        """Close each linear ring in-place (first point == last point) per the GeoJSON spec."""
        for ring in rings:
            if ring[0] != ring[-1]:
                ring.append(ring[0])

    @property
    def bounds(self):
        return self.geometry.bounds  # (minx, miny, maxx, maxy)

    @property
    def centroid(self):
        c = self.geometry.centroid
        return (c.x, c.y)

    @property
    def to_geojson(self):
        return self.geojson

    @classmethod
    def from_four_points(cls, points, name="AOI"):
        if len(points) != 4:
            raise ValueError("Exactly four corner points required.")
        geojson = {
            "type": "Feature",
            "properties": {"name": name},
            "geometry": {"type": "Polygon", "coordinates": [points + [points[0]]]},
        }
        return cls(geojson)
