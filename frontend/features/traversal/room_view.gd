extends Node2D
## Draw the snapshot geometry and move the drone using actual Godot colliders.

const SCALE_METRE := 42.0
const STEP_SPEED := 5.0 * SCALE_METRE
const WALL := 3.0
var rooms: Dictionary = {}
var door: Dictionary = {}
var drone: CharacterBody2D
var leaves: Array[StaticBody2D] = []
var fraction := -1.0
var last_confirmed := Vector2.ZERO
var drone_name := ""
var body_radius := 0.0
var motor_active := false
var motor_strain := false
var physical_contact := false
var heading := 0.0
var drone_view := false
var sensor: Variant = null
var report: Variant = null


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
		body_radius = float(state.steering.body_radius_m) * SCALE_METRE
		circle.radius = body_radius
		col.shape = circle
		drone.add_child(col)
		add_child(drone)
		drone.position = _point(world.drone.location)
		drone_name = str(world.drone.display_name)
		heading = float(world.drone.heading_degrees)
	last_confirmed = _point(world.drone.location)
	sensor = state.get("sensor")
	report = state.get("door_report")
	if absf(fraction - float(state.opening_fraction)) > 0.00001:
		fraction = float(state.opening_fraction)
		var ends := leaf_ends()
		_set_segment(leaves[0], ends[0], ends[1])
		_set_segment(leaves[1], ends[2], ends[3])
	queue_redraw()


func reset_to_confirmed(confirmed_heading := -1.0) -> void:
	if is_instance_valid(drone):
		drone.position = last_confirmed
		if confirmed_heading >= 0.0:
			heading = confirmed_heading
		queue_redraw()


func begin_physics_sample() -> void:
	motor_active = false
	motor_strain = false
	physical_contact = false


func _move(displacement: Vector2) -> bool:
	var before := drone.position
	var hit := drone.move_and_collide(displacement)
	motor_active = drone.position.distance_squared_to(before) > 0.0001
	physical_contact = hit != null
	motor_strain = physical_contact and displacement.length_squared() > 0.0001
	queue_redraw()
	return not physical_contact


func navigate(target: Vector2, delta: float) -> bool:
	var remaining := target - drone.position
	if remaining.length() < 0.01:
		return true
	if not _move(remaining.limit_length(STEP_SPEED * delta)):
		return false
	queue_redraw()
	return drone.position.distance_to(target) < 0.01


func set_view(local: bool) -> void:
	drone_view = local
	queue_redraw()


func steer(axis: Vector2, speed: float, turn: float, delta: float) -> void:
	if not is_instance_valid(drone):
		return
	if axis.y:
		var change := axis.y * turn * delta
		heading = fposmod(heading + change, 360.0)
		motor_active = absf(change) > 0.0001
	elif axis.x:
		var forward := Vector2.from_angle(deg_to_rad(heading))
		_move(forward * axis.x * speed * SCALE_METRE * delta)
	queue_redraw()


func manual_point_is_inside() -> bool:
	for room: Rect2 in rooms.values():
		var p := drone.position
		if p.x > room.position.x + 0.01 and p.x < room.end.x - 0.01 and p.y > room.position.y + 0.01 and p.y < room.end.y - 0.01:
			return true
	return false


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
	if drone_view and sensor is Dictionary:
		var polygon := PackedVector2Array()
		for p: Dictionary in sensor.polygon:
			polygon.append(_point(p))
		draw_colored_polygon(polygon, Color("#22433f"))
	for room_id: String in rooms:
		var room: Rect2 = rooms[room_id]
		if not drone_view:
			draw_rect(room, Color("#17303e"))
			draw_rect(room, Color("#748e9c"), false, WALL)
			draw_string(font, room.position + Vector2(12, 24), room_id, HORIZONTAL_ALIGNMENT_LEFT)
	if not door.is_empty():
		var ends := leaf_ends()
		var live := (drone_view and sensor is Dictionary and bool(sensor.door_visible)) or (not drone_view and report is Dictionary)
		var color := Color("#aabac4")
		if live:
			color = Color("#f2b66a") if fraction < 1.0 else Color("#8cceb0")
			draw_line(gap_start(), gap_end(), Color("#17303e"), WALL * 2.0)
			draw_line(ends[0], ends[1], color, WALL * 2.0)
			draw_line(ends[2], ends[3], color, WALL * 2.0)
		else:
			draw_dashed_line(gap_start(), gap_end(), color, WALL)
		draw_string(font, (gap_start() + gap_end()) / 2 + Vector2(10, -12), str(door.id),
					HORIZONTAL_ALIGNMENT_LEFT, -1, 16, color)
	if drone_view and sensor is Dictionary:
		for marker: Dictionary in sensor.visible_markers:
			var p := _point(marker.point)
			draw_circle(p, 5, Color("#e0ce7b"))
			draw_string(font, p + Vector2(8, 5), str(marker.id), HORIZONTAL_ALIGNMENT_LEFT)
	if is_instance_valid(drone):
		draw_line(drone.position, drone.position + Vector2.from_angle(deg_to_rad(heading)) * 24,
				Color("#87d7ff"), 3)
		draw_circle(drone.position, body_radius, Color("#87d7ff"))
		draw_string(font, drone.position + Vector2(14, 5), drone_name,
					HORIZONTAL_ALIGNMENT_LEFT)
