import os
from threading import Lock

# Simple in-memory quota manager for Gemini API requests
_max_requests = int(os.getenv("GEMINI_MAX_REQUESTS", "50"))
_lock = Lock()
_count = 0

def can_make_request() -> bool:
    """Return True if another Gemini request can be made."""
    with _lock:
        return _count < _max_requests


def record_request() -> int:
    """Record a Gemini request and return the current count."""
    global _count
    with _lock:
        _count += 1
        return _count
