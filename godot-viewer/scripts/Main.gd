extends Node3D

## Connects to the twin-engine's live WebSocket feed (the same feed the
## React frontend uses) and renders every "vellore" scenario EV as a
## proportioned 3D vehicle (see Vehicle.gd) driving over the real Vellore
## road network (see RoadNetwork.gd / data/vellore_roads.json).

@export var telemetry_url: String = "ws://127.0.0.1:8100/ws"
# Center of the real exported road network bounds (simulation/export_vellore_roads.py),
# not a guess - keeps vehicles and roads in the same coordinate frame.
@export var origin_lat: float = 12.937711
@export var origin_lon: float = 79.152291

const VEHICLE_SCENE := preload("res://scenes/Vehicle.tscn")
const RECONNECT_DELAY := 3.0

@onready var camera: Camera3D = $Camera
@onready var status_label: Label = $HUD/StatusLabel
@onready var sun: DirectionalLight3D = $Sun

var socket := WebSocketPeer.new()
var vehicles: Dictionary = {}
var camera_target := Vector3.ZERO
var camera_distance := 22.0
var camera_height := 11.0
var _reconnect_cooldown := 0.0
var _camera_framed := false
var _tracked_vehicle: Node3D = null
var _following := true


func _ready() -> void:
	_setup_environment()
	_setup_sun()
	_update_camera()
	socket.connect_to_url(telemetry_url)


func _setup_environment() -> void:
	var env := Environment.new()

	env.background_mode = Environment.BG_SKY
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(0.06, 0.07, 0.13)
	sky_material.sky_horizon_color = Color(0.20, 0.19, 0.27)
	sky_material.ground_bottom_color = Color(0.04, 0.04, 0.06)
	sky_material.ground_horizon_color = Color(0.14, 0.13, 0.17)
	sky_material.sun_angle_max = 6.0
	var sky := Sky.new()
	sky.sky_material = sky_material
	env.sky = sky

	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.7

	env.fog_enabled = true
	env.fog_light_color = Color(0.05, 0.06, 0.10)
	env.fog_density = 0.0012
	env.fog_sky_affect = 0.35

	env.glow_enabled = true
	env.glow_intensity = 0.7
	env.glow_bloom = 0.15
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.glow_hdr_threshold = 1.6

	env.ssao_enabled = true
	env.ssao_intensity = 1.5
	env.ssao_radius = 1.5

	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05

	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)


func _setup_sun() -> void:
	# Hand-typed Euler rotations are error-prone to get pointing at the
	# ground correctly - position it off to a side and look_at the origin
	# instead, same trick used for the camera.
	sun.position = Vector3(1500, 2200, 1200)
	sun.look_at(Vector3.ZERO, Vector3.UP)
	sun.light_energy = 1.6
	sun.light_color = Color(1.0, 0.96, 0.88)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 2000.0


func _process(delta: float) -> void:
	if _following and is_instance_valid(_tracked_vehicle):
		camera_target = _tracked_vehicle.global_position
		_update_camera()
	_pan_camera(delta)
	_poll_socket(delta)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera_distance = max(6.0, camera_distance / 1.15)
			camera_height = max(3.5, camera_height / 1.15)
			_update_camera()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera_distance = min(6000.0, camera_distance * 1.15)
			camera_height = min(4500.0, camera_height * 1.15)
			_update_camera()


func _pan_camera(delta: float) -> void:
	var pan := Vector3.ZERO
	if Input.is_key_pressed(KEY_LEFT):
		pan.x -= 1
	if Input.is_key_pressed(KEY_RIGHT):
		pan.x += 1
	if Input.is_key_pressed(KEY_UP):
		pan.z -= 1
	if Input.is_key_pressed(KEY_DOWN):
		pan.z += 1
	if pan != Vector3.ZERO:
		_following = false
		camera_target += pan.normalized() * 900.0 * delta
		_update_camera()


func _update_camera() -> void:
	camera.position = camera_target + Vector3(0, camera_height, camera_distance)
	camera.look_at(camera_target, Vector3.UP)


func _poll_socket(delta: float) -> void:
	socket.poll()
	var state := socket.get_ready_state()
	match state:
		WebSocketPeer.STATE_OPEN:
			_reconnect_cooldown = 0.0
			while socket.get_available_packet_count() > 0:
				_handle_message(socket.get_packet().get_string_from_utf8())
			status_label.text = "Connected to twin-engine - %d vellore vehicles" % vehicles.size()
		WebSocketPeer.STATE_CONNECTING:
			status_label.text = "Connecting to %s ..." % telemetry_url
		WebSocketPeer.STATE_CLOSING:
			status_label.text = "Closing connection..."
		WebSocketPeer.STATE_CLOSED:
			status_label.text = "Disconnected from twin-engine - retrying..."
			_reconnect_cooldown -= delta
			if _reconnect_cooldown <= 0.0:
				socket.connect_to_url(telemetry_url)
				_reconnect_cooldown = RECONNECT_DELAY


func _handle_message(text: String) -> void:
	var json := JSON.new()
	if json.parse(text) != OK:
		return
	var envelope = json.get_data()
	if typeof(envelope) != TYPE_DICTIONARY or envelope.get("entity_type") != "ev":
		return
	var data: Dictionary = envelope.get("data", {})
	if data.get("scenario") != "vellore":
		return
	var vehicle_id: String = str(envelope.get("entity_id", ""))
	var lat = data.get("lat")
	var lon = data.get("lon")
	if vehicle_id == "" or lat == null or lon == null:
		return
	var world_pos := GeoProjection.to_world(float(lat), float(lon), origin_lat, origin_lon)
	world_pos.y = 0.0
	var vehicle := _get_or_spawn_vehicle(vehicle_id, str(data.get("vehicle_class", "4W")))
	vehicle.set_target(world_pos, float(data.get("speed_kmh", 0.0)), float(data.get("battery_pct", 0.0)))
	if not _camera_framed:
		# The projection origin is just the geometric center of the road
		# network bounds - it isn't guaranteed to have a road or vehicle
		# near it, so track the very first live vehicle instead. Camera
		# follows it every frame until the user pans manually (see _process).
		_camera_framed = true
		_tracked_vehicle = vehicle


func _get_or_spawn_vehicle(vehicle_id: String, vehicle_class: String) -> Node3D:
	if vehicles.has(vehicle_id):
		return vehicles[vehicle_id]
	var vehicle := VEHICLE_SCENE.instantiate()
	vehicle.vehicle_id = vehicle_id
	vehicle.vehicle_class = vehicle_class
	add_child(vehicle)
	vehicles[vehicle_id] = vehicle
	return vehicle
