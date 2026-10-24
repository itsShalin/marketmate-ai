"""Per-request monotonic budget, isolated across FastAPI worker threads."""
from contextvars import ContextVar
import time

deadline = ContextVar('agent_deadline', default=None)

class DeadlineExceeded(Exception):
    pass

def remaining():
    end = deadline.get()
    if end is None:
        return float('inf')
    left = end - time.monotonic()
    if left <= 0:
        raise DeadlineExceeded('Run time budget exhausted')
    return left

def timeout(limit):
    return min(limit, remaining())

def pause(seconds):
    left = remaining()
    if seconds >= left:
        raise DeadlineExceeded('Not enough run time left for retry backoff')
    time.sleep(seconds)
