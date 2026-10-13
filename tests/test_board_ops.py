import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class BoardOpsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.data, self.backups = base/'data', base/'backups'
        self.data.mkdir()
        self.old_env = {k: os.environ.get(k) for k in ('AI_NEWS_DATA_ROOT', 'AI_NEWS_BACKUP_ROOT')}
        os.environ['AI_NEWS_DATA_ROOT'] = str(self.data)
        os.environ['AI_NEWS_BACKUP_ROOT'] = str(self.backups)
        for name in ('board.sqlite3', 'media.sqlite3'):
            db = sqlite3.connect(self.data/name)
            db.execute('CREATE TABLE items(id TEXT)'); db.execute("INSERT INTO items VALUES('x')"); db.commit(); db.close()

    def tearDown(self):
        for k, v in self.old_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self.tmp.cleanup()

    def test_daily_backup_once_per_day_and_keeps_seven(self):
        from ai_news_pipeline.backup import daily_backup, latest_backup
        start = datetime(2026, 10, 1, 2, tzinfo=timezone.utc)
        first = daily_backup(start, self.data, self.backups)
        self.assertEqual(first['files'], 2)
        self.assertEqual(daily_backup(start + timedelta(hours=4), self.data, self.backups)['status'], 'skipped')
        copy = sqlite3.connect(self.backups/'20261001'/'board.sqlite3')
        self.assertEqual(copy.execute('SELECT id FROM items').fetchone()[0], 'x'); copy.close()
        for d in range(1, 10):
            daily_backup(start + timedelta(days=d), self.data, self.backups)
        kept = sorted(p.name for p in self.backups.iterdir())
        self.assertEqual(len(kept), 7)
        self.assertEqual(kept[-1], '20261010')
        self.assertEqual(latest_backup(self.backups)['day'], '20261010')

    def test_backup_day_uses_singapore_date(self):
        from ai_news_pipeline.backup import daily_backup
        # 17:00 UTC is already the next day in Singapore.
        result = daily_backup(datetime(2026, 10, 1, 17, tzinfo=timezone.utc), self.data, self.backups)
        self.assertTrue(result['folder'].endswith('20261002'))

    def _runs(self, *runs):
        (self.data/'schedule.json').write_text(json.dumps({'enabled': True}), encoding='utf-8')
        logs = self.data/'scheduled-runs'; logs.mkdir()
        for i, r in enumerate(runs):
            (logs/f'2026100{i}T000000Z.json').write_text(json.dumps(r), encoding='utf-8')

    def test_health_fresh_and_stale(self):
        from ai_news_pipeline.runtime import schedule_health
        now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        self._runs({'status': 'completed', 'finishedAt': (now - timedelta(hours=3)).isoformat()})
        fresh = schedule_health(now)
        self.assertFalse(fresh['stale']); self.assertEqual(fresh['hoursSinceSuccess'], 3.0)
        late = schedule_health(now + timedelta(hours=6))
        self.assertTrue(late['stale'])

    def test_health_reports_latest_failure(self):
        from ai_news_pipeline.runtime import schedule_health
        now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        self._runs({'status': 'completed', 'finishedAt': (now - timedelta(hours=10)).isoformat()},
                   {'status': 'failed', 'finishedAt': (now - timedelta(hours=1)).isoformat(), 'error': 'RuntimeError: TUN 未就绪'})
        h = schedule_health(now)
        self.assertTrue(h['stale']); self.assertEqual(h['lastRun']['status'], 'failed')
        self.assertIn('TUN', h['lastRun']['error'])

    def test_health_disabled_never_stale(self):
        from ai_news_pipeline.runtime import schedule_health
        self.assertFalse(schedule_health()['stale'])


if __name__ == '__main__':
    unittest.main()
