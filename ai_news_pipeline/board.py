"""Evidence-backed personal dashboard ingestion; isolated from the legacy daily pipeline."""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from .board_network import Fetcher, verify_tunnel
from .settings import get_settings
from .runtime import data_root, schedule_state, schedule_health

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / 'site'
UTC = timezone.utc


def date(value):
    if not value:
        return None
    for parser in (lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')),
                   parsedate_to_datetime,
                   lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=UTC)):
        try:
            dt = parser(value)
            # Never infer an unknown timezone from the machine's local timezone.
            if dt.tzinfo is None:
                return None
            return dt.astimezone(UTC).isoformat()
        except (ValueError, TypeError, OverflowError):
            continue
    return None


def plain(value):
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', value or '', flags=re.S | re.I)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def canonical(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('来源条目不是有效的公开 HTTPS 链接')
    query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'gclid','fbclid'}]
    return urlunsplit(('https', p.netloc.lower(), p.path or '/', urlencode(query), p.fragment))


def identity(url):
    return hashlib.sha256(canonical(url).encode()).hexdigest()[:20]


def record(source, title, url, published=None, summary='', **extra):
    url = canonical(url)
    return dict(id=identity(url), sourceId=source['id'], brand=source['name'], title=plain(title),
                url=url, date=published, summary=plain(summary)[:750], type='release',
                category=source['category'], **extra)


def parse_rss(raw, source):
    root = ET.fromstring(raw)
    atom = '{http://www.w3.org/2005/Atom}'
    output = []
    is_atom = root.tag == atom+'feed'
    nodes = root.findall(atom+'entry') if is_atom else root.findall('./channel/item')
    if not nodes:
        raise ValueError('订阅未包含 RSS/Atom 条目，可能发生结构变化')
    for n in nodes:
        if is_atom:
            links = [a.get('href') for a in n.findall(atom+'link') if a.get('rel','alternate') == 'alternate']
            url = next((u for u in links if u and u.startswith('https://')), '')
            title = n.findtext(atom+'title','')
            published = date(n.findtext(atom+'published'))
            summary = n.findtext(atom+'summary') or n.findtext(atom+'content','')
            category = ''
        else:
            url, title = n.findtext('link',''), n.findtext('title','')
            published = date(n.findtext('pubDate'))
            summary = n.findtext('description') or n.findtext('{http://purl.org/rss/1.0/modules/content/}encoded','')
            category = n.findtext('category','')
        if not title or not url.startswith('https://'):
            continue
        # Customer stories, hiring and corporate announcements are not product launches.
        if source['id'] == 'openai' and category.lower() != 'product':
            continue
        if source['id'] == 'google' and not re.search(r'introduc|launch|new |expand|updates|making .*easier', title, re.I):
            continue
        if source['id'] == 'google' and re.search(r'experts|team|trailer', title, re.I):
            continue
        if source['id'] == 'huggingface' and not re.search(r'introduc|model|agent|asr|launch|release|dataset|tool|synth', title, re.I):
            continue
        output.append(record(source,title,url,published,summary))
    return output


def parse_cursor(raw, source):
    output = []
    for article in re.findall(r'<article\b[^>]*>(.*?)</article>',raw,re.S|re.I):
        title = re.search(r'<h1\b[^>]*>\s*<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',article,re.S)
        stamp = re.search(r'<time\b[^>]*datetime="([^"]+)"',article,re.I)
        paragraph = re.search(r'</header>.*?<p\b[^>]*>(.*?)</p>',article,re.S)
        if title:
            output.append(record(source, title[2], urljoin(source['url'],title[1]),
                                 date(stamp[1]) if stamp else None, paragraph[1] if paragraph else ''))
    if not output:
        raise ValueError('未识别到更新日志，保留旧记录并等待适配')
    return list({r['id']:r for r in output}.values())


def parse_event(raw,source):
    from .page_parsers import mlh_event
    return mlh_event(raw,source)


def parse_structured(raw, source):
    output=[]
    def visit(node):
        if isinstance(node,list):
            for x in node:visit(x)
        elif isinstance(node,dict):
            kind=node.get('@type','')
            if kind in ['Event','NewsArticle','BlogPosting','Article'] and node.get('url') and (node.get('headline') or node.get('name')):
                r=record(source,node.get('headline') or node['name'],urljoin(source['url'],node['url']),date(node.get('datePublished')),node.get('description',''))
                if kind=='Event':r.update(type='event',start=date(node.get('startDate')),end=date(node.get('endDate')),redeemEnd=None)
                output.append(r)
            for value in node.values():
                if isinstance(value,(dict,list)):visit(value)
    for s in re.findall(r'<script\b[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>',raw,re.S|re.I):
        try:visit(json.loads(s))
        except (ValueError,TypeError):continue
    if not output:raise ValueError('页面可访问，但尚未解析出消息；需适配页面结构')
    return output


