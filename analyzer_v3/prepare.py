"""Create a new, isolated pilot run; never overwrite customer/prior artifacts."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil

import pdfplumber

from .document import build_index

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '13SB003_05_+E122' / '=112=122=132=152=170.pdf'
KNOWN_HASH = '22a290d625b550f0c0d8af4433d4a6d1d7460ced27e2aba26c7ebce9d59546f7'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def display_point(point, bbox):
    # pdfplumber has already applied /Rotate: do NOT rotate these points again.
    return [round(point[0]-bbox[0], 4), round(point[1]-bbox[1], 4)]


def original_point(point, bbox):
    return [point[0]+bbox[0], point[1]+bbox[1]]


def oriented_words(page):
    """Rotated EPLAN labels come back reversed; fix the reading order from the glyph matrix.

    The raw string is kept as raw_text and every rotated word is flagged, so nothing is
    silently rewritten. An undecidable rotation keeps the raw order and says so.
    """
    chars = page.chars
    out = []
    for w in page.extract_words(extra_attrs=['upright']):
        if w.get('upright', True):
            out.append(dict(w, raw_text=w['text'], rotated=False))
            continue
        inside = [c for c in chars if w['x0']-.5 <= c['x0'] <= w['x1']+.5
                  and w['top']-.5 <= c['top'] <= w['bottom']+.5 and c.get('matrix')]
        signs = {1 if c['matrix'][1] > 0 else -1 if c['matrix'][1] < 0 else 0 for c in inside}
        if signs == {1}:      # 90° counter-clockwise: PDF char order runs bottom-to-top.
            out.append(dict(w, text=w['text'][::-1], raw_text=w['text'], rotated=True, rotation='CCW'))
        elif signs == {-1}:
            out.append(dict(w, raw_text=w['text'], rotated=True, rotation='CW'))
        else:
            out.append(dict(w, raw_text=w['text'], rotated=True, rotation='UNKNOWN'))
    return out


def trace_page(page, folder):
    """Write the raw objects, the normalised line list and the 300 DPI image of one sheet."""
    folder.mkdir(parents=True, exist_ok=True)
    render = page.to_image(resolution=300, force_mediabox=True)
    bbox = list(render.bbox)
    render.original.save(folder/'page.png')
    write_json(folder/'raw_page.json',
               dict(words=page.extract_words(), lines=page.lines, curves=page.curves, rects=page.rects,
                    images=[{k: v for k, v in i.items() if k != 'stream'} for i in page.images]))
    # Reading-order words are a separate artifact: raw_page.json keeps the untouched extraction,
    # words.json carries the rotated labels the right way round with their raw string.
    write_json(folder/'words.json', dict(words=oriented_words(page),
                                         note='Döndürülmüş yazılar glif matrisine göre çevrildi; '
                                              'ham metin raw_text alanında.'))
    segments = []
    for i, line in enumerate(page.lines):
        points = line.get('pts', [])
        if len(points) != 2:
            continue  # Retained in raw_page.json, not interpreted.
        dash = line.get('dash')
        segments.append(dict(id=f'line:{i}', a=display_point(points[0], bbox), b=display_point(points[1], bbox),
                             dash=bool(dash and dash[0]), linewidth=line.get('linewidth'),
                             source='raw_page.json/lines/'+str(i)))
    # The point list is kept: two different shapes can share one bounding box, so the box alone
    # is not shape evidence.
    curves = [dict(id=f'curve:{i}', bbox=display_point([c['x0'], c['top']], bbox)+display_point([c['x1'], c['bottom']], bbox),
                   points=[display_point(p, bbox) for p in c.get('pts', [])],
                   fill=bool(c.get('fill')), stroke=bool(c.get('stroke')), linewidth=c.get('linewidth'),
                   source='raw_page.json/curves/'+str(i))
              for i, c in enumerate(page.curves)]
    write_json(folder/'geometry.json',
               dict(segments=segments, curves=curves,
                    unsupported_objects=dict(curves=len(page.curves), rects=len(page.rects), images=len(page.images)),
                    limitation='Only standalone PDF line objects are traced. Curves are listed with their '
                               'bounding boxes for symbol matching only - they are NOT traced as wires.'))
    return dict(render_bbox=bbox, width=bbox[2]-bbox[0], height=bbox[3]-bbox[1], dpi=300,
                pixel_width=render.original.width, pixel_height=render.original.height,
                page_bbox=page.bbox, mediabox=page.mediabox, cropbox=page.cropbox, rotation=page.rotation,
                segments=len(segments), pins_marked=False)


def seeds(bbox):
    pins = []
    def add(pid, device, pin, x, y, kind='PHYSICAL'):
        pins.append(dict(id=pid, device='=112+E122-'+device, pin=pin, page=4, method='MANUAL',
                         point=display_point([x,y], bbox), kind=kind,
                         note='Elle işaretlenmiş pilot pini; otomatik tanıma değil.', version=1))
    for k,x in [('52',311.81),('53',368.5),('55',425.2)]:
        add('k'+k+'_top', '17K'+k, '13' if k=='52' else '11', x,271.29)
        add('k'+k+'_bottom', '17K'+k, '14', x,285.46)
    for pin,x in [('1',311.81),('2',368.5),('3',425.2),('4',453.54)]:
        add('x4_'+pin,'X4',pin,x,481.05)
    add('p24','X4','P24.32',524.41,481.05,'NETWORK')
    add('n24_a','X4','N24.30',467.72,481.05,'NETWORK')
    add('n24_b','X4','N24.30',538.58,481.05,'NETWORK')
    boxes = [dict(id='contact_'+k, page=4, version=1, note='Kontak sembolü iç sınırı (elle).',
                  bbox=display_point([x-6,271.29],bbox)+display_point([x+6,285.46],bbox),
                  source='MANUAL_VISUAL_MASK') for k,x in [('52',311.81),('53',368.5),('55',425.2)]]
    # Three old user confirmations are fixtures, NOT automatically discovered truth.
    claims = []
    for cid,a,b,kind,note in [
        ('C01','p24','k52_top','NETWORK','P24.32 hat ilişkisi teyitli; ayrıntılı fiziksel klemens adı belirsiz.'),
        ('C02','k53_top','k55_top','PHYSICAL','Kullanıcının teyit ettiği röle köprüsü.'),
        ('C03','k55_top','x4_4','PHYSICAL','Kullanıcının teyit ettiği ayrı klemens dalı.')]:
        claims.append(dict(id=cid, source_id=a,target_id=b,kind=kind,note=note,
                           source_sha256=KNOWN_HASH,physical_page=4,expected_revision=1,
                           reviewer='Kullanıcı — MAIN.md tarihli düzeltme',
                           visual_evidence=dict(file='page.png', method='MANUAL_VISUAL_SEED_NOT_BLIND_TRUTH',
                                                reference='MAIN.md / 2026-09-08 bağlantı güncellemesi')))
    return dict(pins=pins,boxes=boxes,claims=claims,
                dots=[dict(point=display_point([425.2,228.77],bbox),radius=2.48,
                           source='MANUAL_VISUAL_JUNCTION_MARKER')])


def prepare(run, extra_pages=()):
    run = Path(run).resolve()
    allowed = (ROOT/'output'/'pilots'/'E122').resolve()
    if run.parent != allowed or run.exists():
        raise ValueError('Yeni, doğrudan output/pilots/E122 altındaki run klasörü gerekli.')
    sha = digest(SOURCE)
    if sha != KNOWN_HASH:
        raise ValueError('PDF değişmiş. Eski kullanıcı onayı başka belgeye uygulanamaz.')
    # Make the directory only after validating source/target. Incomplete runs have no manifest.
    run.mkdir(parents=True)
    with pdfplumber.open(SOURCE) as pdf:
        inventory = [dict(physical_page=i+1,width=p.width,height=p.height,rotation=p.rotation,
                          mediabox=p.mediabox,cropbox=p.cropbox,bbox=p.bbox,
                          analyzed=(i==3)) for i,p in enumerate(pdf.pages)]
        # Page-level facts for every sheet: identity, cross-references, printed device tags.
        # Only the analyzed page gets geometry; other sheets stay text-fact level and say so.
        write_json(run/'document_index.json',
                   dict(source_sha256=sha, page_count=len(pdf.pages),
                        traced_pages=[4]+sorted({int(n) for n in extra_pages}-{4}),
                        extraction='pdfplumber.extract_words + title block labels; '
                                   'döndürülmüş yazılar glif matrisine göre okuma sırasına çevrildi',
                        limitation='Sayfa kimliği, çapraz referans ve cihaz yazıları her sayfa için; '
                                   'çizgi geometrisi yalnız traced_pages listesindeki sayfalar için. '
                                   'İzlenen sayfalarda bile pin işaretleri yalnız sayfa 4 içindir.',
                        pages=build_index([oriented_words(p) for p in pdf.pages])))
        page = pdf.pages[3]
        # The seeded page keeps the historical layout at the run root; further traced sheets
        # live under pages/<n>/ and carry no manual pins yet.
        primary = trace_page(page, run)
        bbox = primary['render_bbox']
        extra = {}
        for number in sorted({int(n) for n in extra_pages} - {4}):
            if not 1 <= number <= len(pdf.pages):
                raise ValueError('Sayfa numarası belgede yok: ' + str(number))
            extra[str(number)] = trace_page(pdf.pages[number-1], run/'pages'/str(number))
        write_json(run/'seeds.json',seeds(bbox))
        write_json(run/'inventory.json',inventory)
        manifest = dict(schema_version=1,created_utc=datetime.now(timezone.utc).isoformat(),
                        source_path=str(SOURCE),source_sha256=sha,physical_page=4,blatt='3',
                        page_count=len(pdf.pages),width=primary['width'],
                        height=primary['height'],render_bbox=bbox,
                        page_bbox=page.bbox,mediabox=page.mediabox,cropbox=page.cropbox,rotation=page.rotation,
                        dpi=300,pixel_width=primary['pixel_width'],pixel_height=primary['pixel_height'],
                        coordinate_space='PDFPLUMBER_ROTATED_TOP_LEFT_MINUS_RENDER_BBOX',
                        python=platform.python_version(),dependencies={p:importlib.metadata.version(p) for p in ['pdfplumber','pypdfium2','Pillow']},
                        main_sha256=digest(ROOT/'MAIN.md'),
                        scope=dict(location='E122',functions=['112','122','132','152','170']),
                        mode='MANUALLY_SEEDED_P03_REGRESSION_NOT_FULL_PAGE_OR_BLIND_EVALUATION',production_ready=False)
        # Use actual bbox extents: raster rounding is not a change to PDF coordinates.
        manifest['width'],manifest['height']=bbox[2]-bbox[0],bbox[3]-bbox[1]
        manifest['traced_pages']=[4]+sorted(int(n) for n in extra)
        manifest['page_artifacts']=extra
        names=['geometry.json','seeds.json','raw_page.json','words.json','page.png','inventory.json',
               'document_index.json']
        names+=[f'pages/{n}/{f}' for n in sorted(extra,key=int)
                for f in ('geometry.json','raw_page.json','words.json','page.png')]
        manifest['artifact_sha256']={name:digest(run/name) for name in names}
        manifest['code_sha256']={p.name:digest(p) for p in (ROOT/'analyzer_v3').glob('*.py')}
        write_json(run/'manifest.json',manifest)
    from .store import PinStore
    seeded=json.loads((run/'seeds.json').read_text(encoding='utf-8'))
    PinStore(run).initialize(seeded['pins'],seeded['boxes'])
    return run


def open_pdf(pdf_path, root=None, primary=None):
    """Kullanıcının seçtiği PDF için YENİ çalışma klasörü. Pilot çalışmalarına dokunmaz.

    Tohum YOKTUR: işaret, kutu, teyit ve çizilmiş nokta boş başlar — bu belgeye başka belgenin
    onayı taşınmaz. Aynı PDF ikinci kez açılırsa (aynı sha256) var olan klasör kullanılır;
    işaretler korunur. Yalnız BİR sayfanın geometrisi çıkarılır (ilk şema sayfası); kalan
    sayfalar sayfa önbelleğinden istendikçe hazırlanır.
    """
    source = Path(pdf_path).resolve()
    if not source.is_file() or source.suffix.lower() != '.pdf':
        raise ValueError('PDF dosyası bulunamadı: %s' % pdf_path)
    sha = digest(source)
    root = Path(root) if root else ROOT/'output'/'documents'
    run = root/sha[:16]
    if (run/'manifest.json').exists():
        return run
    if run.exists():
        raise ValueError('Yarım kalmış çalışma klasörü var, elle bakın: %s' % run)
    staging = run.with_name(run.name + '.tmp')
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with pdfplumber.open(source) as pdf:
        pages = build_index([oriented_words(page) for page in pdf.pages])
        if primary is None:
            schematics = [row['physical_page'] for row in pages if row.get('doc_type') == 'Schaltplan']
            primary = schematics[0] if schematics else 1
        primary = int(primary)
        if not 1 <= primary <= len(pdf.pages):
            raise ValueError('Sayfa numarası belgede yok: %s' % primary)
        page = pdf.pages[primary-1]
        info = trace_page(page, staging)
        bbox = info['render_bbox']
        write_json(staging/'document_index.json',
                   dict(source_sha256=sha, page_count=len(pdf.pages), traced_pages=[primary],
                        extraction='pdfplumber.extract_words + title block labels',
                        limitation='Çizgi geometrisi yalnız traced_pages için; kalan sayfalar '
                                   'sayfa önbelleğinden hazırlanır. İşaret yoktur: bu belge yeni açıldı.',
                        pages=pages))
        write_json(staging/'inventory.json',
                   [dict(physical_page=i+1, width=q.width, height=q.height, rotation=q.rotation,
                         mediabox=q.mediabox, cropbox=q.cropbox, bbox=q.bbox, analyzed=(i+1 == primary))
                    for i, q in enumerate(pdf.pages)])
        write_json(staging/'seeds.json', dict(pins=[], boxes=[], claims=[], dots=[]))
        row = next((r for r in pages if r['physical_page'] == primary), {})
        manifest = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                        source_path=str(source), source_sha256=sha, physical_page=primary,
                        blatt=row.get('blatt'), page_count=len(pdf.pages),
                        width=bbox[2]-bbox[0], height=bbox[3]-bbox[1], render_bbox=bbox,
                        page_bbox=page.bbox, mediabox=page.mediabox, cropbox=page.cropbox,
                        rotation=page.rotation, dpi=300, pixel_width=info['pixel_width'],
                        pixel_height=info['pixel_height'],
                        coordinate_space='PDFPLUMBER_ROTATED_TOP_LEFT_MINUS_RENDER_BBOX',
                        python=platform.python_version(),
                        dependencies={q: importlib.metadata.version(q)
                                      for q in ['pdfplumber', 'pypdfium2', 'Pillow']},
                        traced_pages=[primary], page_artifacts={},
                        mode='USER_DOCUMENT_NO_SEEDED_MARKS', production_ready=False)
        names = ['geometry.json', 'seeds.json', 'raw_page.json', 'words.json', 'page.png',
                 'inventory.json', 'document_index.json']
        manifest['artifact_sha256'] = {name: digest(staging/name) for name in names}
        manifest['code_sha256'] = {q.name: digest(q) for q in (ROOT/'analyzer_v3').glob('*.py')}
        write_json(staging/'manifest.json', manifest)
    from .store import PinStore
    PinStore(staging).initialize([], [])
    staging.rename(run)                     # manifest tamamlanmadan klasör adı kesinleşmez
    return run


def trace_extra(run, pages):
    """Add sheet geometry to an EXISTING run. Page 4, seeds, marks and reviews stay untouched.

    Continuation checking needs the target sheet's own lines; re-preparing the run would throw
    away the user's marks and approvals, so extra sheets are added in place instead.
    """
    run = Path(run).resolve()
    manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    if digest(SOURCE) != manifest['source_sha256']:
        raise ValueError('PDF değişmiş; bu çalışmaya sayfa eklenemez.')
    wanted = {int(n) for n in pages} - set(manifest['traced_pages'])
    if not wanted:
        return manifest['traced_pages']
    added = {}
    with pdfplumber.open(SOURCE) as pdf:
        for number in sorted(wanted):
            if not 1 <= number <= len(pdf.pages):
                raise ValueError('Sayfa numarası belgede yok: ' + str(number))
            added[str(number)] = trace_page(pdf.pages[number-1], run/'pages'/str(number))
    manifest.setdefault('page_artifacts', {}).update(added)
    manifest['traced_pages'] = sorted(set(manifest['traced_pages']) | {int(n) for n in added})
    manifest['artifact_sha256'].update({'pages/%s/%s' % (n, f): digest(run/'pages'/n/f)
                                        for n in added
                                        for f in ('geometry.json', 'raw_page.json', 'words.json', 'page.png')})
    manifest.setdefault('traced_pages_added', []).append(
        dict(utc=datetime.now(timezone.utc).isoformat(), pages=sorted(int(n) for n in added),
             reason='Sayfa 4 devam referanslarının hedef sayfası; yalnız geometri eklendi.'))
    index = run/'document_index.json'
    if index.exists():
        data = json.loads(index.read_text(encoding='utf-8'))
        data['traced_pages'] = manifest['traced_pages']
        write_json(index, data)
        manifest['artifact_sha256']['document_index.json'] = digest(index)
    write_json(run/'manifest.json', manifest)
    return manifest['traced_pages']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run', default=str(ROOT/'output'/'pilots'/'E122'/'20260910_v3_p05_rev8'))
    parser.add_argument('--pages', default='', help='Sayfa 4 dışında geometrisi çıkarılacak fiziksel sayfalar, virgüllü')
    parser.add_argument('--add-pages', default='', help='Var olan run klasörüne sayfa geometrisi ekle; işaretler korunur')
    args=parser.parse_args()
    extra=[p for p in args.add_pages.split(',') if p.strip()]
    print(trace_extra(args.run,extra) if extra else
          prepare(args.run,[p for p in args.pages.split(',') if p.strip()]))
