import importlib.util
import json
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('board_server',Path(__file__).resolve().parents[1]/'scripts/serve_news_board.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ServerTests(unittest.TestCase):
    def test_refresh_is_local_authorized_and_single_flight(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),module.Handler)
        module.PORT=server.server_port
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        host=f'127.0.0.1:{module.PORT}'
        gate=threading.Event()
        def request(method,path,headers=None):
            conn=HTTPConnection('127.0.0.1',module.PORT,timeout=5)
            conn.request(method,path,headers=headers or {})
            result=conn.getresponse();status=result.status;body=result.read();conn.close()
            return status,json.loads(body)
        try:
            with patch.object(module,'refresh',side_effect=lambda:gate.wait(3)) as collect, patch.object(module.time,'monotonic',return_value=1.0), patch.object(module,'LAST_START',float('-inf')):
                self.assertEqual(request('GET','/api/status',{'Host':'evil.example'})[0],403)
                self.assertEqual(request('POST','/api/refresh',{'Origin':'https://evil.example','X-Board-Token':module.TOKEN})[0],403)
                self.assertEqual(request('POST','/api/refresh',{'Origin':'http://'+host})[0],403)
                headers={'Origin':'http://'+host,'X-Board-Token':module.TOKEN}
                self.assertEqual(request('POST','/api/refresh',headers)[0],202)
                self.assertTrue(request('GET','/api/status')[1]['running'])
                self.assertIn(request('POST','/api/refresh',headers)[0],[409,429])
                gate.set()
                for _ in range(30):
                    if not request('GET','/api/status')[1]['running']:break
                    time.sleep(.01)
                self.assertEqual(collect.call_count,1)
                self.assertFalse(request('GET','/api/status')[1]['running'])
                self.assertEqual(request('GET','/.env')[0],404)
        finally:
            gate.set();server.shutdown();server.server_close();worker.join()

if __name__=='__main__':unittest.main()