def parse(raw, source):
    kind=source['kind']
    if kind=='anthropic':
        from .page_parsers import anthropic
        return anthropic(raw,source)
    if kind=='mlh-index':
        from .page_parsers import mlh_index
        return mlh_index(raw,source)
    return (parse_rss if kind=='rss' else parse_cursor if kind=='cursor' else parse_event if kind.startswith('mlh-') else parse_structured)(raw,source)


class Store:
    def __init__(self,path=None):
        self.path=path or data_root()/'board.sqlite3'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,source TEXT NOT NULL,payload TEXT NOT NULL,hash TEXT NOT NULL,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions(id TEXT,hash TEXT,seen TEXT,payload TEXT,PRIMARY KEY(id,hash));
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,payload TEXT NOT NULL,last_success TEXT);
                CREATE TABLE IF NOT EXISTS runs(stamp TEXT PRIMARY KEY,payload TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=20);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def ingest(self, rows, source, stamp):
        count={'added':0,'updated':0,'unchanged':0}
        with self.connect() as db:
            for row in rows:
                payload=json.dumps(row,ensure_ascii=False,sort_keys=True)
                digest=hashlib.sha256(payload.encode()).hexdigest()
                old=db.execute('SELECT hash,first_seen FROM items WHERE id=?',(row['id'],)).fetchone()
                count['added' if not old else 'updated' if old['hash']!=digest else 'unchanged']+=1
                db.execute('INSERT INTO items VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,hash=excluded.hash,last_seen=excluded.last_seen',
                           (row['id'],source['id'],payload,digest,old['first_seen'] if old else stamp,stamp))
                db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?)',(row['id'],digest,stamp,payload))
        return count

    def source(self, source, stamp):
        with self.connect() as db:
            old=db.execute('SELECT last_success FROM sources WHERE id=?',(source['id'],)).fetchone()
            success=stamp if source['status']=='ok' else old['last_success'] if old else None
            data=dict(source,checkedAt=stamp,lastSuccess=success)
            db.execute('INSERT OR REPLACE INTO sources VALUES(?,?,?)',(source['id'],json.dumps(data,ensure_ascii=False),success))

    def bundle(self):
        with self.connect() as db:
            records=db.execute('SELECT * FROM items').fetchall()
            sources=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM sources')]
        by_source={s['id']:s for s in sources}
        rows=[]
        for r in records:
            row=json.loads(r['payload']);source=by_source[row['sourceId']]
            row.update(firstSeen=r['first_seen'],lastChecked=r['last_seen'],evidenceHash=r['hash'],stale=source['status']!='ok')
            rows.append(row)
        by_url={r['url']:r for r in rows}
        for r in rows:
            if r.get('parentUrl') in by_url:
                parent=by_url[r['parentUrl']]
                # Event end remains separate from the unknown code redemption expiry.
                r.update(start=parent.get('start'),end=parent.get('end'),eventTimeChecked=parent['lastChecked'],eventTimeStale=parent['stale'])
                r['dateBasis']='活动时段来自关联官方报名页；不代表兑换码有效期。'
        for r in rows:decorate(r)
        editorial_path=ROOT/'config/board-editorial.json'
        editorial=json.loads(editorial_path.read_text(encoding='utf-8')) if editorial_path.exists() else {}
        for r in rows:
            note=editorial.get(r['url'])
            if note and note.get('evidenceHash')==r['evidenceHash']:
                r['originalTitle']=r['title']
                for field in ['title','summary','angle','audience','format']:
                    if note.get(field):r[field]=note[field]
                r['tags']=[r['category'],'已整理 · 待实测']
        rows.sort(key=lambda r:(r['priority'], -(datetime.fromisoformat(r['date']).timestamp() if r.get('date') else 0)))
        stamp=max((s['checkedAt'] for s in sources),default=datetime.now(UTC).isoformat())
        for s in sources:
            s['state']='采集成功' if s['status']=='ok' else '采集失败'
            s['desc']=f"最近检查：{s['checkedAt']} · " + (f"本轮读取 {s.get('parsed',0)} 条" if s['status']=='ok' else s.get('error','未知错误'))
        return {'meta':{'snapshot':stamp,'checkedDate':stamp[:10],'mode':'collected','timezone':'Asia/Singapore','scheduled':schedule_state().get('enabled',False),'schedule':schedule_health(),
                        'sourceSuccess':sum(s['status']=='ok' for s in sources),'sourceTotal':len(sources)},'items':rows,'sources':sources}


