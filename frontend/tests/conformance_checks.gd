extends SceneTree
## Real scene and bridge. Rendered mode measures the mixed engine signal, not speakers.

const Sandbox = preload("res://app/sandbox.tscn")
const AudioProbe = preload("res://tests/audio_probe.gd")
const SETTLE_S := 0.25
const SILENCE := 0.0001
const POSITIVE := 0.004
var probe := AudioProbe.new()
var app: Node
var command: LineEdit
var measure_audio := false
var records: Array[Dictionary] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	measure_audio = "--measure-audio" in OS.get_cmdline_user_args()
	var driver := AudioServer.get_driver_name()
	if not _expect((driver != "Dummy") if measure_audio else true, "rendered test needs real audio driver"):
		return
	print("M0_CONFORMANCE_DRIVER: " + driver)
	app = Sandbox.instantiate()
	app.client.received.connect(_feedback)
	root.add_child(app)
	command = app.get_node("HUD/Command")
	if measure_audio:
		probe.setup(root)
	if not await _until(func(): return app.client.live, "backend ready"):
		return
	if "--interruption" in OS.get_cmdline_user_args():
		if not await _interruption():
			return
		print("M0_CONFORMANCE_OK: accepted queue, stop, pause, takeover and resource accounting")
	else:
		if not await _audio_and_route():
			return
		print("M0_CONFORMANCE_OK: wait/open/arrive, actual cue and gate behavior")
	probe.finish()
	app.shutdown()


func _audio_and_route() -> bool:
	if not await _quiet("startup Schematic"):
		return false
	_key(KEY_1)
	if not await _until(func(): return app.monitor.enabled, "Drone feed became current"):
		return false
	if measure_audio:
		probe.reset()
		await create_timer(0.12).timeout
		if not _mix(&"Master", true, "Drone idle ambience"):
			return false
	# Native focus event delivery is exercised by the inherited focus check.
	app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	if not await _quiet("focus-out gate"):
		return false
	app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	_press(KEY_UP)
	if not await _until(func(): return app.view.motor_active and _point().x > 4.2, "real motor motion"):
		return false
	if measure_audio:
		probe.reset()
		await create_timer(0.12).timeout
		if not _mix(&"M0Motor", true, "Drone motion"):
			return false
	if measure_audio:
		probe.reset()
	if not await _until(func(): return app.monitor.impacts == 1 and app.view.motor_strain,
						"actual closed-door contact and strain"):
		return false
	await create_timer(0.10).timeout
	if measure_audio:
		if not _mix(&"M0Strain", true, "Drone blocked motor") or not _mix(&"M0Collision", true, "Drone first impact"):
			return false
	_key(KEY_0)
	_release(KEY_UP)
	if not await _quiet("leaving Drone during contact"):
		return false
	if not await _until(func(): return app.state.manual == null, "manual release confirmed"):
		return false

	if not await _send("move 1 R2"):
		return false
	if not await _until(func(): return _phase() == "waiting", "route waits at D1"):
		return false
	var order: String = app.state.active.command_id
	var stopped := _point()
	if not await _send("status 1") or not await _send("queue show 1"):
		return false
	if not await _until(func(): return _has_record("QUEUE:", "godot"), "real queue report"):
		return false
	if not _expect(_point() == stopped and _phase() == "waiting" and app.state.active.command_id == order,
					"inspection did not replace or move queued work"):
		return false
	var mechanism_before := _mechanism_mj()
	if not await _send("open D1"):
		return false
	if not await _until(func(): return app.state.door_activity is Dictionary, "live opening evidence"):
		return false
	var opening_id: String = app.state.door_activity.command_id
	if not _expect(app.state.door_activity.phase == "opening" and opening_id != order,
					"opening has a separate confirmed identity"):
		return false
	if not await _until(func(): return _phase() == "running" and app.view.motor_active, "route resumes"):
		return false
	if not await _quiet("Schematic during active route"):
		return false
	if not _expect(_phase() == "running" and app.view.motor_active, "route still moves while Schematic is silent"):
		return false
	var impacts: int = app.monitor.impacts
	if measure_audio:
		probe.reset()
	_key(KEY_1)
	if not await _until(func(): return app.monitor.enabled and app.monitor.players[1].playing,
						"return to current motor activity"):
		return false
	await create_timer(0.13).timeout
	if measure_audio:
		if not _mix(&"M0Motor", true, "return current motor") or not _mix(&"M0Collision", false, "return no stale impact"):
			return false
	if not _expect(app.monitor.impacts == impacts, "old collision did not replay"):
		return false
	if not await _until(func(): return _phase() == "" and app.state.world.drone.room_id == "R2", "confirmed R2"):
		return false
	if not _expect(_has_record("OPENED:", "godot", opening_id) and
			_has_record("ARRIVED:", "godot", order) and _mechanism_mj() - mechanism_before == 1000000,
			"door and path completion agree with mechanism accounting"):
		return false

	if not await _send("navigate 1 R1"):
		return false
	if not await _until(func(): return app.monitor.players[1].playing, "fresh return motor"):
		return false
	_key(KEY_F3)
	if not await _until(func(): return bool(app.state.paused), "authoritative pause"):
		return false
	var paused_stamp: int = int(app.state.stamp_ms)
	var charge := _charge()
	if not await _quiet("confirmed pause"):
		return false
	if not _expect(int(app.state.stamp_ms) == paused_stamp and _charge() == charge,
					"pause froze authoritative clock and charge"):
		return false
	_key(KEY_F3)
	if not await _until(func(): return not app.state.paused and app.monitor.players[1].playing,
						"resumed audio on actual movement"):
		return false
	if measure_audio:
		probe.reset()
		await create_timer(0.10).timeout
		if not _mix(&"Master", true, "before disconnect"):
			return false
	var before_loss := _point()
	var loss_stamp: int = int(app.state.stamp_ms)
	app.client.peer.disconnect_from_host()
	if not await _until(func(): return app.client.failed, "socket disconnect observed"):
		return false
	if not await _quiet("backend disconnected"):
		return false
	return _expect(_point() == before_loss and app.view.semantic_point().is_equal_approx(before_loss)
				and int(app.state.stamp_ms) == loss_stamp and not command.editable,
				"disconnect preserved confirmed state without player command or fabricated progress")


