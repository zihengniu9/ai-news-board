"""Runtime state outside the synced source checkout."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .settings import PROJECT_ROOT, load_dotenv

def data_root():
    load_dotenv(PROJECT_ROOT/'.env')
    value=Path(os.environ.get('AI_NEWS_DATA_ROOT',str(PROJECT_ROOT/'data'))).expanduser()
    if not value.is_absolute():raise ValueError('AI_NEWS_DATA_ROOT 必须是绝对路径')
    return value

def schedule_state():
    path=data_root()/'schedule.json'
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {'enabled':False}


STALE_HOURS=8

def schedule_health(now=None):
    """Latest scheduled run and latest successful one, so the page can flag missed collections."""
    now=now or datetime.now(timezone.utc)
    state=schedule_state();enabled=bool(state.get('enabled'))
    runs=[]
    try:
        for f in sorted((data_root()/'scheduled-runs').glob('*.json')):
            try:runs.append(json.loads(f.read_text(encoding='utf-8')))
            except (OSError,ValueError):continue
    except (OSError,ValueError):pass
    last=runs[-1] if runs else None
    ok=[r for r in runs if r.get('status')=='completed' and r.get('finishedAt')]
    last_ok=ok[-1]['finishedAt'] if ok else None
    hours=None
    if last_ok:
        try:hours=(now-datetime.fromisoformat(last_ok)).total_seconds()/3600
        except ValueError:hours=None
    stale=enabled and (hours is None or hours>STALE_HOURS)
    try:
        from .backup import latest_backup
        backup=latest_backup()
    except Exception:
        backup=None
    return {'enabled':enabled,'staleAfterHours':STALE_HOURS,'stale':stale,'hoursSinceSuccess':hours,'lastSuccess':last_ok,
            'lastRun':{k:last.get(k) for k in ('status','finishedAt','error')} if last else None,'backup':backup}
