"""Loopback-only review UI; no production export, arbitrary file route or remote API."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlparse, parse_qs

from .service import Pilot
from .prepare import ROOT

STATIC=Path(__file__).parent/'static'


def make_server(pilot,port=8765):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def allowed(self):
            return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']

        def send(self,code,body,mime='application/json; charset=utf-8'):
            if isinstance(body,(dict,list)):
                body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            if isinstance(body,str):
                body=body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                return self.send(403,{'error':'Yalnız yerel erişim.'})
            url=urlparse(self.path)
            try:
                if url.path=='/api/state':
                    return self.send(200,dict(pilot.state(),csrf_token=token))
                if url.path=='/api/trace':
                    pid=parse_qs(url.query).get('pin',[''])[0]
                    return self.send(200,pilot.trace(pid))
                query=parse_qs(url.query)
                if url.path=='/api/candidates':
                    return self.send(200,pilot.candidates(query.get('template',[''])[0]))
                if url.path=='/api/path':
                    return self.send(200,pilot.path(query.get('pin',[''])[0]))
                if url.path in ('/api/coverage','/api/continuations','/api/table','/api/todo',
                                '/api/dash','/api/overview'):
                    page=query.get('page',[None])[0]
                    handler={'/api/coverage':pilot.coverage,'/api/continuations':pilot.continuations,
                             '/api/table':pilot.table,'/api/todo':pilot.todo,
                             '/api/dash':pilot.dash_proposals,'/api/overview':pilot.overview}[url.path]
                    return self.send(200,handler(int(page) if page and page.isdigit() else None))
                if url.path=='/api/library/candidates':
                    page=query.get('page',[None])[0]
                    return self.send(200,pilot.library_candidates(query.get('entry',[''])[0],
                                                                  int(page) if page and page.isdigit() else None))
                for path,handler in (('/api/crossrefs',pilot.cross_references),('/api/endpoints',pilot.endpoints),
                                     ('/api/effort',pilot.effort),('/api/reviews',pilot.review_status),
                                     ('/api/library',pilot.library_entries)):
                    if url.path==path:
                        return self.send(200,handler())
                if url.path=='/page.png':
                    number=query.get('page',[''])[0]
                    number=int(number) if number.isdigit() else pilot.manifest['physical_page']
                    if number not in pilot.pages():
                        return self.send(404,{'error':'Bu çalışmada izlenmeyen sayfa.'})
                    name='page.png' if number==pilot.manifest['physical_page'] else 'pages/%s/page.png'%number
                    return self.send(200,pilot._artifact(name).read_bytes(),'image/png')
                assets={'/':(STATIC/'durum.html','text/html; charset=utf-8'),
                        '/ayrinti':(STATIC/'index.html','text/html; charset=utf-8'),
                        '/durum.js':(STATIC/'durum.js','text/javascript; charset=utf-8'),
                        '/durum.css':(STATIC/'durum.css','text/css; charset=utf-8'),
                        '/app.js':(STATIC/'app.js','text/javascript; charset=utf-8'),
                        '/style.css':(STATIC/'style.css','text/css; charset=utf-8'),
                        }
                if url.path in assets:
                    path,mime=assets[url.path]
                    return self.send(200,path.read_bytes(),mime)
                self.send(404,{'error':'Bulunamadı.'})
            except (ValueError,KeyError) as e:
                self.send(400,{'error':str(e)})
            except Exception:
                self.send(500,{'error':'Yerel işlem başarısız. Sunucuyu yeniden başlatın; kanıt dosyalarını kontrol edin.'})

        def do_POST(self):
            if not self.allowed():
                return self.send(403,{'error':'Yalnız yerel erişim.'})
            origin=self.headers.get('Origin')
            expected='http://'+self.headers.get('Host','')
            if origin!=expected or not secrets.compare_digest(self.headers.get('X-Pilot-Token',''),token):
                return self.send(403,{'error':'Geçersiz yerel işlem kaynağı.'})
            if self.path not in ('/api/pins','/api/boxes','/api/reviews','/api/library','/api/library/update'):
                return self.send(404,{'error':'Bulunamadı.'})
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('Aktarım biçimi desteklenmiyor.')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384 or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise ValueError('Geçersiz veri boyutu veya biçimi.')
                body=json.loads(self.rfile.read(length))
                handler={'/api/pins':pilot.change,'/api/boxes':pilot.change_box,
                         '/api/reviews':pilot.add_review,'/api/library':pilot.library_save,
                         '/api/library/update':pilot.library_update}[self.path]
                self.send(200,handler(body))
            except (ValueError,KeyError,TypeError) as e:
                self.send(400,{'error':str(e)})
            except Exception:
                self.send(500,{'error':'Kayıt yapılamadı.'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,default=ROOT/'output/pilots/E122/20260910_v3_p05_rev8')
    p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    server=make_server(Pilot(args.run),args.port)
    print(f'UVP pilot: http://127.0.0.1:{server.server_port} — üretim/import kapalı',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
