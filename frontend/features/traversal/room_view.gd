extends Node2D
## Draw the snapshot geometry and move the drone using actual Godot colliders.

const SCALE_METRE := 42.0
const STEP_SPEED := 5.0 * SCALE_METRE
const DRONE_RADIUS := 9.0
const WALL := 3.0
var rooms: Dictionary = {}
var door: Dictionary = {}
var drone: CharacterBody2D
var leaves: Array[StaticBody2D] = []
var fraction := -1.0
var last_confirmed := Vector2.ZERO
var drone_name := ""


func apply(state: Dictionary) -> void:
	var world: Dictionary = state.world
	if rooms.is_empty():
		door = world.door
		for room: Dictionary in world.rooms:
			var lower := _point(room.min_corner)
			var upper := _point(room.max_corner)
			rooms[room.id] = Rect2(lower, upper - lower)
		for room: Rect2 in rooms.values():
			_build_room(room)
		leaves.append(_segment(gap_start(), gap_end()))
		leaves.append(_segment(gap_start(), gap_end()))
		drone = CharacterBody2D.new()
		var col := CollisionShape2D.new()
		var circle := CircleShape2D.new()
		circle.radius = DRONE_RADIUS
		col.shape = circle
		drone.add_child(col)
		add_child(drone)
		drone.position = _point(world.drone.location)
		drone_name = str(world.drone.display_name)
	last_confirmed = _point(world.drone.location)
	if absf(fraction - float(state.opening_fraction)) > 0.00001:
		fraction = float(state.opening_fraction)
		var ends := leaf_ends()
		_set_segment(leaves[0], ends[0], ends[1])
		_set_segment(leaves[1], ends[2], ends[3])
	queue_redraw()


func reset_to_confirmed() -> void:
	if is_instance_valid(drone):
		drone.position = last_confirmed
		queue_redraw()


func navigate(target: Vector2, delta: float) -> bool:
	var remaining := target - drone.position
	if remaining.length() < 0.01:
		return true
	if drone.move_and_collide(remaining.limit_length(STEP_SPEED * delta)) != null:
		return false
	queue_redraw()
	return drone.position.distance_to(target) < 0.01


func _point(value: Dictionary) -> Vector2:
	return Vector2(float(value.x_m), float(value.y_m)) * SCALE_METRE


func gap_start() -> Vector2:
	return _point(door.gap_start)


func gap_end() -> Vector2:
	return _point(door.gap_end)


func room_center(id: String) -> Vector2:
	var room: Rect2 = rooms[id]
	return room.get_center()


func semantic_point() -> Vector2:
	return drone.position / SCALE_METRE


func leaf_ends() -> Array[Vector2]:
	var a := gap_start()
	var b := gap_end()
	var ratio := (1.0 - clampf(fraction, 0.0, 1.0)) / 2.0
	return [a, a.lerp(b, ratio), b.lerp(a, ratio), b]


func _build_room(room: Rect2) -> void:
	var a := room.position
	var b := Vector2(room.end.x, a.y)
	var c := room.end
	var d := Vector2(a.x, c.y)
	_wall_edge(a, b)
	_wall_edge(b, c)
	_wall_edge(d, c)
	_wall_edge(a, d)


func _wall_edge(a: Vector2, b: Vector2) -> void:
	var lo := gap_start()
	var hi := gap_end()
	var same_axis := (
		(a.x == b.x and a.x == lo.x and lo.x == hi.x
		 and a.y <= lo.y and hi.y <= b.y)
		or (a.y == b.y and a.y == lo.y and lo.y == hi.y
		 and a.x <= lo.x and hi.x <= b.x)
	)
	if same_axis:
		if a != lo:
			_segment(a, lo)
		if hi != b:
			_segment(hi, b)
	else:
		_segment(a, b)


func _segment(a: Vector2, b: Vector2) -> StaticBody2D:
	var segment := StaticBody2D.new()
	var col := CollisionShape2D.new()
	col.shape = RectangleShape2D.new()
	segment.add_child(col)
	add_child(segment)
	_set_segment(segment, a, b)
	return segment


func _set_segment(segment: StaticBody2D, a: Vector2, b: Vector2) -> void:
	var col := segment.get_child(0) as CollisionShape2D
	var shape := col.shape as RectangleShape2D
	var length := a.distance_to(b)
	col.set_deferred("disabled", length < 0.01)
	segment.position = (a + b) / 2.0
	shape.size = Vector2(WALL, maxf(length, 0.01)) if a.x == b.x else Vector2(maxf(length, 0.01), WALL)


func _draw() -> void:
	var font := ThemeDB.fallback_font
	for room_id: String in rooms:
		var room: Rect2 = rooms[room_id]
		draw_rect(room, Color("#17303e"))
		draw_rect(room, Color("#748e9c"), false, WALL)
		draw_string(font, room.position + Vector2(12, 24), room_id, HORIZONTAL_ALIGNMENT_LEFT)
	if not door.is_empty():
		var ends := leaf_ends()
		draw_line(gap_start(), gap_end(), Color("#17303e"), WALL * 2.0)
		var color := Color("#f2b66a") if fraction < 1.0 else Color("#8cceb0")
		draw_line(ends[0], ends[1], color, WALL * 2.0)
		draw_line(ends[2], ends[3], color, WALL * 2.0)
		draw_string(font, (gap_start() + gap_end()) / 2 + Vector2(10, -12), str(door.id),
					HORIZONTAL_ALIGNMENT_LEFT, -1, 16, color)
	if is_instance_valid(drone):
		draw_circle(drone.position, DRONE_RADIUS, Color("#87d7ff"))
		draw_string(font, drone.position + Vector2(14, 5), drone_name,
					HORIZONTAL_ALIGNMENT_LEFT)
