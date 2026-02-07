class_name Config
extends Resource

var config: ConfigFile = ConfigFile.new()
var id: String = ""
var _phase: int = 0
var _model: String = ""
var _rpm: float = 450.0
var _light: float = 1.0

const configFile: String = "user://config.cfg"
const configSection: String = "master"

signal phase_changed(phase: int)
signal model_changed(model: String)
signal rpm_changed(rpm: float)
signal light_changed(light: float)

func _init() -> void:
	var err: int = load_config()
	if err != OK:
		new_config()
		return
	
	print("ID: " + id)
	print("Phase: " + str(_phase))
	if _model != "":
		print("Model: " + _model)

func new_config() -> void:
	id = generate_unique_id()
	_phase = 0
	_model = ""
	_rpm = 450.0
	_light = 1.0
	save_config()

func save_config() -> void:
	config.set_value(configSection, "id", id)
	config.set_value(configSection, "phase", _phase)
	config.set_value(configSection, "model", _model)
	config.set_value(configSection, "rpm", _rpm)
	config.set_value(configSection, "light", _light)
	config.save(configFile)

func load_config() -> int:
	var err: int = config.load(configFile)
	if err != OK:
		return err
	
	var loaded_id = config.get_value(configSection, "id", null)
	if loaded_id == null:
		return ERR_FILE_UNRECOGNIZED
	
	id = str(loaded_id)
	setPhase(int(config.get_value(configSection, "phase", 0)))
	
	var loaded_model = config.get_value(configSection, "model", null)
	setModel(str(loaded_model) if loaded_model != null else "")
	
	setRpm(float(config.get_value(configSection, "rpm", 450.0)))
	setLight(float(config.get_value(configSection, "light", 1.0)))
	
	return OK

func setPhase(phase: int) -> void:
	_phase = phase
	phase_changed.emit(phase)

func setModel(model: String) -> void:
	_model = model
	model_changed.emit(model)

func setRpm(rpm: float) -> void:
	_rpm = rpm
	rpm_changed.emit(rpm)

func setLight(light: float) -> void:
	_light = light
	light_changed.emit(light)

func generate_unique_id(length: int = 16) -> String:
	var characters: String = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	var result: String = ""
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.randomize()
	
	for i in range(length):
		var random_index: int = rng.randi() % characters.length()
		result += characters[random_index]
	
	return result
