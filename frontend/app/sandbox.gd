extends Node
## Compose a small live sandbox; Python owns accepted work and ship time.

const LocalClient = preload("res://bridge/local_client.gd")
const View = preload("res://features/traversal/room_view.gd")
const TICK_MS := 50
const MAX_TICK_MS := 250
var client := LocalClient.new()
var state: Dictionary = {}
var pending_event: Dictionary = {}
var clock_buffer := 0.0
var smoke := false
var smoke_phase := 0
var smoke_deadline := 0

@onready var view := $RoomView as View
@onready var status := $HUD/Status as Label
@onready var output := $HUD/Output as RichTextLabel
@onready var command := $HUD/Command as LineEdit


func _ready() -> void:
	smoke = "--smoke" in OS.get_cmdline_user_args()
	smoke_deadline = Time.get_ticks_msec() + 15000
	client.received.connect(_snapshot)
	client.lost.connect(_lost)
	command.text_submitted.connect(_submit)
	client.start(OS.get_environment("KOIOS_M0_PORT").to_int(), OS.get_environment("KOIOS_M0_NONCE"))


func _process(delta: float) -> void:
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
	if _scripted_smoke():
		return
	if not pending_event.is_empty():
		pending_event.stamp_ms = int(state.stamp_ms)
		client.send("physical", {"event": pending_event})
		# Wait for confirmation before accepting another physical result.
		return
	if clock_buffer >= TICK_MS:
		var interval := int(clock_buffer)
		clock_buffer -= interval
		client.send("tick", {"elapsed_ms": interval})


func _physics_process(delta: float) -> void:
	if not client.live or state.is_empty() or not pending_event.is_empty() or bool(state.paused):
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
	var world: Dictionary = state.world
	status.text = "Connected | %s | confirmed room %s | %s %s | ship %d ms" % [
		world.deck_id, world.drone.room_id, world.door.id, world.door.position, int(state.stamp_ms)]
	command.editable = true
	for record: Dictionary in feedback:
		output.add_text(str(record.text) + "\n")
		if smoke:
			print(record.text)


func _submit(text: String) -> void:
	var line := text.strip_edges()
	if line.is_empty():
		return
	if not pending_event.is_empty() or not client.send("command", {"text": line}):
		output.add_text("Not sent: wait for the current acknowledgement and press Enter again.\n")
		return
	command.clear()


func _lost(message: String) -> void:
	pending_event.clear()
	command.editable = false
	view.reset_to_confirmed()
	status.text = "Offline | last confirmed state stays visible"
	output.add_text(message + "\n")
	if smoke:
		push_error(message)
		get_tree().quit(1)


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
				client.close()
				get_tree().quit()
				return true
	return false


func _exit_tree() -> void:
	client.close()
