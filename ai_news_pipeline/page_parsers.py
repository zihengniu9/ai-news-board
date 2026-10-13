"""Extract published page content. No campaign-specific copy or inferred publication times."""
import html
import json
import re
from datetime import datetime
from urllib.parse import urljoin

def anthropic(raw,source):
    from .board import plain,record,date
    rows={}
    for a in re.findall(r'<a\b[^>]*>.*?</a>',raw,re.S|re.I):
        href=re.search(r'href="([^"]+)"',a)
        stamp=re.search(r'<time\b[^>]*>(.*?)</time>',a,re.S)
        title=re.search(r'<h[234]\b[^>]*>(.*?)</h[234]>',a,re.S) or re.search(r'<span\b[^>]*class="[^"]*__title[^\"]*"[^>]*>(.*?)</span>',a,re.S)
        if not (href and stamp and title):continue
        desc=re.search(r'<p\b[^>]*>(.*?)</p>',a,re.S)
        row=record(source,title[1],urljoin(source['url'],html.unescape(href[1])),summary=desc[1] if desc else '')
        try:row['publishedDay']=datetime.strptime(plain(stamp[1]),'%b %d, %Y').date().isoformat()
        except ValueError:row['publishedDay']=None
        row['datePrecision']='day';row['dateBasis']='页面只给出发布日期，未给出发布时间与时区。'
        if row['id'] not in rows or row['summary']:rows[row['id']]=row
    if not rows:raise ValueError('Anthropic 页面未找到带日期的新闻条目')
    return list(rows.values())

def mlh_event(raw,source):
    from .board import plain,record,date
    if source['kind']=='mlh-challenge':
        match=re.search(r'<script\b[^>]*data-page="app"[^>]*>(.*?)</script>',raw,re.S)
        if not match:raise ValueError('MLH 挑战页结构已变化；不复用旧活动文案')
        props=json.loads(match[1]).get('props',{});c=props.get('challenge',{})
        title=c.get('name');description=c.get('descriptionHtml','')
        if not title or not description:raise ValueError('挑战标题或正文缺失')
        row=record(source,title,source['url'],summary=plain(c.get('shortDescriptionHtml','')))
        row['facts']=[plain(p) for p in re.findall(r'<(?:p|li)\b[^>]*>(.*?)</(?:p|li)>',description,re.S) if plain(p)][:15]
        row['sourceDescription']=plain(description)
        row['conditions']=['赠送权益、参与资格、兑换期限和续费条件需分别核对原文、活动邮件及结算页。']
        if source.get('eventSlug') and props.get('eventSlug')==source['eventSlug'] and source.get('parentUrl'):
            row['parentUrl']=source['parentUrl']
        else:row['conditions'].append('此挑战尚未绑定已核验的活动时段。')
    else:
        title=re.search(r'<h1\b[^>]*>(.*?)</h1>',raw,re.S|re.I)
        if not title:raise ValueError('活动页面标题缺失')
        section=re.search(r'Event Description\s*</[^>]+>(.*?)(?:<h[1-6]|Who can attend)',raw,re.S|re.I)
        desc=plain(section[1])[:1500] if section else ''
        row=record(source,title[1],source['url'],summary=desc[:450])
        row['facts']=[desc] if desc else ['活动页面已读取，介绍正文未提取；请查看原文。']
        row['conditions']=['活动结束时间不等于优惠兑换截止时间；资格与权益需核对当前页面。']
        for key,prop in [('start','startDate'),('end','endDate')]:
            m=re.search(r'<meta\b[^>]*itemprop="'+prop+r'"[^>]*content="([^"]+)"',raw,re.I)
            row[key]=date(m[1]) if m else None
    row.update(type='event',category='活动福利',redeemEnd=None)
    row.setdefault('start',None);row.setdefault('end',None)
    return [row]

def mlh_index(raw,source):
    from .board import plain,record
    rows={}
    pattern=r'([A-Z][a-z]+) (\d{1,2})(?:st|nd|rd|th)?\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})'
    for a in re.findall(r'<a\b[^>]*>.*?</a>',raw,re.S|re.I):
        href=re.search(r'href="([^"]+)"',a);text=plain(a);period=re.search(pattern,text)
        if not href or '/events/' not in href[1] or not period:continue
        title=text[:period.start()].strip();description=text[period.end():].replace('Learn More >','').strip()
        row=record(source,title,urljoin(source['url'],href[1]),summary=description)
        month=datetime.strptime(period[1],'%B').month;year=int(period[4])
        row.update(type='event',periodStart=f'{year:04}-{month:02}-{int(period[2]):02}',periodEnd=f'{year:04}-{month:02}-{int(period[3]):02}',start=None,end=None,redeemEnd=None,
                   dateBasis='活动列表仅提供日期范围，未提供时区和精确时刻；不用于精确倒计时。')
        rows[row['id']]=row
    if not rows:raise ValueError('MLH 首页未找到有效活动卡片')
    return list(rows.values())
