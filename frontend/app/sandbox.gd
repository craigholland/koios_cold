extends Node
## Compose a small live sandbox; Python owns accepted work and ship time.

const LocalClient = preload("res://bridge/local_client.gd")
const View = preload("res://features/traversal/room_view.gd")
const Monitor = preload("res://components/audio/drone_monitor.gd")
const Controls = preload("res://input/m0_controls.gd")
const Draft = preload("res://input/command_draft.gd")
const Delivery = preload("res://input/command_delivery.gd")
var controls := Controls.new()
var command_draft := Draft.new()
var command_delivery := Delivery.new()
var local_view := false
var window_active := true
var pause_target: Variant = null
var handoff_pending := false
const TICK_MS := 50
const MAX_TICK_MS := 250
var client := LocalClient.new()
var monitor := Monitor.new()
var ending := false
var state: Dictionary = {}
var pending_event: Dictionary = {}
var clock_buffer := 0.0
var smoke := false
var smoke_phase := 0
var smoke_deadline := 0

@onready var view := $RoomView as View
@onready var status := $HUD/Status as Label
@onready var activity := $HUD/Activity as Label
@onready var output := $HUD/Output as RichTextLabel
@onready var command := $HUD/Command as LineEdit


func _ready() -> void:
	add_child(monitor)
	get_tree().auto_accept_quit = false
	get_window().close_requested.connect(shutdown)
	smoke = "--smoke" in OS.get_cmdline_user_args()
	smoke_deadline = Time.get_ticks_msec() + 15000
	client.received.connect(_snapshot)
	client.lost.connect(_lost)
	command.text_submitted.connect(_submit)
	command.focus_entered.connect(controls.clear)
	_load_bindings()
	client.start(OS.get_environment("KOIOS_M0_PORT").to_int(), OS.get_environment("KOIOS_M0_NONCE"))


func _process(delta: float) -> void:
	if ending:
		return
	client.poll()
	if smoke and Time.get_ticks_msec() >= smoke_deadline:
		push_error("M0 smoke timed out before confirmed arrival")
		get_tree().quit(1)
		return
	if not client.live:
		return
	clock_buffer = minf(clock_buffer + delta * 1000.0, MAX_TICK_MS)
	if not client.idle():
		return
	if _scripted_smoke() or _control_requests():
		return
	if not pending_event.is_empty():
		pending_event.stamp_ms = int(state.stamp_ms)
		client.send("physical", {"event": pending_event})
		# Wait for confirmation before accepting another physical result.
		return
	if command_delivery.send_next(client):
		return
	if clock_buffer >= TICK_MS:
		var interval := int(clock_buffer)
		clock_buffer -= interval
		var tick := {"elapsed_ms": interval}
		var active: Variant = state.active
		if active is Dictionary and active.phase == "running" and active.verb == "move" and view.manual_point_is_inside():
			tick.route_pose = _route_pose(active, interval)
		client.send("tick", tick)


func _physics_process(delta: float) -> void:
	if ending:
		return
	view.begin_physics_sample()
	_move_body(delta)
	monitor.sample(_feed_enabled(), view.motor_active, view.motor_strain, view.physical_contact)
	_refresh_activity()


func _feed_enabled() -> bool:
	return (window_active and local_view and client.live and not state.is_empty()
			and not bool(state.paused) and pause_target != true and state.sensor is Dictionary)


func _refresh_activity() -> void:
	if not client.live or state.is_empty():
		activity.text = "No live command confirmation"
		return
	var items: PackedStringArray = []
	var active: Variant = state.get("active")
	if active is Dictionary:
		items.append("%s.%s %s %s" % [active.command_id, str(active.step), active.phase, active.verb])
	elif state.manual != null:
		items.append("%s direct control" % state.manual)
	var door_work: Variant = state.get("door_activity")
	if door_work is Dictionary:
		items.append("%s %s %s" % [door_work.command_id, door_work.door_id, door_work.phase])
	var waiting := command_delivery.waiting_count()
	if waiting > 0:
		items.append("Console: %d waiting to send" % waiting)
	if _feed_enabled() and view.motor_strain:
		items.append("Local drive obstructed")
	activity.text = " | ".join(items) if not items.is_empty() else "No active work"


