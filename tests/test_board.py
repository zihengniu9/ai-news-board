import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_news_pipeline.board import Store, date, parse_rss, record, canonical, consume

class BoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent);self.root=Path(self.tmp.name)
        assert self.root.resolve().is_relative_to(Path(__file__).resolve().parent)
        self.store=Store(self.root/'test.sqlite3')
        self.source={'id':'test','name':'Test','url':'https://example.org/feed','kind':'rss','category':'产品更新','status':'ok'}
        self.stamp='2026-10-13T03:00:00+00:00'

    def tearDown(self):self.tmp.cleanup()

    def test_unknown_dates_never_become_collection_time(self):
        for value in [None,'','bad','2026-10-12T10:00:00','2026-10-12']:self.assertIsNone(date(value))
        self.assertEqual(date('2026-10-15T13:00:00-04:00'),'2026-10-15T17:00:00+00:00')
        rows=parse_rss('<rss><channel><item><title>T</title><link>https://example.org/a</link><pubDate>bad</pubDate></item></channel></rss>',self.source)
        self.assertIsNone(rows[0]['date'])

    def test_same_url_updates_without_losing_history(self):
        r=record(self.source,'Before','https://example.org/a?utm_source=feed',summary='one')
        first=self.store.ingest([r],self.source,self.stamp)
        r2=record(self.source,'After','https://example.org/a',summary='two')
        second=self.store.ingest([r2],self.source,'2026-10-14T03:00:00+00:00')
        self.assertEqual(first['added'],1);self.assertEqual(second['updated'],1)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM items').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM revisions').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT first_seen FROM items').fetchone()[0],self.stamp)
        self.assertNotEqual(canonical('https://example.org/a?ref=one'),canonical('https://example.org/a?ref=two'))

    def test_source_failure_retains_content_and_last_success(self):
        r=record(self.source,'Before','https://example.org/a')
        self.store.ingest([r],self.source,self.stamp);self.store.source(self.source,self.stamp)
        self.store.source({**self.source,'status':'error','error':'certificate expired'},'2026-10-14T03:00:00+00:00')
        b=self.store.bundle()
        self.assertTrue(b['items'][0]['stale']);self.assertEqual(b['items'][0]['lastChecked'],self.stamp)
        self.assertEqual(b['sources'][0]['lastSuccess'],self.stamp)

    def test_current_event_with_old_publication_is_retained(self):
        a=self.root/'20261013T030000Z';a.mkdir()
        (a/'test.raw').write_text('placeholder',encoding='utf-8')
        (a/'probe.json').write_text(json.dumps({'sources':[self.source]}),encoding='utf-8')
        r=record(self.source,'Event','https://example.org/event','2026-01-01T00:00:00+00:00')
        r.update(type='event',end='2026-10-15T17:00:00+00:00',redeemEnd=None)
        with patch('ai_news_pipeline.board.parse',return_value=[r]),patch('ai_news_pipeline.board.write_bundle'):
            b=consume(a,self.store)
        self.assertEqual(len(b['items']),1);self.assertIsNone(b['items'][0]['redeemEnd'])

    def test_atom_alternate_and_missing_publication(self):
        raw='''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link rel="self" href="https://example.org/api"/><link rel="alternate" href="https://example.org/article"/><updated>2026-10-13T00:00:00Z</updated></entry></feed>'''
        r=parse_rss(raw,self.source)[0]
        self.assertEqual(r['url'],'https://example.org/article');self.assertIsNone(r['date'])

if __name__=='__main__':unittest.main()
