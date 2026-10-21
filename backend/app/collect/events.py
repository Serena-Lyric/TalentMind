"""Private event stream for the existing collector subprocesses."""
import json
import os
from datetime import datetime, timezone


def emit_event(callback, platform: str, event: str, **payload) -> None:
    value = {'event': event, 'platform': platform,
             'observed_at': datetime.now(timezone.utc).isoformat(), **payload}
    if callback:
        callback(value)
    if os.environ.get('TALENTMIND_COLLECTION_EVENTS') == '1':
        print('TM_EVENT ' + json.dumps(value, ensure_ascii=False, default=str), flush=True)