func _move_body(delta: float) -> void:
	if not client.live or state.is_empty() or handoff_pending or not pending_event.is_empty() or bool(state.paused):
		return
	if state.manual != null:
		if _can_steer() and clock_buffer < MAX_TICK_MS - 30:
			view.steer(controls.direction(), float(state.steering.speed_m_s),
						float(state.steering.turn_deg_s), delta)
		return
	var active: Variant = state.active
	if not active is Dictionary or active.phase != "running" or active.verb != "move":
		return
	var world: Dictionary = state.world
	var destination := str(active.room_id)
	var checkpoint := str(world.drone.room_id) != destination and not bool(active.checkpoint_seen)
	var target := (view.gap_start() + view.gap_end()) / 2.0 if checkpoint else view.room_center(destination)
	if not view.navigate(target, delta) or not bool(active.waypoint_ready):
		return
	var p := view.semantic_point()
	if checkpoint:
		# Report the doorway plane exactly; the other coordinate is measured by the mover.
		var plane := view.gap_start() / View.SCALE_METRE
		if view.gap_start().x == view.gap_end().x:
			p.x = plane.x
		else:
			p.y = plane.y
	pending_event = {
		"command_id": str(active.command_id),
		"step": int(active.step),
		"drone_id": str(world.drone.permanent_id),
		"waypoint": "boundary" if checkpoint else "arrival",
		"target_id": str(world.door.id) if checkpoint else destination,
		"x_m": p.x,
		"y_m": p.y,
	}


func _snapshot(next: Dictionary, feedback: Array) -> void:
	command_delivery.acknowledged()
	var old_manual: Variant = state.get("manual")
	handoff_pending = false
	var active: Variant = next.active
	if not pending_event.is_empty():
		# A preceding tick can be in flight when the mover reaches a waypoint.
		# Clear only after the associated physical request was actually sent.
		if pending_event.has("stamp_ms"):
			pending_event.clear()
		elif not active is Dictionary or active.command_id != pending_event.command_id or int(active.step) != int(pending_event.step) or active.phase != "running":
			pending_event.clear()
	state = next
	view.apply(state)
	if old_manual != state.manual:
		view.reset_to_confirmed(float(state.world.drone.heading_degrees))
		if state.manual == null:
			controls.clear()
	if state.get("note") != null:
		output.add_text(str(state.note) + "\n")
		controls.clear()
		if old_manual != null:
			view.reset_to_confirmed(float(state.world.drone.heading_degrees))
	if bool(state.paused):
		controls.clear()
		monitor.silence()
	var world: Dictionary = state.world
	var door_status := "no current evidence"
	if not local_view and state.door_report is Dictionary:
		door_status = str(state.door_report.position) + " (controller)"
	elif local_view and state.sensor is Dictionary and bool(state.sensor.door_visible):
		door_status = str(world.door.position) + " (local)"
	status.text = "%s | %s | %s (%s) in %s | %s %s | %d ms" % [
		"Drone" if local_view else "Schematic", str(world.deck_id) + (" PAUSED" if state.paused else ""),
		world.drone.display_name, str(world.drone.slot), world.drone.room_id,
		world.door.id, door_status, int(state.stamp_ms)]
	command.editable = true
	for record: Dictionary in feedback:
		output.add_text(str(record.text) + "\n")
		if smoke:
			print(record.text)


func _submit(text: String) -> void:
	var line := text.strip_edges()
	if line.is_empty():
		return
	if not client.live:
		output.add_text("Console offline: command is still in input.\n")
		return
	if not command_delivery.capture(line):
		output.add_text("Console transmission buffer full: command is still in input.\n")
		return
	output.add_text("> " + line + "\n")
	command_draft.submitted(line)
	command.clear()


func _lost(message: String) -> void:
	for notice in command_delivery.disconnect_notices():
		output.add_text(notice + "\n")
	pending_event.clear()
	controls.clear()
	monitor.silence()
	command.editable = false
	view.reset_to_confirmed()
	status.text = "Offline | last confirmed state stays visible"
	output.add_text(message + "\n")
	if smoke:
		push_error(message)
		get_tree().quit(1)


func _can_steer() -> bool:
	return (window_active and local_view and client.live and not state.is_empty()
		and not state.paused and pause_target == null and not command.has_focus())


