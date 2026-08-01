class_name GeoProjection
extends RefCounted

## Shared equirectangular lat/lon -> local-meter projection, used by both the
## live vehicle feed (Main.gd) and the road mesh (RoadNetwork.gd) so they
## share one coordinate frame.

const EARTH_RADIUS := 6371000.0


static func to_world(lat: float, lon: float, origin_lat: float, origin_lon: float) -> Vector3:
	var lat_rad := deg_to_rad(origin_lat)
	var x := deg_to_rad(lon - origin_lon) * EARTH_RADIUS * cos(lat_rad)
	var z := -deg_to_rad(lat - origin_lat) * EARTH_RADIUS
	return Vector3(x, 0.0, z)
