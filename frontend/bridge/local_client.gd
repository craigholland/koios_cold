class_name M0LocalClient
extends RefCounted
## Single-flight loopback transport. Never replays an uncertain request.

signal received(snapshot: Dictionary, feedback: Array)
signal lost(message: String)

const Frames = preload("res://bridge/json_frames.gd")
const TIMEOUT_MS := 4000
const IO_BUDGET := 16384
var peer := StreamPeerTCP.new()
var frames := Frames.new()
var outgoing := PackedByteArray()
var sequence := 0
var pending_sequence := 0
var deadline := 0
var live := false
var failed := false
var _hello := false
var _nonce := ""


func start(port: int, nonce: String) -> void:
	if port < 1 or port > 65535 or nonce.is_empty():
		_fail("Start the sandbox with the Python launcher.")
		return
	_nonce = nonce
	deadline = Time.get_ticks_msec() + TIMEOUT_MS
	if peer.connect_to_host("127.0.0.1", port) != OK:
		_fail("Could not connect to the local semantic process.")


func idle() -> bool:
	return live and not failed and pending_sequence == 0


func send(kind: String, payload: Dictionary) -> bool:
	if not idle():
		return false
	_send(kind, payload)
	return true


func _send(kind: String, payload: Dictionary) -> void:
	sequence += 1
	pending_sequence = sequence
	deadline = Time.get_ticks_msec() + TIMEOUT_MS
	outgoing = Frames.encode(payload.merged({"kind": kind, "seq": sequence}, true))


func poll() -> void:
	if failed:
		return
	if peer.poll() != OK:
		_fail("Connection polling failed. Pending work was not confirmed.")
		return
	var status := peer.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED:
		if not _hello:
			peer.set_no_delay(true)
			_hello = true
			_send("hello", {"version": 1, "nonce": _nonce})
			_nonce = ""
		_read_partial()
		if not failed:
			_write_partial()
	elif status != StreamPeerTCP.STATUS_CONNECTING:
		_fail("Backend disconnected. Pending work was not confirmed.")
	if not failed and (not live or pending_sequence != 0) and Time.get_ticks_msec() > deadline:
		_fail("Backend did not acknowledge in time. Pending work was not confirmed.")


func _write_partial() -> void:
	if outgoing.is_empty():
		return
	var result := peer.put_partial_data(outgoing)
	if result[0] != OK:
		_fail("Could not send; pending work was not confirmed.")
		return
	outgoing = outgoing.slice(int(result[1]))


func _read_partial() -> void:
	var available := mini(peer.get_available_bytes(), IO_BUDGET)
	if available <= 0:
		return
	var result := peer.get_partial_data(available)
	if result[0] != OK:
		_fail("Could not read; pending work was not confirmed.")
		return
	var messages := frames.feed(result[1])
	for message in messages:
		if message.get("kind") == "error":
			_fail("Backend rejected a request: " + str(message.get("message", "")))
			return
		var tag: Variant = message.get("seq")
		if (not (tag is float or tag is int) or pending_sequence == 0
				or tag != pending_sequence or message.get("kind") != "snapshot"
				or not message.get("state") is Dictionary or not message.get("feedback") is Array):
			_fail("Unexpected backend response. Work was not confirmed.")
			return
		pending_sequence = 0
		live = true
		message.state["note"] = message.get("note")
		received.emit(message.state, message.feedback)
	if frames.failed:
		_fail("Invalid backend message. Pending work was not confirmed.")


func close() -> void:
	peer.disconnect_from_host()
	outgoing.clear()
	pending_sequence = 0
	live = false


func _fail(message: String) -> void:
	failed = true
	close()
	lost.emit(message)
