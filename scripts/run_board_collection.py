"""One bounded collection cycle. Task Scheduler invokes this every four hours."""
from pathlib import Path
import sys,json
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_news_pipeline.runtime import data_root
from ai_news_pipeline.collection_lock import collection_lock
from ai_news_pipeline.settings import get_settings
from ai_news_pipeline.board_network import verify_tunnel
from ai_news_pipeline.board import refresh
from ai_news_pipeline.media import refresh_media
from ai_news_pipeline.backup import daily_backup
from build_site_data import build_site_data

def run():
    root=data_root();root.mkdir(parents=True,exist_ok=True)
    report={'startedAt':datetime.now(timezone.utc).isoformat(),'status':'running'}
    exit_code=0
    try:
        with collection_lock():
            verify_tunnel(get_settings().proxy_url)
            products=refresh();report['products']=products['meta']
            if products['meta'].get('networkHalted'):raise RuntimeError('产品采集遇到瞬态故障，重试仍失败；本轮停止，不继续媒体网络采集')
            media=refresh_media();report['media']={'success':sum(s['status']=='ok' for s in media['sources']),'total':len(media['sources'])}
            if not report['media']['success']:raise RuntimeError('本轮没有媒体来源成功；请检查本轮 source/report 记录')
            if not products['meta']['sourceSuccess']:raise RuntimeError('本轮没有产品来源成功；请检查本轮 source/report 记录')
            report['status']='completed'
    except Exception as e:
        report.update(status='failed',error=f'{type(e).__name__}: {e}');exit_code=1
    # Backup runs even when collection fails: it protects what is already stored.
    try:report['backup']=daily_backup()
    except Exception as e:
        report['backup']={'status':'failed','error':f'{type(e).__name__}: {e}'};exit_code=1
    report['finishedAt']=datetime.now(timezone.utc).isoformat()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    logs=root/'scheduled-runs';logs.mkdir(exist_ok=True)
    (logs/(stamp+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:build_site_data()
    except Exception as e:print('页面数据重建失败：',e,file=sys.stderr);exit_code=1
    return exit_code

if __name__=='__main__':sys.exit(run())
