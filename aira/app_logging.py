import json
from datetime import datetime, timezone


def log_event(event_name, **fields):
    event = {
        "event": event_name,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    event.update(fields)
    print(json.dumps(event, sort_keys=True), flush=True)
