extends SceneTree

const Client = preload("res://bridge/local_client.gd")
const Frames = preload("res://bridge/json_frames.gd")
var client := Client.new()
var server := TCPServer.new()
var remote: StreamPeerTCP
var decoder := Frames.new()
var frames: Array[Dictionary] = []
var received: Array[Dictionary] = []
var lost_messages: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var parser := Frames.new()
	var sample := Frames.encode({"text": "電力"})
	var at := sample.find(231) + 1
	if not _expect(parser.feed(sample.slice(0, at)).is_empty(), "partial UTF-8 frame"):
		return
	var rest := sample.slice(at)
	rest.append_array(Frames.encode({"seq": 2}))
	var combined := parser.feed(rest)
	if not _expect(combined.size() == 2 and combined[0].text == "電力", "combined frames"):
		return
	if not _expect(server.listen(0, "127.0.0.1") == OK, "listen on loopback"):
		return
	client.received.connect(func(state: Dictionary, _feedback: Array): received.append(state))
	client.lost.connect(func(message: String): lost_messages.append(message))
	client.start(server.get_local_port(), "test-nonce")
	if not await _until(func(): return frames.size() == 1):
		return
	if not _expect(frames[0].kind == "hello" and int(frames[0].seq) == 1, "initial handshake"):
		return
	var reply := Frames.encode({"kind": "snapshot", "seq": 1, "state": {"confirmed": "R1"},
		"feedback": []})
	remote.put_data(reply.slice(0, 7))
	for _i in range(12):
		await process_frame
		_poll()
	if not _expect(received.is_empty() and lost_messages.is_empty(), "responsive before full ack"):
		return
	remote.put_data(reply.slice(7))
	if not await _until(func(): return client.idle()):
		return
	if not _expect(received.size() == 1, "one confirmed state"):
		return
	if not _expect(client.send("command", {"text": "move 1 R2"}), "command sent once"):
		return
	if not await _until(func(): return frames.size() == 2):
		return
	if not _expect(not client.send("command", {"text": "move 1 R2"}), "mid-ack duplicate rejected"):
		return
	remote.disconnect_from_host()
	remote = null
	if not await _until(func(): return not lost_messages.is_empty()):
		return
	if not _expect(received.size() == 1 and received[0].confirmed == "R1"
			and not client.send("command", {"text": "move 1 R2"}), "unknown outcome was not fabricated"):
		return
	server.stop()
	print("M0_BRIDGE_CHECKS_OK: fragmented/combined frames, responsiveness, disconnect without replay")
	quit()


func _poll() -> void:
	client.poll()
	if remote == null and server.is_connection_available():
		remote = server.take_connection()
	if remote == null:
		return
	remote.poll()
	var count := remote.get_available_bytes()
	if count > 0:
		var read := remote.get_partial_data(count)
		if read[0] == OK:
			frames.append_array(decoder.feed(read[1]))


func _until(condition: Callable) -> bool:
	var until := Time.get_ticks_msec() + 5500
	while not condition.call() and Time.get_ticks_msec() < until:
		await process_frame
		_poll()
	return _expect(bool(condition.call()), "bounded wait")


func _expect(condition: bool, note: String) -> bool:
	if not condition:
		push_error(note)
		quit(1)
	return condition
