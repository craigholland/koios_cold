extends SceneTree
## Real live scene, no pose overrides. Check the first accepted waypoint snapshots.

const View = preload("res://features/traversal/room_view.gd")
const Sandbox = preload("res://app/sandbox.tscn")
var app: Node
var command: LineEdit
var crossings: Array[String] = []
var crossing_ids: Array[String] = []
var arrivals: Array[String] = []
var errors: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	app = Sandbox.instantiate()
	root.add_child(app)
	command = app.get_node("HUD/Command")
	app.client.received.connect(_snapshot)
	if not await _until(func(): return app.client.live, "connect"):
		return
	_submit("open D1")
	if not await _until(func(): return app.state.world.door.position == "open", "D1 open"):
		return
	_submit("move 1 R2")
	if not await _until(func(): return "R2" in arrivals, "reach R2"):
		return

	_key(KEY_1)
	_press(KEY_LEFT, true)
	if not await _until(func(): return _angle(app.view.heading, 322.0) < 3.0, "manual upper-right turn"):
		return
	_press(KEY_LEFT, false)
	if not await _until(func(): return app.state.manual == null, "manual turn confirmed"):
		return
	var initial_heading: float = app.view.heading
	var start: Vector2 = app.view.semantic_point()

	_press(KEY_DOWN, true)
	if not await _until(func(): return app.view.semantic_point().x < start.x - 0.13, "manual reverse"):
		return
	_press(KEY_DOWN, false)
	if not await _until(func(): return app.state.manual == null, "manual reverse released"):
		return
	if not _expect(_angle(app.view.heading, initial_heading) < 0.1, "manual reverse does not rotate"):
		return
	start = app.view.semantic_point()

	_key(KEY_0)
	_submit("move 1 r1")
	if not await _until(func(): return _angle(app.view.heading, initial_heading) > 15.0 or app.view.semantic_point().distance_to(start) > 0.08, "autonomous starts turning"):
		return
	if not _expect(app.view.semantic_point().distance_to(start) < 0.02
			and _angle(app.view.heading, initial_heading) > 15.0, "turn in place before translating"):
		return
	var turning_confirmed := func() -> bool:
		var confirmed := float(app.state.world.drone.heading_degrees)
		return _angle(confirmed, initial_heading) > 10.0 and _angle(_sensor_heading(app.state), confirmed) < 0.1
	if not await _until(turning_confirmed, "Python confirms forward sensing during the turn"):
		return
	_key(KEY_F3)
	if not await _until(func(): return app.state.paused, "confirmation of pause in turn"):
		return
	var paused_heading: float = app.view.heading
	var paused_point: Vector2 = app.view.semantic_point()
	await create_timer(0.18).timeout
	if not _expect(_angle(app.view.heading, paused_heading) < 0.1
			and app.view.semantic_point().distance_to(paused_point) < 0.01, "pause freezes rotation and translation"):
		return
	_key(KEY_F3)
	if not await _until(func(): return not app.state.paused and app.view.semantic_point().x < start.x - 0.18,
			"resume and actually travel left"):
		return
	var gap: Vector2 = (app.view.gap_start() + app.view.gap_end()) / (2.0 * View.SCALE_METRE)
	if not _expect(_angle(app.view.heading, rad_to_deg((gap - app.view.semantic_point()).angle())) < 1.0
			and _angle(app.view.heading, float(app.state.world.drone.heading_degrees)) < 2.0,
			"body faces its actual leftward leg and Python agrees"):
		return
	_key(KEY_1)
	if not await _until(func(): return "R1" in arrivals, "first confirmed return"):
		return
	_key(KEY_0)
	_submit("navigate 1 R2")
	if not await _until(func(): return arrivals.count("R2") == 2, "alias traverses reverse trip"):
		return
	_submit("move 1 R1")
	if not await _until(func(): return _angle(app.view.heading, 0.0) > 15.0, "next leftward turn starts"):
		return
	_submit("stop 1")
	if not await _until(func(): return app.state.active == null, "stop accepted during turn"):
		return
	var stopped_heading: float = app.view.heading
	var stopped_point: Vector2 = app.view.semantic_point()
	await create_timer(0.20).timeout
	if not _expect(_angle(app.view.heading, stopped_heading) < 0.1
			and app.view.semantic_point().distance_to(stopped_point) < 0.01, "stop does not revive work"):
		return
	if not _expect(crossings == ["R2", "R1", "R2"] and arrivals == ["R2", "R1", "R2"]
			and errors.is_empty(), "each crossing and first arrival agrees: " + str(errors)):
		return
	print("M0_AUTONOMOUS_HEADING_OK: manual reverse, pause/stop, both bearings, first arrivals and sensor cone")
	app.shutdown()


func _snapshot(state: Dictionary, feedback: Array) -> void:
	var active: Variant = state.active
	if active is Dictionary and active.get("checkpoint_seen") and not crossing_ids.has(str(active.command_id)):
		var destination := str(active.room_id)
		crossing_ids.append(str(active.command_id))
		crossings.append(destination)
		if _angle(float(state.world.drone.heading_degrees), app.view.heading) > 1.0:
			errors.append("first boundary heading disagrees at " + destination)
	for row: Dictionary in feedback:
		if not str(row.text).begins_with("ARRIVED:"):
			continue
		var drone: Dictionary = state.world.drone
		var destination := str(drone.room_id)
		arrivals.append(destination)
		var point := _point(drone.location)
		var heading := float(drone.heading_degrees)
		var expected := 180.0 if destination == "R1" else 0.0
		var points: Array = state.sensor.polygon
		if (point.distance_to(app.view.semantic_point()) > 0.01 or _angle(heading, app.view.heading) > 0.1
				or _angle(heading, expected) > 1.0 or _point(points[0]).distance_to(point) > 0.001
				or _angle(_sensor_heading(state), heading) > 0.1):
			errors.append("first arrival pose or cone mismatch at " + destination)


func _sensor_heading(state: Dictionary) -> float:
	var points: Array = state.sensor.polygon
	var middle := int(float(points.size()) / 2.0)
	return rad_to_deg((_point(points[middle]) - _point(points[0])).angle())


func _point(raw: Dictionary) -> Vector2:
	return Vector2(raw.x_m, raw.y_m)


func _angle(a: float, b: float) -> float:
	return absf(wrapf(a - b, -180.0, 180.0))


func _submit(line: String) -> void:
	command.text_submitted.emit(line)


func _key(code: Key) -> void:
	_press(code, true)
	_press(code, false)


func _press(code: Key, down: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = down
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _until(predicate: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 6500
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _expect(predicate.call(), label)


func _expect(ok: bool, label: String) -> bool:
	if not ok:
		push_error("M0 autonomous heading: " + label)
		quit(1)
	return ok
