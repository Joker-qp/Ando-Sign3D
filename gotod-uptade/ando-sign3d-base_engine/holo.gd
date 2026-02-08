extends Node3D

# Exported variables
@export var camera_node: Node3D
@export var target_node: Node3D
@export var websocket_node: WS
@export var light1: Light3D
@export var light2: Light3D
@export var light3: Light3D
@export var light4: Light3D
@export var video_mesh: MeshInstance3D

# Resources and paths
var local_file_path: String = "user://downloaded_model.glb"
var local_video_path: String = "user://downloaded_video.ogv"
var http_request: HTTPRequest

# Video variables
var video_player: VideoStreamPlayer
var is_video_mode: bool = false

# Rotation variables
var rpm: float = 450.0
var fps: int = 120
var phase: float = 0.0
var angle_per_frame: float = 0.0
var current_angle: float = 0.0

# Synchronization variables
var start_time: float = 0.0
var current_time_ms: int = 0
var frame_counter: int = 0
var frame_drift_detected: int = 0
var frame_drift_threshold: int = 30

# Config
var config: Config

func _ready() -> void:
	_initialize_video_player()
	_initialize_config()
	_setup_engine()
	start_time = Time.get_unix_time_from_system()

func _initialize_video_player() -> void:
	video_player = VideoStreamPlayer.new()
	add_child(video_player)
	video_player.autoplay = false
	video_player.loop = true

func _initialize_config() -> void:
	config = Config.new()
	config.phase_changed.connect(_on_phase_changed)
	config.model_changed.connect(_on_model_changed)
	config.rpm_changed.connect(_on_rpm_changed)
	config.light_changed.connect(_on_light_changed)
	
	_on_phase_changed(config._phase)
	_on_model_changed(config._model)
	_on_rpm_changed(config._rpm)
	_on_light_changed(config._light)
	
	if websocket_node:
		websocket_node.start(config.id)
		websocket_node.message_received.connect(on_message_received)

func _setup_engine() -> void:
	Engine.max_fps = fps * 2
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	angle_per_frame = (TAU * rpm) / (60.0 * fps)

func _on_model_changed(model: String) -> void:
	if model != "" and model != "null":
		load_model(model)

func _on_rpm_changed(_rpm: float) -> void:
	rpm = _rpm
	angle_per_frame = (TAU * rpm) / (60.0 * fps)

func _on_light_changed(light: float) -> void:
	var lights: Array[Light3D] = [light1, light2, light3, light4]
	for light_node in lights:
		if light_node != null:
			light_node.light_energy = light

func load_model(url: String) -> void:
	stop_video()
	
	if http_request:
		http_request.queue_free()
	
	http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_model_request_complete)
	
	var error: Error = http_request.request(url)
	if error != OK:
		push_error("HTTP request error: " + str(error))

