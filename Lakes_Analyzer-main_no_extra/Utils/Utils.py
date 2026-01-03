def rectangle_from_points(points, name="Rectangle AOI"):
    """
    Create a GeoJSON polygon from a list of 5 coordinates (closed ring).
    Example input:
      [(lon, lat), ... x5]
    """
    if len(points) != 5:
        raise ValueError("Rectangle needs exactly 5 points (closed ring).")

    return {
        "type": "Feature",
        "properties": {"name": name},
        "geometry": {
            "type": "Polygon",
            "coordinates": [points]
        }
    }
