extends Node
## Local microphone presentation. Nothing here changes simulation or damage.

const FEED := &"M0DroneFeed"
const CUE_BUSES := [&"M0Ambience", &"M0Motor", &"M0Strain", &"M0Collision"]
const CUES := [
	preload("res://assets/audio/ambience.wav"),
	preload("res://assets/audio/motor.wav"),
	preload("res://assets/audio/strain.wav"),
	preload("res://assets/audio/collision.wav"),
]
const MIX_DB := [-16.0, -13.0, -14.0, -9.0]

var players: Array[AudioStreamPlayer] = []
var enabled := false
var contact := false
var impacts := 0
var _feed_bus := -1


func _ready() -> void:
	_feed_bus = _bus(FEED, &"Master")
	for index in CUES.size():
		_bus(CUE_BUSES[index], FEED)
		var player := AudioStreamPlayer.new()
		var cue: AudioStreamWAV = CUES[index].duplicate()
		if index < 3:
			cue.loop_mode = AudioStreamWAV.LOOP_FORWARD
			cue.loop_end = cue.data.size() >> 1
		player.stream = cue
		player.bus = CUE_BUSES[index]
		player.volume_db = MIX_DB[index]
		add_child(player)
		players.append(player)
	silence()


func sample(eligible: bool, motor: bool, strain: bool, touching: bool) -> void:
	var impact := touching and not contact
	contact = touching
	if not eligible:
		if enabled:
			silence()
		return
	if not enabled:
		enabled = true
		AudioServer.set_bus_mute(_feed_bus, false)
	_loop(players[0], true)
	_loop(players[1], motor)
	_loop(players[2], strain)
	if impact:
		impacts += 1
		players[3].play()


func silence() -> void:
	enabled = false
	if _feed_bus >= 0:
		AudioServer.set_bus_mute(_feed_bus, true)
	for player in players:
		player.stop()


func _exit_tree() -> void:
	silence()


func _bus(bus_name: StringName, send: StringName) -> int:
	var bus := AudioServer.get_bus_index(bus_name)
	if bus < 0:
		AudioServer.add_bus()
		bus = AudioServer.bus_count - 1
		AudioServer.set_bus_name(bus, bus_name)
	AudioServer.set_bus_send(bus, send)
	return bus


func _loop(player: AudioStreamPlayer, active: bool) -> void:
	if active and not player.playing:
		player.play()
	elif not active and player.playing:
		player.stop()
