extends SceneTree

const View = preload("res://features/traversal/room_view.gd")


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	# This is test-owned collision geometry, not a second runtime room manifest.
	var model := {
		"rooms": [
			{"id": "A", "min_corner": _point(0, 0), "max_corner": _point(2, 4)},
			{"id": "B", "min_corner": _point(2, 0), "max_corner": _point(4, 4)},
		],
		"door": {"id": "test", "gap_start": _point(2, 1), "gap_end": _point(2, 3)},
		"drone": {"location": _point(1, 2), "display_name": "Test body", "heading_degrees": 0},
	}
	var view := View.new()
	root.add_child(view)
	for aperture in [0.0, 0.1, 1.0]:
		view.apply({"world": model, "opening_fraction": aperture})
		view.reset_to_confirmed()
		for _i in range(60):
			await physics_frame
			view.navigate(view.room_center("B"), 1.0 / 60.0)
		var x := view.semantic_point().x
		if (aperture < 1.0 and x >= 2.0) or (aperture == 1.0 and absf(x - 3.0) > 0.01):
			push_error("Unexpected traversal at aperture %.2f: x=%f" % [aperture, x])
			quit(1)
			return
	print("M0_MOVEMENT_CHECKS_OK: closed/narrow leaves block; open aperture passes")
	quit()


func _point(x: float, y: float) -> Dictionary:
	return {"x_m": x, "y_m": y}
