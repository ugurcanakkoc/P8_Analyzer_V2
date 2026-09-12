"""Belge sayfa önbelleği: izlenmemiş sayfaları pilot çalışmasına DOKUNMADAN hazırlar.

Regresyon pilotu (işaretli, incelemeli) değişmez. Burada hazırlanan sayfa yalnız geometri,
okuma sıralı kelime ve görüntü taşır; işaret, inceleme veya onay TAŞIMAZ. Kök:
`output/pagecache/<pdf_sha256>/`. Aynı PDF'nin her çalışması bu önbelleği paylaşır; PDF
değişirse hash değişir ve eski önbellek kullanılmaz.

Hazırlama kuyruğu tek arka plan iş parçacığıdır: PDF'yi bir kez açar, sayfa sayfa işler, her
sayfadan sonra durumu diske yazar. Durdurulabilir, kaldığı yerden devam eder, hatalı sayfa
yeniden denenebilir. Bir sayfanın hatası diğerlerini durdurmaz.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading

import pdfplumber
import pypdfium2

from .prepare import ROOT, digest, trace_page

FILES = ('geometry.json', 'raw_page.json', 'words.json', 'page.png')
PREVIEW_DPI = 40
STATES = ('NOT_PREPARED', 'QUEUED', 'PREPARING', 'PREPARED', 'FAILED')


def _now():
    return datetime.now(timezone.utc).isoformat()


class PageCache:
    def __init__(self, source_path, source_sha256, page_count, root=None):
        self.source = Path(source_path)
        self.sha = source_sha256
        self.page_count = int(page_count)
        self.root = (Path(root) if root else ROOT/'output'/'pagecache')/source_sha256
        self.lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._status = self._load()

    # ------------------------------------------------------------------ kalıcı durum
    def _load(self):
        path = self.root/'status.json'
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        data.setdefault('source_sha256', self.sha)
        data.setdefault('pages', {})
        data.setdefault('queue', [])
        # Önceki oturumda yarım kalan sayfa: kuyruğun başına geri alınır, "hazırlandı" SAYILMAZ.
        for key, entry in data['pages'].items():
            if entry.get('state') == 'PREPARING':
                entry.update(state='QUEUED', note='Önceki oturumda yarım kaldı; yeniden hazırlanacak.')
                if int(key) not in data['queue']:
                    data['queue'].insert(0, int(key))
        return data

    def _save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root/'status.json.tmp'
        tmp.write_text(json.dumps(self._status, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, self.root/'status.json')

    def _check(self, number):
        number = int(number)
        if not 1 <= number <= self.page_count:
            raise ValueError('Sayfa numarası belgede yok: %s' % number)
        return number

    def page_dir(self, number):
        return self.root/'pages'/str(self._check(number))

    # ------------------------------------------------------------------ okuma
    def state(self, number):
        with self.lock:
            return self.entry(number).get('state', 'NOT_PREPARED')

    def entry(self, number):
        with self.lock:
            number = self._check(number)
            entry = dict(self._status['pages'].get(str(number), {}))
            if entry.get('state') == 'PREPARED':
                missing = [f for f in FILES if not (self.page_dir(number)/f).is_file()]
                if missing:
                    # Diskteki eski PREPARED kaydı onarım kuyruğunu kilitlememeli.
                    # Okuma kalıcı durumu değiştirmez; yeniden deneme bunu kaydeder.
                    entry.update(state='FAILED', error='Önbellek dosyası eksik: ' + ', '.join(missing))
            return entry

    def prepared(self):
        """Hazırlanmış sayfalar ve boyutları. Dosyası eksik olan sayfa hazırlanmış SAYILMAZ."""
        with self.lock:
            out = {}
            for key, entry in self._status['pages'].items():
                if entry.get('state') != 'PREPARED':
                    continue
                folder = self.root/'pages'/key
                if all((folder/f).exists() for f in FILES):
                    out[int(key)] = (entry['width'], entry['height'])
            return out

    def file(self, number, name, verify=False):
        """Hazırlanmış sayfanın bir dosyası. Yol önbellek kökünün DIŞINA çıkamaz."""
        if name not in FILES:
            raise ValueError('Geçersiz önbellek dosyası: ' + str(name))
        number = self._check(number)
        entry = self.entry(number)
        if entry.get('state') != 'PREPARED':
            raise ValueError('Sayfa %s hazırlanmadı.' % number)
        path = (self.page_dir(number)/name).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError('Geçersiz önbellek yolu.')
        if verify and digest(path) != entry['sha256'][name]:
            raise ValueError('Önbellek dosyası değişmiş: sayfa %s / %s' % (number, name))
        return path

    def preview(self, number):
        """Küçük önizleme — HER sayfa için, hazırlanmadan da. Bir kez üretilir, sonra diskten."""
        number = self._check(number)
        path = self.root/'previews'/('%d.png' % number)
        with self.lock:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                doc = pypdfium2.PdfDocument(str(self.source))
                try:
                    doc[number-1].render(scale=PREVIEW_DPI/72).to_pil().save(path)
                finally:
                    doc.close()
        return path

    def snapshot(self):
        with self.lock:
            counts = {s: 0 for s in STATES}
            for n in range(1, self.page_count+1):
                counts[self.state(n)] += 1
            failed = [dict(page=n, error=self.entry(n).get('error'))
                      for n in range(1, self.page_count+1) if self.state(n) == 'FAILED']
            return dict(counts=counts, queue=list(self._status['queue']),
                        running=bool(self._thread and self._thread.is_alive()),
                        stopped=self._stop.is_set(), failed=failed,
                        current=next((int(k) for k, e in self._status['pages'].items()
                                      if e.get('state') == 'PREPARING'), None))

    # ------------------------------------------------------------------ kuyruk
    def enqueue(self, pages, front=False):
        """Sayfaları kuyruğa ekle. Hazırlanmış sayfa tekrar hazırlanmaz. `front`: seçilen sayfa önce."""
        with self.lock:
            wanted = [self._check(n) for n in pages]
            added = []
            for n in wanted:
                if self.state(n) in ('PREPARED', 'PREPARING'):
                    continue
                if n in self._status['queue']:
                    if front:
                        self._status['queue'].remove(n)
                    else:
                        continue
                if front:
                    self._status['queue'].insert(len(added), n)
                else:
                    self._status['queue'].append(n)
                self._status['pages'][str(n)] = dict(self._status['pages'].get(str(n), {}),
                                                     state='QUEUED', queued_utc=_now())
                added.append(n)
            self._save()
        self.resume()
        return added

    def stop(self):
        """Şu anki sayfa bitince durur. Kuyruk silinmez; `resume` kaldığı yerden devam eder."""
        self._stop.set()
        return self.snapshot()

    def resume(self):
        with self.lock:
            self._stop.clear()
            if self._status['queue'] and not (self._thread and self._thread.is_alive()):
                self._thread = threading.Thread(target=self._worker, name='uvp-pagecache', daemon=True)
                self._thread.start()
        return self.snapshot()

    def retry(self, number):
        number = self._check(number)
        with self.lock:
            if self.state(number) != 'FAILED':
                raise ValueError('Sayfa %s hatalı değil; yeniden deneme gerekmez.' % number)
            self._status['pages'][str(number)]['state'] = 'NOT_PREPARED'
        return self.enqueue([number], front=True)

    def wait(self, timeout=None):
        """Testler ve komut satırı için: kuyruk boşalana veya durdurulana kadar bekle."""
        thread = self._thread
        if thread:
            thread.join(timeout)
        return self.snapshot()

    def _worker(self):
        if digest(self.source) != self.sha:
            with self.lock:
                for n in self._status['queue']:
                    self._status['pages'][str(n)] = dict(state='FAILED', error='Kaynak PDF değişmiş; '
                                                         'önbellek bu belgeye ait değil.', utc=_now())
                self._status['queue'] = []
                self._save()
            return
        with pdfplumber.open(self.source) as pdf:
            while not self._stop.is_set():
                with self.lock:
                    if not self._status['queue']:
                        return
                    number = self._status['queue'].pop(0)
                    self._status['pages'][str(number)] = dict(state='PREPARING', started_utc=_now())
                    self._save()
                try:
                    info = trace_page(pdf.pages[number-1], self.page_dir(number))
                    entry = dict(state='PREPARED', utc=_now(),
                                 sha256={f: digest(self.page_dir(number)/f) for f in FILES},
                                 render_bbox=info['render_bbox'], width=info['width'],
                                 height=info['height'], segments=info['segments'],
                                 rotation=info['rotation'])
                except Exception as exc:                     # noqa: BLE001 — sayfa hatası kuyruğu durdurmaz
                    entry = dict(state='FAILED', utc=_now(), error='%s: %s' % (type(exc).__name__, exc))
                with self.lock:
                    self._status['pages'][str(number)] = entry
                    self._save()
