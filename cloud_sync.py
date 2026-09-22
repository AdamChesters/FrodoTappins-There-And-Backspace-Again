"""Cumulative sync protocol and cloud-display validation (no GUI dependencies)."""
FIELDS = ("keystrokes", "words", "deletions", "alt_tabs", "power_cycles")
MAX_COUNT = 2**53 - 1


def validate_counts(value):
    if not isinstance(value, dict):
        raise ValueError("Cloud response is missing totals.")
    out = {}
    for field in FIELDS:
        n = value.get(field)
        if type(n) is not int or not 0 <= n <= MAX_COUNT:
            raise ValueError("Cloud response contains invalid counts.")
        out[field] = n
    return out


def validate_cloud(value):
    if not isinstance(value, dict) or not isinstance(value.get("devices"), list):
        raise ValueError("Cloud returned an invalid response.")
    global_counts = validate_counts(value.get("global"))
    combined = dict.fromkeys(FIELDS, 0)
    ids = set()
    for device in value["devices"]:
        if not isinstance(device, dict) or not isinstance(device.get("device_id"), str):
            raise ValueError("Cloud returned an invalid installation.")
        identifier = device["device_id"]
        if not identifier or identifier in ids:
            raise ValueError("Cloud returned duplicate installation IDs.")
        if not isinstance(device.get("device_name"), (str, type(None))):
            raise ValueError("Cloud returned an invalid installation name.")
        ids.add(identifier)
        for field, n in validate_counts(device).items():
            combined[field] += n
    if combined != global_counts or value.get("device_count") != len(ids):
        raise ValueError("Cloud device totals do not match the combined total.")
    return value


def make_payload(identity, local_totals, cloud):
    validate_cloud(cloud)
    if cloud.get("protocol") != 2:
        raise ValueError("Update your cloud Worker to cumulative sync before uploading with this app.")
    identifier, name = identity
    previous = next((d for d in cloud["devices"] if d["device_id"] == identifier), None)
    revision = previous.get("revision") if previous else 0
    if type(revision) is not int or revision < 0:
        raise ValueError("Cloud returned an invalid revision.")
    return {"protocol": 2, "device_id": identifier, "device_name": name,
            "expected_revision": revision, "totals": validate_counts(local_totals)}


def progress_words(local_words, configured, endpoint, cache):
    """No silent fallback to local words when the user expects cloud progress."""
    if not configured:
        return local_words
    if not isinstance(cache, dict) or cache.get("endpoint") != endpoint:
        return None
    try:
        return validate_cloud(cache.get("totals"))["global"]["words"]
    except ValueError:
        return None
