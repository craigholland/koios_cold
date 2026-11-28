extends RefCounted
## Local transmission buffer only. Python still owns accepted commands and outcomes.

const CAPACITY := 4
var _waiting: Array[String] = []
var _in_flight := ""


func capture(line: String) -> bool:
	if _waiting.size() >= CAPACITY:
		return false
	_waiting.append(line)
	return true


func send_next(client: M0LocalClient) -> bool:
	if _waiting.is_empty() or not client.send("command", {"text": _waiting[0]}):
		return false
	_in_flight = _waiting.pop_front()
	return true


func waiting_count() -> int:
	return _waiting.size()


func acknowledged() -> void:
	# The bridge validates the current sequence before emitting a snapshot.
	_in_flight = ""


func disconnect_notices() -> Array[String]:
	var notices: Array[String] = []
	if not _in_flight.is_empty():
		notices.append("Not confirmed: " + _in_flight)
	for line in _waiting:
		notices.append("Not sent: " + line)
	acknowledged()
	_waiting.clear()
	return notices