func _on_model_request_complete(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		push_error("Download failed. Error: " + str(result))
		return
	
	if response_code != 200:
		push_error("Download failed. HTTP code: " + str(response_code))
		return
	
	var file: FileAccess = FileAccess.open(local_file_path, FileAccess.WRITE)
	if file == null:
		push_error("File write error: " + str(FileAccess.get_open_error()))
		return
	
	file.store_buffer(body)
	file.close()
	
	call_deferred("_instantiate_glb_model")

func _instantiate_glb_model() -> void:
	var importer: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	
	var error: Error = importer.append_from_file(local_file_path, state)
	if error != OK:
		push_error("GLB parse error: " + str(error))
		return
	
	var scene: Node = importer.generate_scene(state)
	if scene == null:
		push_error("Scene generation failed")
		return
	
	_clear_target_children()
	
	scene.name = "downloaded_model"
	if target_node:
		target_node.add_child(scene)
	
	_setup_animation(scene)
	_show_model()

func _clear_target_children() -> void:
	if not target_node:
		return
	
	for child in target_node.get_children():
		target_node.remove_child(child)
		child.queue_free()

func _setup_animation(node: Node) -> void:
	var animation_player: AnimationPlayer = _find_animation_player(node)
	if animation_player == null:
		return
	
	var anim_list: PackedStringArray = animation_player.get_animation_list()
	if anim_list.size() > 0:
		animation_player.speed_scale = 0.9
		animation_player.play(anim_list[0])

func _show_model() -> void:
	if target_node:
		target_node.visible = true
	if video_mesh:
		video_mesh.visible = false

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node
	
	for child in node.get_children():
		var result: AnimationPlayer = _find_animation_player(child)
		if result != null:
			return result
	
	return null

func load_video_from_url(url: String) -> void:
	var video_http: HTTPRequest = HTTPRequest.new()
	add_child(video_http)
	video_http.request_completed.connect(_on_video_request_complete)
	
	var error: Error = video_http.request(url)
	if error != OK:
		push_error("Video request error: " + str(error))

func _on_video_request_complete(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		push_error("Video download failed")
		return
	
	var file: FileAccess = FileAccess.open(local_video_path, FileAccess.WRITE)
	if file == null:
		push_error("Video file write error: " + str(FileAccess.get_open_error()))
		return
	
	file.store_buffer(body)
	file.close()
	
	call_deferred("_play_video")

func _play_video() -> void:
	var video_stream: VideoStreamTheora = VideoStreamTheora.new()
	var file_check: FileAccess = FileAccess.open(local_video_path, FileAccess.READ)
	if file_check == null:
		push_error("Video file not found")
		return
	file_check.close()
	
	video_stream.file = local_video_path
	video_player.stream = video_stream
	video_player.play()
	
	if video_mesh:
		_setup_video_material()
		_show_video()

func _setup_video_material() -> void:
	if not video_mesh:
		return
		
	var material: StandardMaterial3D = StandardMaterial3D.new()
	var video_texture: Texture = video_player.get_video_texture()
	
	material.albedo_texture = video_texture
	material.emission_enabled = true
	material.emission_texture = video_texture
	material.emission_energy = 1.5
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	
	video_mesh.material_override = material

func _show_video() -> void:
	if video_mesh:
		video_mesh.visible = true
	if target_node:
		target_node.visible = false
	is_video_mode = true

func stop_video() -> void:
	if video_player and video_player.is_playing():
		video_player.stop()
	
	is_video_mode = false
	_show_model()

func on_message_received(msg: String) -> void:
	if msg == "+":
		current_angle += angle_per_frame
	elif msg == "-":
		current_angle -= angle_per_frame
	elif msg == "reset":
		_reset_animation()
		current_angle = phase
	elif msg.begins_with("phase "):
		_handle_phase_command(msg)
	elif msg.begins_with("model "):
		_handle_model_command(msg)
	elif msg.begins_with("rpm "):
		_handle_rpm_command(msg)
	elif msg.begins_with("light "):
		_handle_light_command(msg)
	elif msg.begins_with("video "):
		_handle_video_command(msg)
	elif msg == "stop_video":
		stop_video()

func _reset_animation() -> void:
	if not target_node:
		return
		
	var model_node: Node = target_node.get_node_or_null("downloaded_model")
	if model_node == null:
		return
	
	var anim_player: AnimationPlayer = _find_animation_player(model_node)
	if anim_player == null:
		return
	
	anim_player.stop()
	anim_player.speed_scale = 0.9
	
	var anim_list: PackedStringArray = anim_player.get_animation_list()
	if anim_list.size() > 0:
		anim_player.play(anim_list[0])

func _handle_phase_command(msg: String) -> void:
	config.setPhase(int(msg.substr(6)))
	config.save_config()

func _handle_model_command(msg: String) -> void:
	config.setModel(msg.substr(6))
	config.save_config()

func _handle_rpm_command(msg: String) -> void:
	config.setRpm(float(msg.substr(4)))
	config.save_config()

func _handle_light_command(msg: String) -> void:
	config.setLight(float(msg.substr(6)))
	config.save_config()

func _handle_video_command(msg: String) -> void:
	load_video_from_url(msg.substr(6))

func _on_phase_changed(newPhase: int) -> void:
	phase = deg_to_rad(newPhase)

func _process(_delta: float) -> void:
	if is_video_mode:
		return
	
	_update_rotation()
	_synchronize_frame()

func _update_rotation() -> void:
	current_angle -= angle_per_frame
	frame_counter += 1

func _synchronize_frame() -> void:
	current_time_ms = int((Time.get_unix_time_from_system() * 1000.0) - (start_time * 1000.0))
	var calculated_frame: int = int(current_time_ms / (1000.0 / fps)) + 1
	
	if frame_counter != calculated_frame:
		_handle_frame_drift(calculated_frame)
	else:
		frame_drift_detected = 0
	
	if camera_node:
		camera_node.rotation.y = current_angle

func _handle_frame_drift(calculated_frame: int) -> void:
	frame_drift_detected += 1
	
	if frame_drift_detected >= frame_drift_threshold:
		if frame_counter < calculated_frame:
			current_angle -= angle_per_frame
			frame_counter += 1
		else:
			current_angle += angle_per_frame
			frame_counter -= 1