def decorate(r):
    r['dateLabel']=(r['date'][:10]+' 发布') if r.get('date') else (r['publishedDay']+' 发布（未标时区）') if r.get('publishedDay') else '发布时间未标注'
    r.setdefault('facts',[r['summary'] or r['title']])
    r.setdefault('conditions',['可用地区、账号资格与费用需回到原文核对；尚未实测。'])
    r.setdefault('sources',[{'label':r['brand']+' · 原文','url':r['url']}])
    if r.get('parentUrl'):r['sources'].append({'label':'关联活动报名页','url':r['parentUrl']})
    if r.get('eventTimeStale'):
        r['conditions'].append('活动时间沿用上次报名页记录；该时间来源本轮采集失败。')
    r['checked']='上次记录 · 本轮采集失败' if r['stale'] else '源文已采集 · 待实测'
    r['tags']=[r['category'],'待核对条件'] if r['type']=='event' else [r['category'],'原文线索']
    r['priority']=1 if r['sourceId']=='mlh-challenge' else 2 if r['sourceId']=='cursor' else 3 if r['sourceId']=='google' else 4
    r['format']='参与攻略' if r['type']=='event' else '操作演示 / 功能对照'
    r['audience']='AI 工具初学者' if r['type']=='event' else '对该工具有需求的读者'
    r['angle']='先核实能得到什么、谁能参与，再整理步骤和常见问题。' if r['type']=='event' else '先试一个普通读者能复现的任务，再判断是否值得做成教程。'
    r['summary']=r['summary'] or '已采集原文标题，具体能力和适用场景待整理。点击查看来源。'


def consume(archive, store=None):
    store=store or Store()
    manifest=json.loads((archive/'probe.json').read_text(encoding='utf-8'))
    stamp=manifest.get('stamp') or datetime.strptime(archive.name,'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC).isoformat()
    config={s['id']:s for s in json.loads((ROOT/'config/board-sources.json').read_text(encoding='utf-8'))}
    for probe in manifest['sources']:
        source={**config.get(probe['id'],{}),**probe}
        source['kind']=config.get(probe['id'],source).get('kind')
        if source.get('status')=='ok':
            try:
                rows=parse((archive/(source['id']+'.raw')).read_text(encoding='utf-8'),source)
                now=datetime.fromisoformat(stamp)
                # Fetch feeds broadly. Only new release candidates use a 30-day window.
                # Open/unknown events and undated items do not disappear at 72 hours.
                rows=[r for r in rows if r['type']=='event' or (not r.get('date') and (not r.get('publishedDay') or (now-timedelta(days=30)).date().isoformat()<=r['publishedDay']<=now.date().isoformat())) or (r.get('date') and now-timedelta(days=30)<=datetime.fromisoformat(r['date'])<=now)]
                source.update(parsed=len(rows),changes=store.ingest(rows,source,stamp))
            except Exception as exc:
                source.update(status='error',error=f'解析失败：{type(exc).__name__}: {exc}')
        elif not source.get('status'):
            source.update(status='error',error='本轮提前停止，未尝试采集')
        store.source(source,stamp)
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO runs VALUES(?,?)',(stamp,json.dumps(manifest,ensure_ascii=False)))
    bundle=store.bundle()
    bundle['meta']['networkHalted']=manifest.get('halted',False)
    write_bundle(bundle)
    (archive/'report.json').write_text(json.dumps(bundle['meta'],ensure_ascii=False,indent=2),encoding='utf-8')
    return bundle


def write_bundle(bundle):
    text='// Generated from archived source responses. Do not edit.\n'
    for key,value in [('META',bundle['meta']),('ITEMS',bundle['items']),('SOURCES',bundle['sources'])]:
        text+='window.BOARD_'+key+' = '+json.dumps(value,ensure_ascii=False).replace('<','\\u003c')+';\n'
    temp=BOARD/'board-data.tmp';temp.write_text(text,encoding='utf-8');temp.replace(BOARD/'board-data.js')


def refresh():
    settings=get_settings();stamp=datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    archive=data_root()/'board-runs'/stamp;archive.mkdir(parents=True,exist_ok=True)
    sources=json.loads((ROOT/'config/board-sources.json').read_text(encoding='utf-8'))
    requests=[]
    halted=False
    try:
        verify_tunnel(settings.proxy_url)
        fetcher=Fetcher(settings.proxy_url,archive)
        for s in sources:
            try:
                _,final=fetcher.fetch(s['url'],s['id']);s.update(status='ok',final_url=final)
            except Exception as exc:s.update(status='error',error=f'{type(exc).__name__}: {exc}')
            if fetcher.halted:break
        requests=fetcher.requests
        halted=fetcher.halted
    except Exception as exc:
        for s in sources:s.update(status='error',error=f'采集未启动：{exc}')
    (archive/'probe.json').write_text(json.dumps({'sources':sources,'requests':requests,'halted':halted},ensure_ascii=False,indent=2),encoding='utf-8')
    return consume(archive)
