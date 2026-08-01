extends Node3D

## Builds a proportioned multi-part vehicle body per class (4W car, 3W auto,
## 2W scooter) instead of a single box - separate chassis/cabin/glass/wheel
## meshes with real PBR materials, plus a class-coded neon underglow +
## light accents (the visual "EV" signature) rather than lurid full-body
## neon paint.

const ACCENT_BY_CLASS := {
	"2W": Color(0.10, 0.95, 0.85),  # neon cyan
	"3W": Color(1.00, 0.72, 0.15),  # neon amber
	"4W": Color(0.75, 0.35, 1.00),  # neon violet
}

const PAINT_PALETTE := [
	Color(0.92, 0.93, 0.95),  # pearl white
	Color(0.62, 0.64, 0.68),  # silver
	Color(0.10, 0.10, 0.13),  # graphite black
	Color(0.08, 0.20, 0.42),  # deep blue
	Color(0.55, 0.06, 0.10),  # dark red
]

# Real 4W meshes (Kenney Car Kit, CC0 - see assets/KENNEY_LICENSE.txt),
# picked deterministically per vehicle_id for variety. No motorbike/auto-
# rickshaw equivalent exists in the kit, so 2W/3W stay procedural.
const CAR_MODELS := [
	preload("res://assets/vehicles/sedan.glb"),
	preload("res://assets/vehicles/suv.glb"),
	preload("res://assets/vehicles/hatchback-sports.glb"),
	preload("res://assets/vehicles/taxi.glb"),
	preload("res://assets/vehicles/van.glb"),
	preload("res://assets/vehicles/delivery.glb"),
]

var vehicle_id: String = "":
	set(value):
		vehicle_id = value
		_update_label()

var vehicle_class: String = "4W":
	set(value):
		vehicle_class = value
		_build_geometry()

var target_position: Vector3 = Vector3.ZERO
var target_speed_kmh: float = 0.0
var target_battery_pct: float = 100.0
var _has_target := false
var _facing := Vector3.FORWARD

@onready var parts: Node3D = $Parts
@onready var info: Label3D = $Info


func _ready() -> void:
	# vehicle_class/vehicle_id are set right after instantiate() but before
	# add_child(), so their setters run while @onready vars (parts, info)
	# are still null and silently no-op - rebuild here now that they're live.
	_build_geometry()
	_update_label()


func set_target(world_pos: Vector3, speed_kmh: float, battery_pct: float) -> void:
	if _has_target and world_pos.distance_to(global_position) > 0.05:
		_facing = (world_pos - global_position).normalized()
	target_position = world_pos
	target_speed_kmh = speed_kmh
	target_battery_pct = battery_pct
	if not _has_target:
		global_position = world_pos
		_has_target = true
	_update_label()


func _process(delta: float) -> void:
	if not _has_target:
		return
	global_position = global_position.lerp(target_position, clamp(delta * 4.0, 0.0, 1.0))
	if _facing.length() > 0.01:
		# Body geometry is built with local +X as the front (see _build_geometry),
		# not Godot's usual -Z-forward convention, so align +X to world _facing
		# directly rather than using Transform3D.looking_at (which assumes -Z-forward).
		var theta := atan2(-_facing.z, _facing.x)
		var target_basis := Basis(Vector3.UP, theta)
		parts.basis = parts.basis.slerp(target_basis, clamp(delta * 6.0, 0.0, 1.0))


func _update_label() -> void:
	if info:
		info.text = "%s\n%.0f km/h  %.0f%%" % [vehicle_id, target_speed_kmh, target_battery_pct]


func _accent_color() -> Color:
	return ACCENT_BY_CLASS.get(vehicle_class, Color(0.8, 0.8, 0.8))


func _paint_color() -> Color:
	var idx: int = absi(hash(vehicle_id)) % PAINT_PALETTE.size()
	return PAINT_PALETTE[idx]


func _paint_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _paint_color()
	mat.metallic = 0.75
	mat.roughness = 0.25
	return mat


func _glass_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.05, 0.08, 0.12, 0.45)
	mat.metallic = 0.0
	mat.roughness = 0.05
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return mat


func _dark_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.04, 0.04, 0.045)
	mat.metallic = 0.0
	mat.roughness = 0.9
	return mat


func _rim_material() -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.75, 0.76, 0.78)
	mat.metallic = 0.9
	mat.roughness = 0.3
	return mat


