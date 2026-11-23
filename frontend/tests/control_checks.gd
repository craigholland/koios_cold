extends SceneTree
## Run against the real Python launcher. Keys are deliberately injected; native focus is separate.

const Scene = preload("res://app/sandbox.tscn")
var app: Node
var command: LineEdit
var native := false
var focus_helper := -1


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	native = "--native-focus" in OS.get_cmdline_user_args()
	app = Scene.instantiate()
	root.add_child(app)
	command = app.get_node("HUD/Command")
	if not await _until(func(): return app.client.live, "connect"):
		return
	_key(KEY_1)
	if not _expect(app.local_view, "slot opens Drone view"):
		return
	await _idle()
	command.text_submitted.emit("move 1 R2")
	if not await _until(func(): return app.state.get("active") is Dictionary and app.state.active.phase == "waiting",
						"autonomous order waits at D1"):
		return
	var order: String = app.state.active.command_id
	command.grab_focus()
	command.text = "unsent draft"
	command.caret_column = command.text.length()
	_key(KEY_0)
	if not _expect(app.local_view and command.text == "unsent draft0", "digit types instead of switching while focused"):
		return
	# A normal text edit is allowed; preserve its actual post-input value.
	command.text = "open d"
	command.caret_column = command.text.length()
	_key(KEY_TAB)
	if not _expect(command.text == "open D1", "completion uses registered spelling"):
		return
	command.text = "unsent draft"
	_key(KEY_UP)
	if not _expect(command.text == "move 1 R2", "command history while focused"):
		return
	_key(KEY_DOWN)
	if not _expect(command.text == "unsent draft", "history returns unsent draft"):
		return
	_key(KEY_ESCAPE)
	_key(KEY_0)
	if not _expect(not app.local_view, "zero opens Schematic outside text"):
		return
	_key(KEY_1)
	if not _expect(command.text == "unsent draft" and app.state.active.command_id == order,
						"draft and autonomous order survive view and Escape"):
		return

	_press(KEY_UP)
	if not await _until(func(): return app.state.manual != null and _point().x > 4.25, "live manual takeover"):
		return
	if not _expect(app.state.active == null, "manual takeover cancelled old route in Python"):
		return
	command.grab_focus()
	if not await _until(func(): return app.state.manual == null, "held Up releases on text focus"):
		return
	var stopped := _point()
	_press(KEY_UP, true)
	_key(KEY_ESCAPE)
	_press(KEY_UP, true)
	await create_timer(0.20).timeout
	if not _expect(_point().is_equal_approx(stopped) and app.state.manual == null,
						"held echo cannot restart after Escape"):
		return
	_release(KEY_UP)
	_press(KEY_UP)
	if not await _until(func(): return _point().x > stopped.x + 0.20, "fresh Up restarts"):
		return
	_release(KEY_UP)
	if not await _until(func(): return app.state.manual == null, "key release stops"):
		return

	var before_turn := _point()
	_press(KEY_RIGHT)
	if not await _until(func(): return _heading() > 24.0, "right turns in place"):
		return
	_release(KEY_RIGHT)
	if not await _until(func(): return app.state.manual == null, "turn released"):
		return
	if not _expect(_point().is_equal_approx(before_turn), "rotation did not translate"):
		return
	var direction := Vector2.from_angle(deg_to_rad(_heading()))
	_press(KEY_UP)
	if not await _until(func(): return (_point() - before_turn).dot(direction) > 0.22, "heading-relative forward"):
		return
	_release(KEY_UP)
	if not await _until(func(): return app.state.manual == null, "forward released"):
		return
	var before_reverse := _point()
	_press(KEY_DOWN)
	if not await _until(func(): return (_point() - before_reverse).dot(direction) < -0.22, "heading-relative reverse"):
		return
	_release(KEY_DOWN)
	if not await _until(func(): return app.state.manual == null, "reverse released"):
		return

	var pose := _point()
	var heading := _heading()
	_key(KEY_0)
	var door: String = app.state.world.door.position
	_key(KEY_1)
	if not _expect(_point() == pose and _heading() == heading and app.state.world.door.position == door,
						"both views share confirmed pose and door state"):
		return
	command.grab_focus()
	_key(KEY_F3)
	if not await _until(func(): return app.state.paused, "F3 pauses from text focus"):
		return
	_key(KEY_ESCAPE)
	_press(KEY_UP)
	var stamp: int = int(app.state.stamp_ms)
	await create_timer(0.20).timeout
	if not _expect(_point() == pose and app.state.manual == null and int(app.state.stamp_ms) == stamp,
						"paused steering and ship time frozen"):
		return
	_release(KEY_UP)
	_key(KEY_F3)
	if not await _until(func(): return not app.state.paused, "resume"):
		return

	_press(KEY_UP)
	if not await _until(func(): return app.state.manual != null, "begin motion before focus loss"):
		return
	if native:
		focus_helper = OS.create_process(OS.get_executable_path(),
			["--path", ProjectSettings.globalize_path("res://"), "--script", "res://tests/focus_helper.gd"])
		if not _expect(focus_helper > 0, "start independent native focus window"):
			return
	else:
		app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	if not await _until(func(): return not app.window_active and app.state.manual == null,
						"focus loss releases motion"):
		return
	var stopped_after_loss := _point()
	if native:
		if not await _until(func(): return not OS.is_process_running(focus_helper), "focus window closes"):
			return
		root.grab_focus()
	else:
		app.notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)
	if not await _until(func(): return app.window_active, "focus return"):
		return
	_press(KEY_UP, true)
	await create_timer(0.20).timeout
	if not _expect(app.state.manual == null and _point().is_equal_approx(stopped_after_loss),
						"held echo cannot restart after focus return"):
		return
	_release(KEY_UP)
	_press(KEY_UP)
	if not await _until(func(): return app.state.manual != null, "fresh press after focus return"):
		return
	_release(KEY_UP)
	if not _expect(not app.controls.remap({"forward": "Left"}), "remap conflict rejected"):
		return
	if not _expect(not app.controls.remap({"pause": "W"}), "global pause cannot steal ordinary typing"):
		return
	if not _expect(app.controls.remap({"forward": "W"}), "nonconflicting remap accepted"):
		return

	if not await _until(func(): return app.state.manual == null, "final release confirmed"):
		return
	app.client.close()
	print("M0_CONTROL_CHECKS_OK: live state, focused text/draft, pause, fresh input and " +
		("native Windows focus" if native else "simulated window focus"))
	quit()


func _idle() -> void:
	await _until(func(): return app.client.idle(), "bridge idle")


func _point() -> Vector2:
	var p: Dictionary = app.state.world.drone.location
	return Vector2(p.x_m, p.y_m)


func _heading() -> float:
	return float(app.state.world.drone.heading_degrees)


func _key(code: Key) -> void:
	_press(code)
	_release(code)


func _press(code: Key, echo := false) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = true
	if code >= KEY_0 and code <= KEY_9:
		event.unicode = code
	event.echo = echo
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _release(code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _until(condition: Callable, note: String) -> bool:
	var deadline := Time.get_ticks_msec() + 3600
	while not condition.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _expect(bool(condition.call()), note)


func _expect(condition: bool, note: String) -> bool:
	if not condition:
		if focus_helper > 0 and OS.is_process_running(focus_helper):
			OS.kill(focus_helper)
		push_error("M0 control check failed: " + note)
		quit(1)
	return condition
