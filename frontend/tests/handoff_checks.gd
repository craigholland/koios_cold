extends SceneTree
## Exercise actual Godot motion and authoritative bridge acceptance.

const Sandbox = preload("res://app/sandbox.tscn")
var app: Node
var command: LineEdit


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	app = Sandbox.instantiate()
	root.add_child(app)
	command = app.get_node("HUD/Command")
	if not await _until(func(): return app.client.live, "connect"):
		return
	_key(KEY_1)
	if "--sensing" in OS.get_cmdline_user_args():
		if not await _sensing():
			return
		print("M0_SENSING_OK: cone and observation eligibility follow both route legs")
	elif "--partial" in OS.get_cmdline_user_args():
		if not await _partial_crossing():
			return
	else:
		if not await _takeover():
			return
	app.client.close()
	if "--sensing" not in OS.get_cmdline_user_args():
		print("M0_HANDOFF_OK: " + ("passable partial opening" if "--partial" in OS.get_cmdline_user_args() else "in-flight pose retained"))
	quit()


func _sensing() -> bool:
	if not await _send("open D1"):
		return false
	if not await _until(func(): return app.state.world.door.position == "open", "open D1 for round trip"):
		return false
	if not await _send("move 1 R2"):
		return false
	if not await _until(func(): return app.view.semantic_point().x > 5.3, "forward physical movement"):
		return false
	if not _expect(_sensor_origin().distance_to(app.view.semantic_point()) < 0.65,
					"forward sensing follows the body before arrival"):
		return false
	if not await _until(func(): return app.state.world.drone.room_id == "R2" and app.state.active == null,
						"R2 arrival confirmed"):
		return false
	if not _expect(not app.state.sensor.visible_markers.is_empty(), "R2 marker visible from arrival pose"):
		return false
	if not await _send("move 1 R1"):
		return false
	if not await _until(func(): return app.view.semantic_point().x < 7.55, "return physical movement"):
		return false
	if not _expect(_sensor_origin().distance_to(app.view.semantic_point()) < 0.65
			and app.state.sensor.visible_markers.is_empty(), "return cone and marker eligibility track motion"):
		return false
	return await _until(func(): return app.state.world.drone.room_id == "R1" and app.state.active == null,
						"R1 return arrival confirmed")


func _sensor_origin() -> Vector2:
	var origin: Dictionary = app.state.sensor.polygon[0]
	return Vector2(origin.x_m, origin.y_m)


func _partial_crossing() -> bool:
	_press(KEY_UP)
	if not await _until(func(): return _confirmed().x > 7.45, "approach closed D1"):
		return false
	_release(KEY_UP)
	if not await _until(func(): return app.state.manual == null, "stop at closed door"):
		return false
	if not await _send("open D1"):
		return false
	if not await _until(func(): return float(app.state.opening_fraction) >= 0.32, "partial aperture"):
		return false
	_press(KEY_UP)
	if not await _until(func(): return app.state.world.drone.room_id == "R2" or _unconfirmed_note(), "partial crossing must reconcile"):
		return false
	var success: bool = (app.state.world.drone.room_id == "R2" and app.state.world.door.position == "closed"
		and float(app.state.opening_fraction) < 1.0 and not _unconfirmed_note())
	if not _expect(success, "Godot's physically passable partial opening must be accepted by Python"):
		return false
	_release(KEY_UP)
	return await _until(func(): return app.state.manual == null, "release in R2")


func _takeover() -> bool:
	if not await _send("open D1"):
		return false
	if not await _until(func(): return app.state.world.door.position == "open", "open D1"):
		return false
	if not await _send("move 1 R2"):
		return false
	if not await _until(func(): return app.view.semantic_point().x > 5.2, "actual in-flight movement"):
		return false
	var before: Vector2 = app.view.semantic_point()
	_press(KEY_RIGHT)
	if not await _until(func(): return app.state.manual != null, "accept direct control"):
		return false
	if not _expect(_confirmed().distance_to(before) < 0.25 and app.state.active == null,
					"in-flight takeover kept physical pose and cancelled the prior order"):
		return false
	_release(KEY_RIGHT)
	return await _until(func(): return app.state.manual == null, "release turn")


func _send(text: String) -> bool:
	if not await _until(func(): return app.client.idle(), "bridge idle"):
		return false
	command.text_submitted.emit(text)
	return true


func _confirmed() -> Vector2:
	var p: Dictionary = app.state.world.drone.location
	return Vector2(p.x_m, p.y_m)


func _unconfirmed_note() -> bool:
	return "Direct motion was not confirmed" in app.get_node("HUD/Output").get_parsed_text()


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
	var deadline := Time.get_ticks_msec() + 5000
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _expect(bool(condition.call()), label)


func _expect(condition: bool, label: String) -> bool:
	if not condition:
		push_error("M0 handoff regression: " + label)
		quit(1)
	return condition
