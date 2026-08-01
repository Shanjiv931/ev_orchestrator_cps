extends Node3D

## Builds the real Vellore road network as two merged meshes (asphalt +
## emissive centerline) from data/vellore_roads.json, which was exported
## from the actual SUMO net (simulation/export_vellore_roads.py) - real
## street geometry, not a flat placeholder plane.

@export var origin_lat: float = 12.937711
@export var origin_lon: float = 79.152291
@export var road_data_path: String = "res://data/vellore_roads.json"
@export var lane_width: float = 3.2
@export var road_color: Color = Color(0.11, 0.115, 0.135)
@export var stripe_color: Color = Color(0.15, 0.85, 0.95)


func _ready() -> void:
	_build()


func _build() -> void:
	var file := FileAccess.open(road_data_path, FileAccess.READ)
	if file == null:
		push_warning("RoadNetwork: could not open %s" % road_data_path)
		return
	var text := file.get_as_text()
	file.close()

	var json := JSON.new()
	if json.parse(text) != OK:
		push_warning("RoadNetwork: failed to parse road data")
		return
	var data = json.get_data()
	var roads: Array = data.get("roads", [])

	var road_surface := SurfaceTool.new()
	road_surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var stripe_surface := SurfaceTool.new()
	stripe_surface.begin(Mesh.PRIMITIVE_TRIANGLES)

	for road in roads:
		var lanes: int = int(road.get("lanes", 1))
		var width: float = max(1, lanes) * lane_width
		var points: Array = road.get("points", [])
		var world_points: Array = []
		for p in points:
			world_points.append(GeoProjection.to_world(float(p[1]), float(p[0]), origin_lat, origin_lon))
		_add_ribbon(road_surface, world_points, width, 0.04)
		_add_ribbon(stripe_surface, world_points, min(width * 0.12, 0.35), 0.05)

	road_surface.index()
	_finish_mesh(road_surface, road_color, false)
	stripe_surface.index()
	_finish_mesh(stripe_surface, stripe_color, true)

	print("RoadNetwork: built %d road segments" % roads.size())


func _finish_mesh(surface: SurfaceTool, color: Color, emissive: bool) -> void:
	var mesh := surface.commit()
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.85
	mat.metallic = 0.05
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	if emissive:
		mat.emission_enabled = true
		mat.emission = color
		mat.emission_energy_multiplier = 0.9
	mesh_instance.set_surface_override_material(0, mat)
	add_child(mesh_instance)


func _add_ribbon(surface: SurfaceTool, points: Array, width: float, y: float) -> void:
	if points.size() < 2:
		return
	var half := width * 0.5
	for i in range(points.size() - 1):
		var a: Vector3 = points[i]
		var b: Vector3 = points[i + 1]
		var dir := b - a
		if dir.length() < 0.001:
			continue
		dir = dir.normalized()
		var side := Vector3(-dir.z, 0.0, dir.x) * half
		var a0 := Vector3(a.x + side.x, y, a.z + side.z)
		var a1 := Vector3(a.x - side.x, y, a.z - side.z)
		var b0 := Vector3(b.x + side.x, y, b.z + side.z)
		var b1 := Vector3(b.x - side.x, y, b.z - side.z)

		surface.set_normal(Vector3.UP)
		surface.add_vertex(a0)
		surface.set_normal(Vector3.UP)
		surface.add_vertex(b0)
		surface.set_normal(Vector3.UP)
		surface.add_vertex(a1)

		surface.set_normal(Vector3.UP)
		surface.add_vertex(b0)
		surface.set_normal(Vector3.UP)
		surface.add_vertex(b1)
		surface.set_normal(Vector3.UP)
		surface.add_vertex(a1)
