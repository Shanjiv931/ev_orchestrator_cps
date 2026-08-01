extends Node3D

## Scatters Kenney city-kit buildings (CC0, see assets/KENNEY_LICENSE.txt)
## offset from real road segments, so the Vellore network reads as an
## actual town rather than empty terrain. Placement is illustrative, not
## real building footprints - Vellore's OSM extract only carried road
## geometry, not building data.

@export var origin_lat: float = 12.937711
@export var origin_lon: float = 79.152291
@export var road_data_path: String = "res://data/vellore_roads.json"
@export var max_buildings: int = 450
@export var placement_probability: float = 0.12
@export var offset_distance: float = 14.0
@export var cell_size: float = 45.0

const BUILDING_MODELS := [
	preload("res://assets/city/buildings/commercial/building-a.glb"),
	preload("res://assets/city/buildings/commercial/building-c.glb"),
	preload("res://assets/city/buildings/commercial/building-e.glb"),
	preload("res://assets/city/buildings/commercial/building-g.glb"),
	preload("res://assets/city/buildings/commercial/building-k.glb"),
	preload("res://assets/city/buildings/commercial/building-m.glb"),
	preload("res://assets/city/buildings/industrial/building-a.glb"),
	preload("res://assets/city/buildings/industrial/building-c.glb"),
	preload("res://assets/city/buildings/industrial/building-e.glb"),
	preload("res://assets/city/buildings/industrial/building-h.glb"),
]

var _rng := RandomNumberGenerator.new()
var _occupied_cells: Dictionary = {}


func _ready() -> void:
	_rng.seed = 1337  # deterministic layout across runs
	_build()


func _build() -> void:
	var file := FileAccess.open(road_data_path, FileAccess.READ)
	if file == null:
		push_warning("CityProps: could not open %s" % road_data_path)
		return
	var text := file.get_as_text()
	file.close()

	var json := JSON.new()
	if json.parse(text) != OK:
		push_warning("CityProps: failed to parse road data")
		return
	var data = json.get_data()
	var roads: Array = data.get("roads", [])

	var placed := 0
	for road in roads:
		if placed >= max_buildings:
			break
		var points: Array = road.get("points", [])
		for i in range(points.size() - 1):
			if placed >= max_buildings:
				break
			if _rng.randf() > placement_probability:
				continue
			var a := GeoProjection.to_world(float(points[i][1]), float(points[i][0]), origin_lat, origin_lon)
			var b := GeoProjection.to_world(float(points[i + 1][1]), float(points[i + 1][0]), origin_lat, origin_lon)
			var dir := b - a
			if dir.length() < 0.5:
				continue
			dir = dir.normalized()
			var side := Vector3(-dir.z, 0.0, dir.x)
			var pick_side := 1.0 if _rng.randf() < 0.5 else -1.0
			var pos := a + side * offset_distance * pick_side
			if not _reserve_cell(pos):
				continue
			_place_building(pos)
			placed += 1

	print("CityProps: placed %d buildings" % placed)


func _reserve_cell(pos: Vector3) -> bool:
	var key := Vector2i(floori(pos.x / cell_size), floori(pos.z / cell_size))
	if _occupied_cells.has(key):
		return false
	_occupied_cells[key] = true
	return true


func _place_building(pos: Vector3) -> void:
	var model_idx := _rng.randi() % BUILDING_MODELS.size()
	var building: Node3D = BUILDING_MODELS[model_idx].instantiate()
	building.position = pos
	building.rotation_degrees.y = _rng.randf_range(0.0, 360.0)
	var s := _rng.randf_range(0.85, 1.3)
	building.scale = Vector3(s, s, s)
	add_child(building)
