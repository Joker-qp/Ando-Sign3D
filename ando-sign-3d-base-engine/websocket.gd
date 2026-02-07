class_name WS
extends Node

@export var websocket_url: String = "ws://192.168.1.3:80/ws"
@export var config: Config = null 

signal message_received(msg: String)

const HEARTBEAT_SECONDS: int = 5
const RECONNECT_DELAY: float = 2.0
const MAX_RECONNECT_ATTEMPTS: int = 5

var socket: WebSocketPeer = WebSocketPeer.new()
var id: String = ""
var heartbeat: SceneTreeTimer = null
var connected: bool = false
var reconnect_attempts: int = 0

func start(_id: String) -> void:
	id = _id
	print("[WS] Starting WebSocket with ID: ", id)
	_connect_websocket()
	_set_heartbeat_timer()

func _connect_websocket() -> void:
	print("[WS] Attempting to connect to: ", websocket_url)
	
	var err: Error = socket.connect_to_url(websocket_url)
	if err != OK:
		print("[WS] ERROR: Failed to initiate connection. Error code: ", err)
		reconnect_attempts += 1
		
		if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
			print("[WS] Retry attempt ", reconnect_attempts, "/", MAX_RECONNECT_ATTEMPTS)
			set_process(false)
			var timer: SceneTreeTimer = get_tree().create_timer(RECONNECT_DELAY)
			timer.timeout.connect(_connect_websocket)
		else:
			print("[WS] Max reconnection attempts reached. Giving up.")
	else:
		print("[WS] Connection initiated, waiting for handshake...")
		set_process(true)

func _set_heartbeat_timer() -> void:
	if heartbeat != null:
		return
	
	heartbeat = get_tree().create_timer(HEARTBEAT_SECONDS)
	heartbeat.timeout.connect(_on_heartbeat)

func _on_heartbeat() -> void:
	if connected and socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		print("[WS] Sending PING: ", id)
		socket.send_text("PING " + id)
	
	heartbeat = null
	_set_heartbeat_timer()

func _process(_delta: float) -> void:
	socket.poll()
	
	var state: WebSocketPeer.State = socket.get_ready_state()
	
	match state:
		WebSocketPeer.STATE_CONNECTING:
			# Still connecting
			pass
			
		WebSocketPeer.STATE_OPEN:
			if not connected:
				print("[WS] ✓ Successfully connected!")
				connected = true
				reconnect_attempts = 0
			_handle_incoming_messages()
		
		WebSocketPeer.STATE_CLOSING:
			print("[WS] Connection closing...")
		
		WebSocketPeer.STATE_CLOSED:
			if connected:
				_handle_disconnection()

func _handle_incoming_messages() -> void:
	while socket.get_available_packet_count() > 0:
		var packet: PackedByteArray = socket.get_packet()
		var message: String = packet.get_string_from_utf8()
		print("[WS] Received: ", message)
		
		var content: String = _extract_message_content(message)
		message_received.emit(content)

func _extract_message_content(message: String) -> String:
	if message.begins_with(id + " "):
		return message.substr(id.length() + 1)
	return message

func _handle_disconnection() -> void:
	var code: int = socket.get_close_code()
	var reason: String = socket.get_close_reason()
	var is_clean: bool = code != -1
	
	print("[WS] Disconnected - Code: %d, Clean: %s, Reason: %s" % [code, is_clean, reason])
	
	connected = false
	reconnect_attempts = 0
	
	var timer: SceneTreeTimer = get_tree().create_timer(RECONNECT_DELAY)
	timer.timeout.connect(_connect_websocket)

func disconnect_websocket() -> void:
	if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		socket.close(1000, "Client closing")
	connected = false
	set_process(false)

func send_message(msg: String) -> void:
	if connected and socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
		print("[WS] Sending: ", msg)
		socket.send_text(msg)
	else:
		push_error("[WS] Cannot send message: WebSocket not connected")

func _exit_tree() -> void:
	disconnect_websocket()