func _control_requests() -> bool:
	var axis := controls.direction()
	var manual: Variant = state.get("manual")
	if manual != null:
		var release := not _can_steer() or axis == Vector2.ZERO
		if (release or clock_buffer >= TICK_MS) and view.manual_point_is_inside():
			var elapsed := int(clock_buffer)
			var point := view.semantic_point()
			var world: Dictionary = state.world
			clock_buffer -= elapsed
			client.send("manual_cycle", {
				"lease_id": manual, "drone_id": world.drone.permanent_id,
				"stamp_ms": int(state.stamp_ms), "elapsed_ms": elapsed,
				"x_m": point.x, "y_m": point.y, "heading": view.heading, "release": release,
			})
			controls.armed = false
			return true
		if release and not view.manual_point_is_inside():
			# A boundary sample is not a room. Restore the last accepted pose on release.
			view.reset_to_confirmed(float(state.world.drone.heading_degrees))
		return false
	if pause_target != null:
		client.send("pause", {"paused": pause_target})
		pause_target = null
		return true
	if controls.armed and _can_steer() and axis != Vector2.ZERO and pending_event.is_empty():
		var active: Variant = state.active
		var request := {"drone_id": state.world.drone.permanent_id}
		if active is Dictionary and active.phase == "running" and active.verb == "move":
			if not view.manual_point_is_inside():
				return false
			var elapsed := int(clock_buffer)
			request.handoff = _route_pose(active, elapsed)
			clock_buffer -= elapsed
		controls.armed = false
		handoff_pending = client.send("manual_begin", request)
		return handoff_pending
	return false


func _route_pose(active: Dictionary, elapsed: int) -> Dictionary:
	var point := view.semantic_point()
	return {"command_id": active.command_id, "step": int(active.step),
		"stamp_ms": int(state.stamp_ms), "elapsed_ms": elapsed,
		"x_m": point.x, "y_m": point.y, "heading": view.heading}


func _input(event: InputEvent) -> void:
	if not is_node_ready() or not event is InputEventKey:
		return
	var key := event as InputEventKey
	var action := controls.action(key)
	if key.pressed and not key.echo and action == "pause" and client.live:
		controls.clear()
		pause_target = not bool(state.paused) if pause_target == null else not bool(pause_target)
		get_viewport().set_input_as_handled()
		return
	if command.has_focus():
		if key.pressed and not key.echo:
			match key.keycode:
				KEY_ESCAPE:
					command.release_focus()
					get_viewport().set_input_as_handled()
				KEY_TAB:
					var result := Draft.complete(command.text, command.caret_column, state.get("completion", {}))
					if not result.is_empty():
						command.text = result.value
						command.caret_column = result.caret
					get_viewport().set_input_as_handled()
				KEY_UP, KEY_DOWN:
					command.text = command_draft.browse(command.text, -1 if key.keycode == KEY_UP else 1)
					command.caret_column = command.text.length()
					get_viewport().set_input_as_handled()
		return
	if event.pressed and not event.echo and action in ["schematic", "drone"]:
		local_view = action == "drone"
		view.set_view(local_view)
		if not local_view:
			monitor.silence()
		controls.clear()
		get_viewport().set_input_as_handled()
		return
	if controls.motion(action, key, _can_steer()):
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_WM_WINDOW_FOCUS_OUT:
		window_active = false
		controls.clear()
		if is_node_ready():
			monitor.silence()
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN or what == NOTIFICATION_WM_WINDOW_FOCUS_IN:
		window_active = true
		controls.clear()


func _load_bindings() -> void:
	const PATH := "user://m0-bindings.json"
	if not FileAccess.file_exists(PATH):
		return
	var custom: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	if not custom is Dictionary or not controls.remap(custom):
		output.add_text("Invalid or conflicting bindings; defaults are unchanged.\n")


func _scripted_smoke() -> bool:
	if not smoke or state.is_empty():
		return false
	var world: Dictionary = state.world
	match smoke_phase:
		0:
			_submit("move 1 R2")
			smoke_phase = 1
			return true
		1:
			var active: Variant = state.active
			if active is Dictionary and active.phase == "waiting" and world.door.position == "closed":
				_submit("open D1")
				smoke_phase = 2
				return true
		2:
			if world.drone.room_id == "R2" and world.door.position == "open" and state.active == null:
				print("M0_SMOKE_OK: Godot mover arrived; Python confirmed R2 and left no active order.")
				shutdown()
				return true
	return false


func shutdown() -> void:
	if ending:
		return
	ending = true
	controls.clear()
	monitor.silence()
	client.close()
	# Allow the engine audio thread to release the stopped streams.
	await get_tree().create_timer(0.10).timeout
	get_tree().quit()


func _exit_tree() -> void:
	client.close()
