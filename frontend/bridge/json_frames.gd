class_name M0JsonFrames
extends RefCounted
## Wire decoder: buffer bytes until the UTF-8 line is complete.

const MAX_FRAME := 65536
var pending := PackedByteArray()
var failed := false


func feed(bytes: PackedByteArray) -> Array[Dictionary]:
	var messages: Array[Dictionary] = []
	if failed:
		return messages
	pending.append_array(bytes)
	var end := pending.find(10)
	while end >= 0:
		if end < 1 or end > MAX_FRAME:
			failed = true
			return messages
		var json := JSON.new()
		var line := pending.slice(0, end).get_string_from_utf8()
		pending = pending.slice(end + 1)
		if json.parse(line) != OK or not json.data is Dictionary:
			failed = true
			return messages
		messages.append(json.data as Dictionary)
		end = pending.find(10)
	if pending.size() > MAX_FRAME:
		failed = true
	return messages


static func encode(message: Dictionary) -> PackedByteArray:
	return (JSON.stringify(message) + "\n").to_utf8_buffer()
