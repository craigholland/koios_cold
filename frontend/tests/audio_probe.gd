extends RefCounted
## Downstream engine-mix capture. A zero-valued signal keeps silent buses sampled.

const NAMES := [&"Master", &"M0Motor", &"M0Strain", &"M0Collision"]
var captures: Dictionary = {}
var sources: Array[AudioStreamPlayer] = []


func setup(owner: Node) -> void:
	var silent := AudioStreamWAV.new()
	silent.format = AudioStreamWAV.FORMAT_16_BITS
	silent.mix_rate = 12000
	var bytes := PackedByteArray()
	bytes.resize(2400)
	bytes.fill(0)
	silent.data = bytes
	silent.loop_mode = AudioStreamWAV.LOOP_FORWARD
	silent.loop_end = 1200
	for bus_name: StringName in NAMES:
		var bus := AudioServer.get_bus_index(bus_name)
		assert(bus >= 0)
		var cap := AudioEffectCapture.new()
		cap.buffer_length = 1.0
		AudioServer.add_bus_effect(bus, cap)
		captures[bus_name] = cap
		var source := AudioStreamPlayer.new()
		owner.add_child(source)
		source.bus = bus_name
		source.stream = silent
		source.play()
		sources.append(source)


func finish() -> void:
	for source in sources:
		source.stop()


func reset() -> void:
	for cap: AudioEffectCapture in captures.values():
		cap.clear_buffer()


func measure(bus_name: StringName) -> Vector2:
	var cap: AudioEffectCapture = captures[bus_name]
	var count := cap.get_frames_available()
	var peak := 0.0
	for sample in cap.get_buffer(count):
		peak = maxf(peak, maxf(absf(sample.x), absf(sample.y)))
	return Vector2(float(count), peak)
