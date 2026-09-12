"""Loopback-only review UI; no production export, arbitrary file route or remote API."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlparse, parse_qs

from .service import Pilot
from .prepare import ROOT, open_pdf
from .pagecache import PageCache

STATIC=Path(__file__).parent/'static'


def make_server(pilot,port=8765):
    token=secrets.token_urlsafe(32)
    # Açık belge çalışırken değişebilir: PDF seçildiğinde yeni Pilot ve yeni sayfa önbelleği
    # devreye girer. Eski belgenin işaretleri kendi klasöründe kalır, karışmaz.
    session={'pilot':pilot,'known':{str(Path(pilot.run).resolve())}}

    def current():
        return session['pilot']

    def document_row(run):
        try:
            manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):
            return None
        source=Path(manifest.get('source_path',''))
        marks=None
        try:
            # Son belgeler listesini okumak eski çalışmalarda şema migrasyonu/yazma yapmamalı.
            path=(run/'annotations.sqlite3').resolve()
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                marks=sum(bool(json.loads(body).get('active',True))
                          for (body,) in db.execute('SELECT body FROM pins'))
        except Exception:                      # noqa: BLE001 — liste satırı yüzünden ekran düşmez
            pass
        return dict(run=str(run),name=source.name,path=str(source),
                    sha256=manifest.get('source_sha256'),page_count=manifest.get('page_count'),
                    mode=manifest.get('mode'),marks=marks,missing_source=not source.exists())

    def document_info(payload=None):
        pilot_now=current()
        row=document_row(pilot_now.run) or {}
        counts=pilot_now.page_index()['counts']

        # Aynı PDF'in birden çok çalışması olabilir (işaretli pilot + yeni açılan). Hepsi listelenir;
        # açık olan işaretleriyle birlikte kendi klasöründe kalır.
        # Listede kullanıcının açtığı belgeler ve ŞU AN açık çalışma durur; eski geliştirme
        # pilotları listeyi kalabalıklaştırmaz (açıkken görünür).
        folders=[d for d in (ROOT/'output'/'documents').glob('*') if d.is_dir()]
        folders+= [Path(d) for d in session['known']]
        folders.append(Path(pilot_now.run))
        recent=[r for r in (document_row(d) for d in sorted({Path(d).resolve() for d in folders})) if r]
        return dict(current=dict(row,counts=counts,marks=len(pilot_now.pins)),recent=recent,
                    note='PDF değiştirmek yeni bir çalışma klasörü açar; işaretler belgeye bağlıdır.')

    def open_document(payload):
        payload=payload or {}
        path,folder=payload.get('path',''),payload.get('run','')
        if folder:
            # Var olan çalışma klasörü: işaretleri ve incelemeleriyle birlikte açılır.
            run=Path(folder).resolve()
            allowed=[(ROOT/'output'/'documents').resolve(),(ROOT/'output'/'pilots').resolve()]
            if not any(root in run.parents for root in allowed) or not (run/'manifest.json').exists():
                raise ValueError('Bilinmeyen çalışma klasörü: %s'%folder)
        elif path:
            run=open_pdf(path)
        else:
            raise ValueError('PDF yolu veya çalışma klasörü gerekir.')
        fresh=Pilot(run)
        fresh.cache=PageCache(fresh.manifest['source_path'],fresh.manifest['source_sha256'],
                              fresh.manifest['page_count'])
        session['pilot']=fresh
        session['known'].add(str(Path(run).resolve()))
        return document_info()

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
                    return self.send(200,dict(current().state(),csrf_token=token))
                if url.path=='/api/trace':
                    pid=parse_qs(url.query).get('pin',[''])[0]
                    return self.send(200,current().trace(pid))
                query=parse_qs(url.query)
                if url.path=='/api/candidates':
                    return self.send(200,current().candidates(query.get('template',[''])[0]))
                if url.path=='/api/path':
                    return self.send(200,current().path(query.get('pin',[''])[0]))
                if url.path=='/api/documents':
                    return self.send(200,document_info())
                if url.path=='/api/pages':
                    return self.send(200,current().page_index())
                if url.path=='/api/prepare':
                    if current().cache is None:
                        return self.send(404,{'error':'Sayfa önbelleği kapalı.'})
                    return self.send(200,current().cache.snapshot())
                if url.path=='/preview.png':
                    number=query.get('page',[''])[0]
                    if current().cache is None or not number.isdigit():
                        return self.send(404,{'error':'Önizleme yok.'})
                    return self.send(200,current().cache.preview(int(number)).read_bytes(),'image/png')
                if url.path in ('/api/coverage','/api/continuations','/api/table','/api/todo',
                                '/api/dash','/api/overview','/api/relations','/api/page_model'):
                    page=query.get('page',[None])[0]
                    handler={'/api/coverage':current().coverage,'/api/continuations':current().continuations,
                             '/api/table':current().table,'/api/todo':current().todo,
                             '/api/dash':current().dash_proposals,'/api/overview':current().overview,
                             '/api/relations':current().relations,'/api/page_model':current().page_model}[url.path]
                    return self.send(200,handler(int(page) if page and page.isdigit() else None))
                if url.path=='/api/propose':
                    page=query.get('page',[None])[0]
                    point=query.get('point',[''])[0]
                    box=query.get('bbox',[''])[0]
                    drop=query.get('exclude',[''])[0]
                    return self.send(200,current().propose_symbol(
                        int(page) if page and page.isdigit() else None,
                        point=[float(v) for v in point.split(',')] if point else None,
                        bbox=[float(v) for v in box.split(',')] if box else None,
                        exclude=[v for v in drop.split(',') if v.strip()]))
                if url.path=='/api/similar':
                    pages=query.get('pages',['ALL'])[0]
                    return self.send(200,current().similar(
                        query.get('template',[''])[0],
                        'ALL' if pages in ('','ALL') else [int(n) for n in pages.split(',') if n.strip()]))
                if url.path=='/api/library/candidates':
                    page=query.get('page',[None])[0]
                    return self.send(200,current().library_candidates(query.get('entry',[''])[0],
                                                                  int(page) if page and page.isdigit() else None))
                for path,handler in (('/api/crossrefs',current().cross_references),('/api/endpoints',current().endpoints),
                                     ('/api/effort',current().effort),('/api/reviews',current().review_status),
                                     ('/api/library',current().library_entries)):
                    if url.path==path:
                        return self.send(200,handler())
                if url.path=='/page.png':
                    number=query.get('page',[''])[0]
                    number=int(number) if number.isdigit() else current().manifest['physical_page']
                    if number not in current().viewable_pages():
                        return self.send(404,{'error':'Bu sayfa hazırlanmadı.'})
                    return self.send(200,current().page_file(number,'page.png').read_bytes(),'image/png')
                assets={'/':(STATIC/'durum.html','text/html; charset=utf-8'),
                        '/isaret':(STATIC/'isaret.html','text/html; charset=utf-8'),
                        '/isaret.js':(STATIC/'isaret.js','text/javascript; charset=utf-8'),
                        '/isaret.css':(STATIC/'isaret.css','text/css; charset=utf-8'),
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
            if self.path not in ('/api/pins','/api/boxes','/api/reviews','/api/library','/api/library/update',
                                 '/api/prepare','/api/mark','/api/package','/api/open'):
                return self.send(404,{'error':'Bulunamadı.'})
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('Aktarım biçimi desteklenmiyor.')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384 or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise ValueError('Geçersiz veri boyutu veya biçimi.')
                body=json.loads(self.rfile.read(length))
                handler={'/api/pins':current().change,'/api/boxes':current().change_box,
                         '/api/reviews':current().add_review,'/api/library':current().library_save,
                         '/api/library/update':current().library_update,
                         '/api/prepare':current().prepare_request,
                         '/api/mark':current().apply_mark,
                         '/api/package':current().package_request,
                         '/api/open':open_document}[self.path]
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
    probe=Pilot(args.run)
    # Sayfa önbelleği aynı PDF'nin hash'ine bağlıdır; pilot çalışmasına yazmaz.
    cache=PageCache(probe.manifest['source_path'],probe.manifest['source_sha256'],
                    probe.manifest['page_count'])
    probe.cache=cache
    server=make_server(probe,args.port)
    print(f'UVP pilot: http://127.0.0.1:{server.server_port} — üretim/import kapalı',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__=='__main__':
    main()
