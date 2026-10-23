"""Pure status parsing for the read-only GRBL USB-host bring-up path.

No USB role switching, VBUS power, serial enumeration, or motion commands.
"""
def parse_status(line):
    """Parse a GRBL 1.1 status frame into a display-safe snapshot.

    Reject malformed numeric fields rather than trusting stale DRO values.
    Coordinates are reported verbatim; WPos is calculated only when both
    MPos and WCO are present. This parser does not imply motion permission.
    """
    if not isinstance(line, (bytes, bytearray, str)):
        return None
    if isinstance(line, (bytes, bytearray)):
        try:
            line = line.decode("ascii")
        except UnicodeError:
            return None
    line = line.strip()
    if not (line.startswith("<") and line.endswith(">")):
        return None
    parts = line[1:-1].split("|")
    if not parts or not parts[0] or len(parts) > 24:
        return None
    state = parts[0]
    if state.split(":", 1)[0] not in (
        "Idle", "Run", "Hold", "Jog", "Alarm", "Door",
        "Check", "Home", "Sleep"):
        return None
    result = {"state": state, "mpos": None, "wpos": None, "wco": None}
    for field in parts[1:]:
        if ":" not in field:
            continue
        key, raw = field.split(":", 1)
        if key not in ("MPos", "WPos", "WCO"):
            continue
        try:
            values = tuple(float(x) for x in raw.split(","))
        except ValueError:
            return None
        if len(values) not in (3, 4, 5, 6):
            return None
        if any(not (-1e12 < x < 1e12) for x in values):
            return None
        result[key.lower()] = values
    if result["wpos"] is None and result["mpos"] and result["wco"]:
        if len(result["mpos"]) != len(result["wco"]):
            return None
        result["wpos"] = tuple(
            m - o for m, o in zip(result["mpos"], result["wco"]))
    return result
