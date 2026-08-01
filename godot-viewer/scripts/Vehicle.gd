extends Node3D

const CLASS_COLORS := {
	"2W": Color(0.10, 0.95, 0.85),  # neon cyan
	"3W": Color(1.00, 0.72, 0.15),  # neon amber
	"4W": Color(0.75, 0.35, 1.00),  # neon violet
}

var vehicle_id: String = "":
	set(value):
		vehicle_id = value
		_update_label()

var vehicle_class: String = "4W":
	set(value):
		vehicle_class = value
		_apply_class_color()

var target_position: Vector3 = Vector3.ZERO
var target_speed_kmh: float = 0.0
var target_battery_pct: float = 100.0
var _has_target := false


func _ready() -> void:
	_apply_class_color()
	_update_label()


func set_target(world_pos: Vector3, speed_kmh: float, battery_pct: float) -> void:
	target_position = world_pos
	target_speed_kmh = speed_kmh
	target_battery_pct = battery_pct
	if not _has_target:
		global_position = world_pos
		_has_target = true
	_update_label()


func _process(delta: float) -> void:
	if _has_target:
		global_position = global_position.lerp(target_position, clamp(delta * 4.0, 0.0, 1.0))


func _update_label() -> void:
	if has_node("Info"):
		$Info.text = "%s\n%.0f km/h  %.0f%%" % [vehicle_id, target_speed_kmh, target_battery_pct]


func _apply_class_color() -> void:
	if has_node("Body"):
		var mat := StandardMaterial3D.new()
		var color: Color = CLASS_COLORS.get(vehicle_class, Color(0.8, 0.8, 0.8))
		mat.albedo_color = color
		mat.emission_enabled = true
		mat.emission = color
		mat.emission_energy_multiplier = 1.5
		$Body.set_surface_override_material(0, mat)
