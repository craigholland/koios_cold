extends SceneTree
## Check the actual imported streams in the monitor, independent of their codec.

const Monitor = preload("res://components/audio/drone_monitor.gd")
const AUTHORED_FRAMES := [4800, 3000, 2400, 2880]


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var monitor := Monitor.new()
	root.add_child(monitor)
	var ok := true
	for index in AUTHORED_FRAMES.size():
		var cue: AudioStreamWAV = monitor.players[index].stream
		var decoded_frames := roundi(cue.get_length() * cue.mix_rate)
		var should_loop := index < AUTHORED_FRAMES.size() - 1
		var correct_mode := cue.loop_mode == (
			AudioStreamWAV.LOOP_FORWARD if should_loop else AudioStreamWAV.LOOP_DISABLED
		)
		var correct_range := not should_loop or (cue.loop_begin == 0 and cue.loop_end == decoded_frames - 1)
		print("M0_CUE: %s format=%d decoded=%d begin=%d end=%d mode=%d" % [
			Monitor.CUE_BUSES[index], cue.format, decoded_frames, cue.loop_begin, cue.loop_end, cue.loop_mode,
		])
		ok = ok and decoded_frames == AUTHORED_FRAMES[index] and correct_mode and correct_range
	monitor.free()
	if not ok:
		push_error("M0 audio loops must span their authored decoded samples; collision must remain one-shot")
		quit(1)
		return
	print("M0_AUDIO_LOOPS_OK")
	quit()
