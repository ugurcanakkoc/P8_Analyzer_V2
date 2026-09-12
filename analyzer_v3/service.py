"""Reconcile a few explicit visual/user claims with independent raw-line tracing."""
import json
from collections import Counter
import threading
from datetime import datetime
from pathlib import Path

from . import dashed, document, similarity
from .document import (XREF, full_device_name, occurrences, reconcile_endpoint,
                       references_for_page, signal_labels, strip_labels, strip_owner,
                       terminal_table)
from .geometry import PIN_ATTACH, PathGraph, ends_near
from .library import SymbolLibrary, descriptor_of, entry_from_descriptor, validate_update
from .models import (IMPLEMENTATION_TYPES, device_parts, endpoint_scope, in_scope,
                     normalized, pair_scope, validate_evidence_row)
from .prepare import ROOT, digest
from .similarity import descriptor, find as find_similar, search as search_similar, template as build_template
from .store import PinStore

# Modül ucunun işaret noktası çubuğun 7,1 pt üstündedir (ölçülen uç boyu, sayfa 28/36).
MODULE_PIN_OFFSET=7.1
# Kesikli koşu köprüsü: bundan küçük boşluk zaten graf tarafından birleştirilmiştir.
EPS_BRIDGE=0.03

# İlişki teyidi ÜÇ durumdur ve üretime uygunlukla karıştırılmaz. Bir kullanıcı teyidi
# askıya alındığında kaybolmaz; "geçmişte teyitli, yeniden inceleme gerekiyor" olur.
CONFIRM_TEXT={'GUNCEL_TEYITLI':'Kullanıcı teyitli (güncel)',
              'TEYIT_ASKIDA':'Geçmişte teyitli — yeniden inceleme gerekiyor',
              'ONAY_BEKLIYOR':'Onay bekliyor'}


def _confirm_state(row):
    if row.get('kind')!='CONFIRMED_PHYSICAL_PAIR':
        return 'ONAY_BEKLIYOR'
    return 'GUNCEL_TEYITLI' if row.get('review_state')=='CURRENT' else 'TEYIT_ASKIDA'

SHORT_SEGMENT=12.0   # a bridge this short is re-counted independently of the table rows
LIBRARY_PATH=ROOT/'output'/'library'/'symbols.sqlite3'   # shared by every run, versioned, local


EPS_RUN=0.05   # koşu/tel iç noktası payı (pt)
SYMBOL_STROKE_MAX=30.0   # sembol çizgisi kısadır; bundan uzun çizgi TELdir, kümeye girmez
SYMBOL_PAD=2.0           # kümeye komşu parça alma payı
SYMBOL_BOX_MAX=70.0      # küme bu boyutu aşarsa sembol değil, çizim alanı sayılır
PIN_MERGE=0.5            # aynı uç sayılan mesafe
DEVICE_TEXT_RADIUS=26.0  # cihaz yazısı arama yarıçapı