func _emissive_material(color: Color, energy: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.emission_enabled = true
	mat.emission = color
	mat.emission_energy_multiplier = energy
	return mat


func _box(size: Vector3, position: Vector3, material: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.position = position
	instance.set_surface_override_material(0, material)
	parts.add_child(instance)
	return instance


func _wheel(position: Vector3, radius: float, thickness: float) -> void:
	var tire_mesh := CylinderMesh.new()
	tire_mesh.top_radius = radius
	tire_mesh.bottom_radius = radius
	tire_mesh.height = thickness
	var tire := MeshInstance3D.new()
	tire.mesh = tire_mesh
	tire.rotation_degrees = Vector3(0, 0, 90)
	tire.position = position
	tire.set_surface_override_material(0, _dark_material())
	parts.add_child(tire)

	var rim_mesh := CylinderMesh.new()
	rim_mesh.top_radius = radius * 0.45
	rim_mesh.bottom_radius = radius * 0.45
	rim_mesh.height = thickness + 0.03
	var rim := MeshInstance3D.new()
	rim.mesh = rim_mesh
	rim.rotation_degrees = Vector3(0, 0, 90)
	rim.position = position
	rim.set_surface_override_material(0, _rim_material())
	parts.add_child(rim)


func _tint_body(node: Node, color: Color) -> void:
	# Kenney's car meshes come out of glTF import with a mostly-white body
	# texture (a KHR_texture_transform atlas quirk, not a broken reference -
	# confirmed the texture itself binds fine). Rather than fight the
	# importer, give each vehicle_id a deliberate paint color, matching the
	# procedural 2W/3W look, without recoloring the wheels/tires.
	if node is MeshInstance3D and node.name.begins_with("body"):
		var mesh: Mesh = node.mesh
		for i in mesh.get_surface_count():
			var base_mat := mesh.surface_get_material(i)
			var mat: StandardMaterial3D = base_mat.duplicate() if base_mat is StandardMaterial3D else StandardMaterial3D.new()
			mat.albedo_color = color
			node.set_surface_override_material(i, mat)
	for child in node.get_children():
		_tint_body(child, color)


func _underglow(length: float, width: float) -> void:
	_box(Vector3(length, 0.03, width), Vector3(0, 0.06, 0), _emissive_material(_accent_color(), 1.4))


func _build_geometry() -> void:
	if not is_instance_valid(parts):
		return
	for child in parts.get_children():
		child.queue_free()

	var paint := _paint_material()
	var glass := _glass_material()
	var accent := _accent_color()
	var headlight := _emissive_material(Color(0.85, 0.92, 1.0), 4.0)
	var taillight := _emissive_material(accent, 3.0)

	match vehicle_class:
		"2W":
			_box(Vector3(1.3, 0.20, 0.32), Vector3(0.0, 0.55, 0.0), paint)
			_box(Vector3(0.5, 0.10, 0.34), Vector3(-0.20, 0.68, 0.0), _dark_material())
			_box(Vector3(0.22, 0.32, 0.28), Vector3(0.55, 0.82, 0.0), paint)
			_box(Vector3(0.06, 0.10, 0.20), Vector3(0.66, 0.90, 0.0), headlight)
			_box(Vector3(0.05, 0.08, 0.22), Vector3(-0.66, 0.60, 0.0), taillight)
			_wheel(Vector3(0.58, 0.30, 0.0), 0.30, 0.10)
			_wheel(Vector3(-0.58, 0.30, 0.0), 0.30, 0.10)
			_underglow(1.3, 0.30)
			info.position = Vector3(0, 1.5, 0)
		"3W":
			_box(Vector3(1.7, 0.65, 1.15), Vector3(0.0, 0.55, 0.0), paint)
			_box(Vector3(1.55, 0.08, 1.05), Vector3(0.0, 0.92, 0.0), paint)
			_box(Vector3(0.05, 0.45, 1.0), Vector3(0.55, 0.60, 0.0), glass)
			_box(Vector3(0.08, 0.14, 0.9), Vector3(0.82, 0.55, 0.0), headlight)
			_box(Vector3(0.06, 0.16, 1.0), Vector3(-0.82, 0.55, 0.0), taillight)
			_wheel(Vector3(0.55, 0.32, 0.0), 0.32, 0.12)
			_wheel(Vector3(-0.55, 0.32, 0.55), 0.32, 0.12)
			_wheel(Vector3(-0.55, 0.32, -0.55), 0.32, 0.12)
			_underglow(1.7, 1.1)
			info.position = Vector3(0, 1.7, 0)
		_:
			var model_idx: int = absi(hash(vehicle_id)) % CAR_MODELS.size()
			var model: Node3D = CAR_MODELS[model_idx].instantiate()
			# Kenney's glTF forward axis vs. this project's local +X-forward
			# convention (see _process) - tuned empirically against screenshots.
			model.rotation_degrees = Vector3(0, 90, 0)
			_tint_body(model, _paint_color())
			parts.add_child(model)
			_underglow(2.6, 1.3)
			info.position = Vector3(0, 2.3, 0)
