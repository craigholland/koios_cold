extends RefCounted
## UI-only draft, history and insertion from Python's permitted completion list.

var entries: Array[String] = []
var index := 0
var draft := ""


func submitted(line: String) -> void:
	entries.append(line)
	if entries.size() > 100:
		entries.pop_front()
	index = entries.size()
	draft = ""


func browse(current: String, delta: int) -> String:
	if index == entries.size():
		draft = current
	index = clampi(index + delta, 0, entries.size())
	return draft if index == entries.size() else entries[index]


static func complete(line: String, caret: int, known: Dictionary) -> Dictionary:
	if known.is_empty():
		return {}
	var start := caret
	while start > 0 and not line[start - 1] in [" ", "\t", ";"]:
		start -= 1
	var end := caret
	while end < line.length() and not line[end] in [" ", "\t", ";"]:
		end += 1
	var prefix := line.substr(start, caret - start)
	var earlier := line.left(start).get_slice(";", line.left(start).count(";")).strip_edges()
	var pieces := earlier.replace("\t", " ").split(" ", false)
	var candidates: Array = []
	if pieces.is_empty() or (pieces[0] == "help" and pieces.size() == 1):
		candidates = known.verbs
	elif pieces.size() == 1:
		match pieces[0]:
			"move", "navigate":
				candidates = [known.slot]
			"stop", "status":
				candidates = [known.slot, "all"]
			"open":
				candidates = _addresses(known.doors, str(known.deck), prefix)
			"context":
				candidates = [known.deck]
			"queue":
				candidates = ["show"]
	elif pieces.size() == 2:
		if pieces[0] in ["move", "navigate"]:
			candidates = _addresses(known.rooms, str(known.deck), prefix)
		elif pieces[0] == "queue" and pieces[1] == "show":
			candidates = [known.slot]
	var matches: Array[String] = []
	for candidate: Variant in candidates:
		if str(candidate).to_lower().begins_with(prefix.to_lower()):
			matches.append(str(candidate))
	if matches.size() != 1:
		return {}
	return {"value": line.left(start) + matches[0] + line.substr(end),
		"caret": start + matches[0].length()}


static func _addresses(items: Array, deck: String, prefix: String) -> Array:
	if "/" not in prefix:
		return items
	var qualified: Array[String] = []
	for item: Variant in items:
		qualified.append(deck + "/" + str(item))
	return qualified
