"""Bounded HTTP collection through the existing, verified TUN/proxy path."""
from __future__ import annotations

import subprocess
import os
import hashlib
from email.parser import Parser
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

from .network import build_url_opener, verify_proxy_listener

AGENT = 'AIEditorialBoard/1.0'
NO_WINDOW = getattr(subprocess,'CREATE_NO_WINDOW',0)
CURL = str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/curl.exe')
_schannel_verified = False


def direct_mode() -> bool:
    """Cloud runners (GitHub Actions) reach sources directly; no local TUN or proxy exists there."""
    return os.environ.get('AI_NEWS_NETWORK', 'tun') == 'direct'


def verify_tunnel(proxy_url: str) -> dict:
    if direct_mode():
        return {'tunnel':None,'verified':False,'transport':'direct HTTPS (cloud runner)'}
    result = subprocess.run(['route', 'print', '0.0.0.0'], capture_output=True, timeout=10,stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
    route = result.stdout.decode('utf-8', 'replace')
    # This workstation's installed Meta TUN must own an active default route.
    if result.returncode or 'Meta Tunnel' not in route or not any(
        '0.0.0.0' in line and '198.18.' in line for line in route.splitlines()
    ):
        raise RuntimeError('未检测到本机 Meta TUN 的有效默认路由；本次不发起网络采集')
    verify_proxy_listener(proxy_url)
    return {'tunnel':'Meta Tunnel','verified':True,'transport':'HTTPS via configured HTTP proxy'}


class Fetcher:
    def __init__(self, proxy_url: str, archive: Path):
        global _schannel_verified
        self.proxy_url=proxy_url
        self.native_tls=os.name=='nt' and not direct_mode() and os.environ.get('AI_NEWS_TLS_BACKEND','schannel')=='schannel'
        if self.native_tls and not _schannel_verified:
            if 'Schannel' not in subprocess.check_output([CURL,'--version'],text=True,stdin=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=NO_WINDOW):
                raise RuntimeError('当前 curl 不支持 Schannel；未降低 TLS 校验要求')
            _schannel_verified=True
        self.archive = archive
        archive.mkdir(parents=True, exist_ok=True)
        self.robots = {}
        self.halted = False
        self.requests = []
        owner = self
        class CheckedRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
                if new.scheme != 'https' or (old.scheme,old.netloc)!=(new.scheme,new.netloc):
                    raise PermissionError('跨站或非 HTTPS 跳转需单独核验，已停止')
                if old.path != '/robots.txt':
                    policy=owner.robots.get(f'{new.scheme}://{new.netloc}')
                    if policy is None or not policy.can_fetch(AGENT,newurl):
                        raise PermissionError('robots.txt 未允许跳转后的路径')
                return super().redirect_request(req,fp,code,msg,headers,newurl)
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({} if direct_mode() else {'https':proxy_url}), CheckedRedirect())

    def request(self, url: str) -> tuple[bytes, str]:
        if self.halted:
            raise RuntimeError('本轮网络采集已停止：瞬态错误重试仍失败')
        if urllib.parse.urlsplit(url).scheme != 'https':
            raise ValueError('采集仅允许 HTTPS')
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={'User-Agent':AGENT, 'Accept':'application/xml,text/xml,text/html,application/json;q=0.8,*/*;q=0.5'})
                if self.native_tls:
                    raw,final,status=self.schannel(url)
                    self.requests.append({'url':url,'status':status,'attempt':attempt+1,'tls':'Windows Schannel'})
                    return raw,final
                with self.opener.open(req, timeout=25) as response:
                    raw = response.read(8_000_001)
                    if len(raw) > 8_000_000:
                        raise ValueError('页面超过 8MB，已停止读取')
                    final = response.geturl()
                    if urllib.parse.urlsplit(final).scheme != 'https':
                        raise ValueError('页面跳转到非 HTTPS 地址')
                    self.requests.append({'url':url,'status':response.status,'attempt':attempt+1})
                    return raw, final
            except Exception as exc:
                transient = isinstance(exc, (TimeoutError, ConnectionResetError)) or isinstance(exc, urllib.error.HTTPError) and exc.code in {502,503,504}
                if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, ConnectionResetError)):
                    transient = True
                self.requests.append({'url':url,'error':str(exc),'attempt':attempt+1})
                if transient and attempt == 0:
                    time.sleep(1)
                    continue
                if transient and attempt == 1:
                    self.halted = True
                raise
        raise RuntimeError('request exhausted')

    def schannel(self,url):
        original=url
        for _ in range(6):
            key=hashlib.sha256(url.encode()).hexdigest()[:16]
            body=self.archive/(key+'.http-body');headers=self.archive/(key+'.http-headers')
            result=subprocess.run([CURL,'--silent','--show-error','--proto','=https','--max-time','25',
                '--max-filesize','8000000','--proxy',self.proxy_url,'--user-agent',AGENT,
                '--dump-header',str(headers),'--output',str(body),'--write-out','%{http_code}',url],
                capture_output=True,timeout=30,stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
            if result.returncode:
                msg=result.stderr.decode('utf-8','replace').strip()
                if result.returncode==28:raise TimeoutError(msg)
                raise RuntimeError('Schannel HTTPS 校验/请求失败：'+msg)
            status=int(result.stdout.decode().strip())
            blocks=headers.read_text(encoding='iso-8859-1').split('\n\n')
            block=next((b for b in reversed(blocks) if b.startswith('HTTP/')),'')
            fields=Parser().parsestr(block.partition('\n')[2])
            if status in {301,302,303,307,308}:
                target=urllib.parse.urljoin(url,fields.get('Location',''))
                a,b=urllib.parse.urlsplit(url),urllib.parse.urlsplit(target)
                if b.scheme!='https' or a.netloc!=b.netloc:raise PermissionError('跨站跳转需单独配置核验：'+target)
                if a.path!='/robots.txt':
                    policy=self.robots.get(f'{b.scheme}://{b.netloc}')
                    if policy is None or not policy.can_fetch(AGENT,target):raise PermissionError('robots.txt 未允许跳转路径')
                url=target;continue
            if status>=400:raise urllib.error.HTTPError(url,status,'HTTP '+str(status),fields,None)
            if status!=200:raise ValueError('非预期 HTTP 状态：'+str(status))
            return body.read_bytes(),url,status
        raise ValueError('跳转次数超过上限：'+original)

    def fetch(self, url: str, name: str) -> tuple[str, str]:
        parts = urllib.parse.urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                raw, _ = self.request(origin + '/robots.txt')
                parser.parse(raw.decode('utf-8', 'replace').splitlines())
            except urllib.error.HTTPError as exc:
                if exc.code in {404,410}:
                    parser.parse([])
                else:
                    self.robots[origin] = None
                    raise RuntimeError(f'robots.txt 无法核验：HTTP {exc.code}') from exc
            except Exception:
                self.robots[origin] = None
                raise
            self.robots[origin] = parser
        parser = self.robots[origin]
        if parser is None or not parser.can_fetch(AGENT, url):
            raise PermissionError('robots.txt 未允许此采集路径，已跳过')
        delay = parser.crawl_delay(AGENT)
        if delay:
            if delay > 30:
                raise PermissionError('该来源要求较长抓取间隔，留待单独调度')
            time.sleep(delay)
        raw, final = self.request(url)
        self.archive.joinpath(name + '.raw').write_bytes(raw)
        return raw.decode('utf-8', 'replace'), final
