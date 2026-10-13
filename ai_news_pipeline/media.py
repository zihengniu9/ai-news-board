"""Media coverage sample, kept separate from first-party product announcements."""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .board import ROOT, BOARD, Store, parse_rss
from .board_network import Fetcher, verify_tunnel
from .settings import get_settings
from .runtime import data_root, schedule_state, schedule_health

AI = re.compile(r'\bAI\b|artificial intelligence|OpenAI|ChatGPT|GPT[- ]|Anthropic|Claude|DeepSeek|Gemini|Nvidia|Muse Wonder|智谱|人工智能|大模型|智能体|多模态|算力|机器学习',re.I)


class MediaStore(Store):
    def __init__(self,path=None):super().__init__(path or data_root()/'media.sqlite3')

    def bundle(self):
        with self.connect() as db:
            sources=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM sources')]
            rows=db.execute('SELECT * FROM items').fetchall()
            runs=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM runs ORDER BY stamp')]
        by_source={s['id']:s for s in sources}
        articles=[]
        for r in rows:
            a=json.loads(r['payload']);a.update(firstSeen=r['first_seen'],lastChecked=r['last_seen'],stale=by_source[a['sourceId']]['status']!='ok')
            articles.append(a)
        stamp=max((s['checkedAt'] for s in sources),default=None)
        # A single RSS response is a recent sample, not complete historical coverage.
        # Only uninterrupted <=6-hour samples spanning 48 hours can support comparisons.
        ready=False
        if stamp and runs:
            latest=datetime.fromisoformat(stamp);baseline=latest-timedelta(hours=48)
            selected=[r for r in runs if datetime.fromisoformat(r['stamp'])>=baseline-timedelta(hours=6)]
            current={s['id'] for s in sources if s['status']=='ok'}
            if len(current)>=2 and selected and datetime.fromisoformat(selected[0]['stamp'])<=baseline:
                times=[datetime.fromisoformat(r['stamp']) for r in selected]
                ready=all((b-a).total_seconds()<=21600 for a,b in zip(times,times[1:])) and all(current<=set(r.get('okSources',[])) for r in selected)
        return {'articles':articles,'sources':sources,'snapshot':stamp,'comparisonReady':ready,
                'comparisonSources':[s['id'] for s in sources if s['status']=='ok'] if ready else [],
                'scheduled':schedule_state().get('enabled',False),'schedule':schedule_health(),'scope':'媒体订阅样本；不代表全网热度或阅读量'}


def consume_media(archive,store=None):
    store=store or MediaStore()
    manifest=json.loads((archive/'probe.json').read_text(encoding='utf-8'))
    stamp=datetime.strptime(archive.name,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat()
    sources=[]
    for source in manifest['sources']:
        source=dict(source)
        if source.get('enabled') is False:source.update(status='disabled',error=source.get('disabledReason','已停用'))
        if source.get('status')=='ok':
            try:
                rows=parse_rss((archive/(source['id']+'.raw')).read_text(encoding='utf-8'),source)
                rows=[r for r in rows if AI.search(r['title']+' '+r['summary'])]
                for r in rows:r.update(type='media')
                source.update(parsed=len(rows),changes=store.ingest(rows,source,stamp))
            except Exception as e:source.update(status='error',error=f'订阅解析失败：{type(e).__name__}: {e}')
        elif not source.get('status'):source.update(status='error',error='本轮提前停止，尚未请求')
        store.source(source,stamp);sources.append(source)
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)',(stamp,json.dumps({'stamp':stamp,'okSources':[s['id'] for s in sources if s['status']=='ok']},ensure_ascii=False)))
    result=store.bundle();write_media(result)
    (archive/'report.json').write_text(json.dumps({'sources':sources,'articles':len(result['articles'])},ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def write_media(bundle):
    temp=BOARD/'media-data.tmp';temp.write_text('window.MEDIA_DATA = '+json.dumps(bundle,ensure_ascii=False).replace('<','\\u003c')+';\n',encoding='utf-8');temp.replace(BOARD/'media-data.js')


def refresh_media():
    settings=get_settings();archive=data_root()/'media-runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive.mkdir(parents=True,exist_ok=True)
    sources=json.loads((ROOT/'config/media-sources.json').read_text(encoding='utf-8'));requests=[]
    try:
        verify_tunnel(settings.proxy_url);fetcher=Fetcher(settings.proxy_url,archive)
        for source in sources:
            if source.get('enabled') is False:
                source.update(status='disabled',error=source.get('disabledReason','已停用'));continue
            try:
                _,url=fetcher.fetch(source['url'],source['id']);source.update(status='ok',final_url=url)
            except Exception as e:source.update(status='error',error=f'{type(e).__name__}: {e}')
            if fetcher.halted:break
        requests=fetcher.requests
    except Exception as e:
        for source in sources:source.update(status='error',error=str(e))
    (archive/'probe.json').write_text(json.dumps({'sources':sources,'requests':requests},ensure_ascii=False,indent=2),encoding='utf-8')
    return consume_media(archive)
