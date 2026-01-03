# aoi.py
from shapely.geometry import shape, Polygon, mapping

class AOI:
    def __init__(self, geojson: dict):
        """
        Initialize with a valid GeoJSON dictionary.
        Ensures the polygon ring is closed.
        """
        if "geometry" not in geojson:
            raise ValueError("GeoJSON must contain a 'geometry' field.")

        geom = geojson["geometry"]

        # Ensure polygon closure
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
            if coords[0] != coords[-1]:
                geom["coordinates"][0].append(coords[0])

        self.geojson = geojson
        self.geometry = shape(geom)

    @property
    def bounds(self):
        """Return bounding box as (minx, miny, maxx, maxy)."""
        return self.geometry.bounds

    @property
    def centroid(self):
        """Return centroid as (lon, lat)."""
        c = self.geometry.centroid
        return (c.x, c.y)

    @property
    def area(self):
        """Return area in degrees² (or projected units if projected)."""
        return self.geometry.area

    @property
    def to_geojson(self):
        """Return stored GeoJSON."""
        return self.geojson

    @classmethod
    def from_four_points(cls, points, name="AOI"):
        """
        Create AOI from 4 points (lon, lat), automatically closing ring.
        
        points: list of 4 coordinate pairs.
        """
        if len(points) != 4:
            raise ValueError("Exactly four corner points are required.")

        # Close polygon
        coords = points + [points[0]]

        geojson = {
            "type": "Feature",
            "properties": {"name": name},
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        }
        return cls(geojson)
