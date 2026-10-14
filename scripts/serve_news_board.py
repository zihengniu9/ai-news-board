"""Loopback-only dashboard; manual refresh, no external posting or scheduler."""
from __future__ import annotations
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_news_pipeline.board import BOARD, Store, refresh
from ai_news_pipeline.media import MediaStore, refresh_media
from ai_news_pipeline.collection_lock import collection_lock
from ai_news_pipeline.runtime import schedule_health

PORT=8766
TOKEN=secrets.token_urlsafe(32)
LOCK=threading.Lock()
STATE={'running':False,'lastError':None,'lastFinished':None}
LAST_START=float('-inf')


def perform_refresh(media=False):
    try:
        with collection_lock():
            (refresh_media if media else refresh)();STATE['lastError']=None
    except Exception as exc:
        STATE['lastError']=f'{type(exc).__name__}: {exc}'
    finally:
        STATE.update(running=False,lastFinished=time.time());LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

    def allowed_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}

    def do_GET(self):
        if not self.allowed_host():return self.send_json(403,{'error':'Host not allowed'})
        path=urlsplit(self.path).path
        if path=='/api/board':return self.send_json(200,{**Store().bundle(),'refresh':STATE.copy(),'token':TOKEN})
        if path=='/api/media':return self.send_json(200,{**MediaStore().bundle(),'refresh':STATE.copy(),'token':TOKEN})
        if path=='/api/status':return self.send_json(200,{**STATE,'schedule':schedule_health()})
        files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/board-data.js':'board-data.js','/editorial-v2.css':'editorial-v2.css','/media-data.js':'media-data.js','/heat-math.js':'heat-math.js','/heat.js':'heat.js','/heat.css':'heat.css','/curation.js':'curation.js','/curation.css':'curation.css'}
        if path not in files:return self.send_json(404,{'error':'Not found'})
        target=BOARD/files[path]
        body=target.read_bytes()
        mime={'.html':'text/html','.js':'text/javascript','.css':'text/css'}[target.suffix]
        self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)

    def do_POST(self):
        global LAST_START
        if not self.allowed_host():return self.send_json(403,{'error':'Host not allowed'})
        if self.headers.get('Origin') not in {f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'}:
            return self.send_json(403,{'error':'Same-origin requests only'})
        if self.headers.get('X-Board-Token')!=TOKEN:return self.send_json(403,{'error':'Invalid token'})
        if self.path not in {'/api/refresh','/api/media/refresh'}:return self.send_json(404,{'error':'Not found'})
        if self.headers.get('Content-Length','0')!='0':return self.send_json(400,{'error':'Request body not accepted'})
        if time.monotonic()-LAST_START<60:return self.send_json(429,{'error':'请至少间隔一分钟后刷新'})
        if not LOCK.acquire(blocking=False):return self.send_json(409,{'error':'已有采集任务进行中'})
        LAST_START=time.monotonic();STATE.update(running=True,lastError=None)
        threading.Thread(target=perform_refresh,args=(self.path=='/api/media/refresh',),daemon=True).start()
        self.send_json(202,{'running':True})


if __name__=='__main__':
    print(f'AI news board: http://127.0.0.1:{PORT}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
