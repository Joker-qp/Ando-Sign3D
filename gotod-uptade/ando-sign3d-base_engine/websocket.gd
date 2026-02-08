class_name WS
extends Node

@export var websocket_url: String = "ws://192.168.1.3/ws"
@export var config: Config = null 

signal message_received(msg: String)

const heartbeatSeconds: int = 5

var socket: WebSocketPeer = WebSocketPeer.new()
var id: String = ""
var heartbeat: SceneTreeTimer = null
var connected: bool = false

func start(_id: String) -> void:
	id = _id
	connectws()
	set_heartbeat_timer()

func connectws() -> void:
	var err: Error = socket.connect_to_url(websocket_url)
	if err != OK:
		print("Unable to connect")
		set_process(false)
		var timer: SceneTreeTimer = get_tree().create_timer(2.0)
		timer.timeout.connect(connectws)
	else:
		await get_tree().create_timer(2.0).timeout
	connected = true

func set_heartbeat_timer() -> void:
	heartbeat = get_tree().create_timer(heartbeatSeconds)
	heartbeat.timeout.connect(on_heartbeat)

func on_heartbeat() -> void:
	print("PING " + id)
	socket.send_text("PING " + id)
	set_heartbeat_timer()

func _process(_delta: float) -> void:
	if not connected:
		return
	
	socket.poll()
	var state: WebSocketPeer.State = socket.get_ready_state()
	
	if state == WebSocketPeer.STATE_OPEN:
		while socket.get_available_packet_count():
			var message: String = socket.get_packet().get_string_from_utf8()
			print("Got data from server: ", message)
			
			# Herhangi bir mesaja cevap ver (pong)
			if message.begins_with("PING"):
				socket.send_text("PONG")
			
			if message.begins_with(id + " "):
				var content: String = message.substr(id.length() + 1)
				message_received.emit(content)
			else:
				message_received.emit(message)
	
	elif state == WebSocketPeer.STATE_CLOSING:
		pass
	
	elif state == WebSocketPeer.STATE_CLOSED:
		var code: int = socket.get_close_code()
		print("WebSocket closed with code: %d. Clean: %s" % [code, code != -1])
		connected = false
		connectws()
