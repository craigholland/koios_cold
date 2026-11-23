extends SceneTree
## Separate test-owned native application used solely to exercise real window focus.


func _initialize() -> void:
	call_deferred("_show")


func _show() -> void:
	root.title = "Koios M0 native focus test companion"
	root.size = Vector2i(320, 140)
	root.grab_focus()
	await create_timer(1.2).timeout
	quit()
