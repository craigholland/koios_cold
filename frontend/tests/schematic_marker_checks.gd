extends SceneTree
## Actual Windows scene and Python connection; native mode also reads the rendered map.

const Sandbox = preload("res://app/sandbox.tscn")
const View = preload("res://features/traversal/room_view.gd")
var app: Node
var command: LineEdit
var native := false
var fresh: Image
var marker_screen: Vector2i


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	native = "--inspect-render" in OS.get_cmdline_user_args()
	app = Sandbox.instantiate()
	root.add_child(app)
	command = app.get_node("HUD/Command")
	if not await _until(func(): return app.client.live, "connected"):
		return
	if not _check(_known().is_empty() and app.state.discovered_markers.is_empty(), "fresh map has no marker"):
		return
	if native:
		fresh = await _frame()
	_submit("open D1")
	if not await _until(func(): return app.state.world.door.position == "open", "opened D1"):
		return
	_submit("move 1 R2")
	if not await _until(func(): return app.state.world.drone.room_id == "R2", "entered R2"):
		return
	_submit("stop 1")
	if not await _until(func(): return app.state.active == null, "stop just inside R2"):
		return
	if not _check(_visible().is_empty() and _known().is_empty() and app.state.discovered_markers.is_empty(),
			"entry alone does not leak undiscovered marker"):
		return
	_key(KEY_1)
	_press(KEY_UP, true)
	if not await _until(func(): return not _visible().is_empty(), "confirmed manual approach finds marker"):
		return
	_press(KEY_UP, false)
	if not await _until(func(): return app.state.manual == null, "release forward"):
		return
	var fact: Dictionary = _visible()[0]
	var p: Dictionary = fact.point
	var map_position := Vector2(float(p.x_m), float(p.y_m)) * View.SCALE_METRE
	marker_screen = Vector2i(app.view.get_global_transform_with_canvas() * map_position)
	if not _check(fact.id == "M0-MARKER" and app.state.discovered_markers == [fact.id], "known identity"):
		return
	if native:
		var drone := await _frame()
		if not _check(_ink(fresh) == Vector2i.ZERO and _rendered(drone), "fresh map blank; live Drone marker and label rendered"):
			return
	_press(KEY_RIGHT, true)
	if not await _until(func(): return _visible().is_empty(), "confirmed turn looks away"):
		return
	_press(KEY_RIGHT, false)
	if not await _until(func(): return app.state.manual == null, "release turn"):
		return
	# Move away while facing away; this is not just a view-switch exercise.
	var away_from: Vector2 = app.view.semantic_point()
	_press(KEY_UP, true)
	if not await _until(func(): return app.view.semantic_point().distance_to(away_from) > 0.26, "moved away"):
		return
	_press(KEY_UP, false)
	if not await _until(func(): return app.state.manual == null, "release movement"):
		return
	for _repeat in range(2):
		if not _check(_visible().is_empty(), "local view does not render retained knowledge"):
			return
		if native:
			var away := await _frame()
			if not _check(_ink(away) == Vector2i.ZERO, "no marker or label pixels in Drone when looking away"):
				return
		_key(KEY_0)
		if native:
			var schematic := await _frame()
			if not _check(_rendered(schematic), "Schematic marker and readable label pixels at the known location"):
				return
			if _repeat == 1:
				schematic.save_png("res://.godot/schematic-marker-check.png")
		if not _check(_known() == [fact], "retained record remains at confirmed position"):
			return
		_key(KEY_1)
	print("M0_SCHEMATIC_MARKERS_OK: manual discovery, look and move away, two view round trips")
	app.shutdown()


func _frame() -> Image:
	await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


func _ink(frame: Image) -> Vector2i:
	var count := Vector2i.ZERO
	for y in range(marker_screen.y - 5, marker_screen.y + 6):
		for x in range(marker_screen.x - 5, marker_screen.x + 6):
			var c := frame.get_pixel(x, y)
			if c.r > 0.65 and c.g > 0.6 and c.r - c.b > 0.20:
				count.x += 1
	for y in range(marker_screen.y - 12, marker_screen.y + 6):
		for x in range(marker_screen.x + 8, marker_screen.x + 112):
			var c := frame.get_pixel(x, y)
			if c.r > 0.75 and c.g > 0.75 and c.b > 0.75:
				count.y += 1
	return count


func _rendered(frame: Image) -> bool:
	var pixels := _ink(frame)
	print("M0_MARKER_PIXELS: dot=%d label=%d" % [pixels.x, pixels.y])
	return pixels.x >= 25 and pixels.y >= 35


func _known() -> Array:
	return app.state.get("known_markers", [])


func _visible() -> Array:
	return app.state.sensor.visible_markers if app.state.sensor is Dictionary else []


func _submit(line: String) -> void:
	command.text_submitted.emit(line)


func _key(code: Key) -> void:
	_press(code, true)
	_press(code, false)


func _press(code: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = pressed
	Input.parse_input_event(event)
	Input.flush_buffered_events()


func _until(predicate: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 6500
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(predicate.call(), label)


func _check(ok: bool, label: String) -> bool:
	if not ok:
		push_error("M0 Schematic marker: " + label)
		quit(1)
	return ok
