extends SceneTree
## Actual scene, actual Python peer; hold the frontend pump to delay a real tick ACK.

const Sandbox = preload("res://app/sandbox.tscn")
var app: Node
var command: LineEdit
var output: RichTextLabel


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	app = Sandbox.instantiate()
	root.add_child(app)
	command = app.get_node("HUD/Command")
	output = app.get_node("HUD/Output")
	if not await _until(func(): return app.client.live, "connected to Python"):
		return
	app.set_process(false)
	while not app.client.idle():
		app.client.poll()
		await process_frame
	app._process(0.05)
	if not _check(not app.client.idle(), "ordinary tick in flight"):
		return
	app.client.poll() # Deliver tick, but deliberately do not consume its ACK yet.
	command.grab_focus()
	await process_frame
	await _submit("status 1")
	await _submit("help move")
	await _submit("zzz_invalid")
	await _submit("queue show 1")
	await _submit("help status")
	if not _check(command.text == "help status" and app.command_draft.entries.size() == 4
			and _text().count("> status 1\n") == 1 and _text().count("> help move\n") == 1
			and _text().count("> zzz_invalid\n") == 1 and _text().count("> queue show 1\n") == 1
			and command.has_focus() and command.is_editing() and "> help status\n" not in _text() and "still in input" in _text()
			and "STATUS:" not in _text() and "USAGE" not in _text(),
			"FIFO captures each local line once while a real ACK is pending; fifth remains a draft"):
		return
	await create_timer(0.12).timeout
	if not _check(not app.client.idle() and "STATUS:" not in _text(), "no fabricated early response"):
		return
	var loss := "--loss" in OS.get_cmdline_user_args()
	if loss:
		var deadline := Time.get_ticks_msec() + 3000
		while not app.client.idle() and Time.get_ticks_msec() < deadline:
			app.client.poll()
			await process_frame
		if not _check(app.client.idle(), "tick separately acknowledged"):
			return
		app._process(0.0) # Only one FIFO line enters the bridge.
		app.client.poll() # Write that command, but there is no acknowledged response yet.
		app.client.peer.disconnect_from_host()
		app._process(0.0)
		if not _check(app.client.failed and not command.editable and command.text == "help status"
				and _text().count("Not confirmed: status 1\n") == 1
				and _text().count("Not sent: help move\n") == 1
				and _text().count("Not sent: zzz_invalid\n") == 1
				and _text().count("Not sent: queue show 1\n") == 1
				and "STATUS:" not in _text() and "USAGE" not in _text(),
				"unconfirmed sent line and definitely unsent lines stay distinct; no replay"):
			return
	else:
		app.set_process(true)
		if not await _until(func(): return "QUEUE:" in _text(), "automatic drain without a second Enter"):
			return
		if not _check(_text().count("STATUS:") == 1 and _text().count("USAGE") == 1
				and _text().count("QUEUE:") == 1 and _text().find("STATUS:") < _text().find("USAGE")
				and _text().find("USAGE") < _text().find("QUEUE:")
				and command.text == "help status", "backend results arrive once in FIFO order"):
			return
		if not _check("zzz_invalid" in _text().substr(_text().find("USAGE") + 5), "parser feedback follows echoed bad input"):
			return
	print("M0_COMMAND_CONSOLE_OK: " + ("disconnect truth" if loss else "delayed tick, FIFO, parser feedback and capacity"))
	app.shutdown()


func _submit(line: String) -> void:
	command.text = line
	command.caret_column = line.length()
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = KEY_ENTER
		event.physical_keycode = KEY_ENTER
		event.pressed = pressed
		Input.parse_input_event(event)
		Input.flush_buffered_events()
		await process_frame


func _text() -> String:
	return output.get_parsed_text()


func _until(predicate: Callable, label: String) -> bool:
	var deadline := Time.get_ticks_msec() + 5500
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await process_frame
	return _check(predicate.call(), label)


func _check(ok: bool, label: String) -> bool:
	if not ok:
		push_error("M0 console: " + label + "\n" + _text())
		quit(1)
	return ok
