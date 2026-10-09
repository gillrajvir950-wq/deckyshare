import time


class NotificationDeduper:
    """Small in-memory guard used to suppress duplicate DeckyShare notifications."""

    def __init__(self, ttl_seconds: float = 4.0):
        self.ttl_seconds = max(0.1, float(ttl_seconds))
        self._seen = {}

    def _key(self, event_type: str, item) -> str:
        item = item or {}
        if isinstance(item, dict):
            identity = item.get("path") or item.get("id") or item.get("name") or "unknown"
        else:
            identity = str(item)
        return f"{event_type}:{identity}"

    def should_notify(self, event_type: str, item, now: float = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        key = self._key(event_type, item)
        previous = self._seen.get(key)

        cutoff = now - self.ttl_seconds
        for stale_key, seen_at in list(self._seen.items()):
            if seen_at < cutoff:
                self._seen.pop(stale_key, None)

        if previous is not None and now - previous < self.ttl_seconds:
            return False

        self._seen[key] = now
        return True

    def clear(self):
        self._seen.clear()
