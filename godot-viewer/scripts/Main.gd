extends Node3D

## Connects to the twin-engine's live WebSocket feed (the same feed the
## React frontend uses) and renders every "vellore" scenario EV as a
## colored box moving in real time, proving the SUMO -> MQTT -> twin-engine
## pipeline reaches a real 3D renderer before any Vellore-styled art goes in.

@export var telemetry_url: String = "ws://127.0.0.1:8100/ws"
@export var origin_lat: float = 12.9375
@export var origin_lon: float = 79.1375

const EARTH_RADIUS := 6371000.0
const VEHICLE_SCENE := preload("res://scenes/Vehicle.tscn")
const RECONNECT_DELAY := 3.0

@onready var camera: Camera3D = $Camera
@onready var status_label: Label = $HUD/StatusLabel

var socket := WebSocketPeer.new()
var vehicles: Dictionary = {}
var camera_target := Vector3.ZERO
var camera_distance := 1800.0
var camera_height := 1400.0
var _reconnect_cooldown := 0.0


func _ready() -> void:
	_update_camera()
	socket.connect_to_url(telemetry_url)


func _process(delta: float) -> void:
	_pan_camera(delta)
	_poll_socket(delta)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera_distance = max(300.0, camera_distance - 150.0)
			camera_height = max(200.0, camera_height - 100.0)
			_update_camera()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera_distance += 150.0
			camera_height += 100.0
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
	var world_pos := geo_to_world(float(lat), float(lon))
	var vehicle := _get_or_spawn_vehicle(vehicle_id, str(data.get("vehicle_class", "4W")))
	vehicle.set_target(world_pos, float(data.get("speed_kmh", 0.0)), float(data.get("battery_pct", 0.0)))


func geo_to_world(lat: float, lon: float) -> Vector3:
	var lat_rad := deg_to_rad(origin_lat)
	var x := deg_to_rad(lon - origin_lon) * EARTH_RADIUS * cos(lat_rad)
	var z := -deg_to_rad(lat - origin_lat) * EARTH_RADIUS
	return Vector3(x, 0.5, z)


func _get_or_spawn_vehicle(vehicle_id: String, vehicle_class: String) -> Node3D:
	if vehicles.has(vehicle_id):
		return vehicles[vehicle_id]
	var vehicle := VEHICLE_SCENE.instantiate()
	vehicle.vehicle_id = vehicle_id
	vehicle.vehicle_class = vehicle_class
	add_child(vehicle)
	vehicles[vehicle_id] = vehicle
	return vehicle
