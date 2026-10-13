import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_news_pipeline.board import parse
from ai_news_pipeline.runtime import data_root
from ai_news_pipeline.collection_lock import collection_lock

class Repairs(unittest.TestCase):
    def test_anthropic_actual_card_shapes_and_day_precision(self):
        raw='<a href="/model-a"><time>Oct 7, 2026</time><h4>New model A</h4><p>New abilities.</p></a><a href="/news/policy"><time>Oct 8, 2026</time><span class="PublicationList__title body-3">Policy update</span></a>'
        rows=parse(raw,{'id':'anthropic','name':'Anthropic','url':'https://www.anthropic.com/news','kind':'anthropic','category':'模型更新'})
        self.assertEqual(len(rows),2);self.assertIsNone(rows[0]['date']);self.assertEqual(rows[0]['publishedDay'],'2026-10-07')

    def test_new_challenge_never_reuses_cursor_or_old_parent(self):
        source={'id':'challenge','name':'MLH','url':'https://www.mlh.com/events/new/challenges/new','kind':'mlh-challenge','category':'活动福利','eventSlug':'old','parentUrl':'https://events.mlh.com/events/14553'}
        props={'eventSlug':'new','challenge':{'name':'Build a new demo','shortDescriptionHtml':'<p>New event summary.</p>','descriptionHtml':'<ol><li>Create a demo.</li><li>Submit a link.</li></ol>'}}
        raw='<script data-page="app" type="application/json">'+json.dumps({'props':props})+'</script>'
        row=parse(raw,source)[0]
        self.assertEqual(row['title'],'Build a new demo');self.assertNotIn('parentUrl',row)
        self.assertNotIn('Cursor',json.dumps(row));self.assertEqual(row['facts'],['Create a demo.','Submit a link.'])

    def test_event_index_discovers_future_cards(self):
        source={'id':'mlh','name':'MLH','url':'https://ghw.mlh.com/','kind':'mlh-index','category':'活动福利'}
        rows=parse('<a href="./events/new">New Week November 6th - 12th, 2026 Build something new! Learn More &gt;</a>',source)
        self.assertEqual(rows[0]['periodStart'],'2026-11-06');self.assertIsNone(rows[0]['end'])
        self.assertEqual(rows[0]['url'],'https://ghw.mlh.com/events/new')

    def test_runtime_path_and_exclusive_collection(self):
        base=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=base) as temp:
            assert Path(temp).resolve().is_relative_to(base)
            with patch.dict(os.environ,{'AI_NEWS_DATA_ROOT':temp}):
                self.assertEqual(data_root(),Path(temp))
                with collection_lock():
                    with self.assertRaises(RuntimeError):
                        with collection_lock():pass
                with collection_lock():pass

if __name__=='__main__':unittest.main()