class Pilot:
    def _artifact(self,name):
        """Evidence files stay inside the run folder; nested page folders are allowed, escapes are not."""
        parts=Path(name).parts
        if Path(name).is_absolute() or '..' in parts or '\\' in name:
            raise ValueError('Geçersiz kanıt dosyası yolu: '+name)
        path=(self.run/name).resolve()
        if self.run.resolve() not in path.parents:
            raise ValueError('Geçersiz kanıt dosyası yolu: '+name)
        return path

    def __init__(self, run, verify=True, cache=None):
        self.run=Path(run)
        self.manifest=json.loads((self.run/'manifest.json').read_text(encoding='utf-8'))
        if verify:
            for file,sha in self.manifest['artifact_sha256'].items():
                if digest(self._artifact(file))!=sha:
                    raise ValueError('Değişmiş kanıt dosyası: '+file)
            if digest(self.manifest['source_path'])!=self.manifest['source_sha256']:
                raise ValueError('Kaynak PDF değişmiş; eski onaylar kullanılamaz.')
        self.geometry=json.loads((self.run/'geometry.json').read_text(encoding='utf-8'))
        self.seeds=json.loads((self.run/'seeds.json').read_text(encoding='utf-8'))
        index=self.run/'document_index.json'
        self.document=json.loads(index.read_text(encoding='utf-8')) if index.exists() else None
        self.store=PinStore(self.run)
        self.lock=threading.RLock()
        self.revision=None
        self._words=None
        self._page_cache={}
        self._signatures={}
        self.graphs={}
        self._class_cache={}
        self._dash_cache={}
        self.library=SymbolLibrary(LIBRARY_PATH)
        # İsteğe bağlı sayfa önbelleği (pagecache.PageCache). Regresyon testlerinde yoktur;
        # sunucu verir. Önbellek sayfaları görüntülenir ama işaret yazılamaz (bkz. pages()).
        self.cache=cache

    def pages(self):
        """Traced sheets and their sizes; a mark outside this set is refused."""
        sizes={self.manifest['physical_page']:(self.manifest['width'],self.manifest['height'])}
        for number,info in self.manifest.get('page_artifacts',{}).items():
            sizes[int(number)]=(info['width'],info['height'])
        return sizes

    def viewable_pages(self):
        """Görüntülenebilir sayfalar: çalışmanın izlediği + önbellekte hazırlanmış.

        İşaret YAZMA doğrulaması bunu kullanmaz: regresyon pilotunun kaydına yalnız kendi
        izlediği sayfalarda işaret konur.
        """
        sizes=dict(self.pages())
        if self.cache is not None:
            for number,size in self.cache.prepared().items():
                sizes.setdefault(number,size)
        return sizes

    def page_file(self,number,name):
        """Bir sayfanın kanıt dosyası: önce çalışmadan, yoksa önbellekten. İkisi de kendi köküne kilitli."""
        number=int(number)
        if number in self.pages():
            prefix='' if number==self.manifest['physical_page'] else 'pages/%s/'%number
            return self._artifact(prefix+name)
        if self.cache is not None and number in self.cache.prepared():
            return self.cache.file(number,name)
        raise ValueError('Sayfa %s hazırlanmadı; geometrisi yok.'%number)

    def _page_signature(self,number,pins,boxes):
        return (json.dumps([p for p in pins if p.get('page',4)==number],sort_keys=True),
                json.dumps([b for b in boxes if b.get('page',4)==number],sort_keys=True))

    def refresh(self):
        revision,pins,boxes,reviews=self.store.snapshot()
        # Geri alınan işaret SİLİNMEZ: kaydı ve geçmişi durur, yalnız pasif olur ve izleme
        # ile ilişki hesabına girmez (bkz. models.validate_pin `active`).
        self.retired=[q for q in pins if not q.get('active',True)]
        pins=[q for q in pins if q.get('active',True)]
        # Runs prepared before boxes were stored keep their seeded masks as read-only templates.
        known={b['id'] for b in boxes}
        boxes=boxes+[dict(b,version=b.get('version',1)) for b in self.seeds.get('boxes',[]) if b['id'] not in known]
        if revision!=self.revision:
            # One graph per traced sheet; only the sheets whose marks changed are rebuilt.
            keep={n:g for n,g in getattr(self,'graphs',{}).items()
                  if self._signatures.get(n)==self._page_signature(n,pins,boxes)}
            self.pins,self.boxes,self.reviews,self.graphs=pins,boxes,reviews,keep
            self._signatures={n:self._page_signature(n,pins,boxes) for n in keep}
            self.revision=revision
            self.graph=self.page_graph(self.manifest['physical_page'])

    def _page_curves(self,number):
        return json.loads(self.page_file(number,'geometry.json').read_text(encoding='utf-8')).get('curves',[])

    def dash_bridges(self,number):
        """Yalnız İNSAN ONAYLI kesikli koşuların kendi iç boşluklarını dolduran köprüler.

        Köprü ham çizim değildir: kimliği `dashbridge:` ile başlar, `geometry.json` ve
        ham parçalar değişmez. Yalnız ölçümün KIRILMAMIŞ saydığı boşluklar doldurulur;
        koşu kırılmaları (sembol boşluğu, desenden geniş boşluk) asla köprülenmez.
        Onay yoksa liste boştur ve graf bugünküyle birebir aynı kalır.
        """
        approved=[r for r in self.reviews
                  if r.get('subject')=='DASH_RUN' and r.get('decision')=='CONFIRMED'
                  and number in (r.get('pages') or [])]
        if not approved:
            return []
        wanted={r['run_key'] for r in approved}
        out=[]
        for run in self._dash_runs(number):
            key='%s#%d'%(run['ruling'],run['index'])
            if key not in wanted:
                continue
            # İmza doğrudan ÖLÇÜMDEN hesaplanır. `dash_proposals` çağrılamaz: o grafı kurar,
            # graf da buraya döner ve sonsuz döngü olurdu.
            signature=json.dumps([run['segment_ids'],dashed._ends(run)],sort_keys=True)
            state=self._dash_decision(number,key,signature)
            if state['decision']!='CONFIRMED' or state['review_state']!='CURRENT':
                continue          # bayat karar köprü kurmaz
            axis,coord=run['axis'],run['coord']
            pieces=sorted(run['raw_pieces'])
            for i in range(len(pieces)-1):
                lo,hi=pieces[i][1],pieces[i+1][0]
                if hi-lo<=EPS_BRIDGE:
                    continue
                a=[lo,coord] if axis=='y' else [coord,lo]
                b=[hi,coord] if axis=='y' else [coord,hi]
                out.append(dict(id='dashbridge:%s:%d'%(key,i),a=a,b=b,
                                bridge=True,run_key=key,
                                note='İnsan onaylı kesikli koşu köprüsü; çizilmiş mürekkep değildir.'))
        return out

    def page_graph(self,number):
        if number not in self.graphs:
            self._signatures[number]=self._page_signature(number,self.pins,self.boxes)
            dots=self.seeds['dots'] if number==self.manifest['physical_page'] else []
            self.graphs[number]=PathGraph(self._page(number)['segments']+self.dash_bridges(number),
                                          dots,
                                          [p for p in self.pins if p.get('page',4)==number],
                                          [b for b in self.boxes if b.get('page',4)==number and b.get('active',True)],
                                          no_join=self._run_crossings(number))
        return self.graphs[number]

    def _run_crossings(self,number):
        """Ölçülmüş kesikli koşuyu noktasız, BOYDAN BOYA geçen tellerin kesişim noktaları.

        Yalnız koşunun iç kısmı (iki yanda da sürüyor) ve telin iç kısmı (tel orada bitmiyor)
        sayılır. Koşuda biten veya koşunun ucuna gelen tel T'dir; ona dokunulmaz.
        """
        from .geometry import pt
        byid={s['id']:s for s in self._page(number)['segments']}
        out=[]
        for run in self._dash_runs(number):
            for sid in run['crossings_without_dot']:
                s=byid.get(sid)
                if s is None:
                    continue
                if run['axis']=='y':
                    point,along,ends=(s['a'][0],run['coord']),s['a'][0],(s['a'][1],s['b'][1])
                    across=run['coord']
                else:
                    point,along,ends=(run['coord'],s['a'][1]),s['a'][1],(s['a'][0],s['b'][0])
                    across=run['coord']
                inside_run=run['start']+EPS_RUN<along<run['end']-EPS_RUN
                through=min(ends)+EPS_RUN<across<max(ends)-EPS_RUN
                if inside_run and through:
                    out.append(pt(point))
        return out

    def _trace(self,pid):
        byid={p['id']:p for p in self.pins}
        if pid not in byid:
            raise ValueError('Pin bulunamadı.')
        source=byid[pid]
        result=self.page_graph(source.get('page',4)).trace(pid)
        result['page']=source.get('page',4)
        if not in_scope(source['device']):
            result['issues'].append('SOURCE_OUT_OF_SCOPE_OR_UNKNOWN')
        if not source['pin'].strip():
            result['issues'].append('SOURCE_PIN_UNKNOWN')
        for t in result['targets']:
            p=byid[t['pin_id']]
            t['in_scope']=in_scope(p['device']) and bool(p['pin'].strip())
            if not t['in_scope']:
                t['relation']='OUT_OF_SCOPE_OR_UNKNOWN_BOUNDARY'
        bridges=sorted({i for e in result.get('path',[]) for i in [e.get('segment_id')]
                        if str(i).startswith('dashbridge:')}
                       | {i for t in result['targets'] for e in t.get('path',[])
                          for i in [e.get('segment_id')] if str(i).startswith('dashbridge:')})
        if bridges:
            result['issues'].append('PATH_USES_APPROVED_DASH_BRIDGE')
            result['dash_bridges']=bridges
        result['production_ready']=False
        result['limitation']='Çizgi erişimi; fiziksel tel veya dağıtım sırası onayı değil. Sembol/pin işaretleme sınırlı.'
        return result

    def trace(self,pid):
        with self.lock:
            self.refresh()
            return self._trace(pid)

    def claims(self):
        rows=[]
        byid={p['id']:p for p in self.pins}
        baseline={p['id']:p for p in self.seeds['pins']}
        for c in self.seeds['claims']:
            a,b=byid[c['source_id']],byid[c['target_id']]
            # Fail closed for ANY annotation edit, not just the two endpoints.
            current=(self.revision==c['expected_revision'] and self.pins==self.seeds['pins']
                     and c['source_sha256']==self.manifest['source_sha256']
                     and c['physical_page']==self.manifest['physical_page'])
            traced=self._trace(a['id'])
            target=next((t for t in traced['targets'] if t['pin_id']==b['id']),None)
            route=target['path'] if target else None
            current=current and in_scope(a['device']) and in_scope(b['device'])
            row=dict(c, source=a,target=b, original_source=baseline[a['id']],original_target=baseline[b['id']],
                     status='CONFIRMED_BOTH' if current and route else ('CONFLICT' if current else 'UNRESOLVED'),
                     review_status='APPROVED' if current and route else 'PENDING',
                     vector_evidence=route or [],visual_evidence=c['visual_evidence'] if current else None,
                     original_visual_evidence=c['visual_evidence'],path=route or [],
                     # The tracing warnings belong to the row: a matching path is not a clean path.
                     trace_issues=traced['issues'],relation=target['relation'] if target else None,
                     branch_points=len(traced['branch_points']),open_ends=len(traced['open_ends']),
                     unattached_pins_on_path=traced['unattached_pins'],
                     annotation_revision=self.revision,production_ready=False,
                     cross_section='',cross_section_provenance='UNKNOWN',wire_color='',wire_color_provenance='UNKNOWN')
            if not current:
                row['note']+=' İşaretleme değişti; eski teyit askıya alındı. Bu ekranda yeniden onay/üretim yetkisi yok.'
                row['reviewer']=None
            elif not route:
                row['note']+=' Geometrik yol bulunamadı; önceki teyit ile çelişki.'
                row['reviewer']=None
            validate_evidence_row(row)
            rows.append(row)
        return rows

    def words(self):
        # raw_page.json is hash-verified at startup; words are read, never rewritten.
        if self._words is None:
            self._words=json.loads((self.run/'raw_page.json').read_text(encoding='utf-8'))['words']
        return self._words

    def candidates(self,box_id):
        """P04: propose similar drawn symbols on the box's own sheet. Nothing is stored."""
        with self.lock:
            self.refresh()
            box=next((b for b in self.boxes if b['id']==box_id),None)
            if box is None:
                raise ValueError('Şablon bulunamadı.')
            if not box.get('active',True):
                raise ValueError('Bu kutu pasif; şablon olarak kullanılmıyor.')
            number=box.get('page',4)
            page=self._page(number)
            marks=[p for p in self.pins if p.get('page',4)==number]
            result=find_similar(box,marks,page['segments'],page['words'],page['render_bbox'],marks,
                                curves=self._page_curves(number))
            result['page']=number
            strips=document.strip_labels(page['words'],page['render_bbox'])
            bars=document.module_bars(page['segments'])
            for c in result['candidates']:
                # Cihaz adı ŞABLONDAN kopyalanmaz: bu sayfanın kendi yazısından çözülür.
                # Belge indeksi olmayan eski çalışmada ad tamamlanamaz; aday adsız kalır, düşmez.
                if self.document is not None:
                    self._name_from_strip(c,strips,page['render_bbox'],number,bars,page['words'],page['segments'])
                else:
                    c.setdefault('issues',[]).append('DEVICE_NAME_UNRESOLVED_NO_DOCUMENT_INDEX')
                for p in c['pins']:
                    # A proposed identity is never treated as scope-verified until the user saves it.
                    p['template_device_in_scope']=in_scope(p['template_device'])
            return dict(result,annotation_revision=self.revision,box_id=box_id)

    def _page_profile(self,number):
        """Customer/style profile of the sheet a symbol was captured from."""
        page=next((p for p in self._index() if p['physical_page']==number),{}) if self.document else {}
        words={w['text'] for w in self._page(number)['words']}
        return dict(customer='TROESTER' if any('TROESTER' in w.upper() for w in words) else None,
                    drawing_style='EPLAN title block (Anlage/Einbauort/Blatt)',
                    anlage=page.get('anlage'),einbauort=page.get('einbauort'),
                    doc_type=page.get('doc_type'),blatt=page.get('blatt'))

    def library_entries(self):
        with self.lock:
            rows=self.library.entries()
            return dict(rows=rows,path=str(LIBRARY_PATH),
                        draft=sum(1 for r in rows if r['status']=='DRAFT'),
                        approved=sum(1 for r in rows if r['status']=='APPROVED'),
                        note='Kütüphane çalışmalardan bağımsızdır ve sürümlüdür. Kayıtlar cihaz adı, '
                             'bağlantı, renk, kesit veya onay taşımaz; onaysız kayıt DRAFT kalır.',
                        production_ready=False)

    def library_save(self,payload):
        """P04+: kaydı çalışmadaki bir kutudan al. Kayıt taslaktır; onay kullanıcıya aittir."""
        with self.lock:
            self.refresh()
            box=next((b for b in self.boxes if b['id']==payload.get('box_id')),None)
            if box is None:
                raise ValueError('Şablon kutusu bulunamadı.')
            number=box.get('page',4)
            page=self._page(number)
            marks=[p for p in self.pins if p.get('page',4)==number]
            tpl=build_template(box,marks,page['segments'],page['words'],page['render_bbox'],
                               curves=self._page_curves(number))
            desc=descriptor(tpl)
            source_device=next((m['device'] for m in tpl['pins'] if m['device'].strip()),None)
            evidence=dict(source_sha256=self.manifest['source_sha256'],run=self.run.name,
                          physical_page=number,box_id=box['id'],box_bbox=box['bbox'],
                          box_note=box.get('note',''),marked_pins=len(desc['pins']),
                          method='CAPTURED_FROM_USER_MARKED_BOX')
            family=payload.get('family')
            if family is not None and (not isinstance(family,str) or not family.strip()):
                raise ValueError('Aile adı geçersiz.')
            entry=entry_from_descriptor(desc,evidence,self._page_profile(number),
                                        family=family.strip() if family else None,
                                        source_device=source_device,note=payload.get('note',''))
            return self.library.add(entry)

    def library_update(self,payload):
        with self.lock:
            return self.library.update(payload.get('id'),payload.get('expected_version'),
                                       validate_update(payload))

    def _complete(self,number,printed):
        """Yazılmamış adres parçasını SAYFADAN tamamla; hangi parçanın devralındığını söyle."""
        parts=device_parts(printed)
        if not parts:
            return printed,[]
        anlage,ort,tag=parts
        facts=next((q for q in self._index() if q['physical_page']==number),{})
        inherited=[]
        if anlage is None:
            anlage=facts.get('anlage'); inherited.append('anlage')
        if ort is None:
            ort=facts.get('einbauort'); inherited.append('ort')
        name=('='+anlage if anlage else '')+('+'+ort if ort else '')+'-'+tag
        return name,inherited

    def _module_identity(self,candidate,bars,words,render_bbox,segments,number):
        """Aday bir PLC modülünün çubuğuna oturuyorsa kimliği MODÜL kuralıyla çöz.

        Cihaz adı başlık bloğundan, pin adı ucun sağındaki yazıdan, DO/DI ayrımı ucun
        üstündeki tanım yazısından gelir. Hiçbiri şablondan kopyalanmaz.
        """
        if not candidate.get('pins'):
            return False
        x,y=candidate['pins'][0]['point']
        for bar in bars:
            if abs(bar['y']-y)>document.MODULE_STUB_MAX or not any(abs(s-x)<=0.5 for s in bar['stubs']):
                continue
            owner,reason,band,hits=document.module_owner(bar,segments,words,render_bbox)
            pin=document.module_pin_name(bar,round(x,2),words,render_bbox)
            mark=document.module_pin_mark(bar,round(x,2),words,render_bbox)
            full,inherited=self._complete(number,owner) if owner else (None,[])
            candidate['device_printed']=owner
            candidate['device_name']=full
            candidate['device_inherited']=inherited
            candidate['device_source']='MODULE_HEADER_OWNERSHIP' if owner else None
            candidate['device_reason']=reason
            candidate['module']=dict(bar=bar['id'],header=band,header_tags=hits,
                                     pin_name=pin,pin_mark=mark,
                                     pin_name_source='MODULE_EDGE_PIN_LABEL' if pin else None)
            for q in candidate['pins']:
                q['module_pin_name']=pin
                q['module_pin_mark']=mark
            candidate['identity_resolved']=bool(owner and pin)
            if not candidate['identity_resolved']:
                candidate.setdefault('issues',[]).append('IDENTITY_UNRESOLVED_NOT_A_RECOGNISED_END')
                if owner and not pin:
                    candidate['issues'].append('MODULE_PIN_LABEL_NOT_PRINTED')
            return True
        return False

    def _name_from_strip(self,candidate,strips,render_bbox,number=None,
                         bars=(),words=(),segments=()):
        """Adayın cihaz adını çöz: şablon ofseti → modül başlığı → çubuk sahipliği.

        Çözülemezse kimlik EKSİK kalır ve aday "doğru tanınmış uç" sayılmaz.
        """
        texts=candidate.get('page_device_texts') or []
        if len(texts)==1:
            full,inherited=self._complete(number,texts[0])
            candidate['device_printed']=texts[0]
            candidate['device_name']=full
            candidate['device_inherited']=inherited
            candidate['device_source']='TEMPLATE_OFFSET'
            candidate['identity_resolved']=True
            return candidate
        if bars and self._module_identity(candidate,bars,words,render_bbox,segments,number):
            return candidate
        point=candidate['pins'][0]['point'] if candidate.get('pins') else None
        owner,reason=(None,'NO_PIN_ON_CANDIDATE') if point is None else strip_owner(strips,point)
        full,inherited=self._complete(number,owner) if owner else (None,[])
        candidate['device_printed']=owner
        candidate['device_name']=full
        candidate['device_inherited']=inherited
        candidate['device_source']='STRIP_LABEL_OWNERSHIP' if owner else None
        candidate['device_reason']=reason
        candidate['identity_resolved']=bool(owner) and len(
            [t for q in candidate.get('pins',[]) for t in q.get('page_pin_texts',[])])>0
        if not candidate['identity_resolved']:
            candidate.setdefault('issues',[]).append('IDENTITY_UNRESOLVED_NOT_A_RECOGNISED_END')
        return candidate

    def library_candidates(self,entry_id,number=None,pages=None):
        """Kütüphane kaydını bu belgede ara. Hiçbir şey kaydedilmez; maske uygulanmaz.

        `pages` verilirse ARAMA ÇOK SAYFALIDIR: her izlenen sayfa ayrı ayrı taranır ve sonuçlar
        sayfa kimliğiyle döner. Belge geneli arama da aynı mekanizmayı kullanır; ilk teslim
        bütün belgenin bitmesini beklemez.
        """
        if pages is not None:
            wanted=[int(n) for n in pages] if pages!='ALL' else sorted(self.viewable_pages())
            out,found,missing=[],0,[]
            for n in wanted:
                if n not in self.viewable_pages():
                    missing.append(n)
                    continue
                one=self.library_candidates(entry_id,n)
                found+=len(one['candidates'])
                out.append(one)
            return dict(entry_id=entry_id,pages=[o['page'] for o in out],
                        untraced_pages=missing,results=out,candidates_total=found,
                        applied_changes=False,production_ready=False,
                        limitation='Çok sayfalı arama, tek sayfalı aramanın aynısını her sayfada '
                                   'çalıştırır. İzlenmeyen sayfa taranmaz ve listelenir; '
                                   'taranmamış olması "bu sayfada yok" demek DEĞİLDİR.')
        with self.lock:
            self.refresh()
            entry=self.library.get(entry_id)
            number=int(number or self.manifest['physical_page'])
            if number not in self.viewable_pages():
                raise ValueError('Bu çalışmada izlenmeyen sayfa: %s'%number)
            page=self._page(number)
            marks=[p for p in self.pins if p.get('page',4)==number]
            result=search_similar(descriptor_of(entry),page['segments'],page['words'],
                                  page['render_bbox'],marks,self._page_curves(number))
            strips=strip_labels(page['words'],page['render_bbox'])
            bars=document.module_bars(page['segments'])
            for candidate in result['candidates']:
                candidate['library_entry']=entry['id']
                candidate['library_family']=entry['family']
                candidate['library_status']=entry['status']
                candidate['requires_user_confirmation']=True
                # Bulgunun KAYNAĞI ayrı tutulur: kütüphaneden yeniden kullanım mı, bu çalışmada
                # elle öğretilmiş bir örnekten mi geldi? İkisi aynı başarı sayılmaz.
                candidate['discovery_source']='LIBRARY_REUSE'
                candidate['taught_in_run']=entry.get('evidence',{}).get('run')
                # Cihaz adı şablon ofsetinde okunamadıysa ÇUBUK SAHİPLİĞİ denenir.
                # Çözülemezse aday "doğru tanınmış uç" SAYILMAZ.
                self._name_from_strip(candidate,strips,page['render_bbox'],number,
                                     bars,page['words'],page['segments'])
                candidate['note']=('Kütüphane eşleşmesi yalnız çizim şeklidir. Cihaz ve pin adları bu '
                                   'belgeden okundu. Kaynak belgenin yazıları kayıtta yalnız kanıt '
                                   'olarak durur, kimlik olarak aktarılmaz; bağlantı, renk, kesit ve '
                                   'onay hiç saklanmaz. Kayıt oluşturulmadı, maske uygulanmadı.')
                for pin in candidate['pins']:
                    pin['template_device']=''
                    pin['template_pin']=''
            return dict(result,page=number,entry=dict(entry,shape=dict(size=entry['shape']['size'])),
                        applied_changes=False,
                        limitation=result['limitation']+' Kütüphane kaydı kaynak belgenin cihaz/pin '
                                   'yazısını yalnız karşılaştırma kanıtı olarak taşır, yeni belgeye kimlik '
                                   'olarak aktarmaz; bağlantı, renk, kesit ve onay saklanmaz.')

    def module_report(self,number=None):
        """Bu sayfadaki PLC modüllerinin uçları: kimliği çözülen, çözülemeyen, ayrı ayrı.

        Kütüphaneden bağımsızdır: yalnız çizimin kendi çizgilerini ve kendi yazılarını okur.
        Hiçbir kayıt oluşturmaz, hiçbir şeyi onaylamaz. Dış iletkeni çizilmemiş bir uç
        "kaçırılmış tel" DEĞİLDİR; ayrı kovada görünür.
        """
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            page=self._page(number)
            rb,segments,words=page['render_bbox'],page['segments'],page['words']
            marks=[q for q in self.pins if q.get('page',4)==number]
            modules=[]
            for bar in document.module_bars(segments):
                owner,reason,band,hits=document.module_owner(bar,segments,words,rb)
                full,inherited=self._complete(number,owner) if owner else (None,[])
                resolved,unresolved,idle=[],[],[]
                names={x:document.module_pin_name(bar,x,words,rb) for x in bar['stubs']}
                numbered=[x for x,v in names.items() if v and v.isdigit()]
                # Başlık metninin sağ sınırı: modülün ilk NUMARALI pini. Sabit değer yok.
                text_limit=min(numbered) if numbered else bar['x1']
                for x in bar['stubs']:
                    pin=names[x]
                    mark=document.module_pin_mark(bar,x,words,rb)
                    point=[x,bar['y']-MODULE_PIN_OFFSET] if bar['side']=='ABOVE' else [x,bar['y']]
                    # Uçtan ÇIKAN iletken: çubuğun öbür yanında aynı x'te devam eden çizgi.
                    out=[s for s in segments
                         if abs(s['a'][0]-x)<0.5 and abs(s['b'][0]-x)<0.5
                         and abs(min(s['a'][1],s['b'][1])-bar['y'])<0.5
                         and max(s['a'][1],s['b'][1])>bar['y']+0.5]
                    existing=[q for q in marks if abs(q['point'][0]-x)<=1.0
                              and abs(q['point'][1]-(bar['y']-MODULE_PIN_OFFSET))<=1.0]
                    row=dict(x=x,point=point,pin=pin,pin_mark=mark,device_printed=owner,
                             device=full,device_inherited=inherited,
                             conductor_ids=[s['id'] for s in out],
                             conductor_to=(round(max(max(s['a'][1],s['b'][1]) for s in out),2)
                                           if out else None),
                             marked=[q['id'] for q in existing],
                             mark_methods=sorted({q.get('method') for q in existing}))
                    if not (owner and pin):
                        row['why']=('MODULE_PIN_LABEL_NOT_PRINTED' if owner else reason)
                        unresolved.append(row)
                    elif not out:
                        row['why']='NO_EXTERNAL_CONDUCTOR_DRAWN_NOT_A_MISSING_WIRE'
                        idle.append(row)
                    else:
                        resolved.append(row)
                modules.append(dict(bar=bar['id'],y=bar['y'],x0=bar['x0'],x1=bar['x1'],
                                    side=bar['side'],stubs=len(bar['stubs']),
                                    device_printed=owner,device=full,device_inherited=inherited,
                                    owner_reason=reason,header=band,header_tags=hits,
                                    header_texts=[w['text'] for w in words
                                                  if band and band[0]<=w['x0']-rb[0]
                                                  and w['x1']-rb[0]<=min(band[2],text_limit)
                                                  and band[1]<=w['top']-rb[1] and w['bottom']-rb[1]<=band[3]],
                                    resolved=resolved,unresolved=unresolved,
                                    no_conductor=idle))
            return dict(page=number,modules=modules,
                        counts=dict(modules=len(modules),
                                    resolved=sum(len(m['resolved']) for m in modules),
                                    no_conductor=sum(len(m['no_conductor']) for m in modules),
                                    unresolved=sum(len(m['unresolved']) for m in modules)),
                        applied_changes=False,production_ready=False,
                        note='Kimlik yalnız bu sayfanın kendi yazısından okundu. DO/DI ayrımı '
                             'şekilden değil, ucun üstündeki tanım yazısından gelir. Dış iletkeni '
                             'çizilmemiş uç ayrı kovadadır ve eksik tel sayılmaz. Kayıt '
                             'oluşturulmadı, onay verilmedi.')

    def _index(self):
        if self.document is None:
            raise ValueError('Bu çalışmada belge indeksi yok; sayfalar arası inceleme için yeni run hazırlayın.')
        return self.document['pages']

    def _shift(self,box,number=None):
        bbox=self._page(number or self.manifest['physical_page'])['render_bbox']
        return [round(box[0]-bbox[0],2),round(box[1]-bbox[1],2),round(box[2]-bbox[0],2),round(box[3]-bbox[1],2)]

    def cross_references(self):
        """P05: sayfa referanslarını çöz ve sınıflandır. Hiçbiri tel üretmez."""
        with self.lock:
            rows=references_for_page(self.manifest['physical_page'],self._index())
            for r in rows:
                r['display_box']=self._shift(r['box'])
            return dict(page=self.manifest['physical_page'],rows=rows,production_ready=False,
                        limitation='Çapraz referans bir çizim işaretidir; kontak-bobin ilişkisi tel devamı değildir. '
                                   'Pozisyon eki yorumlanmaz.')

    def _page_source(self,number):
        if number==self.manifest['physical_page']:
            return '','',self.manifest['render_bbox']
        info=self.manifest.get('page_artifacts',{}).get(str(number))
        if info:
            return 'pages/%s/'%number,'pages/%s/'%number,info['render_bbox']
        if self.cache is not None and number in self.cache.prepared():
            return None,None,self.cache.entry(number)['render_bbox']
        raise ValueError('Sayfa %s bu çalışmada izlenmedi; geometrisi yok.'%number)

    def _page(self,number):
        if number not in self._page_cache:
            _,_,bbox=self._page_source(number)
            # words.json holds reading-order text; older runs fall back to the raw extraction.
            words=self.page_file(number,'words.json')
            if not words.exists():
                words=self.page_file(number,'raw_page.json')
            self._page_cache[number]=dict(
                segments=json.loads(self.page_file(number,'geometry.json').read_text(encoding='utf-8'))['segments'],
                words=json.loads(words.read_text(encoding='utf-8'))['words'],render_bbox=bbox)
        return self._page_cache[number]

    def _dash_run_end(self,number,ends,centre):
        """Bu uçların hepsi ÖLÇÜLMÜŞ tek bir kesikli koşuya mı ait? Öyleyse koşunun ucunu ver.

        Kanıt `dashed.rulings`ten gelir: aynı eksen, aynı koordinat, aynı kalem kalınlığı ve
        kırılmamış tek koşu. Farklı koşular karışıyorsa karar verilmez (None) ve referans
        çözümsüz kalır. Koşunun kendi kırılmaları burada da geçerlidir: kırılmış bir desende
        uçlar iki ayrı koşuya düşer ve bu kural sessizce birleştirmez.
        """
        runs=self._dash_runs(number)
        wanted={e['segment_id'] for e in ends}
        for run in runs:
            if not wanted.issubset(set(run['segment_ids'])):
                continue
            axis,coord=run['axis'],run['coord']
            lo=[run['start'],coord] if axis=='y' else [coord,run['start']]
            hi=[run['end'],coord] if axis=='y' else [coord,run['end']]
            far=lambda p:abs(p[0]-centre[0])+abs(p[1]-centre[1])
            point=lo if far(lo)<=far(hi) else hi
            return dict(point=point,segment_id=run['segment_ids'][0 if point is lo else -1],
                        dash_run='%s#%d'%(run['ruling'],run['index']),
                        dash_pieces=run['pieces'],
                        evidence='MEASURED_DASH_RUN_END_NOT_A_GAP_BRIDGE')
        return None

    def _dash_runs(self,number):
        if number not in getattr(self,'_run_cache',{}):
            self.refresh()          # maskeler işaret deposundan gelir
            data=self._page_data(number)
            self._run_cache=getattr(self,'_run_cache',{})
            self._run_cache[number]=dashed.rulings(data,dashed.junction_dots(data['curves']))
        return self._run_cache[number]

    def _wire_end(self,number,box):
        """The drawn end a sheet reference sits next to, plus the label printed on it."""
        page=self._page(number)
        bbox=page['render_bbox']
        centre=((box[0]+box[2])/2-bbox[0],(box[1]+box[3])/2-bbox[1])
        # A rotated reference is printed ALONG its wire: then the end lies on the text's own axis
        # (same x, further down), not beside it. Search window follows the text, never widens both ways.
        tall=(box[3]-box[1])>(box[2]-box[0])
        ends=ends_near(page['segments'],centre,*((8.0,45.0) if tall else (45.0,8.0)))
        if len(ends)!=1:
            if not ends:
                return None,[],'NO_LINE_END_AT_REFERENCE'
            # KESİKLİ HAT: bir tire dizisinin her parçasının iki ucu vardır, bu yüzden
            # referansın yanında birden çok uç görünür ve kural fail-closed kapanırdı.
            # Uçların hepsi ÖLÇÜLMÜŞ tek bir koşuya aitse, referansın ucu o koşunun kendi
            # ucudur. Bu bir yakınlık tahmini değildir; kesik BOŞLUĞU da köprülenmez —
            # yalnız "bu yazı hangi çizilmiş hattın ucunda duruyor" sorusu yanıtlanır.
            end=self._dash_run_end(number,ends,centre)
            if end is None:
                return None,[],'MULTIPLE_LINE_ENDS_AT_REFERENCE'
        else:
            end=ends[0]
        # Sayfa devamı eşleşmesi POTANSİYEL ADIYLA SINIRLI DEĞİLDİR: uçta basılı kablo damar
        # kimliği (örn. "112/3W67:9") de aynı iletkeni iki sayfada eşleştirir. Ölçüm/birim
        # yazıları ve cihaz etiketleri yine dışarıdadır; eşleşen yazının TÜRÜ kayda geçer.
        labels=signal_labels(page['words'],(end['point'][0]+bbox[0],end['point'][1]+bbox[1]),
                             *((8.0,120.0) if tall else (120.0,8.0)),
                             kinds=('POTENTIAL','CABLE_CORE','UNRECOGNISED'))
        return end,labels,None

    def _continuation_rows(self,number):
        return self.continuations(number)['rows']

    def continuations(self,number=None):
        """P05: sayfa devamlarını hedef sayfanın kendi çizgisiyle doğrula. Tel iddiası yok."""
        with self.lock:
            index=self._index()
            source=int(number or self.manifest['physical_page'])
            if source not in self.viewable_pages():
                raise ValueError('Bu çalışmada izlenmeyen sayfa: %s'%source)
            page=next(p for p in index if p['physical_page']==source)
            # Çalışmanın izlediği sayfalar (manifest) + önbellekte hazırlanmış sayfalar.
            traced=set(self.manifest.get('traced_pages',[source]))
            if self.cache is not None:
                traced|=set(self.cache.prepared())
            rows=[]
            for ref in references_for_page(source,index):
                row=dict(text=ref['text'],kind=ref['kind'],target_pages=ref['target_pages'],
                         resolution=ref['status'],position_token=ref.get('position_token'),
                         display_box=self._shift(ref['box'],source),issues=list(ref['issues']),
                         relation='SHEET_CONTINUATION_EVIDENCE_ONLY_NOT_A_WIRE',production_ready=False)
                if ref['kind']=='DEVICE_CROSS_REFERENCE':
                    # A contact/coil pointer is another symbol of the same device, never a wire continuation.
                    rows.append(dict(row,status='DEVICE_REFERENCE_NOT_A_CONTINUATION',
                                     owner_device=ref.get('owner_device')))
                    continue
                end,labels,problem=self._wire_end(source,ref['box'])
                row.update(source_end=end,source_labels=[l['text'] for l in labels],
                           source_signal=labels[0]['text'] if labels else None)
                if problem:
                    rows.append(dict(row,status=problem))
                    continue
                if ref['status']!='RESOLVED':
                    rows.append(dict(row,status='TARGET_PAGE_'+ref['status']))
                    continue
                target=ref['target_pages'][0]
                if target not in traced:
                    rows.append(dict(row,status='TARGET_PAGE_NOT_TRACED',
                                     note='Hedef sayfanın geometrisi bu çalışmada yok; --pages ile '
                                          'veya sayfa gezgininden hazırlanmalı.'))
                    continue
                facts=next(p for p in index if p['physical_page']==target)
                back=[r for r in facts['cross_references']
                      if (r['anlage'] or facts['anlage'])==page['anlage'] and r['blatt']==page['blatt']]
                # Pair on the label printed ON the end (nearest word), not on any nearby text:
                # neighbouring rows carry their own potentials a few points away.
                matches,weak=[],[]
                for candidate in back:
                    other,other_labels,other_problem=self._wire_end(target,candidate['box'])
                    if other_problem or not other_labels or not labels:
                        continue
                    row_signal=dict(reference=candidate['text'],end=other,
                                    signal=other_labels[0]['text'],labels=[l['text'] for l in other_labels])
                    if other_labels[0]['text']==labels[0]['text']:
                        matches.append(row_signal)
                    elif {l['text'] for l in other_labels} & {l['text'] for l in labels}:
                        weak.append(row_signal)
                status=('RECIPROCAL_END_MATCHED' if len(matches)==1 else
                        'NO_RECIPROCAL_END_FOUND' if not matches else 'MULTIPLE_RECIPROCAL_ENDS')
                row['nearby_same_label_ends']=weak
                rows.append(dict(row,status=status,target_page=target,candidates=matches,
                                 back_references=[r['text'] for r in back]))
            return dict(page=source,rows=rows,traced_pages=sorted(traced),production_ready=False,
                        limitation='Eşleşme, iki sayfada karşılıklı sayfa referansı ve uçlara basılı aynı '
                                   'potansiyel adıyla kurulur; referansın pozisyon eki yorumlanmaz. '
                                   'Aynı potansiyelin devam etmesi elektriksel ağdır, fiziksel tel değildir: '
                                   'hedef sayfadaki cihaz ucu ancak o sayfada pin işaretlenirse doğrulanır.')

    def path(self,pin_id):
        """P05 pilotu: kaynak pin → doğrulanmış sayfa devamı → hedef sayfadaki işaretli uçlar.

        Bu bir ELEKTRİKSEL AĞ yoludur. Aynı potansiyelin başka sayfada devam etmesi tek bir
        fiziksel tel değildir; ortak potansiyelden zincir üretilmez, her sıçrama ayrı kanıtla verilir.
        """
        with self.lock:
            self.refresh()
            traced=self._trace(pin_id)
            source=next(p for p in self.pins if p['id']==pin_id)
            page=traced['page']
            byid={p['id']:p for p in self.pins}
            hops=[]
            for end in traced['open_ends']:
                match=next((c for c in self._continuation_rows(page)
                            if c.get('source_end') and
                            abs(c['source_end']['point'][0]-end['point'][0])<=PIN_ATTACH and
                            abs(c['source_end']['point'][1]-end['point'][1])<=PIN_ATTACH),None)
                hop=dict(from_page=page,from_point=end['point'],
                         relation='NETWORK_CONTINUATION_NOT_ONE_PHYSICAL_WIRE',production_ready=False)
                if match is None:
                    hops.append(dict(hop,status='NO_SHEET_REFERENCE_AT_END',
                                     reason='Bu açık ucun yanında çözülmüş bir sayfa referansı yok.'))
                    continue
                hop.update(reference=match['text'],signal=match.get('source_signal'),
                           continuation_status=match['status'],to_page=match.get('target_page'))
                if match['status']!='RECIPROCAL_END_MATCHED':
                    hops.append(dict(hop,status=match['status'],
                                     reason='Sayfa devamı doğrulanamadı; hedef uç seçilmedi.'))
                    continue
                target_point=match['candidates'][0]['end']['point']
                far=self.page_graph(match['target_page']).trace_from_point(tuple(target_point))
                reached=[dict(pin_id=t['pin_id'],device=byid[t['pin_id']]['device'],pin=byid[t['pin_id']]['pin'],
                              kind=byid[t['pin_id']]['kind'],point=byid[t['pin_id']]['point'],
                              in_scope=in_scope(byid[t['pin_id']]['device']),
                              method=byid[t['pin_id']].get('method','MANUAL'),
                              relation='DRAWN_REACHABILITY_ONLY',edges=len(t['path']))
                         for t in far['targets']]
                hops.append(dict(hop,to_point=target_point,status=('TARGET_PINS_REACHED' if reached else
                                 'NO_MARKED_PIN_ON_TARGET_PAGE'),target_pins=reached,
                                 target_issues=far['issues'],target_open_ends=far['open_ends'],
                                 target_edges=far['edges'],
                                 reason=None if reached else
                                 'Hedef sayfada bu hatta bağlı işaretli uç yok; uç işaretlenmeli.'))
            return dict(pin=source,page=page,local=traced,hops=hops,annotation_revision=self.revision,
                        production_ready=False,
                        limitation='Sayfa sıçraması aynı potansiyelin devamıdır: elektriksel ağ ilişkisi, '
                                   'tek fiziksel tel değil. Hedef uçlar yalnız o sayfada işaretlenmiş '
                                   'pinlerdir; işaretlenmemiş uç doğrulanmış sayılmaz.')

    def _components(self,graph):
        """Every drawn net on the sheet: nodes, pins, branch points, open ends, segments."""
        seen,groups=set(),[]
        for node in graph.adj:
            if node in seen:
                continue
            stack,nodes=[node],[]
            seen.add(node)
            while stack:
                current=stack.pop()
                nodes.append(current)
                for other,_ in graph.adj[current]:
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
            degrees={n:len({m for m,_ in graph.adj[n]}) for n in nodes}
            pins=[pid for n in nodes for pid in graph.node_pins[n]]
            points=[graph.coords[n] for n in nodes]
            groups.append(dict(nodes=nodes,pins=pins,
                               open_ends=[graph.coords[n] for n in nodes
                                          if degrees[n]==1 and not graph.node_pins[n]],
                               branch_points=[graph.coords[n] for n in nodes if degrees[n]>2],
                               unattached=[pid for n in nodes for pid in graph.node_unattached[n]],
                               segments=sorted({e['segment_id'] for n in nodes for _,e in graph.adj[n]}),
                               bbox=[round(min(p[0] for p in points),2),round(min(p[1] for p in points),2),
                                     round(max(p[0] for p in points),2),round(max(p[1] for p in points),2)]))
        return groups

    def _page_data(self,number):
        """Bir sayfanın ölçüm için gereken ham katmanları: parçalar, eğriler, maskeler, yazı kutuları."""
        page=self._page(number)
        bbox=page['render_bbox']
        return dict(segments=page['segments'],curves=self._page_curves(number),
                    masks=[dict(id=m['id'],bbox=m['bbox']) for m in self.boxes
                           if m.get('page',4)==number and m.get('active',True)],
                    word_boxes=[[w['x0']-bbox[0],w['top']-bbox[1],w['x1']-bbox[0],w['bottom']-bbox[1],
                                 w['text']] for w in page['words']],
                    render_bbox=bbox,words=page['words'])

    def _dash_signature(self,number,run_key):
        """Bir koşunun çizim imzası: hangi ham parçalar, hangi uçlar. Kanıt değişirse imza değişir."""
        for run in (self._dash_cache.get(number) or self.dash_proposals(number))['runs']:
            if '%s#%d'%(run['ruling'],run['index'])==run_key:
                return json.dumps([run['segment_ids'],run['ends']],sort_keys=True)
        raise ValueError('Kesikli hat koşusu bulunamadı: '+str(run_key))

    def _dash_decision(self,number,run_key,signature):
        """Bu koşu için kayıtlı insan kararı. Yoksa ONAY_BEKLIYOR; bayatsa NEEDS_REVIEW."""
        history=[r for r in self.reviews
                 if r.get('subject')=='DASH_RUN' and r.get('run_key')==run_key
                 and number in (r.get('pages') or [])]
        if not history:
            return dict(decision='ONAY_BEKLIYOR',decided_by=None,review_state='NO_DECISION',
                        review_reason=None,review_history=[])
        current=history[-1]
        frozen=(current.get('page_signatures') or {}).get('dash_run')
        stale=bool(current.get('stale_events'))
        changed=bool(frozen) and frozen[1]!=signature
        state=('CURRENT' if not stale and not changed else 'NEEDS_REVIEW')
        reason=None
        if changed:
            reason='Koşunun çizim imzası değişti (parça veya uç); eski karar geçerli sayılmaz.'
        elif stale:
            reason='Bağlı sayfada işaret/maske değişti (%d kez).'%len(current['stale_events'])
        return dict(decision=current['decision'] if state=='CURRENT' else 'ONAY_BEKLIYOR',
                    decided_by=current.get('reviewer'),review_state=state,review_reason=reason,
                    recorded_decision=current['decision'],
                    review_history=[dict(reference=r.get('reference') or r['id'],
                                         decision=r['decision'],reviewer=r.get('reviewer'),
                                         recorded_utc=r.get('recorded_utc'),
                                         stale_events=len(r.get('stale_events') or []))
                                    for r in history])

    def dash_proposals(self,number=None):
        """Kesikli / kesikli-noktalı hatlar için ÖNERİ. Graf ve ham parçalar değişmez.

        Üç kanıt türü BİLEREK ayrı alanlarda durur ve birbirine dönüşmez:
          * `evidence`      — çizimden okunan görsel kanıt (yazı, nokta, kutu, kesişme),
          * `path_evidence` — grafın bugün gerçekten izleyebildiği yol (kesikli hatta: yok),
          * `decision`      — insan kararı; varsayılan `ONAY_BEKLIYOR`, Claude asla dolduramaz.
        """
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            page=self._page(number)
            bbox=page['render_bbox']
            data=self._page_data(number)
            pins=[p for p in self.pins if p.get('page',4)==number]
            graph=self.page_graph(number)
            dots,rejected_dots=dashed.junction_dots(data['curves'],with_rejected=True)
            runs=dashed.rulings(data,dots)

            def near_box(word,where,limit):
                # Yazının KUTUSUNA uzaklık: döndürülmüş (uzun) etiketlerde merkez yanıltır.
                dx=max(word['x0']-where[0],where[0]-word['x1'],0.0)
                dy=max(word['top']-where[1],where[1]-word['bottom'],0.0)
                return (dx*dx+dy*dy)**0.5<=limit

            def labels_at(point):
                where=(point[0]+bbox[0],point[1]+bbox[1])
                close=[w for w in page['words'] if near_box(w,where,10.0)]
                # Kesikli hat kanıtında YALNIZ potansiyel adı sayılır: kesit, birim, kablo damarı
                # ve tanınmayan yazı bir potansiyel kanıtı değildir.
                names={l['text'] for l in signal_labels(page['words'],where,dx=26.0,dy=26.0,
                                                        kinds=('POTENTIAL',))}
                potentials=[w['text'] for w in close if w['text'] in names]
                sheets=[w['text'] for w in close if XREF.match(w['text'].strip())]
                return dict(potentials=sorted(set(potentials)),sheet_references=sorted(set(sheets)))

            result=dashed.proposals(data,runs=runs,dots=dots,pins=pins,labels_at=labels_at)
            dashed.measure_dots(result['dots'],page['segments'],result['boxes'])
            result['rejected_dots']=rejected_dots
            # Algoritmik yol kanıtı ÖLÇÜLÜR, varsayılmaz: graf, TAM ORTAK UÇ paylaşan parçaları
            # zaten birleştirir (kesikli olsalar bile); birleştirmediği şey kesik BOŞLUĞUDUR.
            component_of,component_pins={},{}
            for index,comp in enumerate(self._components(graph)):
                component_pins[index]=list(comp['pins'])
                for sid in comp['segments']:
                    component_of[sid]=index
            byid={q['id']:q for q in self.pins}
            for row in result['runs']:
                groups=sorted({component_of[i] for i in row['segment_ids'] if i in component_of})
                attached=sorted({pid for g in groups for pid in component_pins.get(g,[])})
                targets=[]
                for pid in attached:
                    for t in self._trace(pid)['targets']:
                        other=byid[t['pin_id']]
                        targets.append('%s:%s'%(other['device'],other['pin']))
                row['path_evidence']=dict(
                    graph_joins_pieces=len(groups)<len(row['segment_ids']),
                    graph_components=len(groups),pieces=len(row['segment_ids']),
                    traced_targets=sorted(set(targets)),attached_pins=attached,
                    note=('Graf, tam ortak uç paylaşan parçaları birleştirir; kesik BOŞLUĞUNU '
                          'birleştirmez. Bu koşunun %d parçası grafta %d ayrı bileşende duruyor. '
                          'Görsel kanıt bu alanın yerine geçmez.'
                          %(len(row['segment_ids']),len(groups))))
                row['page']=number
                row['production_ready']=False
                row['run_key']='%s#%d'%(row['ruling'],row['index'])
                # İnsan kararı SABİT DEĞİL: reviews tablosundan okunur, koşunun çizim imzasına
                # bağlıdır ve Claude tarafından doldurulamaz.
                row.update(self._dash_decision(
                    number,row['run_key'],
                    json.dumps([row['segment_ids'],row['ends']],sort_keys=True)))
            result.update(page=number,annotation_revision=self.revision,
                          graph_unchanged=True,
                          raw_geometry_untouched=True,
                          note='MAIN.md: ortak potansiyel ağından fiziksel tel zinciri türetilmez. '
                               'Onaylanan bir koşu bile yalnız AĞ ilişkisidir; uç çifti üretmez.')
            return result

    def drawing_classes(self,number=None,components=None):
        """Her çizim bileşenini KANITIYLA sınıflandır: incelenmemiş sayısı bağlantı sayısı değildir.

        Her sınıfın ölçülebilir bir gerekçesi vardır (yazı kutusu, sembol maskesi, dolgu taraması,
        kesikli cetvel, sayfa çerçevesi). Hiçbir şey toplu elenmez: hiçbir kurala girmeyen bileşen
        AÇIKLANMAYAN olarak tek tek listelenir ve incelenmemiş sayılır.
        """
        with self.lock:
            self.refresh()
        number=int(number or self.manifest['physical_page'])
        page=self._page(number)
        bbox=page['render_bbox']
        width,height=bbox[2]-bbox[0],bbox[3]-bbox[1]
        comps=components if components is not None else self._components(self.page_graph(number))
        words=[[w['x0']-bbox[0],w['top']-bbox[1],w['x1']-bbox[0],w['bottom']-bbox[1]] for w in page['words']]
        block=[w for w,raw in zip(words,page['words']) if raw['text'] in ('Datum','Kommission','Blatt')]
        title_top=min((w[1] for w in block),default=height)
        masks=[m['bbox'] for m in self.boxes if m.get('page',4)==number and m.get('active',True)]
        # Kesikli / kesikli-noktalı hatlar: ölçülmüş desen üzerinden (dashed.py). Her parça,
        # ait olduğu KOŞUNUN sınıfını taşır: kapalı kutu kenarı mı, iletken adayı mı, belirsiz mi.
        proposal=self.dash_proposals(number) if components is None else None
        if proposal is None:
            proposal=self._dash_cache.get(number) or self.dash_proposals(number)
        self._dash_cache[number]=proposal
        dash_kind={}
        for run in proposal['runs']:
            for sid in run['segment_ids']:
                dash_kind[sid]=(run['kind'],run['reason'])
        rule_y=sorted({r['coord'] for r in proposal['runs'] if r['axis']=='y'})
        rule_x=sorted({r['coord'] for r in proposal['runs'] if r['axis']=='x'})
        # Dolu sembol gövdeleri hairline yığınıdır. Yığın testi YEREL olmalı: aynı sütunda
        # olmak yetmez, parçanın o yığının bir üyesine 0,4 pt içinde olması gerekir. Ölçüm
        # katmanının kendi testi kullanılır ki iki yerde iki farklı kural olmasın.
        fill_ids=dashed.fill_scanlines(page['segments'])

        seg_by_id={seg['id']:seg for seg in page['segments']}
        edge=0.08*min(width,height)

        def page_frame(c):
            """Uzunluk TEK BAŞINA çerçeve kanıtı değildir. Üç değer döner.

            Üç bağımsız kanıt birlikte aranır:
              (1) her İKİ yönde de sayfanın yüzde 90 üstü,
              (2) dört kenarın da sayfa sınırına yakın olması,
              (3) sayfa boyunca uzanan, hem yatay hem dikey parçalardan oluşan ve en az dört
                  T/dal noktası taşıyan ızgara.

            Ölçülen paylar (bu belgenin 73 sayfası): gerçek çerçeve genişlik oranı 0,9982;
            yükseklik oranı 0,9275–0,9450 — (1) için en dar pay 22,3 pt. Kenar toleransı
            0,08·min(W,H) = 64,79 pt; en kötü gerçek çerçevenin üst kenarı 57,69 pt, yani (2)
            için pay yalnız 7,10 pt. Toleransı 0,06·min(W,H) yapmak 11 sayfanın çerçevesini
            kaybettirir. TEK YÖNLÜ bir eşiğe dönülemez: aynı belgede %91,0 genişliğinde
            gerçek bir dağıtım barası vardır ve (1)'i tek başına geçer.

            (1)+(2) sağlanıp (3) sağlanmazsa sonuç 'UNDECIDED'tir: çerçeve sayılmaz, AÇIK İŞTE
            kalır ve başka hiçbir kural onu yutamaz.
            """
            box=c['bbox']
            if box[2]-box[0] < 0.90*width or box[3]-box[1] < 0.90*height:
                return None
            if not (box[0]<=edge and box[1]<=edge and width-box[2]<=edge and height-box[3]<=edge):
                return None
            parts=[seg_by_id[i] for i in c['segments'] if i in seg_by_id]
            horizontal=sum(1 for q in parts if abs(q['a'][1]-q['b'][1])<=0.02)
            vertical=sum(1 for q in parts if abs(q['a'][0]-q['b'][0])<=0.02)
            if len(parts)>=4 and horizontal>=2 and vertical>=2 and len(c['branch_points'])>=4:
                return 'FRAME'
            return 'UNDECIDED' 

        def inside(box,outer,pad=1.0):
            return (box[0]>=outer[0]-pad and box[2]<=outer[2]+pad
                    and box[1]>=outer[1]-pad and box[3]<=outer[3]+pad)

        def classify(c):
            box=c['bbox']
            if c['pins']:
                return 'MARKED_NET','Üzerinde işaretli uç var.'
            if box[1]>=title_top-2:
                return 'TITLE_BLOCK','Yazı bloğunun üstünde (y>=%.1f).'%title_top
            verdict=page_frame(c)
            if verdict=='FRAME':
                return 'PAGE_FRAME',('Sayfa çerçevesi: her iki yönde de sayfanın yüzde 90 üstü, '
                                     'dört kenarı da sayfa sınırında ve sayfa boyunca uzanan '
                                     'yatay+dikey ızgara (%d parça, %d T/dal noktası).'
                                     % (len(c['segments']),len(c['branch_points'])))
            if verdict=='UNDECIDED':
                return 'PAGE_FRAME_UNDECIDED',('Sayfa kadar büyük ve dört kenarı sayfa sınırında, '
                                               'ama çerçeve ızgarası yok (%d parça, %d T/dal '
                                               'noktası). Belirsiz: AÇIK İŞTE kalır.'
                                               % (len(c['segments']),len(c['branch_points'])))
            if any(inside(box,m) for m in masks):
                return 'SYMBOL_INTERIOR_MASK','Elle çizilmiş sembol maskesinin içinde.'
            if c['segments'] and all(i in fill_ids for i in c['segments']):
                return 'SYMBOL_FILL_SCANLINE',('Dolu sembol gövdesinin tarama çizgisi: aynı '
                                               'sütunda >=10 hairline, ardışıkları arasında '
                                               '<=0,4 pt adım.')
            # Sınıf tek bir segmentten DEVRALINMAZ: bileşenin bütün parçaları aynı kesikli
            # koşu sınıfına ait olmalı. Aksi hâlde tek segment üzerinden koca bir bileşen
            # sessizce "iş değil" olabilirdi.
            verdicts={dash_kind[i][0] for i in c['segments'] if i in dash_kind}
            if verdicts and len(verdicts)==1 and all(i in dash_kind for i in c['segments']):
                only=verdicts.pop()
                return 'DASH_'+only,('Ölçülmüş kesikli hat koşusunun parçası (bileşenin TÜM '
                                     'parçaları aynı koşu sınıfında). '
                                     +next(v[1] for k,v in dash_kind.items() if k in c['segments']))
            if any(inside(box,w) for w in words):
                return 'TEXT_STROKE','Basılı bir yazının kutusunun içinde.'
            if (max(box[2]-box[0],box[3]-box[1])>=20.0 and min(box[2]-box[0],box[3]-box[1])<0.05
                    and len(c['open_ends'])==2 and not c['branch_points']):
                return 'CONDUCTOR_CANDIDATE','Tek eksende 20pt+ sürekli çizgi, iki açık uç, dal yok: iletken adayı, işaretli ucu yok.'
            return 'UNEXPLAINED','Hiçbir kanıt kuralına girmedi; incelenmemiş sayılır.'

        self._class_cache[number]={id(c):classify(c) for c in comps}
        classes,unexplained={},[]
        for c in comps:
            name,why=self._class_cache[number][id(c)]
            entry=classes.setdefault(name,dict(kind=name,count=0,reason=why,examples=[]))
            entry['count']+=1
            if len(entry['examples'])<3:
                entry['examples'].append(c['bbox'])
            # Hiçbir sınıf toplu elenmez: "iş değil" sayılan sınıfların üyeleri de tek tek durur.
            if name in ('UNEXPLAINED','CONDUCTOR_CANDIDATE','PAGE_FRAME_UNDECIDED',
                        'DASH_ZONE_BOX_EDGE','DASH_CONDUCTOR_CANDIDATE','DASH_UNDECIDED',
                        'PAGE_FRAME','TITLE_BLOCK'):
                entry.setdefault('items',[]).append(
                    dict(bbox=c['bbox'],segments=len(c['segments']),
                         open_ends=c['open_ends'],branch_points=c['branch_points']))
            if name=='UNEXPLAINED':
                unexplained.append(dict(bbox=c['bbox'],segments=len(c['segments']),
                                        open_ends=c['open_ends'],branch_points=c['branch_points']))
        return dict(page=number,components=len(comps),
                    classes=sorted(classes.values(),key=lambda r:-r['count']),
                    unexplained=unexplained,unexplained_count=len(unexplained),
                    dashed_rules=dict(horizontal=rule_y,vertical=rule_x),
                    dash_runs=[dict(ruling=r['ruling'],index=r['index'],kind=r['kind'],
                                    ends=r['ends'],pieces=r['pieces'],
                                    evidence=[e['kind'] for e in r['evidence']])
                               for r in proposal['runs']],
                    dash_links=proposal['links'],dash_boxes=proposal['boxes'],
                    junction_dots=proposal['dots'],
                    production_ready=False,
                    note='MARKED_NET dışındaki sınıflar çizim kanıtıdır; işaretli uç taşıyan '
                         'bileşen önce MARKED_NET sayılır, yani bu tek sınıf insan işaretinin '
                         'fonksiyonudur. Sınıf kapsam kararı değildir: kapsamı cihaz adı belirler. '
                         'Kesikli cetveller gerçek iletken olabilir ama parçalı çizildikleri için '
                         'graf onları birleştirmez; bu bir sınırdır, yokluk kanıtı değildir. '
                         'AÇIKLANMAYAN bileşenler tek tek listelenir, toplu elenmez.')

    def _sheet_reference_near(self,number,point,refs):
        return sorted({r['text'] for r in refs
                       if abs((r['display_box'][0]+r['display_box'][2])/2-point[0])<=45
                       and abs((r['display_box'][1]+r['display_box'][3])/2-point[1])<=12})

    def _implementation(self,reference):
        """Bir bağlantının UYGULAMA TÜRÜ: tel mi, aksesuar köprü mü, cihaz içi mi?

        İlişki teyidinden ve üretime uygunluktan AYRI bir boyuttur. Kaydı yoksa BELIRSIZ'dir;
        Claude dolduramaz, yalnız kullanıcı kaydı doldurur. Bir tür kaydı, askıya alınmış bir
        incelemeyi tazelemez ve bağlantıyı üretime uygun yapmaz.
        """
        history=[r for r in self.reviews
                 if r.get('subject')=='IMPLEMENTATION_TYPE' and r.get('reference')==reference]
        if not history:
            return dict(implementation_type='BELIRSIZ',implementation_source=None,
                        implementation_note='Uygulama türü kaydı yok: tel mi, takılabilir köprü mü, '
                                            'cihaz içi mi belirlenmedi.',
                        implementation_history=[])
        current=history[-1]
        return dict(implementation_type=current.get('implementation','BELIRSIZ'),
                    implementation_source=current.get('reviewer'),
                    implementation_note=current.get('note',''),
                    implementation_history=[dict(implementation=r.get('implementation'),
                                                 reviewer=r.get('reviewer'),
                                                 source=r.get('source'),
                                                 recorded_utc=r.get('recorded_utc'))
                                            for r in history])

    def table(self,number=None):
        """P05: sayfa bağlantı tablosu. Fiziksel çift, ağ ilişkisi ve belirsizlik ayrı tutulur."""
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            graph=self.page_graph(number)
            byid={p['id']:p for p in self.pins}
            index=self._index()
            refs=[dict(r,display_box=self._shift(r['box'],number)) for r in references_for_page(number,index)]
            page=next(p for p in index if p['physical_page']==number)
            labels=[dict(text=d['text'],box=self._shift(d['box'],number),
                         device=full_device_name(d,page)[0]) for d in page['devices']]
            rows,gaps,other=[],[],[]
            components=self._components(graph)
            breakdown=self.drawing_classes(number,components)
            verdict=self._class_cache[number]
            run_of={sid:'%s#%d'%(r['ruling'],r['index'])
                    for r in (self._dash_cache.get(number) or {}).get('runs',[])
                    for sid in r['segment_ids']}
            # Sayfa çerçevesi, yazı bloğu ve dolgu taraması AÇIK İŞ değildir: kanıtı ölçülebilir
            # ve sınıf dökümünde görünür kalır. Belirsiz olan hiçbir şey buradan elenmez.
            # Kesikli iletken adayı ve belirsiz koşu AÇIK İŞTİR: graf onları izleyemiyor.
            NOT_WORK={'PAGE_FRAME','TITLE_BLOCK','SYMBOL_FILL_SCANLINE','TEXT_STROKE',
                      'DASH_ZONE_BOX_EDGE'}
            for net in components:
                pins=[byid[i] for i in net['pins']]
                describe=lambda p:dict(pin_id=p['id'],device=p['device'],pin=p['pin'],kind=p['kind'],
                                       point=p['point'],method=p.get('method','MANUAL'),
                                       scope=endpoint_scope(p['device'],p['pin']),
                                       in_scope=in_scope(p['device']) and bool(p['pin'].strip()))
                sheet=sorted({r for end in net['open_ends'] for r in self._sheet_reference_near(number,end,refs)})
                near_labels=sorted({l['device'] for l in labels
                                    if not (l['box'][2]<net['bbox'][0]-30 or l['box'][0]>net['bbox'][2]+30
                                            or l['box'][3]<net['bbox'][1]-30 or l['box'][1]>net['bbox'][3]+30)})
                centre=((net['bbox'][0]+net['bbox'][2])/2,(net['bbox'][1]+net['bbox'][3])/2)
                nearest=min(labels,key=lambda l:abs((l['box'][0]+l['box'][2])/2-centre[0])
                            +abs((l['box'][1]+l['box'][3])/2-centre[1]),default=None)
                common=dict(net_id='net:%s:%s:%s'%(number,net['bbox'][0],net['bbox'][1]),
                            bbox=net['bbox'],segments=len(net['segments']),segment_ids=net['segments'],
                            nearest_device_label=nearest and nearest['device'],
                            branch_points=net['branch_points'],open_ends=net['open_ends'],
                            sheet_references=sheet,nearby_device_labels=near_labels,
                            unattached_pins=sorted(set(net['unattached'])),production_ready=False)
                if not pins:
                    # En yakın etiket değil, penceredeki HERHANGİ bir kapsam içi etiket sayılır:
                    # aksi hâlde sayfa 28/36'nın en büyük besleme ağı açık işten düşüyordu.
                    owner_in_scope=any(in_scope(d) for d in near_labels) or \
                        (bool(nearest) and in_scope(nearest['device']))
                    kind_of,why_of=verdict[id(net)]
                    # İletken adayı (düz ya da kesikli) ve belirsiz koşu HER ZAMAN açık iştir:
                    # yakınında kapsam içi cihaz yazısı olmaması onu iş olmaktan çıkarmaz.
                    always_work=kind_of in ('CONDUCTOR_CANDIDATE','DASH_CONDUCTOR_CANDIDATE',
                                            'DASH_UNDECIDED','PAGE_FRAME_UNDECIDED')
                    # ÖLÇÜLMÜŞ geometri (dolgu yığını, çerçeve ızgarası, yazı bloğu, kutu kenarı)
                    # "yakınında kapsam içi yazı var" kanıtından güçlüdür: yakınlıktan iş üretmek
                    # MAIN.md'nin yasakladığı davranıştır. Bunun yerine NOT_WORK'e giren her
                    # bileşen sınıf dökümünde TEK TEK listelenir (aşağıda `items`).
                    bucket=(other if kind_of in NOT_WORK else
                            gaps if (always_work or sheet or (near_labels and owner_in_scope))
                            else other)
                    bucket.append(dict(common,kind='NO_MARKED_END_ON_NET',
                                       owner_in_scope=owner_in_scope,
                                       drawing_class=kind_of,drawing_class_reason=why_of,
                                       dash_run=next((run_of[i] for i in net['segments']
                                                      if i in run_of),None),
                                       reason=(why_of if kind_of in NOT_WORK else
                                               'Sayfa devamı referansı var, işaretli uç yok.' if sheet else
                                               'İletken adayı: işaretli uç yok, graf izleyemiyor. '
                                               +why_of if always_work else
                                               'Kapsam içi cihaz yazısına yakın çizim, işaretli uç yok.'
                                               if owner_in_scope else
                                               'En yakın cihaz kapsam dışı (saha/başka konum) ya da yalnız '
                                               'çerçeve/yazı çizgisi; incelenmedi.')))
                    continue
                clean=not net['branch_points'] and not net['open_ends'] and not net['unattached']
                scopes=[endpoint_scope(q['device'],q['pin']) for q in pins]
                scope=pair_scope(scopes)
                same_device=(len(pins)==2 and
                             normalized(pins[0]['device'])==normalized(pins[1]['device']))
                reference='net:%s:%s:%s'%(number,net['bbox'][0],net['bbox'][1])
                implementation=self._implementation(reference)
                if len(pins)==2 and clean and scope=='IN_SCOPE_BOTH':
                    kind,note='PHYSICAL_PAIR','İki uç, dalsız ve açık uçsuz tek yol: fiziksel tel adayı.'
                elif len(pins)==2 and clean:
                    # KAPSAM KUSURU DÜZELTMESİ: saha ya da belirsiz kapsamlı ucu olan bir bağ,
                    # pano içi fiziksel tel adayı DEĞİLDİR (MAIN.md "PANO SINIRI KURALI").
                    # İlişki silinmez, satır kalır; yalnız aday olmaktan çıkar.
                    kind='PAIR_OUT_OF_PANEL_SCOPE'
                    note=('İki uç arasında çizim yolu var ama %s: pano içi tek damar tel adayı '
                          'DEĞİL. İlişki görünür kalır, üretim listesine giremez.'
                          %('bir uç pano dışı (saha/başka yerleşim)' if scope=='OUT_OF_PANEL_END'
                            else 'en az bir ucun kapsamı belirsiz'))
                elif len(pins)==1:
                    kind,note='SINGLE_END','Ağda tek işaretli uç var; karşı uç işaretlenmemiş.'
                else:
                    kind,note=('NETWORK_GROUP','Ağda ikiden fazla uç veya dal var: ortak potansiyel. '
                               'Fiziksel tel çiftleri buradan türetilmez.')
                if same_device:
                    # SEMBOL İÇİ / HARİCİ JUMPER AYRIMI: otomatik eleme YOK. Aynı cihazın iki ucu
                    # cihaz içi bağlantı da olabilir, dışarıdan çekilmiş bir jumper da.
                    note+=(' Aynı cihazın iki ucu: cihaz içi bağlantı da olabilir, harici jumper '
                           'da. Otomatik elenmedi; uygulama türü kullanıcı kaydıyla belirlenir.')
                names=[normalized(p['device'])+':'+normalized(p['pin']) for p in pins]
                rows.append(dict(common,kind=kind,note=note,pins=[describe(p) for p in pins],
                                 reference=reference,
                                 scope_state=scope,endpoint_scopes=scopes,same_device=same_device,
                                 duplicate_names=len(names)!=len(set(names)),
                                 unresolved=bool(net['open_ends'] or net['unattached']),
                                 **implementation))
            # Independent second pass: short bridges and T branches are counted from the drawing,
            # not from the rows, and then matched against the rows.
            rows.extend(self._confirmed_pairs(number,graph,byid,refs))
            short=[s for s in self._page(number)['segments']
                   if abs(s['a'][0]-s['b'][0])+abs(s['a'][1]-s['b'][1])<=SHORT_SEGMENT]
            in_rows={sid for r in rows for sid in ()}
            row_segments={sid:r for r in rows for sid in r.get('segment_ids',[])}
            gap_segments={sid for g in gaps for sid in g.get('segment_ids',[])}
            excluded={e['segment_id'] for e in graph.excluded}
            short_ids={s['id'] for s in short}
            # Kovalar AYRIK tutulur: aynı parça iki kez sayılmaz, toplam daima eşit çıkar.
            in_rows=short_ids&set(row_segments)
            in_gaps=(short_ids&gap_segments)-in_rows
            in_excluded=(short_ids&excluded)-in_rows-in_gaps
            unaccounted=short_ids-in_rows-in_gaps-in_excluded
            second=dict(short_segment_limit=SHORT_SEGMENT,short_segments=len(short),
                        short_in_rows=len(in_rows),
                        short_in_gaps=len(in_gaps),
                        short_excluded_from_graph=len(in_excluded),
                        short_unaccounted=sorted(unaccounted)[:20],
                        short_unaccounted_count=len(unaccounted),
                        branch_points_in_rows=sum(len(r['branch_points']) for r in rows),
                        branch_points_in_gaps=sum(len(g['branch_points']) for g in gaps),
                        unjoined_crossings=len(graph.crossings),
                        note='Kısa köprüler ve T dalları çizimden bağımsız sayılıp satır/boşluklarla '
                             'eşleştirilir. "unaccounted" olanlar hiçbir satıra veya boşluğa girmemiştir: '
                             'çoğu çerçeve/yazı çizgisidir, ama incelenmemiştir.')
            return dict(page=number,rows=sorted(rows,key=lambda r:(r['kind'],r['bbox'])),gaps=gaps,
                        unreviewed_nets=len(other),unreviewed_sample=[o['bbox'] for o in other[:20]],
                        unreviewed_breakdown=breakdown,
                        second_pass=second,annotation_revision=self.revision,production_ready=False,
                        limitation='Satırlar çizim erişimidir; kesit, renk ve üretim onayı yoktur. '
                                   'Pano içi tel adayı olmak için İKİ ucun da kapsam içi olması '
                                   'şarttır: saha ya da belirsiz kapsamlı uç taşıyan satır '
                                   'PAIR_OUT_OF_PANEL_SCOPE olur, ilişki görünür kalır. İlişki '
                                   'teyidi, uygulama türü (tel/aksesuar/cihaz içi) ve üretime '
                                   'uygunluk AYRI alanlardır; biri diğerini doldurmaz. '
                                   'PHYSICAL_PAIR yalnız aday demektir. NETWORK_GROUP satırından uç çifti '
                                   'türetilmez. İşaretli ucu olmayan ağlar boşluk olarak listelenir. '
                                   'CONFIRMED_PHYSICAL_PAIR satırında çizgi kanıtı (line_evidence) ile '
                                   'inceleme durumu (review_state) ayrı alanlardır; askıya alınmış karar '
                                   'silinmez, satır "yeniden inceleme gerekiyor" olarak kalır.')

    def _confirmed_pairs(self,number,graph,byid,refs):
        """MAIN.md gereği: kullanıcı teyitli fiziksel uç çiftleri kendi satırında görünür.

        Bir fiziksel uç çifti ana tabloda TEK satırdır: kaynak-hedef yönü satır üretmez ve yeniden
        onay yeni satır açmaz, o bağlantının güncel incelemesi olur. Eski kararlar silinmez;
        satırın inceleme geçmişinde durur. Kaynak yalnız açık teyitlerdir: tohum claim kayıtları ve
        PIN_PAIR inceleme kararları. Ortak ağdan otomatik çift veya zincir TÜRETİLMEZ.
        """
        claim_status={row['id']:row for row in self.claims()}
        review_status={row['id']:row for row in self.review_status()['rows']}
        decisions=[]
        for claim in self.seeds.get('claims',[]):
            if claim.get('kind') not in ('PHYSICAL','NETWORK'):
                continue
            state=claim_status.get(claim['id'],{})
            decisions.append(dict(reference=claim['id'],pins=(claim['source_id'],claim['target_id']),
                                  reviewer=claim.get('reviewer') or 'Kullanıcı (tohum teyidi)',
                                  origin='SEED_CLAIM',decision='CONFIRMED',note=claim.get('note',''),
                                  # HAT seviyesinde teyit: MAIN.md 2026-09-08 §1 gereği ana tabloda
                                  # KENDİ satırında görünür, ama fiziksel tel çifti SAYILMAZ.
                                  level=claim.get('kind'),
                                  recorded_utc=None,record_id=claim['id'],
                                  state='CURRENT' if state.get('status')=='CONFIRMED_BOTH' else 'NEEDS_REVIEW',
                                  reason=None if state.get('status')=='CONFIRMED_BOTH'
                                  else 'Tohum teyidi askıda: işaretleme değişti veya yol bulunamadı.'))
        for review in self.reviews:
            if review.get('subject')!='PIN_PAIR' or len(review.get('pin_ids',[]))!=2:
                continue
            state=review_status.get(review['id'],{})
            decisions.append(dict(reference=review.get('reference') or review['id'],
                                  pins=tuple(review['pin_ids']),reviewer=review.get('reviewer',''),
                                  origin='USER_REVIEW',decision=review.get('decision','CONFIRMED'),
                                  note=review.get('note',''),recorded_utc=review.get('recorded_utc'),
                                  record_id=review['id'],state=state.get('status','NEEDS_REVIEW'),
                                  level='PHYSICAL',reason=state.get('reason')))
        # Direction is not identity: the same two physical ends are one connection.
        groups={}
        for entry in decisions:
            a,b=entry['pins']
            if a not in byid or b not in byid:
                continue
            if byid[a].get('page',4)!=number or byid[b].get('page',4)!=number:
                continue
            groups.setdefault(tuple(sorted((a,b))),[]).append(entry)
        rows=[]
        for key,entries in groups.items():
            seed=next((e for e in entries if e['origin']=='SEED_CLAIM'),None)
            reference=(seed or entries[0])['reference']          # C01/C02/C03 sabit kalır
            current=entries[-1]                                   # en son açık karar
            # Bir uç çifti için HAT ve FİZİKSEL teyit bir arada varsa fiziksel olan geçerlidir.
            level='PHYSICAL' if any(e.get('level')=='PHYSICAL' for e in entries) else 'NETWORK'
            a,b=byid[entries[-1]['pins'][0]],byid[entries[-1]['pins'][1]]
            traced=self.page_graph(number).trace(a['id'])
            hit=next((t for t in traced['targets'] if t['pin_id']==b['id']),None)
            pins=[dict(pin_id=q['id'],device=q['device'],pin=q['pin'],kind=q['kind'],point=q['point'],
                       method=q.get('method','MANUAL'),
                       scope=endpoint_scope(q['device'],q['pin']),
                       in_scope=in_scope(q['device']) and bool(q['pin'].strip())) for q in (a,b)]
            scopes=[q['scope'] for q in pins]
            scope=pair_scope(scopes)
            same_device=normalized(a['device'])==normalized(b['device'])
            implementation=self._implementation(reference)
            bbox=[round(min(q['point'][0] for q in (a,b)),2),round(min(q['point'][1] for q in (a,b)),2),
                  round(max(q['point'][0] for q in (a,b)),2),round(max(q['point'][1] for q in (a,b)),2)]
            # Two independent facts, never merged: is the line still there, is the decision still valid.
            line_evidence='CURRENT_PATH_FOUND' if hit else 'NO_CURRENT_PATH'
            valid=current['state']=='CURRENT' and current['decision']=='CONFIRMED'
            # Teyitli çift de KAPSAM kontrolünden geçer. Geçmiş ilişki asla silinmez; kapsam
            # sorunu ayrı alanda gösterilir ve satır üretim adayı olmaktan çıkar.
            if level=='NETWORK':
                # MAIN.md: "Hat seviyesinde doğrulandı; kesin fiziksel klemens/bağlantı tarafı
                # bekleniyor." Bu satır ne gizlenir ne de fiziksel tel sayılır.
                label=('HAT SEVİYESİNDE TEYİTLİ — FİZİKSEL KLEMENS SEÇİMİ BEKLENİYOR' if valid
                       else 'GEÇMİŞTE HAT SEVİYESİNDE TEYİTLİ — YENİDEN İNCELEME GEREKİYOR')
            else:
                label=('TEYİTLİ ÇİFT' if valid and hit and scope=='IN_SCOPE_BOTH' else
                       'TEYİTLİ — KAPSAM DIŞI UÇ, PANO İÇİ TEL ADAYI DEĞİL' if valid and hit
                       else 'GEÇMİŞTE TEYİTLİ — YENİDEN İNCELEME GEREKİYOR')
            reasons=[]
            if not hit:
                reasons.append('Güncel çizimde yol bulunamadı (çatışma).')
            if not valid:
                reasons.append(current['reason'] or 'İnceleme askıda; yeniden inceleme gerekiyor.')
            if scope!='IN_SCOPE_BOTH':
                reasons.append('Kapsam: %s. Pano içi tek damar tel adayı değil; ilişki görünür kalır.'
                               %('bir uç pano dışı' if scope=='OUT_OF_PANEL_END'
                                 else 'en az bir ucun kapsamı belirsiz'))
            history=[dict(reference=e['reference'],origin=e['origin'],reviewer=e['reviewer'],
                          decision=e['decision'],recorded_utc=e['recorded_utc'],state=e['state'],
                          record_id=e['record_id'],current=e is current) for e in entries]
            rows.append(dict(kind=('CONFIRMED_PHYSICAL_PAIR' if level=='PHYSICAL'
                                   else 'CONFIRMED_NETWORK_RELATION'),
                             confirmation_level=level,
                             net_id='pair:%s:%s'%(number,reference),
                             reference=reference,confirmation_origin=current['origin'],
                             reviewer=current['reviewer'],pin_ids=list(key),
                             bbox=bbox,segments=len(hit['path']) if hit else 0,
                             segment_ids=[e['segment_id'] for e in (hit['path'] if hit else [])],
                             pins=pins,duplicate_names=False,
                             branch_points=traced['branch_points'],open_ends=[],
                             sheet_references=[],nearby_device_labels=[],nearest_device_label=None,
                             unattached_pins=traced['unattached_pins'],
                             line_evidence=line_evidence,review_state=current['state'],
                             review_decision=current['decision'],status_label=label,
                             review_history=history,review_count=len(history),
                             review_reason=' '.join(reasons) or None,
                             scope_state=scope,endpoint_scopes=scopes,same_device=same_device,
                             unresolved=not hit or not valid or scope!='IN_SCOPE_BOTH',
                             production_ready=False,**implementation,
                             note=(('Aynı cihazın iki ucu: cihaz içi bağlantı da olabilir, harici '
                                    'jumper da; otomatik elenmedi. ' if same_device else '')+
                                   ('Hat seviyesinde doğrulandı; kesin fiziksel klemens/bağlantı '
                                    'tarafı bekleniyor. Bu satır FİZİKSEL TEL ÇİFTİ DEĞİLDİR ve '
                                    'üretim listesine giremez. ' if level=='NETWORK' else '')+
                                   'Kullanıcı teyitli bağlantı kaydı; bu uç çifti için TEK satır. '
                                   'Yön satır üretmez, yeniden onay yeni satır açmaz; eski kararlar '
                                   'inceleme geçmişinde durur. Çizgi kanıtı ve inceleme durumu ayrı '
                                   'alanlardır. ')+current['note']))
        return sorted(rows,key=lambda r:r['reference'])

    def todo(self,number=None):
        """P05: kapsam içi cihazların işlenmemiş uçları ve çözülemeyen devamlar."""
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            data=self.table(number)
            coverage=self.coverage(number)
            continuations=self.continuations(number)['rows']
            marked={}
            for p in self.pins:
                if p.get('page',4)==number and p['device'].strip():
                    marked.setdefault(normalized(p['device']),[]).append(p['pin'])
            devices=[]
            for device in coverage['devices']:
                pins=sorted(marked.get(device['device'],[]))
                nets=[g for g in data['gaps'] if g.get('nearest_device_label')==device['device']]
                devices.append(dict(device=device['device'],in_scope=device['in_scope'],
                                    local_location=device.get('local_location'),
                                    marked_pins=pins,unmarked_nets=len(nets),
                                    unmarked_net_bboxes=[g['bbox'] for g in nets],
                                    status='NEVER_COMPLETE',
                                    note='Bir cihazın bazı pinlerinin bulunması cihazın tamamlandığı '
                                         'anlamına gelmez; sembolün tüm harici uçları ayrıca doğrulanmalıdır.'))
            open_items=[dict(kind='UNRESOLVED_CONTINUATION',reference=r['text'],status=r['status'],
                             reason=r.get('reason') or r.get('note'))
                        for r in continuations if r['status'] not in
                        ('RECIPROCAL_END_MATCHED','DEVICE_REFERENCE_NOT_A_CONTINUATION')]
            open_items+=[dict(kind='NET_WITHOUT_MARKED_END',bbox=g['bbox'],reason=g['reason'],
                              devices=g['nearby_device_labels'],references=g['sheet_references'])
                         for g in data['gaps']]
            open_items+=[dict(kind='SINGLE_END_NET',bbox=r['bbox'],
                              pins=[q['device']+':'+q['pin'] for q in r['pins']],
                              reason='Ağda tek işaretli uç var; karşı uç işaretlenmemiş.')
                         for r in data['rows'] if r['kind']=='SINGLE_END']
            open_items+=[dict(kind='UNATTACHED_PIN',pin_id=i,reason=coverage['pin_issues'].get(i))
                         for i in coverage['unattached_pins']]
            return dict(page=number,devices=sorted(devices,key=lambda d:(not d['in_scope'],d['device'])),
                        open_items=open_items,open_count=len(open_items),
                        unreviewed_nets=data['unreviewed_nets'],production_ready=False,
                        note='Bu liste kapsanmayanı görünür kılar; tamlık kanıtı değildir. Cihaz asla '
                             '"tamamlandı" işaretlenmez.')

    def effort(self):
        """P05 ölçütü 5: elle ve P04 destekli işaretlemenin kayıtlı süresi."""
        with self.lock:
            self.refresh()
            events=[e for e in self.store.events() if e['kind']=='pin']
            rows,previous=[],None
            for event in events:
                seconds=None
                if previous is not None:
                    seconds=round((datetime.fromisoformat(event['time'])
                                   -datetime.fromisoformat(previous)).total_seconds(),1)
                rows.append(dict(time=event['time'],record_id=event['record_id'],created=event['created'],
                                 method=event['body'].get('method','MANUAL'),page=event['body'].get('page',4),
                                 seconds_since_previous=seconds))
                previous=event['time']
            summary={}
            for row in rows:
                bucket=summary.setdefault(row['method'],dict(events=0,seconds=0.0,measured_events=0))
                bucket['events']+=1
                if row['seconds_since_previous'] is not None:
                    bucket['seconds']=round(bucket['seconds']+row['seconds_since_previous'],1)
                    bucket['measured_events']+=1
            for bucket in summary.values():
                bucket['seconds_per_event']=(round(bucket['seconds']/bucket['measured_events'],1)
                                             if bucket['measured_events'] else None)
            return dict(events=rows,summary=summary,
                        pins_by_method={m:sum(1 for p in self.pins if p.get('method','MANUAL')==m)
                                        for m in {p.get('method','MANUAL') for p in self.pins}},
                        note='Süre, iki kayıt olayı arasındaki duvar saati farkıdır: inceleme, kaydırma ve '
                             'ara vermeler dahildir, saf işaretleme süresi değildir. İlk olayın öncesi yoktur.',
                        production_ready=False)

    def endpoints(self):
        """P05: işaretli uçların diğer sayfalarda basılı karşılıkları; ad eşleşmesi tel onayı değildir."""
        with self.lock:
            self.refresh()
            index=self._index()
            rows=[]
            for p in self.pins:
                if not p['device'].strip():
                    continue
                row=reconcile_endpoint(p['device'],p['pin'],index)
                rows.append(dict(row,pin_id=p['id'],kind=p['kind'],in_scope=in_scope(p['device'])))
            return dict(rows=rows,terminals={k:sorted({o['physical_page'] for o in v})
                                             for k,v in terminal_table(index).items()},
                        klemmenplan_note='Bu PDF içinde ayrı Klemmenplan/klemens tablosu belgesi yok; '
                                         'tablo yalnız şema (Schaltplan) sayfalarındaki klemens yazılarından '
                                         'kurulmuştur. Uç uzlaştırma ise tüm belge türlerini tarar ve her '
                                         'satırda türü yazar.',
                        production_ready=False)

    def coverage(self,number=None):
        """P05: bağımsız tamlık taraması — kapsanmayan cihaz ve düğümleri say, tamlık iddia etme."""
        with self.lock:
            self.refresh()
            index=self._index()
            number=int(number or self.manifest['physical_page'])
            if number not in self.viewable_pages():
                raise ValueError('Bu çalışmada izlenmeyen sayfa: %s'%number)
            page=next(p for p in index if p['physical_page']==number)
            graph=self.page_graph(number)
            on_page=[p for p in self.pins if p.get('page',4)==number]
            marked={normalized(p['device']) for p in on_page if p['device'].strip()}
            printed={}
            for d in page['devices']:
                name,inherited=full_device_name(d,page)
                base=normalized(name).split(':')[0]
                printed.setdefault(base,dict(device=base,texts=set(),boxes=[],inherited=inherited,
                                             # A device with its own printed location is not panel-internal.
                                             local_location=d.get('local_location'),
                                             location_uncertain=bool(d.get('location_uncertain'))))
                printed[base]['texts'].add(d['text'])
                printed[base]['boxes'].append(self._shift(d['box'],number))
            devices=[dict(row,texts=sorted(row['texts']),
                          marked=row['device'] in marked,
                          in_scope=in_scope(row['device']) and not row['location_uncertain'],
                          # Every document type is searched; each hit says which type it came from.
                          other_pages=sorted({o['physical_page'] for o in occurrences(row['device'],index)
                                              if o['physical_page']!=page['physical_page']}),
                          other_pages_by_type=sorted({(o['physical_page'],o['doc_type'])
                                                      for o in occurrences(row['device'],index)
                                                      if o['physical_page']!=page['physical_page']}))
                     for row in printed.values()]
            touched,open_ends,unattached=set(),[],set()
            for p in on_page:
                if p['id'] not in graph.pin_nodes:
                    continue
                traced=graph.trace(p['id'])
                touched.update(e['segment_id'] for e in traced['edges'])
                unattached.update(traced['unattached_pins'])
                for end in traced['open_ends']:
                    if end['point'] not in [o['point'] for o in open_ends]:
                        open_ends.append(dict(end,from_pin=p['id']))
            # Only a sheet-continuation reference explains an open end. A contact/coil cross
            # reference points at another symbol of the same device and is never a wire continuation.
            refs=[dict(r,display_box=self._shift(r['box'],number)) for r in references_for_page(number,index)
                  if r['kind']=='LINE_CONTINUATION_CANDIDATE']
            for end in open_ends:
                near=[r for r in refs
                      if abs((r['display_box'][0]+r['display_box'][2])/2-end['point'][0])<=45
                      and abs((r['display_box'][1]+r['display_box'][3])/2-end['point'][1])<=12]
                end['sheet_references']=sorted({r['text'] for r in near})
                end['reason']=('CONTINUES_ON_REFERENCED_SHEET_UNVERIFIED' if near else end['reason'])
            return dict(devices=sorted(devices,key=lambda r:(r['marked'],r['device'])),
                        unmarked_devices=sum(1 for d in devices if not d['marked']),
                        # An open end on a traced path is a wire that continues to nothing marked yet.
                        open_ends=open_ends,unattached_pins=sorted(unattached),
                        pin_issues=graph.pin_issues,
                        traced_segments=len(touched),
                        untraced_segments=len({s['id'] for s in self._page(number)['segments']})-len(touched),
                        excluded_segments=len(graph.excluded),unjoined_crossings=len(graph.crossings),
                        page=number,marked_pins=len(on_page),production_ready=False,
                        limitation='Bu tarama yalnız kapsanmayanları görünür kılar; tamlık kanıtı değildir. '
                                   'İzlenmemiş çizgilerin çoğu çerçeve/yazı olabilir, tersi de mümkündür. '
                                   'Eğri/kesikli/eğik nesneler ve diğer sayfalar hâlâ incelenmemiştir.')

    def overview(self,number=None):
        """Sade durum: bu sayfada ne bulundu, ne onay bekliyor, ne çözülemedi.

        Teknik alanları düz Türkçeye çevirir. Hiçbir şeyi onaylamaz, hiçbir şey üretmez;
        yalnız var olan kayıtları okur.
        """
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            facts=next((q for q in (self._index() or []) if q['physical_page']==number),{})
            marks=[q for q in self.pins if q.get('page',4)==number]
            short=lambda name:name.split('-',1)[-1] if '-' in name else name

            connections,networks,singles,line_relations=[],[],[],[]
            table=self.table(number) if marks else dict(rows=[],gaps=[],unreviewed_nets=0)
            for row in table['rows']:
                ends=row['pins']
                if row['kind'] in ('PHYSICAL_PAIR','CONFIRMED_PHYSICAL_PAIR'):
                    a,b=ends[0],ends[1]
                    connections.append(dict(
                        from_device=a['device'],from_pin=a['pin'],to_device=b['device'],to_pin=b['pin'],
                        plain='-%s:%s  →  -%s:%s'%(short(a['device']),a['pin'],short(b['device']),b['pin']),
                        evidence='Tek çizgi yolu; dal yok, açık uç yok.' if not row['branch_points']
                                 else '%d dallı yol.'%len(row['branch_points']),
                        state=CONFIRM_TEXT[_confirm_state(row)],
                        confirm_state=_confirm_state(row),
                        review_state=row.get('review_state'),
                        production_ready=False,
                        implementation=row.get('implementation_type','BELIRSIZ'),
                        scope=row.get('scope_state'),reference=row.get('reference') or row['net_id'],
                        points=[a['point'],b['point']],bbox=row['bbox']))
                elif row['kind']=='CONFIRMED_NETWORK_RELATION':
                    a,b=ends[0],ends[1]
                    line_relations.append(dict(
                        plain='-%s:%s  ~  -%s:%s'%(short(a['device']),a['pin'],
                                                   short(b['device']),b['pin']),
                        warning='Bu iki uç AYNI HATTA olduğu kullanıcı tarafından teyitli. Ama '
                                'hangi fiziksel klemensin kullanılacağı çizimden çıkmıyor, bu '
                                'yüzden tel sayılmıyor.',
                        state=CONFIRM_TEXT[_confirm_state(dict(row,kind='CONFIRMED_PHYSICAL_PAIR'))],
                        reference=row.get('reference'),
                        points=[a['point'],b['point']],bbox=row['bbox']))
                elif row['kind']=='NETWORK_GROUP':
                    names=['-%s:%s'%(short(q['device']),q['pin']) for q in ends]
                    networks.append(dict(
                        plain='%d uç aynı hatta bağlı: %s'%(len(names),', '.join(names)),
                        warning='Bu ortak bir hat. Hangi telin hangi uca gittiği çizimden '
                                'çıkmıyor, bu yüzden tel çifti üretilmedi.',
                        members=names,points=[q['point'] for q in ends],bbox=row['bbox']))
                elif row['kind']=='SINGLE_END':
                    q=ends[0]
                    singles.append(dict(plain='-%s:%s'%(short(q['device']),q['pin']),
                                        why='Karşı ucu bu sayfada işaretli değil.',
                                        points=[q['point']],bbox=row['bbox']))
                elif row['kind']=='PAIR_OUT_OF_PANEL_SCOPE':
                    a,b=ends[0],ends[1]
                    singles.append(dict(plain='-%s:%s  →  -%s:%s'%(short(a['device']),a['pin'],
                                                                   short(b['device']),b['pin']),
                                        why='Bir ucu pano dışında; pano içi tel sayılmaz.',
                                        points=[a['point'],b['point']],bbox=row['bbox']))

            todo=[]
            drafts=[q for q in marks if q.get('method')=='AGENT_DRAFT']
            if drafts:
                todo.append(dict(
                    title='Cihaz adını doğrula (%d uç)'%len(drafts),
                    why='Bu uçları program kendi başına adlandıramadı. Cihaz adı sayfada bir kez '
                        'yazılı olduğu için hangi ucun hangi cihaza ait olduğunu ben okudum. '
                        'Doğru mu diye bakman gerekiyor.',
                    items=['-%s:%s'%(short(q['device']),q['pin']) for q in drafts],
                    points=[q['point'] for q in drafts]))
            found=[q for q in marks if q.get('method')=='P04_CANDIDATE']
            if found:
                todo.append(dict(
                    title='Programın bulduğu uçları onayla (%d uç)'%len(found),
                    why='Bunları kütüphanedeki örnek şekle bakarak program buldu, adlarını da bu '
                        'sayfanın kendi yazısından okudu. Hiçbiri onaylı değil.',
                    items=['-%s:%s'%(short(q['device']),q['pin']) for q in found],
                    points=[q['point'] for q in found]))
            stale=[r for r in self.review_status()['rows'] if r['status']!='CURRENT']
            if stale:
                todo.append(dict(
                    title='Askıya alınan kararları yenile (%d kayıt)'%len(stale),
                    why='Sayfaya yeni işaret eklendiği için eski onayların hepsi askıya alındı. '
                        'Kararlar silinmedi; yeniden bakman gerekiyor.',
                    items=[r.get('reference') or r['id'] for r in stale],points=[]))
            try:
                dash=self.dash_proposals(number)
            except Exception:                                   # noqa: BLE001
                dash=dict(runs=[])
            waiting=[r for r in dash['runs']
                     if r['kind']=='CONDUCTOR_CANDIDATE' and r.get('decision')=='ONAY_BEKLIYOR']
            if waiting:
                todo.append(dict(
                    title='Kesikli hat önerilerine bak (%d hat)'%len(waiting),
                    why='Bu hatlar noktalı çizilmiş. Program parçaları kendi kendine '
                        'birleştirmiyor; birleştirme önerisi hazır, kararı sen veriyorsun.',
                    items=[r['run_key'] for r in waiting],
                    points=[r['ends'][0] for r in waiting]))

            unresolved=len(table['gaps'])
            # Üç ayrı boyut, üç ayrı sayı. Biri diğerinin yerine geçmez.
            counted=Counter(c['confirm_state'] for c in connections)
            stale_rows=[r for r in self.review_status()['rows'] if r['status']!='CURRENT']
            confirmed=counted['GUNCEL_TEYITLI']
            suspended=counted['TEYIT_ASKIDA']
            waiting=counted['ONAY_BEKLIYOR']
            if not marks:
                headline='Bu sayfada henüz işaret yok.'
            else:
                parts=['%d tel bulundu'%len(connections)]
                if networks:
                    parts.append('%d ortak hat var'%len(networks))
                if line_relations:
                    parts.append('%d hat seviyesinde teyit var'%len(line_relations))
                if confirmed:
                    parts.append('%d tanesi kullanıcı teyitli'%confirmed)
                if suspended:
                    parts.append('%d teyit askıda (yeniden inceleme gerekiyor)'%suspended)
                if waiting and not (confirmed or suspended):
                    parts.append('hiçbiri onaylı değil')
                elif waiting:
                    parts.append('%d tanesi onay bekliyor'%waiting)
                headline=', '.join(parts)+'.'
            return dict(page=number,pages=sorted(self.viewable_pages()),
                        page_label='%s · %s · Blatt %s (fiziksel sayfa %d)'
                                   %(facts.get('anlage') and '='+facts['anlage'] or '?',
                                     facts.get('einbauort') and '+'+facts['einbauort'] or '?',
                                     facts.get('blatt') or '?',number),
                        headline=headline,
                        summary=dict(connections=len(connections),networks=len(networks),
                                     singles=len(singles),marks=len(marks),
                                     unresolved=unresolved,
                                     confirmed_current=confirmed,
                                     confirmed_suspended=suspended,
                                     awaiting_confirmation=waiting,
                                     reviews_needing_refresh=len(stale_rows),
                                     line_relations=len(line_relations),
                                     production_ready=0),
                        dimensions=[
                            dict(key='confirmed_current',label='İlişki teyidi (güncel)',
                                 value=confirmed,
                                 hint='Bu iki ucun bağlı olduğunu kullanıcı onayladı ve onay hâlâ geçerli.'),
                            dict(key='confirmed_suspended',label='Teyit askıda',
                                 value=suspended,
                                 hint='Kullanıcı daha önce onaylamıştı; sayfaya yeni işaret geldiği için '
                                      'yeniden bakılması gerekiyor. Karar silinmedi.'),
                            dict(key='awaiting_confirmation',label='Onay bekliyor',
                                 value=waiting,
                                 hint='Program çizgiyi izledi; kullanıcı henüz onaylamadı.'),
                            dict(key='production_ready',label='Üretime uygun',value=0,
                                 hint='Üretim/EPLAN aktarımı kapalı. Bu sayı ayrı bir karardır ve '
                                      'ilişki teyidiyle dolmaz.')],
                        connections=connections,networks=networks,singles=singles,
                        line_relations=line_relations,todo=todo,
                        note='Bu ekran yalnız gösterir. İlişki teyidi, yeniden inceleme ve üretime '
                             'uygunluk AYRI sayılır; üretim/EPLAN aktarımı kapalıdır.')

    # ================================================================ S01: bütün sayfa gezgini
    def page_index(self):
        """Belgenin BÜTÜN sayfaları: fiziksel sıra, Blatt, yapı, tür, kapsam, hazırlık durumu.

        Varsayılan şema filtresi IN_SCOPE Schaltplan'dır; sayı belge indeksinden SAYILIR, sabit
        yazılmaz. "Hazırlanmadı", "hazırlandı / işaret yok" ve "hazırlandı / işaretli" ayrı
        durumlardır; hiçbir sayfa "çözüldü" diye işaretlenmez.
        """
        with self.lock:
            self.refresh()
            index=self._index()
            run=self.pages()
            viewable=self.viewable_pages()
            marks=Counter(q.get('page',4) for q in self.pins)
            rows=[]
            for facts in index:
                n=facts['physical_page']
                if n in run:
                    state,origin='PREPARED','RUN'
                    info=self.manifest.get('page_artifacts',{}).get(str(n))
                    segments=(info or {}).get('segments',len(self.geometry['segments']) if n==self.manifest['physical_page'] else None)
                elif n in viewable:
                    state,origin='PREPARED','CACHE'
                    segments=self.cache.entry(n).get('segments')
                else:
                    state=self.cache.state(n) if self.cache is not None else 'NOT_PREPARED'
                    origin,segments=None,None
                rows.append(dict(page=n,blatt=facts.get('blatt'),anlage=facts.get('anlage'),
                                 einbauort=facts.get('einbauort'),doc_type=facts.get('doc_type'),
                                 scope=facts.get('scope'),issues=list(facts.get('issues') or []),
                                 default_selected=(facts.get('doc_type')=='Schaltplan'
                                                   and facts.get('scope')=='IN_SCOPE'),
                                 state=state,origin=origin,segments=segments,marks=marks.get(n,0),
                                 error=(self.cache.entry(n).get('error') if self.cache is not None
                                        and state=='FAILED' else None)))
            counts=dict(total=len(rows),
                        default_selected=sum(1 for r in rows if r['default_selected']),
                        prepared=sum(1 for r in rows if r['state']=='PREPARED'),
                        prepared_default=sum(1 for r in rows if r['state']=='PREPARED' and r['default_selected']),
                        marked=sum(1 for r in rows if r['marks']),
                        failed=sum(1 for r in rows if r['state']=='FAILED'))
            return dict(pages=rows,counts=counts,
                        queue=self.cache.snapshot() if self.cache is not None else None,
                        cache_enabled=self.cache is not None,production_ready=False,
                        note='Varsayılan seçim IN_SCOPE Schaltplan sayfalarıdır; diğer sayfalar bağlam '
                             'olarak açılabilir ama otomatik şema aktarımına seçili gelmez. Hazırlanmış '
                             'sayfa yalnız geometri taşır; işaret, inceleme veya onay taşımaz.')

    def prepare_request(self,payload):
        """Hazırlama kuyruğu komutu. Pilot çalışmasına YAZMAZ; yalnız sayfa önbelleğine."""
        if self.cache is None:
            raise ValueError('Sayfa önbelleği bu sunucuda kapalı.')
        action=payload.get('action','enqueue')
        if action=='enqueue':
            pages=payload.get('pages')
            if (not isinstance(pages,list) or not pages or len(pages)>self.cache.page_count
                    or not all(isinstance(n,int) and not isinstance(n,bool) for n in pages)):
                raise ValueError('Sayfa listesi geçersiz.')
            added=self.cache.enqueue(pages,front=bool(payload.get('front')))
            return dict(self.cache.snapshot(),added=added)
        if action=='stop':
            return self.cache.stop()
        if action=='resume':
            return self.cache.resume()
        if action=='retry':
            page=payload.get('page')
            if not isinstance(page,int) or isinstance(page,bool):
                raise ValueError('Sayfa numarası geçersiz.')
            return dict(self.cache.snapshot(),added=self.cache.retry(page))
        raise ValueError('Bilinmeyen hazırlama komutu.')

    # ================================================================ S01: şema ilişkileri
    def relations(self,number=None):
        """Şema ilişkileri: pin→pin, pin→potansiyel, pin→sayfa devamı, gerçek birleşim, açık uç.

        Bu bir FİZİKSEL TEL listesi değildir; iki cihaz pini şartı yoktur. `L1 → -3F22:1`
        ikinci bir cihaz olmadan anlamlı bir şema ilişkisidir ve potansiyel sahte cihaz/pin
        olarak kaydedilmez. Her ilişki gerçek segment kimlikleri ve kenar koordinatlarıyla gelir;
        düz yardımcı çizgi yolun yerine geçmez.

        Potansiyel adı yalnız o hattın KENDİ ucuna basılı yazıdan veya o uçtaki doğrulanmış sayfa
        devamından gelir. Aynı ad tek başına iki ayrı hattı BİRLEŞTİRMEZ: her ağ kendi çizilmiş
        segment kümesiyle tanımlanır. Bir ağda iki farklı ad okunursa ad verilmez, çelişki yazılır.
        """
        from .models import device_tail
        from .document import classify_label
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            if number not in self.viewable_pages():
                raise ValueError('Sayfa %s hazırlanmadı; önce sayfa gezgininden hazırlayın.'%number)
            page=self._page(number)
            rb=page['render_bbox']
            graph=self.page_graph(number)
            byid={p['id']:p for p in self.pins}
            marks=[q for q in self.pins if q.get('page',4)==number]
            try:
                conts=self.continuations(number)['rows']
            except ValueError:
                conts=[]
            cont_ends=[(r['source_end']['point'],r) for r in conts if r.get('source_end')]
            dots=[d['point'] for d in dashed.junction_dots(self._page_curves(number))]

            def poly(path):
                return [[round(e['a'][0],2),round(e['a'][1],2),round(e['b'][0],2),round(e['b'][1],2)]
                        for e in path]

            def seg_ids(path):
                return [e['segment_id'] for e in path]

            def label(q):
                return '-%s:%s'%(device_tail(q['device']),q['pin'])

            def cont_at(point):
                return [r for p,r in cont_ends if abs(p[0]-point[0])<=0.5 and abs(p[1]-point[1])<=0.5]

            def near_text(point):
                best=None
                for w in page['words']:
                    cx=(w['x0']+w['x1'])/2-rb[0]
                    cy=(w['top']+w['bottom'])/2-rb[1]
                    d=max(abs(cx-point[0]),abs(cy-point[1]))
                    if d<=14 and (best is None or d<best[0]):
                        best=(d,w['text'])
                return best[1] if best else None

            segs=page['segments']

            def label_owner(lab,point,horizontal):
                """Uçtaki yazı bu hattın mı? Yalnız sahipliği TEK anlamlı olan yazı ad verir.

                Ret 1 — ifade parçası: yazının aynı satırında bitişik başka kelime var (`X1 P1`
                port adıdır, `P1` potansiyeli değil). Ret 2 — komşu hat: aynı yönde başka bir çizgi
                yazıya bu hat kadar yakın (klemens sırasında `N24.30` yazısı iki telin arasında durur;
                hangisinin olduğu yakınlıktan seçilmez). Reddedilen yazı silinmez, nedenle döner.
                """
                x0,y0,x1,y1=lab['box'][0]-rb[0],lab['box'][1]-rb[1],lab['box'][2]-rb[0],lab['box'][3]-rb[1]
                along_x=(x1-x0)>=(y1-y0)
                thick=min(x1-x0,y1-y0) or 1.0
                for w in page['words']:
                    a0,b0,a1,b1=w['x0']-rb[0],w['top']-rb[1],w['x1']-rb[0],w['bottom']-rb[1]
                    if abs(a0-x0)<0.01 and abs(b0-y0)<0.01:
                        continue
                    if along_x:
                        cross=min(y1,b1)-max(y0,b0); gap=max(a0-x1,x0-a1)
                    else:
                        cross=min(x1,a1)-max(x0,a0); gap=max(b0-y1,y0-b1)
                    if cross>=0.5*thick and gap<1.2*thick:
                        return 'ifade parçası (%s %s)'%(lab['text'],w['text'])
                if horizontal:
                    lo,hi,own,span=y0,y1,point[1],(x0,x1)
                else:
                    lo,hi,own,span=x0,x1,point[0],(y0,y1)

                def dist(v):
                    return max(lo-v,v-hi,0.0)
                d_own=dist(own)
                for sg in segs:
                    (ax,ay),(bx,by)=sg['a'],sg['b']
                    if horizontal and abs(ay-by)<0.01:
                        v,r0,r1=ay,min(ax,bx),max(ax,bx)
                    elif not horizontal and abs(ax-bx)<0.01:
                        v,r0,r1=ax,min(ay,by),max(ay,by)
                    else:
                        continue
                    if abs(v-own)<=0.5 or min(r1,span[1])-max(r0,span[0])<=0:
                        continue
                    if dist(v)<=d_own+6.0:
                        return 'komşu hatla paylaşılıyor'
                return None

            def classify_end(point,path):
                found=cont_at(point)
                if found:
                    r=found[0]
                    match=(r.get('candidates') or [None])[0] or {}
                    # Devam eşleşmesi kablo damar kimliğini (`112/3W67:9`) kanıt olarak kullanabilir;
                    # bu bir POTANSİYEL ADI DEĞİLDİR (MAIN 2026-09-10 §5). Ağa ad yalnız POTENTIAL
                    # türündeki yazıdan verilir; diğerleri türüyle ayrı alanda durur.
                    signal=r.get('source_signal')
                    signal_kind=classify_label(signal) if signal else None
                    return dict(kind='CONTINUATION',point=[round(point[0],2),round(point[1],2)],
                                potential=signal if signal_kind=='POTENTIAL' else None,
                                signal=signal,signal_kind=signal_kind,
                                reference=r['text'],status=r['status'],
                                target_page=r.get('target_page') or (r.get('target_pages') or [None])[0],
                                target_reference=match.get('reference'),
                                target_end=(match.get('end') or {}).get('point'),
                                verified=r['status']=='RECIPROCAL_END_MATCHED')
                last=path[-1] if path else None
                horizontal=bool(last) and abs(last['a'][1]-last['b'][1])<0.01
                found=signal_labels(page['words'],(point[0]+rb[0],point[1]+rb[1]),
                                    *((45.0,8.0) if horizontal else (8.0,45.0)),kinds=('POTENTIAL',))
                rejected=[]
                for lab in list(found):
                    why=label_owner(lab,point,horizontal)
                    if why:
                        found.remove(lab); rejected.append('%s: %s'%(lab['text'],why))
                if found:
                    names=sorted({l['text'] for l in found})
                    return dict(kind='POTENTIAL',point=[round(point[0],2),round(point[1],2)],
                                potential=found[0]['text'],ambiguous_names=names if len(names)>1 else [],
                                label_box=found[0]['box'])
                return dict(kind='OPEN_END',point=[round(point[0],2),round(point[1],2)],potential=None,
                            nearby_text=near_text(point),rejected_labels=rejected,
                            reason=('Uçtaki yazı sahipliği belirsiz (%s); ad verilmedi.'%'; '.join(rejected))
                                   if rejected else
                                   'Uçta potansiyel yazısı veya doğrulanmış sayfa devamı yok; '
                                   'uç bilinmiyor, uydurulmadı.')

            networks={}

            def network(trace):
                key=frozenset(e['segment_id'] for e in trace['edges'])
                if key not in networks:
                    networks[key]=dict(id='net:%d:%d'%(number,len(networks)+1),segment_ids=sorted(key),
                                       edges=poly(trace['edges']),pins=[],ends={},junctions={},paths={})
                return networks[key]

            def add_trace(net,trace):
                for oe in trace['open_ends']:
                    point=tuple(oe['point'])
                    end=classify_end(oe['point'],oe.get('path') or [])
                    net['ends'].setdefault(point,end)
                for bp in trace['branch_points']:
                    kind=('DRAWN_DOT' if any(abs(d[0]-bp[0])<=0.6 and abs(d[1]-bp[1])<=0.6 for d in dots)
                          else 'T_GEOMETRY')
                    net['junctions'].setdefault(tuple(bp),dict(point=[round(bp[0],2),round(bp[1],2)],
                                                               evidence=kind))

            relations,seen=[],set()
            # (a) İşaretli pinlerden: pin→pin ve pinin ağının uçları.
            for q in marks:
                trace=graph.trace(q['id'])
                if not trace['edges']:
                    continue
                net=network(trace)
                if q['id'] not in net['pins']:
                    net['pins'].append(q['id'])
                add_trace(net,trace)
                net['paths'][q['id']]={tuple(oe['point']):oe.get('path') or [] for oe in trace['open_ends']}
                for target in trace['targets']:
                    other=byid.get(target['pin_id'])
                    pair=tuple(sorted((q['id'],target['pin_id'])))
                    if other is None or pair in seen:
                        continue
                    seen.add(pair)
                    relations.append(dict(kind='PIN_PIN',network=net['id'],source=label(q),source_pin_id=q['id'],
                                          target=label(other),target_pin_id=other['id'],
                                          segment_ids=seg_ids(target['path']),edges=poly(target['path']),
                                          note='Çizimde iki pin arası yol. Fiziksel tel/imalat kararı değildir.'))
            # (b) İşaretsiz uçlar: sayfa devamı ucundan izleme. Pin UYDURULMAZ; ağ görünür olur.
            for point,row in cont_ends:
                if any(tuple(point) in net['ends'] for net in networks.values()):
                    continue
                trace=graph.trace_from_point(point)
                if not trace['edges']:
                    continue
                net=network(trace)
                net['ends'].setdefault(tuple(point),classify_end(point,[]))
                add_trace(net,trace)
                for target in trace['targets']:
                    if target['pin_id'] in byid and target['pin_id'] not in net['pins']:
                        net['pins'].append(target['pin_id'])

            out=[]
            for net in networks.values():
                ends=list(net['ends'].values())
                names=sorted({e['potential'] for e in ends if e['kind']!='OPEN_END' and e.get('potential')})
                potential=names[0] if len(names)==1 else None
                pins=[byid[pid] for pid in net['pins'] if pid in byid]
                for q in pins:
                    paths=net['paths'].get(q['id'],{})
                    for end in ends:
                        path=paths.get(tuple(end['point']),[])
                        kind={'CONTINUATION':'PIN_CONTINUATION','POTENTIAL':'PIN_POTENTIAL',
                              'OPEN_END':'PIN_OPEN_END'}[end['kind']]
                        relations.append(dict(kind=kind,network=net['id'],source=label(q),source_pin_id=q['id'],
                                              potential=end.get('potential'),target=end,
                                              segment_ids=seg_ids(path) or net['segment_ids'],
                                              edges=poly(path) or net['edges']))
                out.append(dict(id=net['id'],potential=potential,
                                potential_conflict=names if len(names)>1 else [],
                                pins=[dict(id=q['id'],label=label(q),device=q['device'],pin=q['pin'],
                                           point=q['point'],method=q.get('method','MANUAL')) for q in pins],
                                continuations=[e for e in ends if e['kind']=='CONTINUATION'],
                                potential_anchors=[e for e in ends if e['kind']=='POTENTIAL'],
                                open_ends=[e for e in ends if e['kind']=='OPEN_END'],
                                junctions=list(net['junctions'].values()),
                                segment_ids=net['segment_ids'],edges=net['edges'],
                                issues=(['POTENTIAL_NAMES_DISAGREE'] if len(names)>1 else [])
                                       +(['UNKNOWN_OPEN_END'] if any(e['kind']=='OPEN_END' for e in ends) else [])))
            out.sort(key=lambda n:(n['potential'] is None,n['potential'] or '',n['id']))
            counts=Counter(r['kind'] for r in relations)
            return dict(page=number,networks=out,relations=relations,
                        summary=dict(networks=len(out),
                                     named_networks=sum(1 for n in out if n['potential']),
                                     pin_pin=counts['PIN_PIN'],pin_potential=counts['PIN_POTENTIAL'],
                                     pin_continuation=counts['PIN_CONTINUATION'],
                                     pin_open_end=counts['PIN_OPEN_END'],
                                     junctions=sum(len(n['junctions']) for n in out),
                                     unknown_open_ends=sum(len(n['open_ends']) for n in out),
                                     marks=len(marks)),
                        production_ready=False,
                        note='Şema ilişkisidir, fiziksel tel değildir. Potansiyel adı yalnız hattın kendi '
                             'ucundaki yazıdan veya doğrulanmış sayfa devamından okunur; aynı ad ayrı '
                             'hatları birleştirmez. Birleşim: DRAWN_DOT çizilmiş nokta, T_GEOMETRY uç uca T.')

    # ================================================================ S02: küçük sayfa modeli
    def page_model(self,number=None):
        """Sözleşme `uvp.pdf2p8.page` 1.0 — BİZİM uygulamamızın sözleşmesi, EPLAN import formatı değil.

        Kaynak gözlemi (PDF), kullanıcı/aday işareti (SQLite, sürümlü) ve standart yorumu ayrı
        alanlardır; biri diğerinin üstüne yazılmaz. Bilinmeyen değer null + gerekçedir.
        """
        with self.lock:
            rel=self.relations(number)
            number=rel['page']
            facts=next((q for q in self._index() if q['physical_page']==number),{})
            size=self.viewable_pages()[number]
            _,_,bbox=self._page_source(number)
            nodes,seen=[],set()

            def add(node):
                if node['id'] not in seen:
                    seen.add(node['id'])
                    nodes.append(node)
            for q in [q for q in self.pins if q.get('page',4)==number]:
                add(dict(id='pin:'+q['id'],kind='PIN',device=q['device'],pin=q['pin'],point=q['point'],
                         source_kind=q.get('method','MANUAL'),version=q.get('version'),
                         raw_value=dict(device=q['device'],pin=q['pin'])))
            for net in rel['networks']:
                for j in net['junctions']:
                    add(dict(id='junction:%s:%s'%tuple(j['point']),kind='JUNCTION',point=j['point'],
                             evidence=j['evidence'],network=net['id']))
                for e in net['continuations']:
                    add(dict(id='interruption:%s:%s'%tuple(e['point']),kind='INTERRUPTION',point=e['point'],
                             raw_value=e['reference'],potential=e.get('potential'),
                             target_page=e.get('target_page'),verified=e.get('verified'),network=net['id']))
                for e in net['potential_anchors']:
                    add(dict(id='potential:%s:%s'%tuple(e['point']),kind='POTENTIAL_ANCHOR',point=e['point'],
                             raw_value=e['potential'],ambiguous_names=e.get('ambiguous_names'),network=net['id']))
                for e in net['open_ends']:
                    add(dict(id='open:%s:%s'%tuple(e['point']),kind='OPEN_END',point=e['point'],
                             nearby_text=e.get('nearby_text'),reason=e['reason'],network=net['id']))
            used={i for net in rel['networks'] for i in net['segment_ids']}
            segments=[dict(id=s['id'],a=s['a'],b=s['b'],dash=bool(s.get('dash')),source=s.get('source'))
                      for s in self._page(number)['segments'] if s['id'] in used]
            return dict(contract='uvp.pdf2p8.page',contract_version='1.0',
                        document_sha256=self.manifest['source_sha256'],
                        page=dict(physical_page=number,blatt=facts.get('blatt'),anlage=facts.get('anlage'),
                                  einbauort=facts.get('einbauort'),doc_type=facts.get('doc_type'),
                                  scope=facts.get('scope'),width=size[0],height=size[1],render_bbox=bbox,
                                  coordinate_space='PDFPLUMBER_ROTATED_TOP_LEFT_MINUS_RENDER_BBOX',
                                  unit='pt'),
                        nodes=nodes,segments=segments,networks=rel['networks'],relations=rel['relations'],
                        overrides=dict(store='annotations.sqlite3',kind='VERSIONED_EVENT_LOG',
                                       note='Kullanıcı ve aday işaretleri çıkarımdan ayrı, sürümlü kayıttır; '
                                            'yeniden analiz onları ezmez.'),
                        production_released=False,
                        issues=[i for net in rel['networks'] for i in net['issues']])


    def state(self):
        with self.lock:
            self.refresh()
            return dict(manifest=self.manifest,revision=self.revision,pins=self.pins,claims=self.claims(),
                        pages={str(k):v for k,v in self.pages().items()},boxes=self.boxes,
                        viewable={str(k):v for k,v in self.viewable_pages().items()},
                        reviews=self.review_status(),
                        templates=[dict(id=b['id'],bbox=b['bbox'],page=b.get('page',4),source=b['source'],
                                        note=b.get('note',''),version=b['version'])
                                   for b in self.boxes if b.get('active',True)],
                        excluded=self.graph.excluded,pin_issues=self.graph.pin_issues,
                        crossings=self.graph.crossings,unsupported_objects=self.geometry['unsupported_objects'],
                        raw_segments=len(self.geometry['segments']),
                        document=None if self.document is None else
                        dict(page_count=self.document['page_count'],traced_pages=self.document['traced_pages'],
                             scopes={s:sum(1 for p in self.document['pages'] if p['scope']==s)
                                     for s in {p['scope'] for p in self.document['pages']}}),
                        production_ready=False)

    def package_request(self,payload=None):
        """S03 kanıt paketini üret ve yolunu döndür. EPLAN'a hiçbir şey yazmaz.

        Paket bizim sözleşmemizdir; hedef sembol eşlemesi AYRI dosyadır ve katalog alınmadan
        yazılamaz. Panel bu yolu EPLAN köprüsüne verir; aktarımı add-in yapar.
        """
        from . import customer, eplan_export
        payload=payload or {}
        profile=customer.load(payload.get('customer') or getattr(self,'customer',None))
        if payload.get('page'):
            number=int(payload['page'])
            package=eplan_export.page_package(self,number,profile)
            target=ROOT/'output'/'exchange'/('sayfa_%d.json'%number)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(package,ensure_ascii=False,indent=1),encoding='utf-8')
            mapping=ROOT/'output'/'exchange'/'proof_s03'/'mapping.json'
            return dict(package=str(target),mapping=str(mapping) if mapping.exists() else None,
                        pages=[number],objects=len(package['pages'][0]['objects']),
                        expected_links=len(package['expected_links']),issues=package['issues'],
                        note='Sayfa paketi yazıldı. EPLAN\'da UvpSayfaAktar.cs ile bu dosyayı seç.')
        if payload.get('all') or payload.get('marked'):
            # İşaretli TÜM sayfalar tek dosyada: EPLAN'a tek aktarım, tek geri alma adımı.
            package=eplan_export.document_package(self,profile=profile)
            target=ROOT/'output'/'exchange'/('%s_tum_sayfalar.json'%profile['customer'])
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(package,ensure_ascii=False,indent=1),encoding='utf-8')
            return dict(package=str(target),customer=profile['customer'],
                        pages=[q['physical_page'] for q in package['pages']],
                        objects=sum(len(q['objects']) for q in package['pages']),
                        expected_links=len(package['expected_links']),
                        families_without_symbol=package['families_without_symbol'],
                        failed_pages=package['failed_pages'],issues=package['issues'],
                        note='Tüm işaretli sayfalar tek pakette. Sembolü eşlenmemiş aile '
                             'varsa o cihazlar aktarımda reddedilir.')
        pages=tuple(int(n) for n in (payload.get('pages') or (4,5)))
        package=eplan_export.proof_package(self,pages=pages)
        target=ROOT/'output'/'exchange'/'proof_s03'/'package.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(package,ensure_ascii=False,indent=1),encoding='utf-8')
        mapping=ROOT/'output'/'exchange'/'proof_s03'/'mapping.json'
        return dict(package=str(target),mapping=str(mapping) if mapping.exists() else None,
                    pages=list(pages),objects=sum(len(q['objects']) for q in package['pages']),
                    expected_links=len(package['expected_links']),issues=package['issues'],
                    note='Paket yazıldı. Sembol eşlemesi yoksa aktarım yapılmaz; önce EPLAN '
                         'kataloğu alınıp eşleme yazılmalıdır.')

    def similar(self,box_id,pages=None):
        """Bu sembolün AYNI ŞEKLİNİ başka sayfalarda ara. Hiçbir şey kaydedilmez.

        Şablon, kullanıcının işaretlediği kutunun kendi çizimi ve kendi pinlerinden kurulur.
        Her sayfada ad ve pin yazıları O SAYFANIN kendi yazısından okunur; şablondan kopyalanmaz.
        Yalnız hazırlanmış sayfalar taranır; taranmamış sayfa "yok" demek DEĞİLDİR ve listelenir.
        """
        with self.lock:
            self.refresh()
            box=next((b for b in self.boxes if b['id']==box_id),None)
            if box is None:
                raise ValueError('Şablon kutusu bulunamadı.')
            if not box.get('active',True):
                raise ValueError('Bu kutu pasif; şablon olarak kullanılmıyor.')
            home=box.get('page',4)
            source=self._page(home)
            home_marks=[q for q in self.pins if q.get('page',4)==home]
            # Kullanıcının çıkardığı parçalar ŞABLONA girmez: etiket kırıntısı yüzünden
            # aynı sembol başka sayfada eşleşmiyordu.
            dropped=set(box.get('excluded_objects') or [])
            template=build_template(box,home_marks,self._without(source['segments'],dropped),
                                    source['words'],source['render_bbox'],
                                    curves=self._without(self._page_curves(home),dropped))
            desc=descriptor(template)
            viewable=sorted(self.viewable_pages())
            if pages in (None,'ALL'):
                wanted,skipped=viewable,[]
            else:
                wanted=[int(n) for n in pages]
                skipped=[n for n in wanted if n not in viewable]
                wanted=[n for n in wanted if n in viewable]
            results,total=[],0
            for number in wanted:
                page=self._page(number)
                marks=[q for q in self.pins if q.get('page',4)==number]
                found=search_similar(desc,page['segments'],page['words'],page['render_bbox'],
                                     marks,self._page_curves(number))
                strips=document.strip_labels(page['words'],page['render_bbox'])
                bars=document.module_bars(page['segments'])
                for candidate in found['candidates']:
                    candidate['page']=number
                    candidate['template_box']=box_id
                    candidate['discovery_source']='USER_MARKED_TEMPLATE'
                    if self.document is not None:
                        self._name_from_strip(candidate,strips,page['render_bbox'],number,bars,
                                              page['words'],page['segments'])
                    for pin in candidate['pins']:
                        pin['template_device']=''
                        pin['template_pin']=''
                total+=len(found['candidates'])
                results.append(dict(page=number,candidates=found['candidates'],
                                    rejected=len(found['rejected'])))
            return dict(template_box=box_id,template_page=home,pages=wanted,
                        unprepared_pages=[n for n in range(1,self.manifest['page_count']+1)
                                          if n not in viewable],
                        requested_but_unprepared=skipped,results=results,candidates_total=total,
                        applied_changes=False,production_ready=False,
                        limitation='Yalnız ÖTELEME eşleşmesi; döndürülmüş/aynalanmış örnek bulunmaz. '
                                   'Hazırlanmamış sayfa taranmadı — "orada yok" anlamına gelmez. '
                                   'Aday kayıt değildir: uygulamayı kullanıcı seçer.')

    # ================================================================ elle cihaz işaretleme
    def _shapes(self,number,exclude=()):
        """Sembol olabilecek KISA çizim parçaları. Uzun çizgi teldir; kümeye alınmaz.

        `exclude`: kullanıcının "bu sembole ait değil" dediği parçalar (etiket kırıntısı,
        komşu telin ucu). Parça silinmez; yalnız bu seçime girmez.
        """
        page=self._page(number)
        exclude=set(exclude or ())
        out=[]
        for seg in page['segments']:
            (ax,ay),(bx,by)=seg['a'],seg['b']
            if seg['id'] in exclude or seg.get('dash') or max(abs(ax-bx),abs(ay-by))>SYMBOL_STROKE_MAX:
                continue
            out.append(dict(id=seg['id'],kind='segment',
                            bbox=[min(ax,bx),min(ay,by),max(ax,bx),max(ay,by)]))
        for curve in self._page_curves(number):
            box=curve.get('bbox')
            if not box or curve['id'] in exclude:
                continue
            box=[min(box[0],box[2]),min(box[1],box[3]),max(box[0],box[2]),max(box[1],box[3])]
            if max(box[2]-box[0],box[3]-box[1])>SYMBOL_STROKE_MAX:
                continue
            out.append(dict(id=curve['id'],kind='curve',bbox=box))
        return out

    @staticmethod
    def _box_distance(box,point):
        return max(box[0]-point[0],point[0]-box[2],0.0)+max(box[1]-point[1],point[1]-box[3],0.0)

    def _cluster_box(self,shapes,point):
        """Tıklanan noktadaki şeklin kutusu: en yakın parçadan başlayıp komşularını toplar."""
        near=sorted(((self._box_distance(sh['bbox'],point),index,sh)
                     for index,sh in enumerate(shapes)),key=lambda r:(r[0],r[1]))
        if not near or near[0][0]>6.0:
            raise ValueError('Tıklanan yerde sembol çizimi yok. Kutuyu elle çizebilirsiniz.')
        used=[near[0][2]]
        seen={id(near[0][2])}
        box=list(near[0][2]['bbox'])
        changed=True
        while changed:
            changed=False
            for sh in shapes:
                if id(sh) in seen:
                    continue
                b=sh['bbox']
                if (b[0]>box[2]+SYMBOL_PAD or b[2]<box[0]-SYMBOL_PAD
                        or b[1]>box[3]+SYMBOL_PAD or b[3]<box[1]-SYMBOL_PAD):
                    continue
                merged=[min(box[0],b[0]),min(box[1],b[1]),max(box[2],b[2]),max(box[3],b[3])]
                if merged[2]-merged[0]>SYMBOL_BOX_MAX or merged[3]-merged[1]>SYMBOL_BOX_MAX:
                    continue
                box,changed=merged,True
                seen.add(id(sh))
                used.append(sh)
        return [round(box[0]-1.0,2),round(box[1]-1.0,2),round(box[2]+1.0,2),round(box[3]+1.0,2)],used

    @staticmethod
    def _wire_pins(segments,box):
        """Kutuya giren tellerin sınırdaki uçları. Kutu içinde kalan çizgi uç üretmez."""
        points=[]
        for seg in segments:
            (ax,ay),(bx,by)=seg['a'],seg['b']
            inside_a=box[0]<=ax<=box[2] and box[1]<=ay<=box[3]
            inside_b=box[0]<=bx<=box[2] and box[1]<=by<=box[3]
            if inside_a==inside_b:
                continue
            if abs(ax-bx)<0.01:
                x=ax
                if not box[0]-0.5<=x<=box[2]+0.5:
                    continue
                y=box[1] if min(ay,by)<box[1] else box[3]
            elif abs(ay-by)<0.01:
                y=ay
                if not box[1]-0.5<=y<=box[3]+0.5:
                    continue
                x=box[0] if min(ax,bx)<box[0] else box[2]
            else:
                continue
            point=[round(x,2),round(y,2)]
            if not any(abs(q[0]-point[0])<=PIN_MERGE and abs(q[1]-point[1])<=PIN_MERGE for q in points):
                points.append(point)
        return sorted(points,key=lambda q:(q[1],q[0]))

    @staticmethod
    def _snap(segments,marks,point,tol=2.5):
        """Önerilen ucu GERÇEK noktaya oturt: önce var olan işaret, sonra telin kendi ucu.

        Kutu sınırındaki kesişim 1-2 pt kayabilir; kaydırılmadan kaydedilirse aynı uca ikinci
        bir kayıt açılır. Yakında kanıt yoksa nokta olduğu gibi kalır.
        """
        near=[m['point'] for m in marks
              if abs(m['point'][0]-point[0])<=tol and abs(m['point'][1]-point[1])<=tol]
        if near:
            return [round(near[0][0],2),round(near[0][1],2)]
        ends=[e for seg in segments for e in (seg['a'],seg['b'])
              if abs(e[0]-point[0])<=tol and abs(e[1]-point[1])<=tol]
        if ends:
            best=min(ends,key=lambda e:abs(e[0]-point[0])+abs(e[1]-point[1]))
            return [round(best[0],2),round(best[1],2)]
        return point

    @staticmethod
    def _without(rows,exclude):
        return [r for r in rows if r['id'] not in exclude]

    def _objects_in(self,number,box,pad=2.0):
        """Kutuya değen çizim parçaları: kullanıcı hangisini çıkaracağını görebilsin."""
        area=[box[0]-pad,box[1]-pad,box[2]+pad,box[3]+pad]
        page=self._page(number)
        rows=[]
        for seg in page['segments']:
            (ax,ay),(bx,by)=seg['a'],seg['b']
            b=[min(ax,bx),min(ay,by),max(ax,bx),max(ay,by)]
            if b[0]<=area[2] and b[2]>=area[0] and b[1]<=area[3] and b[3]>=area[1]:
                rows.append(dict(id=seg['id'],kind='segment',a=seg['a'],b=seg['b'],
                                 dash=bool(seg.get('dash')),
                                 inside=(area[0]<=b[0] and b[2]<=area[2]
                                         and area[1]<=b[1] and b[3]<=area[3])))
        for curve in self._page_curves(number):
            b=curve.get('bbox')
            if not b:
                continue
            b=[min(b[0],b[2]),min(b[1],b[3]),max(b[0],b[2]),max(b[1],b[3])]
            if b[0]<=area[2] and b[2]>=area[0] and b[1]<=area[3] and b[3]>=area[1]:
                rows.append(dict(id=curve['id'],kind='curve',bbox=b,
                                 points=curve.get('points') or [],
                                 inside=(area[0]<=b[0] and b[2]<=area[2]
                                         and area[1]<=b[1] and b[3]<=area[3])))
        return rows

    def propose_symbol(self,number=None,point=None,bbox=None,exclude=()):
        """Tıklanan (veya çizilen) yerdeki cihaz ÖNERİSİ: kutu, uçlar ve sayfadan okunan adlar.

        Hiçbir şey kaydedilmez. Ad ve pin yazıları BU SAYFANIN kendi yazısından okunur; komşu
        sayfadan, şablondan veya kütüphaneden kopyalanmaz. Okunamayan ad boş döner ve
        `identity_resolved` yanlış olur — uydurulmaz.
        """
        from .models import device_tail
        with self.lock:
            self.refresh()
            number=int(number or self.manifest['physical_page'])
            if number not in self.viewable_pages():
                raise ValueError('Sayfa %s hazırlanmadı; önce sayfa gezgininden hazırlayın.'%number)
            page=self._page(number)
            rb=page['render_bbox']
            exclude=set(exclude or ())
            segments=self._without(page['segments'],exclude)
            if bbox is None:
                if not point:
                    raise ValueError('Nokta veya kutu gerekir.')
                point=[float(point[0]),float(point[1])]
                box,used=self._cluster_box(self._shapes(number,exclude),point)
                evidence=[dict(id=sh['id'],kind=sh['kind']) for sh in used]
                source='CLICK_CLUSTER'
            else:
                box=[round(min(float(bbox[0]),float(bbox[2])),2),round(min(float(bbox[1]),float(bbox[3])),2),
                     round(max(float(bbox[0]),float(bbox[2])),2),round(max(float(bbox[1]),float(bbox[3])),2)]
                if box[2]-box[0]<=0.5 or box[3]-box[1]<=0.5:
                    raise ValueError('Kutu çok küçük.')
                evidence,source=[],'USER_BOX'
            marks=[q for q in self.pins if q.get('page',4)==number]
            found=[self._snap(segments,marks,q) for q in self._wire_pins(segments,box)]
            pins=[]
            for q in found:
                rivals=[tuple(o) for o in found if o!=q]
                # Uç adı telin yönünde 16 pt'ye kadar aranır (PLC modülünde ad uçtan 12 pt
                # yukarıda basılı); yana yalnız 4 pt — komşu kanalın adı çalınmasın.
                hit=similarity.nearest_word(page['words'],rb,tuple(q),11.0,others=rivals,reach=16.0)
                existing=[m for m in marks if abs(m['point'][0]-q[0])<=0.6 and abs(m['point'][1]-q[1])<=0.6]
                pins.append(dict(point=q,pin=hit[1]['text'] if hit else '',
                                 pin_source='PAGE_LABEL' if hit else None,
                                 external_lines=len(similarity.attached(segments,tuple(q))),
                                 already_marked=[m['id'] for m in existing],
                                 already_label=('-%s:%s'%(device_tail(existing[0]['device']),existing[0]['pin']))
                                               if existing else None))
            # Maske kutusu UÇLARIN ÜSTÜNE oturur: uç kutunun içinde kalırsa dış tel de maskeye
            # girer ve pin hiçbir çizgiye bağlanamaz (NO_LINE_AT_PIN). Kutu yalnız daraltılır.
            for q in pins:
                x,y=q['point']
                if 0<=y-box[1]<=1.6: box[1]=y
                if 0<=box[3]-y<=1.6: box[3]=y
                if 0<=x-box[0]<=1.6: box[0]=x
                if 0<=box[2]-x<=1.6: box[2]=x
            box=[round(v,2) for v in box]
            candidate=dict(bbox=box,pins=[dict(point=q['point'],page_pin_texts=[q['pin']] if q['pin'] else [])
                                          for q in pins],page_device_texts=[])
            tags=[]
            for w in page['words']:
                if document.classify_label(w['text'])!='DEVICE_TAG':
                    continue
                # Uzaklık yazının MERKEZİNDEN değil KUTUSUNDAN ölçülür. Ölçüm (sayfa 42,
                # `=170-13K52` kontağı): yazı 66.5 pt geniş; merkezi kutudan 40.7 pt uzakta
                # kalıyor ve 26 pt yarıçapla eleniyordu — ad boş dönüyordu. Kendi sağ
                # kenarından uzaklık 7.45 pt. Uzun etiket, yakın etikettir.
                rect=[w['x0']-rb[0],w['top']-rb[1],w['x1']-rb[0],w['bottom']-rb[1]]
                distance=(max(box[0]-rect[2],rect[0]-box[2],0.0)
                          +max(box[1]-rect[3],rect[1]-box[3],0.0))
                if distance<=DEVICE_TEXT_RADIUS:
                    tags.append((distance,w['text']))
            if tags:
                candidate['page_device_texts']=[min(tags,key=lambda r:r[0])[1]]
            strips=document.strip_labels(page['words'],rb)
            self._name_from_strip(candidate,strips,rb,number,document.module_bars(page['segments']),
                                  page['words'],page['segments'])
            issues=list(candidate.get('issues') or [])
            if not pins:
                issues.append('NO_WIRE_AT_SYMBOL')
            objects=self._objects_in(number,box)
            for row in objects:
                row['excluded']=row['id'] in exclude
            return dict(page=number,bbox=box,box_source=source,shape_evidence=evidence,
                        objects=objects,excluded=sorted(exclude),
                        device=candidate.get('device_name') or '',
                        device_printed=candidate.get('device_printed'),
                        device_source=candidate.get('device_source'),
                        device_inherited=candidate.get('device_inherited') or [],
                        identity_resolved=bool(candidate.get('identity_resolved')),
                        pins=pins,issues=issues,stored=False,production_ready=False,
                        note='Öneridir. Cihaz ve pin adları bu sayfanın yazısından okundu; '
                             'kaydedilmeden hiçbir kayıt oluşmaz, onay sayılmaz.')

    def apply_mark(self,payload):
        """Onaylanan öneriyi kaydet: sembol maskesi + uçlar. Yöntem MANUAL (kullanıcı işareti).

        Önce hepsi doğrulanır, sonra yazılır. Aynı noktaya ikinci uç açılmaz (mükerrer koruması
        `change` içindedir). Onay/üretim kararı AYRIDIR: işaret koymak onay değildir.
        """
        with self.lock:
            number=int(payload.get('page') or self.manifest['physical_page'])
            if number not in self.viewable_pages():
                raise ValueError('Sayfa %s hazırlanmadı.'%number)
            device=(payload.get('device') or '').strip()
            rows=payload.get('pins') or []
            # Yöntem ayrı sayılır: elle konan işaret ile programın bulup kullanıcının seçtiği
            # aday aynı kovaya girmez (effort ölçümü bunun üstünde durur).
            method=payload.get('method') or 'MANUAL'
            if method not in ('MANUAL','P04_CANDIDATE'):
                raise ValueError('Bilinmeyen işaretleme yöntemi: %s'%method)
            if not device:
                raise ValueError('Cihaz adı boş olamaz; okunamadıysa siz yazın.')
            if not rows:
                raise ValueError('En az bir uç gerekir.')
            for row in rows:
                if not isinstance(row,dict) or not row.get('point'):
                    raise ValueError('Uç kaydı eksik.')
                if not str(row.get('pin','')).strip():
                    raise ValueError('Uç adı boş olamaz: %s'%(row.get('point'),))
            created={'box':None,'pins':[]}
            if payload.get('bbox'):
                created['box']=self.change_box(dict(page=number,bbox=payload['bbox'],
                                                    note='Elle işaretlenen cihaz: '+device,active=True,
                                                    excluded_objects=payload.get('exclude') or []))
            for row in rows:
                created['pins'].append(self.change(dict(page=number,device=device,
                                                        pin=str(row['pin']).strip(),point=row['point'],
                                                        kind=row.get('kind') or 'PHYSICAL',
                                                        method=method,note=payload.get('note',''))))
            return dict(page=number,device=device,method=method,created=created,
                        note='Kullanıcı işareti kaydedildi. Onay/üretim kararı ayrıdır.')

    def change(self,payload):
        with self.lock:
            self.refresh()
            # MUKERRER KAYIT KORUMASI sunucu tarafinda: ayni sayfada ayni noktaya IKINCI bir uc
            # acilamaz. Var olan kaydi duzeltmek icin `id` verilir. Koruma yalniz arayuzde
            # olsaydi tekrar calistirilan gruplu uygulama kopya uretebilirdi.
            if not payload.get('id') and payload.get('point'):
                point=[round(float(v),2) for v in payload['point']]
                page=int(payload.get('page') or self.manifest['physical_page'])
                clash=next((q for q in self.pins if q.get('page',4)==page
                            and [round(v,2) for v in q['point']]==point),None)
                if clash is not None:
                    raise ValueError('Bu noktada zaten bir uç var: %s:%s (%s). Mükerrer kayıt '
                                     'açılmaz; düzeltmek için mevcut kaydı seçin.'
                                     %(clash['device'],clash['pin'],clash['id']))
            pages=self.viewable_pages()
            if payload.get('id') and payload.get('active') is False:
                # Geri alma HER ZAMAN mümkün olmalı: sayfası şu an hazırlanmamış olsa bile
                # kullanıcı yanlış işareti pasifleştirebilir. Kaydın kendi sayfası eklenir.
                old=next((q for q in list(self.pins)+list(getattr(self,'retired',[]))
                          if q['id']==payload['id']),None)
                if old is not None and old.get('page',4) not in pages:
                    pages=dict(pages)
                    pages[old.get('page',4)]=(old['point'][0]+1.0,old['point'][1]+1.0)
            result=self.store.change(payload,pages)
            # A mark on a sheet suspends every review that depends on that sheet.
            self.store.mark_stale([result['page']],'PIN_CHANGED',self.revision)
            self.refresh()
            return result

    def add_review(self,payload):
        """Kullanıcı incelemesini; incelenen pin sürümleri VE bağlı olduğu sayfalarla sakla."""
        with self.lock:
            self.refresh()
            byid={p['id']:p for p in self.pins}
            missing=[i for i in payload.get('pin_ids',[]) if i not in byid]
            if missing:
                raise ValueError('İncelenen pin bulunamadı: '+', '.join(missing))
            versions={i:byid[i]['version'] for i in payload.get('pin_ids',[])}
            pages=payload.get('pages')
            if pages is None and payload.get('subject')=='DASH_RUN':
                # Sessiz varsayılan YOK: sayfa 4 ile 5'in geometrisi birebir aynı olduğu için
                # sayfası yazılmayan bir karar yanlış sayfaya işlenebilirdi.
                if payload.get('page') in (None,''):
                    raise ValueError('Kesikli hat incelemesi sayfa numarası ister.')
                pages=[int(payload['page'])]
            if pages is None:
                pages=sorted({byid[i].get('page',4) for i in versions} or {self.manifest['physical_page']})
            if not isinstance(pages,list) or not all(isinstance(n,int) and n in self.pages() for n in pages):
                raise ValueError('İnceleme sayfaları geçersiz.')
            signatures={str(n):list(self._page_signature(n,self.pins,self.boxes)) for n in pages}
            if payload.get('subject')=='DASH_RUN':
                # Karar, koşunun KENDİ çizim imzasına da bağlanır: parçalar veya uçlar
                # değişirse eski onay kendiliğinden geçerli sayılmaz.
                run_key=(payload.get('run_key') or '').strip()
                if not run_key:
                    raise ValueError('Kesikli hat incelemesi koşu kimliği ister.')
                signatures['dash_run']=[run_key,self._dash_signature(pages[0],run_key)]
            result=self.store.add_review(payload,versions,self.revision,pages,signatures)
            self.refresh()
            return result

    def review_status(self):
        """Kayıtlı incelemeler ve hâlâ geçerli olup olmadıkları."""
        with self.lock:
            self.refresh()
            byid={p['id']:p for p in self.pins}
            rows=[]
            for review in self.reviews:
                changed=[i for i,v in review.get('pin_versions',{}).items()
                         if i not in byid or byid[i]['version']!=v]
                stale=review.get('stale_events') or []
                reasons=[]
                if changed:
                    reasons.append('İncelenen pin(ler) değişti.')
                if stale:
                    pages=sorted({n for event in stale for n in event['pages']})
                    reasons.append('Bağlı sayfa(lar) %s üzerinde işaret/maske değişti (%d kez).'
                                   %(', '.join(str(n) for n in pages),len(stale)))
                rows.append(dict(review,changed_pins=changed,stale_events=stale,
                                 pins=[dict(id=i,device=byid[i]['device'],pin=byid[i]['pin'],
                                            page=byid[i].get('page',4),version=byid[i]['version'])
                                       for i in review.get('pin_ids',[]) if i in byid],
                                 status='NEEDS_REVIEW' if (changed or stale) else 'CURRENT',
                                 reason=' '.join(reasons) or None,production_ready=False))
            return dict(rows=rows,current=sum(1 for r in rows if r['status']=='CURRENT'),
                        needs_review=sum(1 for r in rows if r['status']=='NEEDS_REVIEW'),
                        annotation_revision=self.revision,production_ready=False,
                        note='İnceleme kaydı hem incelenen pin sürümlerini hem de bağlı olduğu sayfaları '
                             'dondurur. O sayfada herhangi bir pin veya sembol kutusu eklenir, değişir ya '
                             'da pasifleşirse kayıt NEEDS_REVIEW olur ve kendiliğinden geri dönmez: eski '
                             'geometrinin geri gelmesi onayı canlandırmaz.',
                        scope_limitation='Bu sürümde geçersizleştirme SAYFA düzeyindedir: aynı sayfadaki '
                                         'ilgisiz bir işaret de yeniden inceleme ister. Güvenli taraf '
                                         'seçildi; yol düzeyinde daraltma sonraki adımdır.')

    def change_box(self,payload):
        with self.lock:
            result=self.store.change_box(payload,self.viewable_pages())
            self.store.mark_stale([result['page']],'SYMBOL_BOX_CHANGED',self.revision)
            self.refresh()
            return result
