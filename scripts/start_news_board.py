"""Idempotent hidden login launcher; never terminates an unrelated listener."""
from pathlib import Path
import http.client
import json
import socket
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
def start():
    try:
        c=http.client.HTTPConnection('127.0.0.1',8766,timeout=3)
        c.request('GET','/api/status');r=c.getresponse();body=json.loads(r.read());c.close()
        if r.status==200 and 'running' in body:return
        raise RuntimeError('8766 端口被其它服务占用，未启动')
    except (ConnectionRefusedError,TimeoutError,OSError):
        pass
    subprocess.Popen([sys.executable,str(root/'scripts/serve_news_board.py')],cwd=root,
                     creationflags=subprocess.CREATE_NO_WINDOW)

if __name__=='__main__':start()
