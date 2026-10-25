"""Business-isolated Python bridge to the actual Meterless H-MEM reference.
Node 24+ required. FileLock serializes read/modify/write across workers.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from filelock import FileLock, Timeout as LockTimeout
from . import budget

PROJECT = Path(__file__).resolve().parent.parent

class MemoryError(RuntimeError):
    pass


def enabled():
    return os.getenv('HMEM_ENABLED', 'true').lower() == 'true'


def invoke(business_id, action, **payload):
    root = Path(os.getenv('HMEM_DIR', str(PROJECT / 'data' / 'hmem'))).resolve()
    # Hash prevents path traversal and creates strict per-business stores/ledgers.
    directory = root / hashlib.sha256(business_id.encode('utf-8')).hexdigest()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with FileLock(str(directory / '.lock'), timeout=budget.timeout(20)):
            proc = subprocess.run([os.getenv('HMEM_NODE', 'node'), '--experimental-transform-types',
                                   str(PROJECT / 'marketing_agent' / 'hmem_bridge.ts')],
                input=json.dumps(dict(directory=str(directory), action=action, **payload)),
                text=True, encoding='utf-8', capture_output=True, timeout=budget.timeout(20))
        budget.remaining()
        if proc.returncode:
            raise MemoryError('H-MEM failed. Check Node 24+ is installed. ' + proc.stderr[-500:])
        return json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError, TimeoutError, LockTimeout) as e:
        raise MemoryError(f'H-MEM unavailable: {e}') from e


def remember(business_id, key, content, source='owner'):
    if not business_id.strip() or not key.strip() or not content.strip():
        raise ValueError('business_id, key and content must be nonempty')
    if source not in ('owner', 'backend_profile'):
        raise ValueError('unsupported source')
    return invoke(business_id, 'remember', key=key, content=content, source=source)


def recall(business_id, query):
    return invoke(business_id, 'recall', query=query)