func _interruption() -> bool:
	if not await _send("move 1 R2"):
		return false
	if not await _until(func(): return _phase() == "waiting", "first order waits"):
		return false
	var old: String = app.state.active.command_id
	if not await _send("stop 1"):
		return false
	if not await _until(func(): return _phase() == "" and _has_record("STOPPED:", "godot"), "stop clears wait"):
		return false
	if not await _send("open D1"):
		return false
	if not await _until(func(): return app.state.world.door.position == "open", "door actually opened"):
		return false
	if not _expect(_phase() == "" and _point().x < 4.1 and not _has_record("ARRIVED:", "godot", old),
					"opening did not revive a stopped wait"):
		return false
	_key(KEY_F3)
	if not await _until(func(): return bool(app.state.paused), "pause first"):
		return false
	var time: int = int(app.state.stamp_ms)
	var energy := _charge()
	var draw := _mechanism_mj()
	var before := _point()
	if not await _send("navigate 1 R2"):
		return false
	if not await _until(func(): return _phase() == "queued", "paused request queues"):
		return false
	var queued: String = app.state.active.command_id
	await create_timer(0.25).timeout
	_key(KEY_1)
	_key(KEY_0)
	if not _expect(_has_record("QUEUED", "godot", queued) and _phase() == "queued"
				and int(app.state.stamp_ms) == time and _charge() == energy and _point() == before
				and _mechanism_mj() == draw,
				"queued motion, energy and time agree across paused views"):
		return false
	_key(KEY_F3)
	if not await _until(func(): return _phase() == "running" and _point().x > before.x + 0.35,
						"previously queued order resumes"):
		return false
	if not _expect(int(app.state.stamp_ms) > time and _charge() < energy and _mechanism_mj() == draw,
					"drone consumes charge and independent mechanism ceased draw"):
		return false
	_key(KEY_1)
	_press(KEY_RIGHT)
	if not await _until(func(): return app.state.manual != null and app.state.active == null,
						"accepted takeover replaced resumed navigation"):
		return false
	_release(KEY_RIGHT)
	if not await _until(func(): return app.state.manual == null, "release direct control"):
		return false
	await create_timer(0.25).timeout
	return _expect(not _has_record("ARRIVED:", "godot", queued) and _phase() == "",
					"superseded navigation did not complete")


func _quiet(label: String) -> bool:
	await create_timer(SETTLE_S).timeout
	if not _expect(not app.monitor.enabled and not app.monitor.players[3].playing, label + " gate"):
		return false
	if measure_audio:
		probe.reset()
		await create_timer(0.13).timeout
		return _mix(&"Master", false, label)
	return true


func _mix(bus: StringName, positive: bool, label: String) -> bool:
	var result := probe.measure(bus)
	print("M0_MIX: %s bus=%s frames=%d peak=%.6f" % [label, bus, int(result.x), result.y])
	return _expect(result.x >= 256 and (result.y > POSITIVE if positive else result.y < SILENCE),
					label + " actual downstream mix")


func _feedback(_state: Dictionary, batch: Array) -> void:
	for row: Dictionary in batch:
		records.append(row)


func _has_record(prefix: String, origin: String, id := "") -> bool:
	for row in records:
		if str(row.text).begins_with(prefix) and row.origin == origin and (id.is_empty() or row.command_id == id):
			return true
	return false


func _phase() -> String:
	return "" if app.state.active == null else str(app.state.active.phase)


func _mechanism_mj() -> int:
	return int(app.state.door_energy_mj.mechanism)


func _charge() -> float:
	return float(app.state.world.drone.charge_wh)


func _point() -> Vector2:
	var p: Dictionary = app.state.world.drone.location
	return Vector2(p.x_m, p.y_m)


func _send(text: String) -> bool:
	if not await _until(func(): return app.client.idle(), "idle"):
		return false
	command.text_submitted.emit(text)
	return true


func _key(code: Key) -> void:
	_press(code)
	_release(code)


func _press(code: Key) -> void:
	_event(code, true)


func _release(code: Key) -> void:
	_event(code, false)


func _event(code: Key, down: bool) -> void:
	var key := InputEventKey.new()
	key.keycode = code
	key.physical_keycode = code
	key.pressed = down
	Input.parse_input_event(key)
	Input.flush_buffered_events()


func _until(condition: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 5500
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _expect(bool(condition.call()), label)


func _expect(condition: bool, label: String) -> bool:
	if not condition:
		push_error("M0 conformance: " + label)
		quit(1)
	return condition
