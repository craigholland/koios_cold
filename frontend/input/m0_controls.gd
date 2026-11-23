extends RefCounted
## Action bindings and fresh-press gate. It never polls OS-held keys.

const MOVEMENT := ["forward", "reverse", "left", "right"]
const RESERVED := [KEY_ENTER, KEY_KP_ENTER, KEY_TAB, KEY_ESCAPE]
var bindings := {
	"schematic": KEY_0, "drone": KEY_1, "pause": KEY_F3,
	"forward": KEY_UP, "reverse": KEY_DOWN, "left": KEY_LEFT, "right": KEY_RIGHT,
}
var held: Dictionary = {}
var armed := false


func remap(overrides: Dictionary) -> bool:
	var next := bindings.duplicate()
	for action: Variant in overrides:
		if not next.has(action) or not overrides[action] is String:
			return false
		var key := OS.find_keycode_from_string(overrides[action])
		if key == KEY_NONE or key in RESERVED or (action == "pause" and (key < KEY_F1 or key > KEY_F12)):
			return false
		next[action] = key
	var used := {}
	for key: Variant in next.values():
		if used.has(key):
			return false
		used[key] = true
	bindings = next
	clear()
	return true


func action(event: InputEventKey) -> String:
	var key := event.physical_keycode if event.physical_keycode != KEY_NONE else event.keycode
	for candidate: String in bindings:
		if bindings[candidate] == key:
			return candidate
	return ""


func motion(action_name: String, event: InputEventKey, enabled: bool) -> bool:
	if action_name not in MOVEMENT:
		return false
	if not event.pressed:
		held.erase(action_name)
		if held.is_empty():
			armed = false
	elif enabled and not event.echo and not held.has(action_name):
		held[action_name] = true
		armed = true
	return enabled


func direction() -> Vector2:
	var longitudinal := int(held.has("forward")) - int(held.has("reverse"))
	var turning := int(held.has("right")) - int(held.has("left"))
	# Authoritative control rule: turn in place rather than always steering along a curve.
	return Vector2(0, turning) if turning else Vector2(longitudinal, 0)


func clear() -> void:
	held.clear()
	armed = false
