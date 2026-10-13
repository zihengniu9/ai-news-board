"""Daily SQLite snapshots, written with SQLite's online backup API (safe while the board is running)."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .runtime import data_root
from .settings import PROJECT_ROOT, load_dotenv

SGT = timezone(timedelta(hours=8))
KEEP = 7
DAY = re.compile(r'^\d{8}$')


def backup_root() -> Path:
    load_dotenv(PROJECT_ROOT/'.env')
    value = Path(os.environ.get('AI_NEWS_BACKUP_ROOT', str(PROJECT_ROOT/'backups'/'db'))).expanduser()
    if not value.is_absolute():
        raise ValueError('AI_NEWS_BACKUP_ROOT 必须是绝对路径')
    return value


def databases(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix in {'.sqlite3', '.db'})


def snapshot(src: Path, dst: Path) -> None:
    tmp = dst.with_suffix(dst.suffix + '.partial')
    tmp.unlink(missing_ok=True)
    source = sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True, timeout=20)
    target = sqlite3.connect(tmp)
    try:
        source.backup(target)
        result = target.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise RuntimeError(f'{src.name} 备份完整性检查未通过：{result}')
    finally:
        target.close(); source.close()
    tmp.replace(dst)


def daily_backup(now: datetime | None = None, source_root: Path | None = None, dest_root: Path | None = None) -> dict:
    """Back up every database in the data root once per Singapore calendar day; keep the newest KEEP days."""
    now = now or datetime.now(timezone.utc)
    source_root = source_root or data_root()
    dest_root = dest_root or backup_root()
    day = now.astimezone(SGT).strftime('%Y%m%d')
    folder = dest_root/day
    if (folder/'manifest.json').exists():
        return {'status': 'skipped', 'reason': '今日已备份', 'folder': str(folder)}
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for db in databases(source_root):
        out = folder/db.name
        snapshot(db, out)
        files.append({'name': db.name, 'bytes': out.stat().st_size})
    if not files:
        raise RuntimeError(f'数据目录中没有找到数据库：{source_root}')
    manifest = {'createdAt': now.isoformat(), 'source': str(source_root), 'files': files, 'integrity': 'ok'}
    (folder/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    removed = []
    days = sorted((p for p in dest_root.iterdir() if p.is_dir() and DAY.match(p.name)), reverse=True)
    for old in days[KEEP:]:
        if old.is_symlink() or getattr(old,'is_junction',lambda:False)() or old.resolve().parent != dest_root.resolve():
            raise RuntimeError(f'备份清理路径不在目标目录内：{old}')
        shutil.rmtree(old); removed.append(old.name)
    return {'status': 'completed', 'folder': str(folder), 'files': len(files), 'removed': removed}


def latest_backup(dest_root: Path | None = None) -> dict | None:
    try:
        dest_root = dest_root or backup_root()
        days = sorted((p for p in dest_root.iterdir() if p.is_dir() and DAY.match(p.name) and (p/'manifest.json').exists()), reverse=True)
    except (OSError, ValueError):
        return None
    if not days:
        return None
    try:
        manifest = json.loads((days[0]/'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return {'day': days[0].name, 'createdAt': manifest.get('createdAt'), 'files': len(manifest.get('files', [])), 'kept': len(days)}
