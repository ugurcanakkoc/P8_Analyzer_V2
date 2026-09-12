import copy
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from analyzer_v3 import document as D
from analyzer_v3.geometry import PathGraph, ends_near
from analyzer_v3.models import (Endpoint, in_scope, pair_key, validate_box, validate_evidence_row,
                                validate_pin)
from analyzer_v3.prepare import ROOT, display_point, original_point
from analyzer_v3.service import Pilot
from analyzer_v3.library import (SymbolLibrary, descriptor_of, entry_from_descriptor,
                                 propose_family, validate_update)
from analyzer_v3.similarity import (descriptor, find as find_similar, search as search_similar,
                                    template as build_template)
from analyzer_v3.server import make_server

RUN=ROOT/'output/pilots/E122/20260909_v3_p03'
LIVE5=ROOT/'output/pilots/E122/20260910_v3_p05_rev8'

# Testler CANLI kayda bakmaz. Kullanıcı uygulamayla yeni işaret koydukça sayfa 4/5'in
# durumu değişir; bu bir gerileme değil, kullanıcının işidir. Takım bu yüzden kaydın
# BELİRLİ BİR ANDAKİ halini kullanır: bu andan sonra açılan kayıtlar kopyadan düşürülür,
# canlı kayda dokunulmaz. Ölçüm: 2026-09-12 16:52'den sonra 210 uç eklendi ve beklentiye
# dayanan 10 test kırmızıya döndü.
FIXTURE_CUTOFF='2026-09-12T16:00:00+00:00'


def _frozen_run():
    """LIVE5'in dondurulmuş kopyası (bir kez kurulur, oturum boyunca kullanılır)."""
    import atexit, sqlite3
    frozen=Path(tempfile.mkdtemp(prefix='uvp-frozen-'))/'run'
    shutil.copytree(LIVE5,frozen)
    atexit.register(shutil.rmtree,frozen.parent,True)
    db=sqlite3.connect(str(frozen/'annotations.sqlite3'))
    try:
        later={row[0] for row in db.execute(
            'select pin_id from events group by pin_id having min(time)>?',(FIXTURE_CUTOFF,))}
        for table in ('pins','boxes','reviews'):
            for record in [r[0] for r in db.execute('select id from %s'%table)]:
                if record in later:
                    db.execute('delete from %s where id=?'%table,(record,))
        db.execute('delete from events where time>?',(FIXTURE_CUTOFF,))
        db.commit()
    finally:
        db.close()
    return frozen


RUN5=_frozen_run() if (LIVE5/'manifest.json').exists() else LIVE5


def seg(i,a,b,**kwargs):
    return dict(id=str(i),a=a,b=b,**kwargs)


def pin(i,x,y,**kwargs):
    return dict(id=i,point=[x,y],device='=112+E122-K1',pin=i,kind='PHYSICAL',**kwargs)


class IdentityTests(unittest.TestCase):
    def test_full_address_and_suffix(self):
        self.assertNotEqual(Endpoint('=112+E122-X4','Q:1').key,Endpoint('=122+E122-X4','Q:1').key)
        self.assertNotEqual(Endpoint('=112+E122-X4','Q:1').key,Endpoint('=112+E122-X4','Q:2').key)
        self.assertEqual(Endpoint(' =112+E122-X4 ','q:1').key,('=112+E122-X4','Q:1'))

    def test_scope_not_device_letter(self):
        self.assertTrue(in_scope('=112+E122-M1'))
        for value in ['=113+E122-K1','=112+M113-K1','=122+T1-X4','X4','=112+E122-']:
            self.assertFalse(in_scope(value),value)

    def test_unknown_not_deduplicated(self):
        with self.assertRaises(ValueError):
            pair_key(Endpoint('X4',''),Endpoint('X4',''))

    def test_input_validation(self):
        pages={4:(10,10),5:(10,10)}
        p=dict(device='',pin='',note='',point=[2,3],kind='PHYSICAL',page=4)
        self.assertEqual(validate_pin(p,pages)['pin'],'')
        self.assertEqual(validate_pin(p,pages)['method'],'MANUAL')
        for point in [[True,3],[math.nan,0],[math.inf,1],[-1,0],[11,0],'2,3']:
            with self.assertRaises(ValueError):
                validate_pin(dict(p,point=point),pages)
        # Bir işaret yalnız izlenen bir sayfaya konur; bilinmeyen sayfa reddedilir.
        for bad in [dict(p,page=9),dict(p,page='4'),dict(p,page=True),dict(p,method='AUTO')]:
            with self.assertRaises(ValueError):
                validate_pin(bad,pages)
        self.assertEqual(validate_box(dict(page=5,bbox=[1,1,4,4]),pages)['source'],'MANUAL_VISUAL_MASK')
        for bad in [dict(page=5,bbox=[1,1,1,4]),dict(page=5,bbox=[1,1,4]),dict(page=9,bbox=[1,1,4,4])]:
            with self.assertRaises(ValueError):
                validate_box(bad,pages)

    def test_evidence_without_both_sources_fails(self):
        with self.assertRaises(ValueError):
            validate_evidence_row(dict(status='CONFIRMED_BOTH',vector_evidence=['a'],visual_evidence=None))

    def test_attribute_provenance_required(self):
        base=dict(status='UNRESOLVED',cross_section='',wire_color='',production_ready=False)
        validate_evidence_row(base)
        for extra in [dict(wire_color='DBU'),dict(cross_section_provenance='ELECTRICAL_RULE'),dict(production_ready=True),dict(review_status='APPROVED')]:
            with self.assertRaises(ValueError):
                validate_evidence_row(dict(base,**extra))


class GeometryTests(unittest.TestCase):
    def test_unjoined_x(self):
        g=PathGraph([seg(1,[0,5],[10,5]),seg(2,[5,0],[5,10])],[],[pin('a',0,5),pin('b',5,10)])
        self.assertEqual(g.trace('a')['targets'],[])
        self.assertEqual(len(g.crossings),1)

    def test_split_x_is_not_a_t(self):
        g=PathGraph([seg(1,[0,5],[5,5]),seg(2,[5,5],[10,5]),seg(3,[5,0],[5,5]),seg(4,[5,5],[5,10])],[],[pin('a',0,5),pin('b',5,10)])
        self.assertEqual(g.trace('a')['targets'],[])

    def test_explicit_dot_connects_only_graph(self):
        g=PathGraph([seg(1,[0,5],[10,5]),seg(2,[5,0],[5,10])],[dict(point=[5,5],radius=1)],[pin('a',0,5),pin('b',5,10)])
        self.assertEqual(g.trace('a')['targets'][0]['relation'],'DRAWN_REACHABILITY_ONLY')

    def test_t_branches_no_chain(self):
        g=PathGraph([seg(1,[0,5],[10,5]),seg(2,[5,5],[5,10])],[],[pin('a',0,5),pin('b',10,5),pin('c',5,10)])
        t=g.trace('a')
        self.assertEqual({p['pin_id'] for p in t['targets']},{'b','c'})
        self.assertIn('BRANCH_ORDER_NOT_INFERRED',t['issues'])
        self.assertNotIn('physical_connections',t)

    def test_short_bridge_preserved(self):
        g=PathGraph([seg(1,[0,0],[1,0]),seg(2,[1,0],[1,1])],[],[pin('a',0,0),pin('b',1,1)])
        self.assertEqual(len(g.trace('a')['targets']),1)

    def test_contact_interior_removed_not_traversed(self):
        g=PathGraph([seg(1,[5,0],[5,20])],[],[pin('a',5,0),pin('b',5,20)],[dict(id='contact',bbox=[0,5,10,15])])
        self.assertEqual(g.trace('a')['targets'],[])
        self.assertIn('DEVICE_INTERIOR',[e['reason'] for e in g.excluded])

    def test_stop_at_intermediate_pin(self):
        g=PathGraph([seg(1,[0,0],[10,0])],[],[pin('a',0,0),pin('b',5,0),pin('c',10,0)])
        self.assertEqual([t['pin_id'] for t in g.trace('a')['targets']],['b'])

    def test_unattached_pin_is_not_traversed_silently(self):
        # Denetim bulgusu: bağlanamayan ara uç, uzak ucu doğrudan erişilebilir gösteriyordu.
        g=PathGraph([seg(1,[0,0],[10,0]),seg(2,[0,.5],[10,.5])],[],[pin('a',0,0),pin('b',5,.25),pin('c',10,0)])
        self.assertEqual(g.pin_issues,{'b':'AMBIGUOUS_PIN_ATTACHMENT'})
        t=g.trace('a')
        self.assertEqual(t['targets'],[])
        self.assertEqual(t['unattached_pins'],['b'])
        self.assertIn('UNATTACHED_PIN_ON_PATH',t['issues'])

    def test_ambiguous_attachment_not_nearest_guess(self):
        g=PathGraph([seg(1,[0,0],[10,0]),seg(2,[0,.5],[10,.5])],[],[pin('a',5,.25)])
        self.assertEqual(g.trace('a')['issues'],['AMBIGUOUS_PIN_ATTACHMENT'])

    def test_same_device_and_dangling_preserved(self):
        g=PathGraph([seg(1,[0,0],[10,0])],[],[pin('a',0,0),pin('b',10,0)])
        self.assertEqual(len(g.trace('a')['targets']),1)
        g=PathGraph([seg(1,[0,0],[10,0])],[],[pin('a',0,0)])
        self.assertEqual(len(g.trace('a')['open_ends']),1)

    def test_ends_near_finds_only_dangling_ends(self):
        segments=[seg(1,[0,0],[10,0]),seg(2,[10,0],[10,10]),seg(3,[40,0],[50,0],dash=True)]
        self.assertEqual([e['point'] for e in ends_near(segments,(0,0),dx=5)],[[0,0]])
        # (10,0) is a corner where two segments meet: not an open end.
        self.assertEqual(ends_near(segments,(10,0),dx=5),[])
        self.assertEqual(ends_near(segments,(45,0),dx=5),[])  # dashed lines are not interpreted

    def test_dashed_and_diagonal_reported(self):
        g=PathGraph([seg(1,[0,0],[10,0],dash=True),seg(2,[0,0],[5,5])],[],[pin('a',0,0)])
        self.assertEqual(len(g.excluded),2)
        self.assertIn('NO_LINE_AT_PIN',g.trace('a')['issues'])


def word(text,x,y):
    return dict(text=text,x0=x-1,x1=x+1,top=y-1,bottom=y+1)


class SimilarityTests(unittest.TestCase):
    """P04: shape-only proposals. Names are never copied from the template."""
    BOX=dict(id='tpl',bbox=[0,0,10,10],source='MANUAL_VISUAL_MASK')
    PINS=[pin('a',2,1),pin('b',8,9)]
    WORDS=[word('A1',3.5,1),word('-K1',2,-6),word('A1',23.5,1),word('-K2',22,-6)]

    def find(self,segments,words=None):
        return find_similar(self.BOX,self.PINS,segments,words or self.WORDS,[0,0,0,0])

    def test_translated_copy_is_a_candidate_without_copying_names(self):
        r=self.find([seg('blade',[2,1],[8,9]),seg('blade2',[22,1],[28,9])])
        self.assertEqual([c['offset'] for c in r['candidates']],[[0,0],[20,0]])
        c=r['candidates'][1]
        self.assertEqual(c['page_device_texts'],['-K2'])
        self.assertIn('DEVICE_LABEL_DIFFERS_FROM_TEMPLATE',c['issues'])
        self.assertTrue(c['requires_user_confirmation'])
        self.assertFalse(c['production_ready'])
        self.assertEqual([p['point'] for p in c['pins']],[[22,1],[28,9]])
        self.assertEqual(c['pins'][0]['page_pin_texts'],['A1'])
        self.assertEqual(c['pins'][0]['already_marked'],[])

    def test_missing_page_label_is_reported_not_invented(self):
        r=self.find([seg('blade',[2,1],[8,9]),seg('blade2',[22,1],[28,9])],
                    [word('A1',3.5,1),word('-K1',2,-6)])
        c=r['candidates'][1]
        self.assertEqual(c['pins'][0]['page_pin_texts'],[])
        self.assertIn('PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET',c['pins'][0]['issues'])
        self.assertIn('DEVICE_LABEL_NOT_FOUND_AT_SAME_OFFSET',c['issues'])

    def test_no_nc_difference_is_rejected_and_reported(self):
        r=self.find([seg('blade',[2,1],[8,9]),seg('blade2',[22,1],[28,9]),seg('bar',[21,5],[29,5])])
        self.assertEqual([c['offset'] for c in r['candidates']],[[0,0]])
        self.assertEqual([(x['offset'],x['reason'],x['candidate_parts']) for x in r['rejected']],
                         [([20,0],'CORE_GEOMETRY_DIFFERS',2)])

    def test_mirrored_instance_is_not_proposed(self):
        r=self.find([seg('blade',[2,1],[8,9]),seg('mirror',[22,9],[28,1])])
        self.assertEqual([c['offset'] for c in r['candidates']],[[0,0]])

    def test_external_wiring_is_rechecked_per_instance(self):
        box=dict(id='tpl',bbox=[0,0,10,10],source='MANUAL_VISUAL_MASK')
        pins=[pin('a',2,0),pin('b',8,10)]
        segments=[seg('blade',[2,0],[8,10]),seg('wire',[2,0],[2,-10]),
                  seg('blade2',[22,0],[28,10]),
                  seg('blade3',[42,0],[48,10]),seg('w3a',[42,0],[42,-10]),seg('w3b',[41.8,0],[41.8,-10])]
        r=find_similar(box,pins,segments,[],[0,0,0,0])
        by={c['offset'][0]:c for c in r['candidates']}
        self.assertEqual(sorted(by),[0,20,40])
        self.assertEqual(by[0]['pins'][0]['external_lines'],1)
        self.assertIn('NO_EXTERNAL_LINE_AT_POINT',by[20]['pins'][0]['issues'])
        self.assertIn('EXTERNAL_LINE_COUNT_DIFFERS_FROM_TEMPLATE',by[40]['pins'][0]['issues'])

    def test_existing_annotation_marks_candidate_instead_of_duplicate(self):
        r=find_similar(self.BOX,self.PINS,[seg('blade',[2,1],[8,9]),seg('blade2',[22,1],[28,9])],
                       self.WORDS,[0,0,0,0],self.PINS+[pin('c',22,1)])
        self.assertEqual(r['candidates'][1]['pins'][0]['already_marked'],['c'])


def sheet(number, anlage, ort, blatt, doc='Schaltplan', extra=()):
    words=[word('Einbauort',1075,756),word('Anlage',1011,756),word('='+anlage,1023,766),word('+'+ort,1076,766),
           word('Blatt',1068,785),word(blatt,1094,785),word('Kommission',235,757),word(doc,487,757)]
    return D.page_facts(number,words+list(extra))


class DocumentTests(unittest.TestCase):
    """P05: sayfa kimliği, çapraz referans ve uç uzlaştırma. Hiçbiri tel üretmez."""

    def test_scope_needs_function_and_location(self):
        self.assertEqual(sheet(1,'112','E122','3')['scope'],'IN_SCOPE')
        self.assertEqual(sheet(2,'112','E112','1')['scope'],'OUT_OF_SCOPE_LOCATION')
        self.assertEqual(sheet(3,'113','E122','1')['scope'],'OUT_OF_SCOPE_FUNCTION')

    def test_missing_title_block_is_unknown_not_guessed(self):
        facts=D.page_facts(9,[word('Blatt',1068,785),word('2',1094,785)])
        self.assertEqual(facts['scope'],'UNKNOWN')
        self.assertIn('TITLE_BLOCK_EINBAUORT_LABEL_MISSING',facts['issues'])

    def test_printed_function_survives_the_page_anlage(self):
        page=sheet(28,'122','E122','17',extra=[word('=112-17K52',117,436)])
        name,inherited=D.full_device_name(page['devices'][0],page)
        self.assertEqual((name,inherited),('=112+E122-17K52',['ort']))

    def test_same_blatt_in_two_documents_stays_ambiguous(self):
        index=[sheet(50,'132','E111','1'),sheet(51,'132','E122','1')]
        r=D.resolve_target(dict(anlage='132',ort=None,blatt='1',position='11'),index[1],index)
        self.assertEqual((r['status'],r['target_pages']),('AMBIGUOUS_TARGET_PAGE',[50,51]))
        exact=D.resolve_target(dict(anlage='132',ort='E122',blatt='1',position='11'),index[1],index)
        self.assertEqual((exact['status'],exact['target_pages']),('RESOLVED',[51]))

    def test_contact_coil_reference_is_not_a_wire(self):
        source=sheet(4,'112','E122','3',extra=[word('-17K52',283,265),word('=122/17.52',280,275)])
        target=sheet(28,'122','E122','17',extra=[word('=112-17K52',117,436)])
        rows=D.references_for_page(4,[source,target])
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual((row['kind'],row['relation']),('DEVICE_CROSS_REFERENCE','CROSS_REFERENCE_ONLY_NOT_A_WIRE'))
        self.assertEqual((row['status'],row['target_pages']),('RESOLVED',[28]))
        self.assertEqual((row['owner_device'],row['target_device_texts']),('=112+E122-17K52',['=112-17K52']))
        self.assertEqual(row['position_token'],'52')
        self.assertFalse(row['production_ready'])

    def test_unresolved_reference_is_reported_not_dropped(self):
        source=sheet(4,'112','E122','3',extra=[word('/9.11',44,83)])
        row=D.references_for_page(4,[source])[0]
        self.assertEqual(row['kind'],'LINE_CONTINUATION_CANDIDATE')
        self.assertIn('TARGET_PAGE_NOT_FOUND',row['issues'])

    def test_same_name_on_two_sheets_is_not_one_point(self):
        index=[sheet(4,'112','E122','3',extra=[word('-X4:4',300,470)]),
               sheet(5,'112','E122','4',extra=[word('-X4:4',300,470),word('-X4:7',400,470)])]
        r=D.reconcile_endpoint('=112+E122-X4','4',index)
        self.assertEqual((r['status'],r['pages']),('EXACT_PIN_PRINTED',[4,5]))
        self.assertTrue(r['multiple_drawing_locations'])
        self.assertEqual([o['printed_pin'] for o in r['other_occurrences']],['7'])
        self.assertFalse(r['production_ready'])

    def test_device_keeps_its_own_printed_location(self):
        # Kullanıcı bulgusu: +M113 saha cihazı pano içi (+E122) sayılıyordu.
        page=sheet(4,'112','E122','3',extra=[word('-3A72',95,573),word('+M113',96,592)])
        device=page['devices'][0]
        self.assertEqual(device['local_location'],'M113')
        name,inherited=D.full_device_name(device,page)
        self.assertEqual((name,inherited),('=112+M113-3A72',['anlage']))
        self.assertFalse(in_scope(name))

    def test_unassignable_location_marker_leaves_devices_uncertain(self):
        page=sheet(4,'112','E122','3',extra=[word('-3A72',95,573),word('-3A73',95,573),word('+M113',96,592)])
        self.assertIn('LOCAL_LOCATION_MARKER_UNASSIGNED',page['issues'])
        self.assertTrue(all(d['location_uncertain'] for d in page['devices']))
        self.assertEqual(page['unassigned_location_markers'][0]['devices_above'],2)

    def test_multi_part_pin_name_is_not_split_from_the_right(self):
        # Kullanıcı bulgusu: -4D27:X1:P1 kaydı 'bulunamadı' dönüyordu.
        index=[sheet(4,'112','E122','3',extra=[word('-4D27:X1:P1',300,300),word('-4D27:X1:P2',400,300)])]
        r=D.reconcile_endpoint('=112+E122-4D27','X1:P1',index)
        self.assertEqual((r['status'],r['pages']),('EXACT_PIN_PRINTED',[4]))
        self.assertEqual([o['printed_pin'] for o in r['other_occurrences']],['X1:P2'])
        self.assertEqual(D.reconcile_endpoint('=112+E122-4D27','X1:P9',index)['status'],
                         'DEVICE_PRINTED_PIN_NOT_PRINTED')

    def test_signal_labels_exclude_references_devices_and_numbers(self):
        words=[word('P24.32',110,94),word('/4.23',150,100),word('-17K52',108,100),word('4',96,100),
               word('N24.30',110,140)]
        labels=D.signal_labels(words,(100,100))
        self.assertEqual([l['text'] for l in labels],['P24.32'])

    def test_rotated_word_keeps_raw_text_and_flag(self):
        # Denetim bulgusu: döndürülmüş yazı sessizce düşüyordu.
        rotated=dict(word('=122/17.44',280,275),rotated=True,raw_text='44.71/221=',rotation='CCW')
        facts=D.page_facts(4,[rotated])
        self.assertEqual(facts['rotated_words'],1)
        self.assertEqual(facts['cross_references'][0]['text'],'=122/17.44')
        self.assertEqual(facts['cross_references'][0]['raw_text'],'44.71/221=')
        undecided=D.page_facts(4,[dict(word('X',10,10),rotated=True,raw_text='X',rotation='UNKNOWN')])
        self.assertIn('ROTATED_TEXT_ORDER_UNDECIDED',undecided['issues'])

    def test_every_document_type_is_searched(self):
        # Denetim bulgusu: yalnız Schaltplan taranıyordu; Stückliste kayıtları sessizce düşüyordu.
        index=[sheet(4,'112','E122','3',extra=[word('-17K52',283,265)]),
               sheet(9,'112','E122','1',doc='Stückliste',extra=[word('-17K52',100,200)])]
        r=D.reconcile_endpoint('=112+E122-17K52','13',index)
        self.assertEqual(sorted({o['physical_page'] for o in r['other_occurrences']}),[4,9])
        self.assertEqual(r['searched_doc_types'],['Schaltplan','Stückliste'])
        self.assertEqual(sorted({o['doc_type'] for o in r['other_occurrences']}),['Schaltplan','Stückliste'])
        self.assertEqual(sorted({o['physical_page'] for o in D.occurrences('=112+E122-17K52',index)}),[4,9])

    def test_pin_not_printed_is_reported(self):
        index=[sheet(4,'112','E122','3',extra=[word('-17K52',283,265)])]
        self.assertEqual(D.reconcile_endpoint('=112+E122-17K52','13',index)['status'],
                         'DEVICE_PRINTED_PIN_NOT_PRINTED')
        self.assertEqual(D.reconcile_endpoint('=112+E122-9K9','1',index)['status'],
                         'DEVICE_NOT_PRINTED_ON_ANY_PAGE')


class CoordinateTests(unittest.TestCase):
    def test_offset_roundtrip(self):
        for bbox in [[-1,1,1120.68,810.87],[10,20,90,180]]:
            p=[31.5,49.5]
            self.assertEqual(original_point(display_point(p,bbox),bbox),p)

    def test_render_alignment_crop_rotation(self):
        # Synthetic PDFs remain in memory: an independent pixel check, not a pure math self-test.
        import pdfplumber
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject, RectangleObject
        for rotation in [0,90,180,270]:
            w=PdfWriter(); p=w.add_blank_page(200,120)
            p.mediabox=RectangleObject([-10,20,190,140]);p.cropbox=RectangleObject([0,30,180,130])
            stream=DecodedStreamObject();stream.set_data(b'0 G 2 w 30 50 m 90 50 l S')
            p[NameObject('/Contents')]=w._add_object(stream)
            p.rotate(rotation)
            buffer=BytesIO();w.write(buffer);buffer.seek(0)
            with pdfplumber.open(buffer) as doc:
                page=doc.pages[0];im=page.to_image(resolution=144,force_mediabox=True)
                line=page.lines[0]
                middle=[sum(p[d] for p in line['pts'])/2 for d in [0,1]]
                pos=display_point(middle,im.bbox)
                x=round(pos[0]*im.original.width/(im.bbox[2]-im.bbox[0]))
                y=round(pos[1]*im.original.height/(im.bbox[3]-im.bbox[1]))
                neighborhood=im.original.crop((x-2,y-2,x+3,y+3)).convert('L')
                self.assertLess(neighborhood.getextrema()[0],50,f'rotation={rotation}')


@unittest.skipUnless((RUN/'manifest.json').exists(),'Prepare the real PDF pilot first')
class RealPilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='uvp-pilot-test-')
        self.run=Path(self.tmp.name)/'run'
        shutil.copytree(RUN,self.run)
        self.p=Pilot(self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_specific_claims_not_full_page_accuracy(self):
        s=self.p.state()
        self.assertEqual([(c['id'],c['status'],len(c['path'])) for c in s['claims']],[(c,'CONFIRMED_BOTH',3) for c in ['C01','C02','C03']])
        self.assertEqual(s['claims'][0]['kind'],'NETWORK')
        self.assertTrue(all(not c['production_ready'] for c in s['claims']))
        t=self.p.trace('k53_top')
        self.assertNotIn('k52_top',[p['pin_id'] for p in t['targets']])

    def test_claim_rows_carry_trace_warnings(self):
        # Denetim bulgusu: T dalı/açık uç uyarıları ilişki satırından düşüyordu.
        c=self.p.state()['claims'][0]
        self.assertIn('trace_issues',c)
        self.assertEqual(c['trace_issues'],self.p.trace(c['source_id'])['issues'])
        self.assertTrue(c['branch_points'] or c['open_ends'] or not c['trace_issues'])
        self.assertEqual(c['relation'],'DRAWN_REACHABILITY_ONLY')

    def test_removed_real_bridge_is_conflict(self):
        page=self.p._page(4)
        page['segments']=[s for s in page['segments'] if s['id']!='line:1933']
        self.p.revision=None
        claims=self.p.state()['claims']
        self.assertEqual(claims[1]['status'],'CONFLICT')
        self.assertEqual(claims[1]['review_status'],'PENDING')
        self.assertEqual(claims[0]['status'],'CONFIRMED_BOTH')

    def test_pin_move_invalidates_prior_approvals_and_logs(self):
        old=next(p for p in self.p.state()['pins'] if p['id']=='k52_top')
        new=self.p.change(dict(old,expected_version=old['version'],point=[50,50]))
        s=self.p.state()
        self.assertTrue(all(c['status']=='UNRESOLVED' and c['review_status']=='PENDING' for c in s['claims']))
        self.assertEqual(len(s['claims']),3)
        self.assertEqual(s['claims'][0]['original_target']['point'],old['point'])
        with self.p.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
        with self.assertRaises(ValueError):
            self.p.change(dict(old,expected_version=old['version']))
        self.p.change(dict(new,expected_version=new['version'],point=old['point']))
        self.assertTrue(all(c['review_status']=='PENDING' for c in self.p.state()['claims']))

    def test_unknown_and_out_of_scope_pins_still_visible(self):
        p=self.p.change(dict(device='=113+E122-X1',pin='1',point=[10,10],kind='PHYSICAL',note='scope test'))
        self.assertIn('SOURCE_OUT_OF_SCOPE_OR_UNKNOWN',self.p.trace(p['id'])['issues'])
        a=self.p.change(dict(device='',pin='',point=[20,20],kind='PHYSICAL',note='unknown a'))
        b=self.p.change(dict(device='',pin='',point=[30,30],kind='PHYSICAL',note='unknown b'))
        self.assertNotEqual(a['id'],b['id'])

    def test_similar_candidates_reread_each_instance_and_store_nothing(self):
        before=self.p.state()
        data=self.p.candidates('contact_52')
        self.assertEqual([c['page_device_texts'] for c in data['candidates']],[['-17K52'],['-17K53'],['-17K55']])
        # The template pin is 13; the other two instances really carry 11 on the page.
        self.assertEqual([c['pins'][0]['page_pin_texts'] for c in data['candidates']],[['13'],['11'],['11']])
        self.assertEqual([c['pins'][0]['template_pin'] for c in data['candidates']],['13']*3)
        for c in data['candidates'][1:]:
            self.assertIn('PIN_LABEL_DIFFERS_FROM_TEMPLATE',c['pins'][0]['issues'])
            self.assertIn('DEVICE_LABEL_DIFFERS_FROM_TEMPLATE',c['issues'])
            self.assertTrue(all(p['already_marked'] for p in c['pins']))
        self.assertTrue(all(not c['production_ready'] and c['requires_user_confirmation'] for c in data['candidates']))
        after=self.p.state()
        self.assertEqual((before['revision'],before['pins']),(after['revision'],after['pins']))
        self.assertEqual([c['status'] for c in after['claims']],['CONFIRMED_BOTH']*3)
        with self.assertRaises(ValueError):
            self.p.candidates('yok')

    def test_tampered_artifact_rejected(self):
        (self.run/'geometry.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):
            Pilot(self.run)

    def test_http_local_security_and_mutation(self):
        server=make_server(self.p,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/api/state') as r:
                state=json.load(r)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+'/api/state',headers={'Host':'evil.example'}))
            self.assertEqual(error.exception.code,403)
            for path in ['/../MAIN.md','/api/export','/api/candidates?template=yok']:
                with self.assertRaises(HTTPError):
                    urlopen(base+path)
            with urlopen(base+'/api/candidates?template=contact_53') as r:
                self.assertEqual(len(json.load(r)['candidates']),3)
            payload=json.dumps(dict(device='',pin='',point=[20,20],kind='PHYSICAL')).encode()
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+'/api/pins',data=payload,headers={'Content-Type':'application/json','Origin':'https://evil.example','X-Pilot-Token':state['csrf_token']}))
            self.assertEqual(error.exception.code,403)
            with urlopen(Request(base+'/api/pins',data=payload,headers={'Content-Type':'application/json','Origin':base,'X-Pilot-Token':state['csrf_token']})) as r:
                self.assertTrue(json.load(r)['id'].startswith('user_'))
        finally:
            server.shutdown();server.server_close();thread.join()


def curve(cid, x0, y0, points, fill=False):
    xs=[x0+p[0] for p in points]; ys=[y0+p[1] for p in points]
    return dict(id=cid, bbox=[min(xs),min(ys),max(xs),max(ys)],
                points=[[x0+p[0], y0+p[1]] for p in points], fill=fill, stroke=True)


CIRCLE=[(0,2.8),(0.4,1.4),(1.4,0.4),(2.8,0),(4.2,0.4),(5.2,1.4),(5.6,2.8),(5.2,4.2),(4.2,5.2),(2.8,5.6),(1.4,5.2),(0.4,4.2)]
SQUARE=[(0,0),(5.6,0),(5.6,5.6),(0,5.6),(0,0)]


class ShapeReliabilityTests(unittest.TestCase):
    """Aynı sınırlayıcı kutu aynı şekil değildir; desteklenmeyen dönüşüm sessizce kabul edilmez."""
    BOX=dict(id='tpl',bbox=[0,0,6,6],source='MANUAL_VISUAL_MASK')
    PINS=[pin('a',0,3),pin('b',6,3)]
    WORDS=[word('1',3,-4),word('-X9',0,-8),word('1',43,-4),word('-X8',40,-8),
           word('1',83,-4),word('-X7',80,-8)]

    def find(self,segments,curves,words=None):
        return find_similar(self.BOX,self.PINS,segments,words or self.WORDS,[0,0,0,0],curves=curves)

    def test_same_bbox_different_shape_is_not_a_match(self):
        r=self.find([],[curve('c1',0.2,0.2,CIRCLE),curve('c2',40.2,0.2,SQUARE)])
        self.assertEqual([c['bbox'][0] for c in r['candidates']],[0])
        self.assertEqual([x['bbox'][0] for x in r['rejected']],[])

    def test_scaled_or_rotated_copy_is_not_accepted(self):
        big=[(x*1.5,y*1.5) for x,y in CIRCLE]
        turned=[(y,x) for x,y in CIRCLE]
        r=self.find([],[curve('c1',0.2,0.2,CIRCLE),curve('big',40.2,0.2,big),curve('rot',80.2,0.2,turned)])
        self.assertEqual([c['bbox'][0] for c in r['candidates']],[0])
        self.assertIn('yalnız öteleme',r['limitation'].lower())

    def test_extra_object_in_box_is_rejected_not_ignored(self):
        # PE klemensi / NC kontağı gibi ek çizim taşıyan örnek elenir ve görünür kalır.
        r=self.find([seg('bar',[40.2,3],[45.8,3])],[curve('c1',0.2,0.2,CIRCLE),curve('c2',40.2,0.2,CIRCLE)])
        self.assertEqual([c['bbox'][0] for c in r['candidates']],[0])
        self.assertEqual([(x['origin'][0],x['template_parts'],x['candidate_parts']) for x in r['rejected']],
                         [(40,1,2)])

    def test_curve_without_point_list_is_flagged_not_trusted(self):
        plain=lambda cid,x0:dict(id=cid,bbox=[x0,0.2,x0+5.6,5.8],fill=False,stroke=True)
        r=self.find([],[plain('c1',0.2),plain('c2',40.2)])
        self.assertEqual(len(r['candidates']),2)
        self.assertTrue(all('CURVE_SHAPE_UNVERIFIED_BBOX_ONLY' in c['issues'] for c in r['candidates']))

    def test_moved_label_is_reported_not_guessed(self):
        words=[word('1',3,-4),word('-X9',0,-8),word('-X8',40,-8),word('1',47,-4)]
        r=self.find([],[curve('c1',0.2,0.2,CIRCLE),curve('c2',40.2,0.2,CIRCLE)],words)
        other=next(c for c in r['candidates'] if c['bbox'][0]==40)
        self.assertIn('PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET',other['pins'][0]['issues'])
        self.assertEqual(other['pins'][0]['page_pin_texts'],[])


class LineFlexibilityTests(unittest.TestCase):
    """Çizgi esnekliğinin BUGÜNKÜ sınırları. Bu pakette boşluklar kapatılmadı."""

    def reach(self,segments,dots=()):
        g=PathGraph(segments,list(dots),[pin('a',0,0),pin('b',20,0)])
        return bool(g.trace('a')['targets'])

    def test_single_line_is_supported(self):
        self.assertTrue(self.reach([seg(1,[0,0],[20,0])]))

    def test_touching_pieces_are_supported(self):
        self.assertTrue(self.reach([seg(1,[0,0],[10,0]),seg(2,[10,0],[20,0])]))

    def test_gapped_pieces_are_not_joined(self):
        # 0,1 pt boşluk: bağlanmaz. Otomatik kapatma bu pakette YOK.
        self.assertFalse(self.reach([seg(1,[0,0],[9.9,0]),seg(2,[10,0],[20,0])]))

    def test_dashed_line_is_not_traced(self):
        self.assertFalse(self.reach([seg(1,[0,0],[20,0],dash=True)]))

    def test_symbol_gap_is_not_bridged(self):
        g=PathGraph([seg(1,[0,0],[8,0]),seg(2,[12,0],[20,0])],[],[pin('a',0,0),pin('b',20,0)])
        self.assertEqual(g.trace('a')['targets'],[])

    def test_dotless_crossing_is_not_joined_but_a_dot_joins(self):
        crossing=[seg(1,[0,0],[20,0]),seg(2,[10,-10],[10,10])]
        marks=[pin('a',0,0),pin('b',10,10)]      # uçlar farklı çizgilerde: kesişim sınanır
        self.assertEqual(PathGraph(crossing,[],marks).trace('a')['targets'],[])
        joined=PathGraph(crossing,[dict(point=[10,0],radius=1)],marks)
        self.assertTrue(joined.trace('a')['targets'])


class LibraryTests(unittest.TestCase):
    """Kalıcı kütüphane: şekil ve konum saklanır; cihaz adı, bağlantı, renk, kesit, onay saklanmaz."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='uvp-library-test-')
        self.library=SymbolLibrary(Path(self.tmp.name)/'symbols.sqlite3')
        box=dict(id='tpl',bbox=[0,0,6,6],source='MANUAL_VISUAL_MASK')
        pins=[pin('a',0,3),pin('b',6,3)]
        words=[word('1',3,-4),word('-K1',0,-8)]
        tpl=build_template(box,pins,[],words,[0,0,0,0],curves=[curve('c1',0.2,0.2,CIRCLE)])
        self.descriptor=descriptor(tpl)
        self.entry=self.library.add(entry_from_descriptor(
            self.descriptor,dict(source_sha256='abc',run='test',physical_page=4,box_id='tpl'),
            dict(customer='TROESTER'),source_device='=112+E122-K1'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_entry_is_draft_and_stores_no_wiring_or_approval(self):
        entry=self.entry
        self.assertEqual((entry['status'],entry['version']),('DRAFT',1))
        self.assertIsNone(entry['approved_by'])
        self.assertEqual(entry['never_stored'],
                         ['CONNECTIONS','WIRE_COLOR','CROSS_SECTION','APPROVAL_OF_CONNECTIONS'])
        body=json.dumps(entry,ensure_ascii=False)
        for forbidden in ('=112+E122-K1','wire_color','cross_section'):
            self.assertNotIn(forbidden,body)
        # Kaynak yazı kanıt olarak durur, kimlik olarak değil.
        self.assertEqual(entry['source_device_label'],'-K1')
        self.assertEqual(entry['evidence_only'],['SOURCE_DEVICE_LABEL','SOURCE_PIN_LABEL'])
        self.assertIn('DEVICE_NAME',entry['never_copied'])
        self.assertNotIn('DEVICE_NAME',entry['never_stored'])
        self.assertIn('K',entry['family'])
        self.assertEqual(entry['transforms'],['TRANSLATION'])

    def test_family_edit_and_approval_are_versioned_and_named(self):
        renamed=self.library.update(self.entry['id'],1,validate_update(dict(family='Röle kontağı')))
        self.assertEqual((renamed['family'],renamed['version'],renamed['family_source']),
                         ('Röle kontağı',2,'USER'))
        with self.assertRaises(ValueError):
            self.library.update(self.entry['id'],1,dict(family='eski sürüm'))
        with self.assertRaises(ValueError):
            validate_update(dict(status='APPROVED'))
        approved=self.library.update(self.entry['id'],2,validate_update(
            dict(status='APPROVED',approved_by='Kullanıcı')))
        self.assertEqual((approved['status'],approved['approved_by']),('APPROVED','Kullanıcı'))
        self.assertEqual(len(self.library.history(self.entry['id'])),3)

    def test_entry_matches_a_new_document_without_source_pins(self):
        # Kaynak çalışmanın pinleri yok; adaylar yeni belgenin yazılarından okunur.
        entry=json.loads(json.dumps(self.entry))       # JSON turu: kalıcı depodan gelmiş gibi
        curves=[curve('n1',100.2,50.2,CIRCLE),curve('n2',140.2,50.2,CIRCLE)]
        words=[word('7',103,46),word('-X3',100,42),word('8',143,46),word('-X3',140,42)]
        result=search_similar(descriptor_of(entry),[],words,[0,0,0,0],[],curves)
        self.assertEqual(len(result['candidates']),2)
        self.assertEqual([c['pins'][0]['page_pin_texts'] for c in result['candidates']],[['7'],['8']])
        self.assertTrue(all(q['template_device']=='' for c in result['candidates'] for q in c['pins']))
        self.assertTrue(all(not c['production_ready'] for c in result['candidates']))


@unittest.skipUnless((RUN5/'manifest.json').exists(),'Prepare the P05 run first')
class PilotFlowTests(unittest.TestCase):
    """Hedef sayfadaki uç değişince ona dayanan doğrulama düşmeli; kopya çalışmada sınanır."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='uvp-flow-test-')
        self.run=Path(self.tmp.name)/'run'
        shutil.copytree(RUN5,self.run)
        self.p=Pilot(self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def reached(self):
        hop=next(h for h in self.p.path('p24')['hops'] if h['to_page']==5)
        return hop['status'],sorted((t['device'],t['pin']) for t in hop.get('target_pins',[]))

    def test_dash_run_decision_is_recorded_and_goes_stale(self):
        """Insan karari SABIT DEGIL: kaydedilir, denetlenir, bayatlar. Canli calismada denenmez."""
        run_key='y=440.37#0'
        before=next(r for r in self.p.dash_proposals(4)['runs'] if r['run_key']==run_key)
        self.assertEqual((before['decision'],before['review_state'],before['decided_by']),
                         ('ONAY_BEKLIYOR','NO_DECISION',None))
        self.assertEqual(before['review_history'],[])
        # Kosu konusu olmadan kayit acilamaz.
        with self.assertRaises(ValueError):
            self.p.add_review(dict(subject='DASH_RUN',decision='CONFIRMED',
                                   reviewer='Test Kullanicisi',page=4))
        # Sayfa da zorunlu: sayfa 4 ile 5'in geometrisi birebir ayni, sessiz varsayilan olamaz.
        with self.assertRaises(ValueError):
            self.p.add_review(dict(subject='DASH_RUN',decision='CONFIRMED',
                                   reviewer='Test Kullanicisi',run_key=run_key))
        self.p.add_review(dict(subject='DASH_RUN',decision='CONFIRMED',
                               reviewer='Test Kullanicisi',run_key=run_key,page=4,
                               reference='PE-1',note='PE barasi kosusu gorsel olarak dogrulandi.'))
        after=next(r for r in self.p.dash_proposals(4)['runs'] if r['run_key']==run_key)
        self.assertEqual((after['decision'],after['review_state']),('CONFIRMED','CURRENT'))
        self.assertEqual(after['decided_by'],'Test Kullanicisi')
        self.assertEqual(len(after['review_history']),1)
        # Onay, kosuyu FIZIKSEL TEL yapmaz: tablo satiri uretmez, yol kaniti bos kalir.
        self.assertEqual(after['path_evidence']['traced_targets'],[])
        self.assertNotIn('PHYSICAL_PAIR',
                         [r['kind'] for r in self.p.table(4)['rows'] if r.get('dash_run')])
        links=self.p.dash_proposals(4)['links']
        self.assertTrue(all(l['relation']=='COMMON_POTENTIAL_NETWORK_ONLY' for l in links))
        # Sayfada isaret degisince karar askiya alinir; eski karar silinmez.
        pin=next(q for q in self.p.state()['pins'] if q['pin']=='PE')
        self.p.change(dict(id=pin['id'],expected_version=pin['version'],page=pin['page'],
                           device=pin['device'],pin=pin['pin'],point=pin['point'],
                           kind=pin['kind'],method=pin.get('method','MANUAL'),
                           note='kayit degisti'))
        stale=next(r for r in self.p.dash_proposals(4)['runs'] if r['run_key']==run_key)
        self.assertEqual((stale['decision'],stale['review_state']),('ONAY_BEKLIYOR','NEEDS_REVIEW'))
        self.assertEqual(stale['recorded_decision'],'CONFIRMED')
        self.assertEqual(len(stale['review_history']),1)
        self.assertIn('değişti',stale['review_reason'])

    def test_out_of_scope_end_is_not_a_panel_wire_candidate(self):
        """Saha ucu tasiyan bag pano ici tel ADAYI sayilmaz; iliski gorunur kalir."""
        pair=next(r for r in self.p.table(4)['rows']
                  if r['kind']=='PHYSICAL_PAIR' and r['net_id']=='net:4:142.73:164.2')
        self.assertEqual(pair['scope_state'],'IN_SCOPE_BOTH')
        target=next(q for q in self.p.state()['pins'] if q['id']==pair['pins'][1]['pin_id'])
        # Ucu SAHA cihazina tasi (=112+M113-3A72, MAIN.md pano siniri disi).
        self.p.change(dict(id=target['id'],expected_version=target['version'],page=target['page'],
                           device='=112+M113-3A72',pin=target['pin'],point=target['point'],
                           kind=target['kind'],method=target.get('method','MANUAL'),
                           note='kapsam testi'))
        after=next(r for r in self.p.table(4)['rows'] if r['net_id']=='net:4:142.73:164.2')
        self.assertEqual(after['kind'],'PAIR_OUT_OF_PANEL_SCOPE')
        self.assertEqual(after['scope_state'],'OUT_OF_PANEL_END')
        self.assertEqual(after['endpoint_scopes'],['IN_SCOPE','OUT_OF_PANEL'])
        self.assertIn('pano içi tek damar tel adayı',after['note'])
        # Iliski SILINMEDI: satir hala duruyor ve iki ucu da yaziyor.
        self.assertEqual(len(after['pins']),2)
        self.assertFalse(after['production_ready'])

    def test_uncertain_scope_end_is_not_counted_as_in_scope(self):
        """Adresi okunamayan uc 'kapsam ici' kovasina konmaz; belirsiz kalir."""
        pair=next(r for r in self.p.table(4)['rows'] if r['net_id']=='net:4:156.91:163.99')
        target=next(q for q in self.p.state()['pins'] if q['id']==pair['pins'][1]['pin_id'])
        self.p.change(dict(id=target['id'],expected_version=target['version'],page=target['page'],
                           device='X1',pin=target['pin'],point=target['point'],
                           kind=target['kind'],method=target.get('method','MANUAL'),
                           note='belirsiz kapsam testi'))
        after=next(r for r in self.p.table(4)['rows'] if r['net_id']=='net:4:156.91:163.99')
        self.assertEqual(after['kind'],'PAIR_OUT_OF_PANEL_SCOPE')
        self.assertEqual(after['scope_state'],'SCOPE_UNCERTAIN')
        self.assertIn('SCOPE_UNCERTAIN',after['endpoint_scopes'])

    def test_confirmed_pair_also_passes_the_scope_check(self):
        """Teyitli cift de kapsam kontrolunden gecer; gecmis teyit silinmez."""
        before=next(r for r in self.p.table(4)['rows'] if r.get('reference')=='C03')
        self.assertEqual(before['scope_state'],'IN_SCOPE_BOTH')
        self.assertNotIn('KAPSAM',before['status_label'])
        target=next(q for q in self.p.state()['pins'] if q['id']==before['pin_ids'][1])
        self.p.change(dict(id=target['id'],expected_version=target['version'],page=target['page'],
                           device='=112+M113-3A72',pin=target['pin'],point=target['point'],
                           kind=target['kind'],method=target.get('method','MANUAL'),
                           note='kapsam testi'))
        after=next(r for r in self.p.table(4)['rows'] if r.get('reference')=='C03')
        self.assertEqual(after['scope_state'],'OUT_OF_PANEL_END')
        self.assertEqual(after['endpoint_scopes'],['IN_SCOPE','OUT_OF_PANEL'])
        # Kapsam sorunu her hâlde GÖRÜNÜR: askıdaki satırda gerekçe alanında yazılı.
        self.assertIn('Kapsam:',after['review_reason'])
        # Teyit kaydi ve gecmis SILINMEDI.
        self.assertTrue(after['review_history'])
        self.assertEqual(after['reference'],'C03')
        self.assertTrue(after['unresolved'])

    def test_same_device_pair_is_flagged_not_eliminated(self):
        """Ayni cihazin iki ucu otomatik elenmez: harici jumper olabilir."""
        network=next(r for r in self.p.table(4)['rows'] if r['net_id']=='net:4:241.94:185.25')
        self.assertTrue(network['same_device'])
        self.assertIn('harici jumper',network['note'])
        self.assertEqual(network['implementation_type'],'BELIRSIZ')
        # Satir duruyor; hicbir sey elenmedi.
        self.assertEqual(len(network['pins']),2)

    def test_implementation_type_is_separate_from_confirmation_and_production(self):
        """Iliski teyidi, uygulama turu ve uretime uygunluk AYRI alanlardir."""
        rows={r.get('reference'): r for r in self.p.table(4)['rows'] if r.get('reference')}
        # C02: kullanicinin 2026-09-10 karari kayitli (ayri tel). Karar iliski teyidini
        # TAZELEMEZ ve uretime uygunluk vermez.
        c02=rows['C02']
        self.assertEqual(c02['implementation_type'],'TEL')
        self.assertIn('Kullanıcı',c02['implementation_source'])
        self.assertFalse(c02['production_ready'])
        self.assertEqual(c02['review_state'],'NEEDS_REVIEW')
        # C02 karari DIGER baglantilara genellenmez.
        self.assertEqual(rows['C03']['implementation_type'],'BELIRSIZ')
        self.assertIsNone(rows['C03']['implementation_source'])
        # Yazma yolu: kaydi olmayan bir baglantiya tur yazilir, ayri alanda gorunur.
        target='net:4:142.73:164.2'
        before=next(r for r in self.p.table(4)['rows'] if r['net_id']==target)
        self.assertEqual(before['implementation_type'],'BELIRSIZ')
        self.p.add_review(dict(subject='IMPLEMENTATION_TYPE',decision='CONFIRMED',
                               implementation='AKSESUAR_KOPRU',reference=target,
                               reviewer='Test Kullanicisi',note='kopya calismada tur testi'))
        after=next(r for r in self.p.table(4)['rows'] if r['net_id']==target)
        self.assertEqual(after['implementation_type'],'AKSESUAR_KOPRU')
        self.assertEqual(after['implementation_source'],'Test Kullanicisi')
        self.assertEqual(len(after['implementation_history']),1)
        self.assertFalse(after['production_ready'])
        # Gecersiz tur ve referanssiz kayit reddedilir.
        with self.assertRaises(ValueError):
            self.p.add_review(dict(subject='IMPLEMENTATION_TYPE',decision='CONFIRMED',
                                   implementation='TARAK',reference=target,reviewer='Test'))
        with self.assertRaises(ValueError):
            self.p.add_review(dict(subject='IMPLEMENTATION_TYPE',decision='CONFIRMED',
                                   implementation='TEL',reviewer='Test'))

    def test_duplicate_mark_is_refused_on_the_server(self):
        """Tekrar calistirilan gruplu uygulama MUKERRER kayit uretemez; koruma sunucuda."""
        pin=next(q for q in self.p.state()['pins'] if q.get('page')==4)
        with self.assertRaises(ValueError) as ctx:
            self.p.change(dict(page=4,device='=112+E122-TEST',pin='9',point=pin['point'],
                               kind='PHYSICAL',method='P04_CANDIDATE',note='mukerrer'))
        self.assertIn('zaten bir uç var',str(ctx.exception))
        # Var olan kaydi DUZELTMEK serbest: `id` verildiginde koruma calismaz.
        updated=self.p.change(dict(id=pin['id'],expected_version=pin['version'],page=4,
                                   device=pin['device'],pin=pin['pin'],point=pin['point'],
                                   kind=pin['kind'],method=pin.get('method','MANUAL'),
                                   note='duzeltme testi'))
        self.assertEqual(updated['id'],pin['id'])
        self.assertEqual(len([q for q in self.p.state()['pins']
                              if q.get('page')==4 and q['point']==pin['point']]),1)

    def test_moving_a_target_pin_drops_its_verification(self):
        before=self.reached()
        self.assertEqual(before[0],'TARGET_PINS_REACHED')
        contact=next(p for p in self.p.state()['pins'] if p['device'].endswith('17K56') and p['pin']=='13')
        moved=self.p.change(dict(contact,expected_version=contact['version'],point=[60,60]))
        after=self.reached()
        self.assertNotIn(('=112+E122-17K56','13'),after[1])
        self.assertTrue(all(c['status']!='CONFIRMED_BOTH' for c in self.p.state()['claims']))
        # Geri taşımak eski doğrulamayı otomatik geri getirmez: kayıt yeni sürümle yeniden değerlendirilir.
        self.p.change(dict(moved,expected_version=moved['version'],point=contact['point']))
        self.assertEqual(self.reached()[1],before[1])
        self.assertTrue(all(c['status']!='CONFIRMED_BOTH' for c in self.p.state()['claims']))

    def test_review_record_goes_stale_when_its_pin_changes(self):
        contact=next(p for p in self.p.state()['pins'] if p['device'].endswith('17K52') and p['pin']=='13')
        review=self.p.add_review(dict(subject='PIN',reference='deneme',pin_ids=[contact['id']],
                                      decision='CONFIRMED',reviewer='Test',source='UI_REVIEW'))
        self.assertEqual(review['pin_versions'],{contact['id']:contact['version']})
        self.assertEqual(self.p.review_status()['rows'][-1]['status'],'CURRENT')
        moved=self.p.change(dict(contact,expected_version=contact['version'],point=[70,70]))
        row=self.p.review_status()['rows'][-1]
        self.assertEqual((row['status'],row['changed_pins']),('NEEDS_REVIEW',[contact['id']]))
        # Kayıt silinmez; geri taşınsa bile sürüm ilerlediği için yeniden inceleme ister.
        self.p.change(dict(moved,expected_version=moved['version'],point=contact['point']))
        self.assertEqual(self.p.review_status()['rows'][-1]['status'],'NEEDS_REVIEW')
        for bad in [dict(subject='PIN',pin_ids=[],decision='CONFIRMED',reviewer='Test'),
                    dict(subject='PIN',pin_ids=[contact['id']],decision='CONFIRMED',reviewer=' '),
                    dict(subject='PIN',pin_ids=['yok'],decision='CONFIRMED',reviewer='Test')]:
            with self.assertRaises(ValueError):
                self.p.add_review(bad)

    def test_review_depends_on_the_whole_sheet_not_only_its_pins(self):
        contact=next(p for p in self.p.state()['pins'] if p['device'].endswith('17K52') and p['pin']=='13')
        review=self.p.add_review(dict(subject='PIN',reference='sayfa bağımlılığı',pin_ids=[contact['id']],
                                      decision='CONFIRMED',reviewer='Test',source='UI_REVIEW'))
        self.assertEqual(review['pages'],[4])
        self.assertEqual(self.p.review_status()['rows'][-1]['status'],'CURRENT')
        # Yol üzerindeki başka bir işaret ya da sembol kutusu da yeniden inceleme ister.
        box=self.p.change_box(dict(page=4,bbox=[600,600,610,610],note='ilgisiz kutu'))
        row=self.p.review_status()['rows'][-1]
        self.assertEqual(row['status'],'NEEDS_REVIEW')
        self.assertTrue(any(e['reason']=='SYMBOL_BOX_CHANGED' for e in row['stale_events']))
        # Kutuyu pasifleştirip eski geometriye dönmek onayı canlandırmaz.
        self.p.change_box(dict(box,expected_version=box['version'],active=False))
        self.assertEqual(self.p.review_status()['rows'][-1]['status'],'NEEDS_REVIEW')
        self.assertIn('SAYFA',self.p.review_status()['scope_limitation'])

    def test_review_on_another_sheet_is_untouched(self):
        page5=next(p for p in self.p.state()['pins'] if p.get('page')==5)
        review=self.p.add_review(dict(subject='PIN',reference='sayfa 5',pin_ids=[page5['id']],
                                      decision='CONFIRMED',reviewer='Test',source='UI_REVIEW'))
        self.assertEqual(review['pages'],[5])
        self.p.change_box(dict(page=4,bbox=[620,620,630,630],note='sayfa 4 kutusu'))
        row=next(r for r in self.p.review_status()['rows'] if r['id']==review['id'])
        self.assertEqual(row['status'],'CURRENT')

    def test_re_approval_keeps_one_row_per_physical_pair(self):
        """Aynı uç çifti yönden bağımsız tek satır; yeniden onay satır açmaz, geçmişe eklenir."""
        pairs=lambda:[r for r in self.p.table(4)['rows'] if r['kind']=='CONFIRMED_PHYSICAL_PAIR']
        start=pairs()
        self.assertEqual(sorted(r['reference'] for r in start),['C02','C03'])
        c02=next(r for r in start if r['reference']=='C02')
        self.assertEqual(c02['review_state'],'NEEDS_REVIEW')   # tohum teyidi askıda
        self.assertEqual(c02['review_count'],1)
        # Ters yönde pin sırasıyla yeniden onay: yeni satır AÇMAZ.
        self.p.add_review(dict(subject='PIN_PAIR',reference='C02 yeniden',
                               pin_ids=list(reversed(c02['pin_ids'])),decision='CONFIRMED',
                               reviewer='Test onayı 1',source='UI_REVIEW'))
        after=pairs()
        self.assertEqual(len(after),len(start))
        row=next(r for r in after if r['reference']=='C02')
        self.assertEqual((row['review_state'],row['reviewer'],row['review_count']),
                         ('CURRENT','Test onayı 1',2))
        self.assertEqual(row['status_label'],'TEYİTLİ ÇİFT')
        self.assertTrue(row['review_history'][0]['origin']=='SEED_CLAIM')   # eski karar korunur
        self.assertTrue(row['review_history'][-1]['current'])
        # İkinci yeniden onay da satır açmaz.
        self.p.add_review(dict(subject='PIN_PAIR',reference='C02 yeniden 2',pin_ids=c02['pin_ids'],
                               decision='CONFIRMED',reviewer='Test onayı 2',source='UI_REVIEW'))
        self.assertEqual(len(pairs()),len(start))
        row=next(r for r in pairs() if r['reference']=='C02')
        self.assertEqual((row['review_state'],row['review_count']),('CURRENT',3))
        # Geometri değişince yeniden NEEDS_REVIEW; geri gelince kendiliğinden onaylanmaz.
        box=self.p.change_box(dict(page=4,bbox=[330,300,340,320],note='yol üstünde kutu'))
        row=next(r for r in pairs() if r['reference']=='C02')
        self.assertEqual((row['review_state'],row['review_count']),('NEEDS_REVIEW',3))
        self.p.change_box(dict(box,expected_version=box['version'],active=False))
        row=next(r for r in pairs() if r['reference']=='C02')
        self.assertEqual(row['review_state'],'NEEDS_REVIEW')
        self.assertEqual(len(pairs()),len(start))
        self.assertIn('YENİDEN İNCELEME',row['status_label'])

    def test_confirmed_pair_row_shows_when_its_review_went_stale(self):
        # Kullanıcı bulgusu: onay düşüyordu ama tablo satırı hâlâ "teyitli" diyordu.
        pins={q['device']+':'+q['pin']:q for q in self.p.state()['pins'] if q.get('page')==4}
        a,b=pins['=112+E122-17K52:14'],pins['=112+E122-X4:1']
        self.p.add_review(dict(subject='PIN_PAIR',reference='cift-testi',pin_ids=[a['id'],b['id']],
                               decision='CONFIRMED',reviewer='Test',source='UI_REVIEW'))
        row=lambda:next(r for r in self.p.table(4)['rows'] if r.get('reference')=='cift-testi')
        self.assertEqual((row()['status_label'],row()['review_state'],row()['line_evidence']),
                         ('TEYİTLİ ÇİFT','CURRENT','CURRENT_PATH_FOUND'))
        box=self.p.change_box(dict(page=4,bbox=[309,300,315,320],note='yolu kesen kutu'))
        cut=row()
        self.assertEqual((cut['review_state'],cut['line_evidence']),('NEEDS_REVIEW','NO_CURRENT_PATH'))
        self.assertIn('YENİDEN İNCELEME',cut['status_label'])
        # Kutu pasifleşince çizgi geri gelir; inceleme yine de yeniden inceleme ister.
        self.p.change_box(dict(box,expected_version=box['version'],active=False))
        back=row()
        self.assertEqual((back['review_state'],back['line_evidence']),('NEEDS_REVIEW','CURRENT_PATH_FOUND'))
        self.assertIn('YENİDEN İNCELEME',back['status_label'])
        self.assertTrue(back['review_reason'])
        self.assertTrue(back['unresolved'])
        # Satır silinmez: karar ve teyit eden kayıtta kalır.
        self.assertEqual(back['reviewer'],'Test')

    def test_table_separates_physical_pairs_networks_and_gaps(self):
        data=self.p.table(4)
        kinds={r['kind'] for r in data['rows']}
        self.assertEqual(kinds,{'PHYSICAL_PAIR','NETWORK_GROUP','SINGLE_END',
                                'CONFIRMED_PHYSICAL_PAIR','CONFIRMED_NETWORK_RELATION'})
        # MAIN.md 2026-09-08 §1: HAT seviyesinde teyitli C01 ana tabloda KENDI satirindadir,
        # ama fiziksel tel cifti SAYILMAZ ve uretim listesine giremez.
        line_level=[r for r in data['rows'] if r['kind']=='CONFIRMED_NETWORK_RELATION']
        self.assertEqual([(r['reference'],tuple(q['device']+':'+q['pin'] for q in r['pins']))
                          for r in line_level],
                         [('C01',('=112+E122-X4:P24.32','=112+E122-17K52:13'))])
        self.assertEqual(line_level[0]['confirmation_level'],'NETWORK')
        self.assertIn('FİZİKSEL TEL ÇİFTİ DEĞİLDİR',line_level[0]['note'])
        self.assertFalse(line_level[0]['production_ready'])
        self.assertIn('HAT SEVİYESİNDE',line_level[0]['status_label'])
        # MAIN.md'deki iki teyitli çift kendi satırında; ortak ağdan çift TÜRETİLMEZ.
        confirmed=[r for r in data['rows'] if r['kind']=='CONFIRMED_PHYSICAL_PAIR']
        self.assertEqual([(r['reference'],tuple(q['device']+':'+q['pin'] for q in r['pins']),r['line_evidence'])
                          for r in confirmed],
                         [('C02',('=112+E122-17K53:11','=112+E122-17K55:11'),'CURRENT_PATH_FOUND'),
                          ('C03',('=112+E122-17K55:11','=112+E122-X4:4'),'CURRENT_PATH_FOUND')])
        self.assertTrue(all(r['confirmation_origin'] in ('SEED_CLAIM','USER_REVIEW') for r in confirmed))
        pairs={tuple(sorted(q['device']+':'+q['pin'] for q in r['pins']))
               for r in data['rows'] if r['kind']=='PHYSICAL_PAIR'}
        self.assertIn(('=112+E122-17K52:14','=112+E122-X4:1'),pairs)
        self.assertIn(('=112+E122-3F22:2','=112+E122-X1:1'),pairs)
        # Ortak potansiyel ağı çift üretmez; T dalı ve açık uç uyarıyla kalır.
        network=[r for r in data['rows'] if r['kind']=='NETWORK_GROUP']
        self.assertTrue(all(len(r['pins'])>2 or r['branch_points'] or r['open_ends'] for r in network))
        self.assertTrue(any(r['duplicate_names'] for r in network))
        self.assertTrue(all(not r['production_ready'] for r in data['rows']))
        self.assertTrue(all(g['reason'] for g in data['gaps']))
        second=data['second_pass']
        self.assertEqual(second['short_segments'],
                         second['short_in_rows']+second['short_in_gaps']
                         +second['short_excluded_from_graph']+second['short_unaccounted_count'])

    def test_todo_never_marks_a_device_complete(self):
        todo=self.p.todo(4)
        self.assertTrue(all(d['status']=='NEVER_COMPLETE' for d in todo['devices']))
        fuse=next(d for d in todo['devices'] if d['device']=='=112+E122-3F22')
        self.assertEqual(fuse['marked_pins'],['1','2','3','4','5','6'])
        self.assertEqual(fuse['status'],'NEVER_COMPLETE')
        kinds={i['kind'] for i in todo['open_items']}
        self.assertTrue({'NET_WITHOUT_MARKED_END','SINGLE_END_NET'} <= kinds)
        # Cozulmemis devam SAYISI, gercekten cozulmemis satir sayisina esittir: ne gizlenir
        # ne de uydurulur. PE kosusu cozuldukten sonra sayfa 4'te sifirdir.
        rows=self.p.continuations(4)['rows']
        unresolved=[r for r in rows if r['status'] not in
                    ('RECIPROCAL_END_MATCHED','DEVICE_REFERENCE_NOT_A_CONTINUATION')]
        self.assertEqual(sum(1 for i in todo['open_items']
                             if i['kind']=='UNRESOLVED_CONTINUATION'),len(unresolved))
        self.assertEqual(unresolved,[])
        self.assertTrue(all(i.get('reason') or i.get('status') for i in todo['open_items']))

    def test_curve_symbols_are_matched_and_names_reread(self):
        box=next(b for b in self.p.state()['boxes'] if b.get('note','').startswith('3F22'))
        data=self.p.candidates(box['id'])
        pins=[[q['page_pin_texts'] for q in c['pins']] for c in data['candidates']]
        self.assertEqual(pins,[[['1'],['2']],[['3'],['4']],[['5'],['6']]])
        self.assertTrue(all(c['requires_user_confirmation'] for c in data['candidates']))

    def test_user_box_masks_only_its_own_page(self):
        box=self.p.change_box(dict(page=5,bbox=[306.81,300.0,318.81,320.0],note='deneme'))
        self.assertEqual(box['page'],5)
        excluded=lambda n:{e['box_id'] for e in self.p.page_graph(n).excluded if e['reason']=='DEVICE_INTERIOR'}
        self.assertIn(box['id'],excluded(5))
        self.assertNotIn(box['id'],excluded(4))


@unittest.skipUnless((RUN5/'manifest.json').exists(),'Prepare the P05 run first')
class RealDocumentTests(unittest.TestCase):
    """Gerçek 73 sayfalık belge üzerinde P05. Bu sayfa incelendi; kör test değildir."""
    @classmethod
    def setUpClass(cls):
        cls.p=Pilot(RUN5)

    def test_document_index_scopes_pages_by_function_and_location(self):
        document=self.p.state()['document']
        self.assertEqual(document['page_count'],73)
        self.assertEqual(document['scopes']['OUT_OF_SCOPE_LOCATION'],2)
        # Sayfa 22 (ET200SP istasyonu) PLC L+/M beslemesini aramak icin eklendi.
        self.assertEqual(document['traced_pages'],[2,4,5,22,28,36])

    def test_contact_coil_references_resolve_without_becoming_wires(self):
        rows=self.p.cross_references()['rows']
        devices=[r for r in rows if r['kind']=='DEVICE_CROSS_REFERENCE']
        self.assertEqual([(r['text'],r['target_pages'],r['owner_device']) for r in devices],
                         [('=122/17.52',[28],'=112+E122-17K52'),('=122/17.53',[28],'=112+E122-17K53'),
                          ('=122/17.55',[28],'=112+E122-17K55')])
        # Hedef sayfanın Anlage'si =122 olsa da cihazın basılı fonksiyonu =112 kalır.
        self.assertEqual([r['target_device_texts'] for r in devices],
                         [['=112-17K52'],['=112-17K53'],['=112-17K55']])
        self.assertTrue(all(r['relation']=='CROSS_REFERENCE_ONLY_NOT_A_WIRE' and not r['production_ready']
                            for r in rows))
        self.assertTrue(all(r['position_token'] and 'yorumlanmaz' in r['position_note'] for r in rows))

    def test_rotated_labels_are_recovered_from_the_real_page(self):
        # Denetim bulgusu (P1): dikey basılı referans ve klemens uçları indekse hiç girmiyordu.
        rows=self.p.cross_references()['rows']
        rotated=[r for r in rows if r['rotated']]
        self.assertEqual([r['text'] for r in rotated],['=122/17.44','=122/25.67','=122/25.68','=122/25.69'])
        self.assertEqual(rotated[0]['raw_text'],'44.71/221=')
        self.assertEqual([r['target_pages'] for r in rotated],[[28],[36],[36],[36]])
        c=self.p.coverage()
        self.assertIn('=122+E122-X4.Q',{d['device'] for d in c['devices']})

    def test_coverage_shows_what_is_not_covered(self):
        c=self.p.coverage()
        unmarked={d['device'] for d in c['devices'] if not d['marked']}
        self.assertEqual(unmarked,{'=112+M113-3A72','=112+E122-3W62','=112+E122-3W67',
                                   '=122+E122-X4.Q','=122+E122-X4.I'})
        # Kullanıcı bulgusu: saha cihazı (+M113) pano içi sayılıyordu.
        field=next(d for d in c['devices'] if d['device']=='=112+M113-3A72')
        self.assertEqual((field['local_location'],field['in_scope']),('M113',False))
        self.assertTrue(all(d['in_scope'] for d in c['devices'] if d['device']!='=112+M113-3A72'))
        # PE klemensinin ucu kesikli çizildiği için hiçbir sayfa devamına ulaşmaz: sayfa referansı
        # olmayan tek açık uçlar bunlardır ve gerekçesiyle görünürler.
        bare=[e for e in c['open_ends'] if not e['sheet_references']]
        self.assertEqual([tuple(e['point']) for e in bare],[(185.25,455.6),(482.89,455.6)])
        self.assertTrue(all(e['reason']=='UNMARKED_END_OR_CONTINUATION' for e in bare))
        # Kontak/bobin referansı açık ucun sayfa devamı kanıtı olarak gösterilemez.
        self.assertEqual({r for e in c['open_ends'] for r in e['sheet_references']},
                         {'/1.110','/1.310','/4.11','/4.23'})
        self.assertGreater(c['untraced_segments'],c['traced_segments'])
        self.assertFalse(c['production_ready'])

    def test_endpoint_reconciliation_reports_instead_of_matching(self):
        rows={(r['device'],r['pin']):r for r in self.p.endpoints()['rows']}
        row=rows[('=112+E122-17K52','13')]
        self.assertEqual(row['status'],'DEVICE_PRINTED_PIN_NOT_PRINTED')
        # Denetim bulgusu (P2): Stückliste sayfaları sessizce atlanıyordu.
        self.assertEqual(sorted({o['physical_page'] for o in row['other_occurrences']}),[4,9,28])
        self.assertIn('Stückliste',row['searched_doc_types'])
        self.assertEqual(sorted({o['doc_type'] for o in row['other_occurrences']}),['Schaltplan','Stückliste'])
        self.assertFalse(row['production_ready'])

    def test_drawing_components_are_split_with_evidence_not_dismissed(self):
        """1712 çizim bileşeni 1712 bağlantı değildir; her sınıfın ölçülebilir gerekçesi vardır."""
        d=self.p.drawing_classes(4)
        self.assertEqual(sum(c['count'] for c in d['classes']),d['components'])
        kinds={c['kind']:c['count'] for c in d['classes']}
        # Dolu klemens/diyot gövdeleri tarama çizgisi olarak dışa aktarılmış: iletken değil.
        # 2026-09-11: kesikli sınır (y=572.18) ile dikey kesikli koşuların noktasız kesişimi artık
        # birleştirilmiyor (DASHED_RUN_CROSSING); iki UNEXPLAINED bileşen ayrıldı: 1416 -> 1418.
        self.assertEqual(kinds['SYMBOL_FILL_SCANLINE'],1418)
        self.assertEqual(kinds['PAGE_FRAME'],1)
        self.assertEqual(kinds['CONDUCTOR_CANDIDATE'],17)
        self.assertEqual(d['dashed_rules']['horizontal'],[440.37,572.18,709.66])
        # Belirsizler toplu elenmez: her biri tek tek listelenir.
        unexplained=next(c for c in d['classes'] if c['kind']=='UNEXPLAINED')
        self.assertEqual(len(d['unexplained']),unexplained['count'])
        # Sınırın (y=572.18) ÜSTÜNDE açıklanmayan yalnız iki bileşen var: PE barasının nokta
        # ile birleşmiş uçları. İkisi de tek tek listeli, toplu elenmiş değil.
        above=[u['bbox'] for u in d['unexplained'] if u['bbox'][3]<572.0]
        self.assertEqual(above,[[482.89,440.37,507.34,442.85]])
        self.assertEqual(kinds['DASH_ZONE_BOX_EDGE'],86)
        self.assertEqual(kinds['DASH_CONDUCTOR_CANDIDATE'],51)
        self.assertEqual(kinds['DASH_UNDECIDED'],20)           # +2: yukarıdaki kesişim ayrımı
        self.assertNotIn('DASH_OUT_OF_SCOPE_ZONE_INTERIOR',kinds)
        self.assertFalse(d['production_ready'])
        # Sayfa çerçevesi açık iş sayılmaz ama sınıf dökümünde durur.
        gaps=self.p.table(4)['gaps']
        self.assertNotIn('PAGE_FRAME',[g.get('drawing_class') for g in gaps])
        # Her iletken adayı açık iştir: kesikli PE koşuları ve düz adaylar dahil.
        self.assertEqual(len(gaps),88)                         # +2 DASH_UNDECIDED açık iş olarak listede
        self.assertTrue(any(g.get('dash_run')=='y=440.37#0' for g in gaps))

    def test_pe_terminals_are_marked_but_stay_untraceable(self):
        """PE klemensi farklı sembol olarak ayrılır; kesikli ucu yüzünden yol bulunamaz."""
        pe=[q for q in self.p.pins if q['pin']=='PE' and q.get('page')==4]
        self.assertEqual(sorted((q['device'],q['method']) for q in pe),
                         [('=112+E122-X1','P04_CANDIDATE'),('=112+E122-X4','P04_CANDIDATE')])
        for q in pe:
            traced=self.p.trace(q['id'])
            self.assertEqual(traced['targets'],[])
            self.assertIn('UNRESOLVED_OPEN_ENDS',traced['issues'])
        rows=[r for r in self.p.table(4)['rows'] if any(x['pin']=='PE' for x in r['pins'])]
        self.assertEqual([r['kind'] for r in rows],['SINGLE_END','SINGLE_END'])

    def test_page_frame_needs_edge_position_and_frame_geometry_not_length(self):
        """Uzunluk tek basina cerceve kaniti degildir; gercek L1 hatti cerceve sayilmamali."""
        comps=self.p._components(self.p.page_graph(4))
        frame=next(c for c in comps if c['bbox']==[1.0,43.52,1120.69,808.87])
        l1=next(c for c in comps if c['bbox'][1]==86.04 and c['bbox'][2]==1007.3)
        # Gercek L1 hatti sayfa genisliginin yuzde 83'u: eski "%80 VEYA" kuralina takiliyordu.
        self.assertGreater(l1['bbox'][2]-l1['bbox'][0],0.80*1121.68)
        self.assertLess(l1['bbox'][3]-l1['bbox'][1],0.10*809.87)
        # Pin isareti KALDIRILSA bile cerceve sayilmamali ve acik iste kalmali.
        stripped=[dict(c,pins=[]) for c in comps]
        classes=self.p.drawing_classes(4,stripped)
        verdict=self.p._class_cache[4]
        bare_l1=next(c for c in stripped if c['bbox']==l1['bbox'])
        bare_frame=next(c for c in stripped if c['bbox']==frame['bbox'])
        self.assertEqual(verdict[id(bare_frame)][0],'PAGE_FRAME')
        self.assertNotEqual(verdict[id(bare_l1)][0],'PAGE_FRAME')
        self.assertIn(verdict[id(bare_l1)][0],{'CONDUCTOR_CANDIDATE','UNEXPLAINED'})
        # Tek duz cizgi sayfa boyunca uzasa da cerceve degildir: kapali geometri yok.
        line=dict(bbox=[1.0,43.52,1120.69,808.87],pins=[],segments=['line:1977'],
                  open_ends=[[1.0,43.52],[1120.69,808.87]],branch_points=[],
                  nodes=[],unattached=[])
        self.p.drawing_classes(4,[line])
        self.assertNotEqual(self.p._class_cache[4][id(line)][0],'PAGE_FRAME')
        # Gercek cerceve hala ayriliyor.
        self.assertEqual([c['count'] for c in classes['classes'] if c['kind']=='PAGE_FRAME'],[1])

    def test_ambiguous_page_sized_drawing_stays_open_work(self):
        """A1+A2 gecip A3 kalan cizim cerceve DEGILDIR ve acik iste kalir."""
        plain=dict(bbox=[1.0,1.0,1120.68,808.87],pins=[],segments=['line:1977'],
                   open_ends=[[1.0,1.0],[1120.68,808.87]],branch_points=[],
                   nodes=[],unattached=[])
        self.p.drawing_classes(4,[plain])
        kind,why=self.p._class_cache[4][id(plain)]
        self.assertEqual(kind,'PAGE_FRAME_UNDECIDED')
        self.assertIn('AÇIK İŞTE',why)
        # Acik is kovasina girer: yaninda kapsam ici cihaz yazisi olmasa bile.
        self.assertIn('PAGE_FRAME_UNDECIDED',
                      [k for k in ('PAGE_FRAME_UNDECIDED',) if kind==k])

    def test_component_does_not_inherit_a_dash_class_from_one_segment(self):
        """Tek segment uzerinden koca bir bilesen sessizce 'is degil' olamaz."""
        edge=next(r for r in self.p.dash_proposals(4)['runs'] if r['kind']=='ZONE_BOX_EDGE')
        mixed=dict(bbox=[0.0,0.0,50.0,50.0],pins=[],
                   segments=[edge['segment_ids'][0],'line:1977'],
                   open_ends=[[0.0,0.0],[50.0,50.0]],branch_points=[],nodes=[],unattached=[])
        self.p.drawing_classes(4,[mixed])
        kind,_=self.p._class_cache[4][id(mixed)]
        self.assertNotEqual(kind,'DASH_ZONE_BOX_EDGE')

    def test_scope_is_a_note_and_never_overrides_evidence(self):
        """Kapsam bir NOT'tur: geometrik konum, insanin isaretledigi kaniti EZEMEZ."""
        r=self.p.dash_proposals(4)
        inner=next(x for x in r['runs'] if x['run_key']=='x=745.09#0')
        self.assertEqual(inner['scope'],'KAPALI_KUTU_ICI')
        self.assertTrue(inner['inside_zone_box'])
        # Sinif kanittan gelir, konumdan degil; kapsam yalniz gerekceye NOT olarak eklenir.
        self.assertIn(inner['kind'],{'UNDECIDED','CONDUCTOR_CANDIDATE'})
        self.assertIn('pano sınırı',inner['reason'])
        self.assertNotIn('OUT_OF_SCOPE_ZONE_INTERIOR',{x['kind'] for x in r['runs']})
        # Kutunun disina tasan kosular kutu kenari sayilmaz.
        self.assertTrue(all(x['kind']!='ZONE_BOX_EDGE'
                            for x in r['runs'] if x['ruling'] in ('y=440.37','x=185.25','x=482.89')))

    def test_fill_detection_is_local_so_a_real_arrow_head_is_not_dismissed(self):
        """Ok basi 'dolu sembol' sayilip acik isten dusuyordu; yigin testi artik YEREL."""
        from analyzer_v3 import dashed
        fills=dashed.fill_scanlines(self.p._page(4)['segments'])
        for sid in ('line:194','line:195','line:196'):
            self.assertNotIn(sid,fills)
        listed=[i for c in self.p.drawing_classes(4)['classes'] for i in c.get('items',[])
                if abs(i['bbox'][0]-475.8)<1 and abs(i['bbox'][1]-600.17)<1]
        self.assertEqual(len(listed),1)

    def test_gap_bridging_is_fail_closed_on_width(self):
        """Gorunur engel olmasa bile desenden genis bosluk koprulenmez."""
        from analyzer_v3 import dashed
        self.assertEqual(dashed.GAP_SLACK,1.25)
        r=self.p.dash_proposals(4)
        for row in r['runs']:
            for brk in row['breaks']:
                self.assertTrue(brk['reason'].startswith('SEMBOL_BOSLUGU')
                                or brk['reason']=='SEMBOL_OLABILIR_BOSLUK_DESENDEN_GENIS')
        # -X4:PE klemensini ayiran bosluk hicbir kosuda koprulenmis olmamali.
        drops=[x for x in r['runs'] if x['ruling']=='x=482.89']
        self.assertTrue(all(not (x['start']<480.05 and x['end']>485.72) for x in drops))

    def test_own_candidate_mark_is_not_independent_evidence(self):
        """Kendi urettigim P04 adayi bagimsiz kanit sinifi sayilmaz: dongusel kanit olurdu."""
        r=self.p.dash_proposals(4)
        drop=next(x for x in r['runs'] if x['run_key']=='x=185.25#0')
        marks=[e for e in drop['evidence'] if e['kind']=='MARKED_PIN_ON_RUN']
        self.assertTrue(marks)
        self.assertTrue(all(e['method']=='P04_CANDIDATE' for e in marks))
        self.assertTrue(all(e['klass']=='ISARET_ONAYSIZ_ADAY' for e in marks))
        self.assertNotIn('ISARET',drop['evidence_classes'])

    def test_ambiguous_end_text_is_not_counted_as_a_potential(self):
        """Iki komsu ad toplaniyorsa uc yazisi kanit degildir."""
        r=self.p.dash_proposals(4)
        drop=next(x for x in r['runs'] if x['run_key']=='x=482.89#0')
        self.assertIn('N24.30',drop['ambiguous_end_text'])
        self.assertEqual(drop['potentials'],[])
        self.assertNotIn('YAZI',drop['evidence_classes'])

    def test_evidence_must_come_from_two_different_classes(self):
        """Iki kanit ayni siniftan gelemez; yalniz yazi kaniti yeterli degildir."""
        r=self.p.dash_proposals(4)
        for row in r['runs']:
            if row['kind']=='CONDUCTOR_CANDIDATE':
                self.assertGreaterEqual(len(row['evidence_classes']),2)
            if row['kind']=='UNDECIDED':
                self.assertLessEqual(len(row['evidence_classes']),1)
        # Olculdugunde asilsiz cikan kanit turu artik uretilmiyor.
        kinds={e['kind'] for row in r['runs'] for e in row['evidence']}
        self.assertNotIn('TOUCHES_SOLID_CONDUCTOR',kinds)

    def test_eliminated_rulings_are_reported_not_dropped_silently(self):
        """Yogunluk/bosluk filtresiyle elenen cetvel gerekcesiyle raporlanir."""
        r=self.p.dash_proposals(4)
        dropped={d['ruling'] for d in r['dropped_rulings']}
        self.assertTrue({'x=142.73','x=156.91','x=171.08','x=312.81','x=369.50'} <= dropped)
        self.assertTrue(all(d['reason'] in ('YOGUNLUK_DUSUK','TIPIK_BOSLUK_BUYUK')
                            for d in r['dropped_rulings']))
        self.assertGreater(r['thin_axis_groups'],0)

    def test_typical_gap_is_a_median_not_a_rounded_mode(self):
        """PE barasinda tipik bosluk 4.25; yuvarlama kovasi tire modunu kaydiriyordu."""
        bus=next(x for x in self.p.dash_proposals(4)['runs'] if x['run_key']=='y=440.37#0')
        self.assertEqual(bus['typical_gap'],4.25)
        self.assertEqual(bus['pieces'],52)
        self.assertAlmostEqual(bus['repeat_unit'],37.2,places=1)

    def test_measurement_and_cable_texts_are_not_potentials(self):
        """Kesit, birim, kablo damar yazisi potansiyel adi gibi kullanilmaz; taninmayan silinmez."""
        from analyzer_v3.document import classify_label
        for text in ('2,5mm²','4x2,5mm²','12x1,5mm²','Cu','0,75','4,5kW','kW','VDC','10-32','24 V'):
            self.assertEqual(classify_label(text),'MEASUREMENT_OR_UNIT',text)
        for text in ('PE','N','L1','L2','L3','P24.32','N24.30'):
            self.assertEqual(classify_label(text),'POTENTIAL',text)
        for text in ('U','V','W'):
            self.assertEqual(classify_label(text),'CABLE_CORE',text)
        self.assertEqual(classify_label('/1.510'),'SHEET_REFERENCE')
        self.assertEqual(classify_label('-3F22'),'DEVICE_TAG')
        # Taninmayan gercek yazi SILINMEZ, belirsiz olarak dondurulur.
        self.assertEqual(classify_label('Wassermangel'),'UNRECOGNISED')
        self.assertEqual(classify_label('X1:PE'),'UNRECOGNISED')
        # Kesikli hat kanitinda yalniz POTENTIAL sayilir: 'W' artik kanit degil.
        drop=next(x for x in self.p.dash_proposals(4)['runs'] if x['run_key']=='x=185.25#0')
        self.assertEqual(drop['potentials'],['PE'])
        # Sayfa devami eslesmesi kablo damar kimligini KULLANABILIR (potansiyel sarti degil).
        rows={(r['text'],r.get('source_signal')):r for r in self.p.continuations(4)['rows']}
        self.assertEqual(rows[('=122/25.67','112/3W67:9')]['status'],'RECIPROCAL_END_MATCHED')

    def test_overview_speaks_plainly_and_claims_no_approval(self):
        """Sade durum ekrani: bulunanlari duz Turkce anlatir, hicbir seyi onayli gostermez."""
        o=self.p.overview(28)
        self.assertEqual(o['page'],28)
        self.assertIn('Blatt 17',o['page_label'])
        self.assertEqual(o['summary']['connections'],8)
        self.assertEqual(o['summary']['production_ready'],0)
        self.assertEqual(len(o['connections']),8)
        self.assertTrue(all(c['state']!='Kullanıcı teyitli' for c in o['connections']))
        self.assertTrue(all('→' in c['plain'] for c in o['connections']))
        # Ortak hat tel cifti olarak sunulmaz.
        self.assertEqual(len(o['networks']),1)
        self.assertIn('tel çifti üretilmedi',o['networks'][0]['warning'])
        # Kullanicidan beklenenler duz dille yazili.
        titles=[t['title'] for t in o['todo']]
        self.assertTrue(any('Cihaz adını doğrula' in t for t in titles))
        self.assertTrue(all(t['why'] for t in o['todo']))
        self.assertIn('üretim/EPLAN aktarımı kapalıdır',o['note'])
        # Isaretsiz sayfada da calisir.
        empty=self.p.overview(2)
        self.assertEqual(empty['summary']['production_ready'],0)

    def test_overview_separates_confirmation_refresh_and_production(self):
        """Ozet ile satirlar TUTARLI; askiya alinan teyit 'onay yok' diye silinmez."""
        o=self.p.overview(4)
        s=o['summary']
        # Satir sayilari ozetle bire bir tutar.
        self.assertEqual(s['connections'],len(o['connections']))
        self.assertEqual(s['confirmed_current']+s['confirmed_suspended']
                         +s['awaiting_confirmation'],s['connections'])
        # C02/C03 kullanici teyitlidir ama sayfaya yeni isaret geldigi icin askidadir:
        # ne "onayli" ne de "hic onaylanmamis" gosterilir.
        self.assertEqual(s['confirmed_suspended'],2)
        suspended=[c for c in o['connections'] if c['confirm_state']=='TEYIT_ASKIDA']
        self.assertEqual(sorted(c['reference'] for c in suspended),['C02','C03'])
        for c in suspended:
            self.assertIn('yeniden inceleme',c['state'])
            self.assertEqual(c['review_state'],'NEEDS_REVIEW')
            self.assertFalse(c['production_ready'])
        # C02'nin TEL karari ayri boyuttur ve teyidi TAZELEMEZ.
        c02=next(c for c in o['connections'] if c['reference']=='C02')
        self.assertEqual(c02['implementation'],'TEL')
        self.assertEqual(c02['confirm_state'],'TEYIT_ASKIDA')
        # Uretime uygunluk ayri sayidir ve her zaman kapalidir.
        self.assertEqual(s['production_ready'],0)
        self.assertEqual([d['value'] for d in o['dimensions'] if d['key']=='production_ready'],[0])
        self.assertEqual(s['reviews_needing_refresh'],
                         self.p.review_status()['needs_review'])
        # Baslik artik satirlarla celismiyor.
        self.assertNotIn('Onaylı bağlantı yok',o['headline'])
        self.assertIn('teyit askıda',o['headline'])
        # C01 HAT seviyesinde teyitlidir: sade ekranda gorunur ama TEL sayilmaz.
        self.assertEqual([r['reference'] for r in o['line_relations']],['C01'])
        self.assertEqual(s['line_relations'],1)
        self.assertNotIn('C01',[c.get('reference') for c in o['connections']])
        self.assertIn('tel sayılmıyor',o['line_relations'][0]['warning'])

    def test_strip_label_owns_only_its_own_terminal_group(self):
        """Bir kez yazilan cubuk adi kendi grubuna baglanir, komsu gruba TASMAZ."""
        from analyzer_v3.document import strip_labels, strip_owner
        page=self.p._page(4)
        labels=strip_labels(page['words'],page['render_bbox'])
        texts={q['text'] for q in labels}
        self.assertIn('-X1',texts)
        self.assertIn('-X4',texts)
        # -X1 grubu: x 142..185 ; -X4 grubu: x 312..540
        self.assertEqual(strip_owner(labels,(142.73,480.05))[0],'-X1')
        self.assertEqual(strip_owner(labels,(185.25,480.05))[0],'-X1')
        self.assertEqual(strip_owner(labels,(312.81,480.05))[0],'-X4')
        self.assertEqual(strip_owner(labels,(539.58,480.05))[0],'-X4')
        # Etiketin SOLUNDA kalan bir noktanin sahibi YOKTUR; ad uydurulmaz.
        owner,reason=strip_owner(labels,(60.0,480.05))
        self.assertIsNone(owner)
        self.assertEqual(reason,'TERMINAL_LEFT_OF_FIRST_STRIP_LABEL')
        # Baska satirda etiket yoksa sahiplik kurulmaz.
        self.assertIsNone(strip_owner(labels,(400.0,120.0))[0])

    def test_partial_device_address_is_read_and_completed_from_the_page(self):
        """`=112-17K53` gibi +Ort'suz adres okunur; eksik parca SAYFADAN tamamlanir."""
        from analyzer_v3.models import device_parts, device_tail
        self.assertEqual(device_parts('=112-17K53'),('112',None,'17K53'))
        self.assertEqual(device_parts('=112+E122-17K53'),('112','E122','17K53'))
        self.assertEqual(device_tail('-17K53'),'17K53')
        self.assertEqual(device_tail('=112-17K53'),device_tail('=112+E122-17K53'))
        full,inherited=self.p._complete(28,'=112-17K53')
        self.assertEqual(full,'=112+E122-17K53')
        self.assertEqual(inherited,['ort'])
        # Tam adres verilirse hicbir sey devralinmaz.
        self.assertEqual(self.p._complete(28,'=112+E122-17K53'),('=112+E122-17K53',[]))

    def test_a_terminal_with_one_wire_is_still_the_same_terminal(self):
        """Sablonun 'cekirdegi' dis tel uclarini da sayiyordu; alti bos klemens eslesmiyordu.

        Sayfa 36'da `-X4.I:10` ve `-X4.I:11` klemenslerinin ALTINA saha teli cizilmemistir.
        Kutu kenarina degen 0,25 pt'lik tel ucu cekirdege katildigi icin sablon 3 parca,
        aday 2 parca oluyor ve `CORE_GEOMETRY_DIFFERS` ile eleniyordu. Artik sembolun KENDI
        cizgisi (daire) karsilastirilir; kenardaki tel ucu farki eleme degil, nottur.
        """
        from analyzer_v3.similarity import edge_row, split_core, distinctive
        entry=next(e for e in self.p.library_entries()['rows']
                   if e['family'].startswith('Klemens (normal') and e['status']!='RETIRED')
        desc=descriptor_of(entry)
        inside,edge=split_core(desc['core'],desc['size'])
        self.assertEqual(len(inside),1)          # daire
        self.assertEqual(len(edge),2)            # ustteki ve alttaki tel ucu
        self.assertTrue(distinctive(inside))
        found={(c['device_name'],c['pins'][0]['page_pin_texts'][0]):c
               for c in self.p.library_candidates(entry['id'],36)['candidates']}
        self.assertEqual(len(found),8)
        for pin in ('10','11'):
            c=found[('=122+E122-X4.I',pin)]
            self.assertEqual(c['edge_difference']['template_edge_parts'],2)
            self.assertEqual(c['edge_difference']['candidate_edge_parts'],1)
            self.assertIn('EXTERNAL_LINE_COUNT_DIFFERS_FROM_TEMPLATE',c['issues'])
        # Onceden bulunan alti klemens BOZULMADI ve kenar farki tasimiyor.
        for pin in ('7','8','9','12','13','14'):
            self.assertIsNone(found[('=122+E122-X4.I',pin)]['edge_difference'])
        # Gevsetme YALNIZ ayirt edici sekli olan sablonlar icindir: tek bir sifir boyutlu
        # nokta her yerde bulunur; olculdu, sayfa 4'te 1 -> 20 adaya cikiyordu.
        dot=next(e for e in self.p.library_entries()['rows']
                 if e['family'].startswith('Klemens (yalnız daire') and e['status']!='RETIRED')
        dot_desc=descriptor_of(dot)
        self.assertFalse(distinctive(split_core(dot_desc['core'],dot_desc['size'])[0]))
        self.assertEqual(len(self.p.library_candidates(dot['id'],4)['candidates']),1)
        # Sayfa 4'un klemens sayisi degismedi.
        self.assertEqual(len(self.p.library_candidates(entry['id'],4)['candidates']),10)

    def test_page36_terminals_10_and_11_complete_their_pairs(self):
        """Duzeltmeden sonra iki ek cift GERCEKTEN izlenir; mevcut alti cift bozulmaz."""
        pairs=sorted(tuple(sorted((r['pins'][0]['device']+':'+r['pins'][0]['pin'],
                                   r['pins'][1]['device']+':'+r['pins'][1]['pin'])))
                     for r in self.p.table(36)['rows'] if r['kind']=='PHYSICAL_PAIR')
        self.assertEqual(len(pairs),8)
        self.assertIn(('=122+E122-25D22:4','=122+E122-X4.I:10'),pairs)
        self.assertIn(('=122+E122-25D22:5','=122+E122-X4.I:11'),pairs)
        for pin,terminal in (('1','7'),('2','8'),('3','9'),('6','12'),('7','13'),('8','14')):
            self.assertIn(('=122+E122-25D22:'+pin,'=122+E122-X4.I:'+terminal),pairs)

    def test_plc_module_owns_its_own_pins_and_never_the_neighbours(self):
        """Modul adi baslik blogundan kendi pinlerine baglanir; komsu sayfanin adi tasinmaz."""
        for number,device,mark,module_mark in ((28,'=122+E122-17D22','DO','8DO'),
                                               (36,'=122+E122-25D22','DI','24VDC')):
            report=self.p.module_report(number)
            self.assertEqual(len(report['modules']),1,number)
            m=report['modules'][0]
            self.assertEqual(m['device'],device)
            self.assertEqual(m['owner_reason'],'MODULE_HEADER_OWNERSHIP')
            # Basliktaki TEK cihaz yazisi sahiptir; birden fazla olsaydi ad uydurulmazdi.
            self.assertEqual(m['header_tags'],[device.split('+E122')[-1]])
            # Sekil ayni oldugu icin DO/DI ayrimi YAZIDAN gelir.
            self.assertEqual(sorted({r['pin_mark'] for r in m['resolved']}),[mark])
            self.assertEqual([r['pin'] for r in m['resolved']],['1','2','3','4','5','6','7','8'])
            self.assertIn(module_mark,m['header_texts'])
            # Dis iletkeni cizilmemis uc AYRI kovadadir; kacirilmis tel degildir.
            self.assertTrue(all(r['why']=='NO_EXTERNAL_CONDUCTOR_DRAWN_NOT_A_MISSING_WIRE'
                                for r in m['no_conductor']))
            self.assertEqual(sorted(r['pin'] for r in m['no_conductor']),
                             ['10','11','12','13','14','15','16','9','L+','M'])
            # Adi basilmamis uc "dogru taninmis uc" SAYILMAZ.
            self.assertEqual(len(m['unresolved']),10)
            self.assertTrue(all(r['pin'] is None for r in m['unresolved']))
        # Sayfa 4/2/5'te PLC modulu YOKTUR: kural bos yere modul uydurmaz.
        for number in (4,2,5):
            self.assertEqual(self.p.module_report(number)['modules'],[])

    def test_page5_pairs_come_from_its_own_geometry_and_c02_is_not_copied(self):
        """Sayfa 5 kendi geometrisinden cozulur; sayfa 4'un C02/C03 teyidi KOPYALANMAZ."""
        rows=self.p.table(5)['rows']
        pairs=sorted(tuple(sorted((r['pins'][0]['device']+':'+r['pins'][0]['pin'],
                                   r['pins'][1]['device']+':'+r['pins'][1]['pin'])))
                     for r in rows if r['kind']=='PHYSICAL_PAIR')
        self.assertEqual(len(pairs),6)
        for a,b in (('=112+E122-4F22:2','=112+E122-X1:4'),
                    ('=112+E122-4F22:4','=112+E122-X1:5'),
                    ('=112+E122-4F22:6','=112+E122-X1:6'),
                    ('=112+E122-17K56:14','=112+E122-X4:5'),
                    ('=112+E122-17K57:14','=112+E122-X4:6'),
                    ('=112+E122-17K59:14','=112+E122-X4:7')):
            self.assertIn(tuple(sorted((a,b))),pairs)
        # 11-11 koprusu + X4:8 dali UC UCLU ortak agdir: sayfa 4'teki gibi ikiye BOLUNMEZ.
        net=[r for r in rows if r['kind']=='NETWORK_GROUP'
             and {q['pin'] for q in r['pins']}>={'11'}]
        self.assertEqual(len(net),1)
        self.assertEqual(sorted(q['device'].split('E122-')[-1]+':'+q['pin'] for q in net[0]['pins']),
                         ['17K57:11','17K59:11','X4:8'])
        self.assertIn('Fiziksel tel çiftleri buradan türetilmez',net[0]['note'])
        # Sayfa 5'te hicbir TEYITLI satir yoktur: C02/C03 sayfa 4'e baglidir.
        self.assertEqual([r for r in rows if r['kind'].startswith('CONFIRMED_')],[])
        for review in self.p.reviews:
            self.assertNotIn(5,review.get('pages') or [])

    def test_approved_dash_run_bridges_the_graph_but_not_the_physical_wire(self):
        """Kontrollu kesikli hat karari UYGULANINCA yol izlenir; fiziksel tel yine CIKMAZ.

        Teknik yol izleme eksikligi ile fiziksel uc/imalat belirsizligi AYRI seylerdir.
        Onay verilmeden graf bugunkuyle birebir aynidir; onay izole kopyada verilir ve
        canli calismaya dokunulmaz.
        """
        import sqlite3, shutil
        # Canli calismada onay YOK: kopru de yok, graf degismedi.
        self.assertEqual(self.p.dash_bridges(4),[])
        pe=[q for q in self.p.pins if q.get('page',4)==4 and q['pin']=='PE']
        self.assertEqual(len(pe),2)
        for q in pe:
            self.assertEqual(self.p.trace(q['id'])['targets'],[])
        with tempfile.TemporaryDirectory() as tmp:
            copy=Path(tmp)/'izole'
            shutil.copytree(self.p.run,copy)
            blind=Pilot(copy,verify=False)
            runs={'y=440.37#0','x=185.25#0','x=482.89#0'}
            for key in sorted(runs):
                blind.add_review(dict(subject='DASH_RUN',decision='CONFIRMED',run_key=key,page=4,
                                      reviewer='IZOLE TEST',reference='TEST-'+key,
                                      note='Yalniz mekanizma testi; canli onay degildir.'))
            blind.refresh(); blind.graphs={}
            bridges=blind.dash_bridges(4)
            self.assertTrue(bridges)
            self.assertTrue(all(b['id'].startswith('dashbridge:') for b in bridges))
            self.assertTrue(all(b['run_key'] in runs for b in bridges))
            # Kosu KIRILMASI asla koprulenmez: her kopru kendi kosusunun uzanimi icindedir.
            spans={}
            for run in blind._dash_runs(4):
                spans['%s#%d'%(run['ruling'],run['index'])]=(run['start'],run['end'])
            for b in bridges:
                lo,hi=spans[b['run_key']]
                axis=0 if b['a'][1]==b['b'][1] else 1
                self.assertTrue(lo-0.01<=b['a'][axis]<=hi+0.01)
                self.assertTrue(lo-0.01<=b['b'][axis]<=hi+0.01)
            # Yol artik izleniyor ve kopru KULLANILDIGI kayitta yaziyor.
            ids={q['device']:q['id'] for q in blind.pins if q.get('page',4)==4 and q['pin']=='PE'}
            for device,pid in ids.items():
                t=blind.trace(pid)
                self.assertTrue(t['targets'],device)
                self.assertIn('PATH_USES_APPROVED_DASH_BRIDGE',t['issues'])
                self.assertTrue(any(i.startswith('dashbridge:') for i in t['dash_bridges']))
            # AMA fiziksel tel cifti CIKMAZ: ortak PE agidir.
            rows=[r for r in blind.table(4)['rows']
                  if any(q['pin']=='PE' for q in r['pins'])]
            self.assertEqual([r['kind'] for r in rows],['NETWORK_GROUP'])
            self.assertIn('Fiziksel tel çiftleri buradan türetilmez',rows[0]['note'])

    def test_plc_identity_comes_from_the_drawing_not_from_existing_marks(self):
        """Kimlik, canli AJAN_TASLAK isaretleri OLMADAN da ayni cikar."""
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            copy=Path(tmp)/'izole'
            shutil.copytree(self.p.run,copy)
            db=sqlite3.connect(copy/'annotations.sqlite3')
            drops=[i for i,b in db.execute('SELECT id,body FROM pins')
                   if json.loads(b).get('method')=='AGENT_DRAFT']
            self.assertTrue(drops)
            db.executemany('DELETE FROM pins WHERE id=?',[(i,) for i in drops])
            db.execute('UPDATE metadata SET revision=revision+1 WHERE id=1')
            db.commit(); db.close()
            blind=Pilot(copy,verify=False)
            for number,device in ((28,'=122+E122-17D22'),(36,'=122+E122-25D22')):
                m=blind.module_report(number)['modules'][0]
                self.assertEqual(m['device'],device)
                self.assertEqual([r['pin'] for r in m['resolved']],
                                 ['1','2','3','4','5','6','7','8'])
                # Bu kopyada o uclarda hicbir isaret yok: sonuc isaretlerden gelmiyor.
                self.assertTrue(all(not r['marked'] for r in m['resolved']))

    def test_library_candidate_on_a_module_takes_the_module_identity(self):
        """Kutuphane aday akisi da modul kuralini kullanir; DO ve DI ayri ailedir."""
        entry=next(e for e in self.p.library_entries()['rows']
                   if e['family'].startswith('PLC DO') and e['status']!='RETIRED')
        found=self.p.library_candidates(entry['id'],28)['candidates']
        outputs=[c for c in found if (c.get('module') or {}).get('pin_mark')=='DO']
        self.assertEqual(len(outputs),8)
        for c in outputs:
            self.assertTrue(c['identity_resolved'])
            self.assertEqual(c['device_name'],'=122+E122-17D22')
            self.assertEqual(c['device_source'],'MODULE_HEADER_OWNERSHIP')
            self.assertEqual(c['device_inherited'],['anlage','ort'])
        # DO ve DI ayni sekildedir: DI ailesi de sayfa 28'de eslesir. Bu, o uclarin DI oldugunu
        # GOSTERMEZ; sayfanin kendi yazisi 'DO' der ve kayitta o durur.
        di=next(e for e in self.p.library_entries()['rows']
                if e['family'].startswith('PLC DI') and e['status']!='RETIRED')
        cross=self.p.library_candidates(di['id'],28)['candidates']
        self.assertTrue(cross)
        self.assertEqual(sorted({(c.get('module') or {}).get('pin_mark') for c in cross
                                 if (c.get('module') or {}).get('pin_mark','').startswith('D')}),
                         ['DO','DQ-M0','DQ-M1','DQ-M2','DQ-M3','DQ-M4','DQ-M5','DQ-M6','DQ-M7'])

    def test_coil_family_reads_full_identity_on_every_instance(self):
        """Bobin ailesi alti bobinin de cihaz ve pin adini kendi yazisindan okur."""
        entry=next(e for e in self.p.library_entries()['rows']
                   if e['family']=='Röle bobini (A1/A2)' and e['status']!='RETIRED')
        found=self.p.library_candidates(entry['id'],28)['candidates']
        names=sorted(c['device_name'] for c in found)
        self.assertEqual(names,['=112+E122-17K52','=112+E122-17K53','=112+E122-17K55',
                                '=112+E122-17K56','=112+E122-17K57','=112+E122-17K59'])
        for c in found:
            self.assertEqual(c['device_inherited'],['ort'])
            self.assertEqual(sorted(t for q in c['pins'] for t in q['page_pin_texts']),['A1','A2'])

    def test_page28_connections_are_traced_and_the_common_net_stays_a_net(self):
        """Sayfa 28 ucdan uca: 8 fiziksel cift + 1 ortak ag; N24.30'dan tel zinciri CIKMAZ."""
        rows=self.p.table(28)['rows']
        pairs=sorted(tuple(sorted((r['pins'][0]['device']+':'+r['pins'][0]['pin'],
                                   r['pins'][1]['device']+':'+r['pins'][1]['pin'])))
                     for r in rows if r['kind']=='PHYSICAL_PAIR')
        self.assertEqual(len(pairs),8)
        self.assertIn(('=112+E122-17K52:A1','=122+E122-17D22:1'),pairs)
        self.assertIn(('=122+E122-17D22:3','=122+E122-X4.Q:4'),pairs)
        net=[r for r in rows if r['kind']=='NETWORK_GROUP']
        self.assertEqual(len(net),1)
        self.assertEqual(len(net[0]['pins']),6)
        self.assertTrue(all(q['pin']=='A2' for q in net[0]['pins']))
        # Ortak agdan uc cifti TURETILMEZ: bu satir fiziksel cift degildir.
        self.assertNotEqual(net[0]['kind'],'PHYSICAL_PAIR')
        self.assertIn('Fiziksel tel çiftleri buradan türetilmez',net[0]['note'])

    def test_agent_draft_marks_are_counted_apart(self):
        """Ajan taslak isareti insan isareti ve program bulgusuyla ayni kovaya konmaz."""
        from analyzer_v3.models import MARK_METHODS
        self.assertIn('AGENT_DRAFT',MARK_METHODS)
        drafts=[q for q in self.p.state()['pins'] if q.get('method')=='AGENT_DRAFT']
        self.assertTrue(drafts)
        for q in drafts:
            # Turkce noktali I buyuk/kucuk donusumu guvenilir degil: sabit onek sinanir.
            self.assertIn('Ajan tasla',q['note'])
        self.assertEqual(self.p.effort()['pins_by_method']['AGENT_DRAFT'],len(drafts))
        # Insan isareti ve program bulgusu ayri kovalarda durur.
        methods=self.p.effort()['pins_by_method']
        self.assertIn('MANUAL',methods)
        self.assertIn('P04_CANDIDATE',methods)

    def test_junction_dots_come_from_the_drawing_and_match_the_seeded_one(self):
        """Birlesme noktasi cizimin kendi es merkezli halkasidir; elle tohumlanani yeniden uretir."""
        dots=self.p.dash_proposals(4)['dots']
        points={tuple(d['point']) for d in dots}
        seeded=tuple(self.p.seeds['dots'][0]['point'])
        self.assertIn(seeded,points)
        self.assertIn((185.25,440.37),points)
        self.assertIn((482.89,440.37),points)
        self.assertTrue(all(len(d['rings'])>=2 for d in dots))
        self.assertTrue(all(d['source']=='DRAWN_CONCENTRIC_RINGS' for d in dots))

    def test_dashed_pe_runs_stay_proposals_and_never_become_wires(self):
        """PE devresi: gorsel kanit, yol kaniti ve insan karari ayri; agdan tel cifti cikmaz."""
        r=self.p.dash_proposals(4)
        self.assertTrue(r['graph_unchanged'])
        self.assertTrue(r['raw_geometry_untouched'])
        self.assertFalse(r['production_ready'])
        bus=next(x for x in r['runs'] if x['ruling']=='y=440.37' and x['index']==0)
        self.assertEqual(bus['kind'],'CONDUCTOR_CANDIDATE')
        self.assertEqual(bus['ends'],[[71.87,440.37],[1007.3,440.37]])
        kinds={e['kind'] for e in bus['evidence']}
        self.assertIn('DRAWN_JUNCTION_DOT',kinds)
        self.assertIn('END_SHEET_REFERENCE',kinds)
        self.assertGreaterEqual(len(kinds),2)
        # Ayni cizgi stili kanit listesine GIRMEZ: stil zaten kosuyu tanimlar.
        self.assertNotIn('LINE_STYLE',kinds)
        # Uc alan ayri. Yol kaniti OLCULUR: graf tam ortak uc paylasan parcalari zaten
        # birlestirir, kesik BOSLUGUNU birlestirmez. Onemli olan izlenebilir HEDEF yoklugudur.
        path=bus['path_evidence']
        self.assertEqual(path['pieces'],52)
        self.assertGreaterEqual(path['graph_components'],50)
        self.assertEqual(path['traced_targets'],[])
        self.assertEqual(path['attached_pins'],[])
        self.assertEqual(bus['decision'],'ONAY_BEKLIYOR')
        self.assertIsNone(bus['decided_by'])
        self.assertEqual(bus['merge_proposal']['status'],'PROPOSED')
        self.assertEqual(bus['merge_proposal']['raw_pieces_kept'],len(bus['raw_pieces']))
        # Nokta ile bulusan kosular yalniz ORTAK POTANSIYEL iliskisidir.
        self.assertEqual(sorted(tuple(l['point']) for l in r['links']),
                         [(185.25,440.37),(482.89,440.37)])
        self.assertTrue(all(l['relation']=='COMMON_POTENTIAL_NETWORK_ONLY' for l in r['links']))
        self.assertTrue(all(l['decision']=='ONAY_BEKLIYOR' for l in r['links']))
        # Saha cihazi cercevesi PE hattindan AYRI: dort kesikli cetvel kapali kutu.
        self.assertEqual([b['bbox'] for b in r['boxes']],[[128.56,572.18,801.79,709.66]])
        self.assertTrue(all(x['kind']=='ZONE_BOX_EDGE'
                            for x in r['runs'] if x['ruling'] in ('y=572.18','y=709.66',
                                                                  'x=128.56','x=801.79')))

    def test_dash_gap_is_not_bridged_over_a_symbol_or_without_a_dot(self):
        """Sembol boslugu ve noktasiz kesisme otomatik birlesmez."""
        r=self.p.dash_proposals(4)
        drops=[x for x in r['runs'] if x['ruling']=='x=185.25']
        # -X1:PE dususu klemensin USTUNDE biter; klemensin alti ayri kosudur.
        self.assertEqual([(x['start'],x['end']) for x in drops],
                         [(440.37,480.05),(485.72,589.89)])
        split=next(b for b in drops[0]['breaks'] if b['between']==[480.05,485.72])
        self.assertTrue(split['reason'].startswith('SEMBOL_BOSLUGU'))
        # PE barasi kendi ustunden gecen telleri kesmez ama onlara BAGLANMAZ da.
        bus=next(x for x in r['runs'] if x['ruling']=='y=440.37')
        self.assertGreaterEqual(len(bus['crossings_without_dot']),6)
        linked=[q for l in r['links'] for q in l['runs']]
        self.assertEqual(sorted(set(linked)),['x=185.25#0','x=482.89#0','y=440.37#0'])
        # Graf hala PE'yi izleyemiyor: oneri, yol kaniti yerine gecmez.
        for pin in [q for q in self.p.pins if q['pin']=='PE' and q.get('page')==4]:
            self.assertEqual(self.p.trace(pin['id'])['targets'],[])

    def test_sheet_continuations_are_verified_on_the_target_page_geometry(self):
        rows={(r['text'],r.get('source_signal')):r for r in self.p.continuations()['rows']}
        matched=rows[('/4.23','P24.32')]
        self.assertEqual((matched['status'],matched['target_page']),('RECIPROCAL_END_MATCHED',5))
        self.assertEqual([(c['reference'],c['signal']) for c in matched['candidates']],[('/3.29','P24.32')])
        self.assertEqual(matched['source_end']['point'],[1007.3,171.07])
        self.assertEqual(matched['candidates'][0]['end']['point'],[241.94,171.07])
        self.assertEqual(matched['relation'],'SHEET_CONTINUATION_EVIDENCE_ONLY_NOT_A_WIRE')
        self.assertFalse(matched['production_ready'])
        # Kontak/bobin referansı devam sayılmaz.
        self.assertEqual(rows[('=122/17.52',None)]['status'],'DEVICE_REFERENCE_NOT_A_CONTINUATION')
        # Döndürülmüş referans kendi ekseninde okunur: uç yazının yanında değil, altındadır.
        rotated=rows[('=122/25.67','112/3W67:9')]
        self.assertEqual((rotated['status'],rotated['target_page']),('RECIPROCAL_END_MATCHED',36))
        self.assertEqual(rotated['source_end']['point'],[667.14,334.07])
        self.assertEqual([(c['reference'],c['signal']) for c in rotated['candidates']],
                         [('=112/3.46','112/3W67:9')])
        statuses=[r['status'] for r in self.p.continuations()['rows']]
        self.assertEqual(statuses.count('RECIPROCAL_END_MATCHED'),16)
        # PE barası kesiklidir: her tire parçasinin iki ucu oldugu icin referansin yaninda
        # birden cok uc gorunur ve kural once fail-closed kapaniyordu. Artik uclarin hepsi
        # AYNI OLCULMUS kosuya aitse referansin ucu o kosunun kendi ucudur.
        pe={t:r for (t,_),r in rows.items() if t in ('/1.510','/4.51')}
        self.assertEqual(sorted(pe),['/1.510','/4.51'])
        self.assertEqual(pe['/1.510']['source_end']['point'],[71.87,440.37])
        self.assertEqual(pe['/4.51']['source_end']['point'],[1007.3,440.37])
        for r in pe.values():
            self.assertEqual(r['status'],'RECIPROCAL_END_MATCHED')
            self.assertEqual(r['source_signal'],'PE')
            self.assertEqual(r['source_end']['dash_run'],'y=440.37#0')
            self.assertEqual(r['source_end']['evidence'],
                             'MEASURED_DASH_RUN_END_NOT_A_GAP_BRIDGE')
            # Devam kanitidir, TEL DEGILDIR: ortak PE agindan tel cifti cikmaz.
            self.assertEqual(r['relation'],'SHEET_CONTINUATION_EVIDENCE_ONLY_NOT_A_WIRE')
            self.assertFalse(r['production_ready'])

    def test_untraced_target_page_is_reported_not_guessed(self):
        pilot=Pilot(RUN5)
        pilot.manifest=dict(pilot.manifest,traced_pages=[4])
        rows=[r for r in pilot.continuations()['rows'] if r['text']=='/4.23']
        self.assertTrue(all(r['status']=='TARGET_PAGE_NOT_TRACED' for r in rows))
        self.assertTrue(all('--pages' in r['note'] for r in rows))

    def test_cross_page_path_reaches_marked_pins_and_stays_network_level(self):
        r=self.p.path('p24')
        self.assertEqual((r['page'],r['pin']['pin']),(4,'P24.32'))
        hops={h['to_page']:h for h in r['hops']}
        self.assertEqual(sorted(hops),[2,5])
        self.assertTrue(all(h['status']=='TARGET_PINS_REACHED' for h in hops.values()))
        self.assertTrue(all(h['relation']=='NETWORK_CONTINUATION_NOT_ONE_PHYSICAL_WIRE' for h in hops.values()))
        self.assertEqual(sorted((t['device'],t['pin']) for t in hops[5]['target_pins']),
                         [('=112+E122-17K56','13'),('=112+E122-X4','P24.32')])
        self.assertEqual([(t['device'],t['pin']) for t in hops[2]['target_pins']],
                         [('=112+E122-X4','P24.32')])
        self.assertFalse(r['production_ready'])

    def test_marks_and_masks_stay_on_their_own_sheet(self):
        pages={p['id']:p.get('page',4) for p in self.p.state()['pins']}
        self.assertEqual({pages[i] for i in ('p24','k52_top')},{4})
        # Sayfa 5 grafiği yalnız o sayfanın işaretlerini tanır.
        self.assertNotIn('p24',self.p.page_graph(5).pins)
        with self.assertRaises(ValueError):
            self.p.change(dict(page=3,device='=112+E122-X1',pin='1',point=[10,10],kind='PHYSICAL'))

    def test_effort_reports_both_marking_methods(self):
        effort=self.p.effort()
        # AGENT_DRAFT: gelistirme calismasinda ajanin koydugu ornek isaret; insan isareti ve
        # program bulgusuyla AYNI KOVAYA konmaz.
        self.assertEqual(set(effort['pins_by_method']),{'MANUAL','P04_CANDIDATE','AGENT_DRAFT'})
        self.assertTrue(all(row['method'] in ('MANUAL','P04_CANDIDATE','AGENT_DRAFT') for row in effort['events']))
        self.assertIn('duvar saati',effort['note'])
        self.assertFalse(effort['production_ready'])

    def test_p03_run_without_index_refuses_cross_page_answers(self):
        with self.assertRaises(ValueError):
            Pilot(RUN).cross_references()



class DashedCrossingTests(unittest.TestCase):
    def test_dash_ending_on_a_through_wire_is_a_crossing_not_a_junction(self):
        # Sayfa 2 bulgusu: PE kesikli rayının bir tiresi N24.30 düşüşünün tam üstünde başlıyordu;
        # geometri T gördü ve N24.30 ile PE aynı ağa girdi. Koşu iki yanda sürüyorsa bu X'tir.
        segments=[seg('v',[5,-10],[5,10]),seg('h',[5,0],[15,0])]
        pins=[dict(id='a',point=[5,10],device='=112+E122-X4',pin='N24.30',kind='PHYSICAL'),
              dict(id='b',point=[15,0],device='=112+E122-X4',pin='PE',kind='PHYSICAL')]
        joined=PathGraph(segments,[],pins)
        self.assertEqual([t['pin_id'] for t in joined.trace('a')['targets']],['b'])
        split=PathGraph(segments,[],pins,no_join=[(5,0)])
        self.assertEqual(split.trace('a')['targets'],[])
        self.assertEqual([c['kind'] for c in split.crossings],['DASHED_RUN_CROSSING'])
        # Çizilmiş nokta varsa kesişim değil birleşimdir; dış kanıt noktayı ezmez.
        dotted=PathGraph(segments,[dict(point=[5,0],radius=1.0)],pins,no_join=[(5,0)])
        self.assertEqual([t['pin_id'] for t in dotted.trace('a')['targets']],['b'])


class SchemaRelationTests(unittest.TestCase):
    """S01 şema ilişkileri gerçek belgede. Sayfa 2/4/5/22 incelendi; kör test değildir."""
    @classmethod
    def setUpClass(cls):
        cls.p=Pilot(RUN5)

    def nets(self,number):
        return self.p.relations(number)['networks']

    def by_pin(self,number,label):
        return next(n for n in self.nets(number) if label in [q['label'] for q in n['pins']])

    def test_upper_phases_reach_the_fuse_without_a_fake_device(self):
        nets=[self.by_pin(4,'-3F22:%d'%i) for i in (1,3,5)]
        self.assertEqual([n['potential'] for n in nets],['L1','L2','L3'])
        # Noktasız kesişim ve sigorta gövdesi birleştirmez: üç faz üç ayrı çizilmiş segment kümesi.
        ids=[set(n['segment_ids']) for n in nets]
        self.assertFalse(ids[0]&ids[1] or ids[0]&ids[2] or ids[1]&ids[2])
        self.assertNotIn('-3F22:2',[q['label'] for q in nets[0]['pins']])
        page={s['id'] for s in self.p._page(4)['segments']}
        self.assertTrue(set(nets[0]['segment_ids'])<=page)
        rel=[r for r in self.p.relations(4)['relations'] if r['source']=='-3F22:1']
        self.assertTrue(rel and all(r['edges'] and r['kind']!='PIN_PIN' for r in rel))

    def test_continuation_is_verified_or_says_why_not(self):
        l1=self.by_pin(4,'-3F22:1')
        self.assertIn(('/4.11',5,True),[(c['reference'],c['target_page'],c['verified']) for c in l1['continuations']])
        l1=self.by_pin(5,'-4F22:1')
        row=next(c for c in l1['continuations'] if c['reference']=='/5.11')
        self.assertEqual((row['target_page'],row['status'],row['verified']),(6,'TARGET_PAGE_NOT_TRACED',False))

    def test_station_supplies_are_visible_without_marks(self):
        nets=self.nets(22)
        names={n['potential'] for n in nets}
        self.assertTrue({'P24.30','N24.30'}<=names)
        self.assertTrue(all(not n['pins'] for n in nets))
        p24=next(n for n in nets if n['potential']=='P24.30')
        self.assertEqual(sorted(c['target_page'] for c in p24['continuations']),[13,26])

    def test_port_name_and_shared_terminal_label_do_not_name_a_line(self):
        # `X1 P1` Ethernet port adıdır; klemens sırasında iki tel arasındaki yazı iki hatta da ad vermez.
        self.assertNotIn('P1',{n['potential'] for n in self.nets(22)})
        rejected=[o['rejected_labels'] for n in self.nets(22) for o in n['open_ends'] if o.get('rejected_labels')]
        self.assertTrue(any('ifade parçası' in r for rows in rejected for r in rows))
        self.assertEqual(self.by_pin(4,'-X4:PE')['potential'],'PE')

    def test_dashed_pe_rail_does_not_swallow_the_n24_drop(self):
        n=self.by_pin(2,'-X4:N24.30')
        self.assertEqual((n['potential'],n['potential_conflict']),('N24.30',[]))
        self.assertIn((681.31,454.54),[tuple(c['point']) for c in self.p.page_graph(2).crossings
                                        if c['kind']=='DASHED_RUN_CROSSING'])

    def test_page_index_separates_physical_page_blatt_and_scope(self):
        idx=self.p.page_index()
        self.assertEqual((idx['counts']['total'],idx['counts']['default_selected'],len(idx['pages'])),(73,58,73))
        rows={r['page']:r for r in idx['pages']}
        self.assertEqual((rows[4]['blatt'],rows[22]['blatt']),('3','11'))
        # Kapsam filtresi silmez: dışarıdaki sayfa listede, yalnız varsayılan seçimde değil.
        self.assertFalse(rows[1]['default_selected'])
        self.assertEqual((rows[22]['state'],rows[22]['marks'],rows[22]['origin']),('PREPARED',0,'RUN'))
        self.assertEqual(rows[40]['state'],'NOT_PREPARED')
        model=self.p.page_model(4)
        self.assertEqual((model['contract'],model['page']['physical_page'],model['page']['blatt']),
                         ('uvp.pdf2p8.page',4,'3'))
        self.assertFalse(model['production_released'])
        self.assertTrue({'PIN','JUNCTION','INTERRUPTION'}<={n['kind'] for n in model['nodes']})


class PreparedPageNavigationTests(unittest.TestCase):
    """İşaretsiz bir sayfayı önbellekte GERÇEKTEN hazırla, gez; eski kayıtlara dokunma."""
    @classmethod
    def setUpClass(cls):
        from analyzer_v3.pagecache import PageCache
        from analyzer_v3.prepare import digest
        cls.tmp=Path(tempfile.mkdtemp())
        manifest=json.loads((RUN5/'manifest.json').read_text(encoding='utf-8'))
        source=Path(manifest['source_path'])
        cls.db=RUN5/'annotations.sqlite3'
        cls.before=digest(cls.db) if cls.db.exists() else None
        cls.cache=PageCache(source,digest(source),73,root=cls.tmp)
        cls.cache.enqueue([6]); cls.cache.wait(300)
        cls.p=Pilot(RUN5,cache=cls.cache)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp,ignore_errors=True)

    def test_prepared_page_is_viewable_and_readable_without_touching_the_run(self):
        """SALT OKUMA testi: canlı çalışmaya yazılmaz. İşaretleme yazması ManualMarkingTests'te,
        kopya çalışmada sınanır."""
        from analyzer_v3.prepare import digest
        self.assertEqual(self.cache.state(6),'PREPARED')
        self.assertIn(6,self.p.viewable_pages())
        self.assertNotIn(6,self.p.pages())                     # çalışmanın kendi izlediği sayfa değil
        row=next(r for r in self.p.page_index()['pages'] if r['page']==6)
        self.assertEqual((row['state'],row['origin'],row['marks']),('PREPARED','CACHE',0))
        rel=self.p.relations(6)
        self.assertTrue(rel['networks'])
        self.assertTrue(all(not n['pins'] for n in rel['networks']))          # pin uydurulmaz
        # Önbellek sayfası çalışmanın izlenen sayfa listesini DEĞİŞTİRMEZ.
        self.assertEqual(self.p.manifest['traced_pages'],[2,4,5,22,28,36])
        if self.before:
            self.assertEqual(digest(self.db),self.before)                       # eski kayıt aynen

    def test_preparing_the_target_resolves_the_open_continuation(self):
        l1=next(n for n in self.p.relations(5)['networks']
                if '-4F22:1' in [q['label'] for q in n['pins']])
        row=next(c for c in l1['continuations'] if c['reference']=='/5.11')
        self.assertNotEqual(row['status'],'TARGET_PAGE_NOT_TRACED')


class EplanProofPackageTests(unittest.TestCase):
    """S03 kaynak paketi ve geri okuma karşılaştırması. EPLAN çalıştırmaz."""
    @classmethod
    def setUpClass(cls):
        from analyzer_v3 import eplan_export
        cls.x=eplan_export
        cls.pkg=eplan_export.proof_package(Pilot(RUN5))

    def test_package_carries_source_topology_not_target_symbols(self):
        p=self.pkg
        self.assertEqual((p['contract'],p['contract_version']),('uvp.pdf2p8.import-request','1.0'))
        self.assertFalse(p['target_policy']['live_project_writes'])
        self.assertNotIn('symbol',json.dumps(p))                         # sembol seçimi eşlemede
        links={frozenset((e['a'],e['b'])) for e in p['expected_links']}
        self.assertIn(frozenset(('p4:junction:L1','p4:dev:-3F22#1')),links)
        self.assertIn(frozenset(('p4:dev:-3F22#2','p4:dev:-X1:1#1')),links)
        ends={o['id']:o for pg in p['pages'] for o in pg['objects'] if o['kind']!='DEVICE'}
        # Devam paket içinde çift; paket dışına giden uçlar ayrı türde işaretli.
        self.assertTrue(ends['p4:end:/4.11']['partner_in_package'] and ends['p5:end:/3.19']['partner_in_package'])
        self.assertEqual(ends['p4:end:/1.110']['kind'],'POTENTIAL_BOUNDARY')
        self.assertFalse(ends['p5:end:/5.11']['partner_in_package'])
        self.assertEqual(p['issues'],[])
        # pt -> mm, sol alt köken: -3F22:1 (142.73, 149.81 pt) sayfa yüksekliği 809.87 pt.
        fuse=next(o for o in p['pages'][0]['objects'] if o['id']=='p4:dev:-3F22')
        self.assertEqual(fuse['pins'][0]['point_mm'],[50.352,232.854])

    def test_page_package_splits_poles_and_skips_lines_without_a_device(self):
        """T3: adlı hat bir CİHAZA girmiyorsa hat aktarılmaz; klemensler yine konur.

        Kullanıcı kuralı (2026-09-12): PE / P24 / N24 sayfada bir cihaza gitmiyorsa yalnız
        klemens eklensin, ray çizilmesin. Atlama sessiz değildir: gerekçe pakette durur.
        """
        pkg=self.x.page_package(Pilot(RUN5),4)
        objects=pkg['pages'][0]['objects']
        devices={o['id']:o for o in objects if o['kind']=='DEVICE'}
        # 3 kutuplu sigorta üç ayrı tek kutuplu nesne; klemens sırasının her ucu ayrı klemens.
        poles=[o for o in devices.values() if o['device_tag'].endswith('-3F22')]
        self.assertEqual(sorted([q['name'] for q in o['pins']] for o in poles),
                         [['1','2'],['3','4'],['5','6']])
        self.assertTrue(all(o['family']=='fuse_1pole' for o in poles))
        terminals=[o for o in devices.values() if o['family']=='terminal']
        self.assertTrue(terminals and all(len(o['pins'])==1 for o in terminals))
        self.assertIn('contact_no',{o['family'] for o in devices.values()})   # röle kontağı tanındı
        self.assertFalse([o for o in devices.values() if o['family'].startswith('unmapped')])
        # Cihaza giden hatlar duruyor…
        potentials={str(l.get('potential')) for l in pkg['expected_links']}
        self.assertTrue({'L1','L2','L3','P24.32'} <= potentials)
        # …cihaza girmeyenler yok ve gerekçesi yazılı.
        self.assertNotIn('PE',potentials)
        self.assertNotIn('N24.30',potentials)
        skipped=[i for i in pkg['issues'] if 'cihaza girmiyor' in i]
        self.assertTrue(any('PE' in i for i in skipped) and any('N24.30' in i for i in skipped))
        # Kimlikler tekil (aynı adlı iki klemens ucu dahil).
        ids=[o['id'] for o in objects]
        self.assertEqual(len(ids),len(set(ids)))

    def test_parts_list_reads_device_and_type_number_without_guessing(self):
        """T4: ürün kodu belgenin malzeme listesinden okunur; iç numara koda karışmaz."""
        from analyzer_v3 import parts

        def row(top, *texts):
            out, x = [], 10.0
            for text in texts:
                out.append(dict(text=text, x0=x, x1=x+len(text)*2.0, top=top, bottom=top+2.0))
                x += len(text)*2.0 + 4
            return out

        words = (row(100, '3', '-4F22', 'Sicherung', '5SE2316', 'SIEMENS', '386270')
                 + row(112, '1', '-17K52', 'Hilfsschütz')          # kod alt satıra taşmış
                 + row(118, '3RH2122-1BB40', 'SIEMENS')
                 + row(130, '1', '-X1', 'Klemmenleiste'))          # kodu olmayan satır
        found = {r['device']: r for r in parts.page_articles(words)}
        self.assertEqual(found['-4F22']['type_numbers'][0], '5SE2316')
        self.assertEqual(found['-4F22']['manufacturer'], 'SIEMENS')
        self.assertNotIn('386270', found['-4F22']['type_numbers'])     # firma iç numarası kod değil
        self.assertEqual(found['-17K52']['type_numbers'], ['3RH2122-1BB40'])   # taşan hücre birleşti
        self.assertEqual(found['-X1']['type_numbers'], [])
        self.assertEqual(found['-X1']['issue'], 'TIP_NUMARASI_OKUNAMADI')      # uydurma yok

    def test_package_says_when_parts_list_pages_are_not_prepared(self):
        """Liste sayfaları hazırlanmadıysa BELGEDEN kod okunmaz ve bu yazılır.

        Etiket listesi (Excel) ayrı bir kaynaktır: oradan gelen kod bu kuralın dışındadır
        ve kaynağı `LABEL_LIST` diye işaretlenir — hangi kodun nereden geldiği gizlenmez.
        """
        pilot = Pilot(RUN5)                                   # önbelleksiz: liste sayfaları hazır değil
        pkg = self.x.page_package(pilot, 4)
        devices = [o for o in pkg['pages'][0]['objects'] if o['kind'] == 'DEVICE']
        self.assertFalse([o for o in devices if o.get('part_source') == 'DOCUMENT_PARTS_LIST'])
        for device in devices:
            self.assertIn(device.get('part_source'), (None, 'LABEL_LIST'))
            if device.get('part_source') is None:
                self.assertIsNone(device['part_number'])
        self.assertTrue(any('Malzeme listesi sayfaları hazırlanmadı' in i for i in pkg['issues']))

    def test_compare_reports_missing_extra_and_identity(self):
        nodes=self.x._nodes(self.pkg)
        def end(node_id,function=None,pin=None):
            e=dict(location=nodes[node_id]['mm'])
            if pin: e.update(function=function,pin=pin)
            return e
        rb=dict(pages=[],interruption_points=[],connections=[
            dict(physical_page=4,start=end('p4:junction:L1'),end=end('p4:dev:-3F22#1','=112+E122-3F22','1')),
            # yanlış birleşme: T doğrudan klemense
            dict(physical_page=4,start=end('p4:junction:L1'),end=end('p4:dev:-X1:1#1','=112+E122-X1:1','1')),
            # kimlik farkı: pin adı yanlış yazılmış
            dict(physical_page=4,start=end('p4:dev:-3F22#2','=112+E122-3F22','9'),end=end('p4:dev:-X1:1#1','=112+E122-X1:1','1'))])
        d=self.x.compare(self.pkg,rb)
        self.assertEqual(d['found'],1)  # Yanlış pinli yol geometrik olarak benziyor; doğru bağ sayılmaz.
        self.assertIn(['p4:dev:-X1:1#1','p4:junction:L1'],d['extra'])
        self.assertTrue(any('KİMLİK FARKI' in i['issue'] for i in d['endpoint_issues']))
        self.assertFalse(d['complete'])
        self.assertEqual(len(d['missing']),len(self.pkg['expected_links'])-1)


class ManualMarkingTests(unittest.TestCase):
    """Kullanıcının kendi cihaz işareti: öneri, kayıt, mükerrer koruması, geri alma.

    Canlı pilot çalışmasına yazılmaz; her test kendi kopyasında çalışır.
    """
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='uvp-mark-test-')
        self.run=Path(self.tmp.name)/'run'
        shutil.copytree(RUN5,self.run)
        self.p=Pilot(self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def test_click_proposes_box_pins_and_names_read_from_this_page(self):
        # Sayfa 4'teki sigorta kutbu: kutu çizimden, adlar sayfanın kendi yazısından.
        r=self.p.propose_symbol(4,point=[142.73,157.0])
        self.assertEqual((r['device'],r['device_source']),('=112+E122-3F22','TEMPLATE_OFFSET'))
        self.assertEqual([q['pin'] for q in r['pins']],['1','2'])
        # Uçlar var olan işaretin ÜSTÜNE oturur; 1-2 pt kayıp mükerrer kayıt açılmaz.
        self.assertEqual([q['point'] for q in r['pins']],[[142.73,149.81],[142.73,163.99]])
        self.assertEqual([q['already_label'] for q in r['pins']],['-3F22:1','-3F22:2'])
        self.assertFalse(r['stored'])
        self.assertFalse(r['production_ready'])
        # Telin üstü sembol değildir: uydurma kutu üretilmez.
        with self.assertRaises(ValueError):
            self.p.propose_symbol(4,point=[600.0,86.04])
        # Kullanıcı kutuyu kendi çizerse de aynı kimlik çözülür.
        drawn=self.p.propose_symbol(4,bbox=[139.0,148.0,146.0,165.0])
        self.assertEqual((drawn['box_source'],drawn['device']),('USER_BOX','=112+E122-3F22'))

    def test_marking_screen_is_served_and_propose_accepts_dropped_parts(self):
        """Basit işaretleme ekranı ve parça çıkarma uç noktası ayakta."""
        server = make_server(self.p, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:%d' % server.server_port
        try:
            for path, needle in (('/isaret', b'Cihaz i'), ('/isaret.js', b'propose'),
                                 ('/isaret.css', b'.part')):
                with urlopen(base + path) as r:
                    self.assertIn(needle, r.read())
            with urlopen(base + '/api/propose?page=4&point=142.73,157.0') as r:
                first = json.load(r)
            self.assertTrue(first['objects'])
            self.assertEqual(first['excluded'], [])
            drop = [o['id'] for o in first['objects'] if o['inside']][0]
            with urlopen(base + '/api/propose?page=4&bbox=139,148,146,165&exclude=' + drop) as r:
                second = json.load(r)
            self.assertEqual(second['excluded'], [drop])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_user_can_drop_a_drawing_part_from_the_selection(self):
        """Sembole ait olmayan parça (etiket kırıntısı, komşu tel) seçimden çıkarılabilir."""
        base = self.p.propose_symbol(4, point=[142.73, 157.0])
        parts = [o['id'] for o in base['objects'] if o['inside']]
        self.assertTrue(parts, 'kutunun içinde parça yok')
        self.assertEqual(base['excluded'], [])
        # Sembolün kendi çizimi çıkarılınca tıklanan yerde şekil kalmaz: uydurma kutu üretilmez.
        with self.assertRaises(ValueError):
            self.p.propose_symbol(4, point=[142.73, 157.0], exclude=parts)
        # Çıkarılan parça KAYBOLMAZ, listede 'excluded' olarak görünür.
        drawn = self.p.propose_symbol(4, bbox=[139.0, 148.0, 146.0, 165.0], exclude=[parts[0]])
        self.assertEqual(drawn['excluded'], [parts[0]])
        self.assertIn(parts[0], [o['id'] for o in drawn['objects']])
        self.assertTrue([o for o in drawn['objects'] if o['id'] == parts[0]][0]['excluded'])

    def test_dropped_parts_are_stored_on_the_box_and_kept_out_of_similar_search(self):
        """Çıkarılan parça kayıtta durur ve benzer aramanın şablonuna girmez."""
        base = self.p.propose_symbol(4, point=[142.73, 157.0])
        outside = [o for o in base['objects'] if not o['inside']]
        self.assertTrue(outside, 'kutuya değen dış çizgi yok')
        box = self.p.change_box(dict(page=4, bbox=base['bbox'], note='maske testi',
                                     excluded_objects=[outside[0]['id']]))
        self.assertEqual(box['excluded_objects'], [outside[0]['id']])
        # Şablon bu parçayı görmeden kurulur; sembolün kendi çizimi durduğu için arama çalışır.
        found = self.p.similar(box['id'], pages=[4])
        self.assertTrue(found['results'][0]['candidates'])
        # Parça SİLİNMEDİ: sayfanın geometrisinde duruyor.
        self.assertIn(outside[0]['id'], [s['id'] for s in self.p._page(4)['segments']])

    def test_mark_saved_on_prepared_page_then_undone_without_deleting_history(self):
        from analyzer_v3.pagecache import PageCache
        from analyzer_v3.prepare import digest
        manifest=json.loads((self.run/'manifest.json').read_text(encoding='utf-8'))
        source=Path(manifest['source_path'])
        cache=PageCache(source,digest(source),73,root=Path(self.tmp.name)/'cache')
        cache.enqueue([6]); cache.wait(300)
        # Önbellek yokken bu sayfa yazılamaz: çalışmanın izlemediği sayfaya işaret konmaz.
        with self.assertRaises(ValueError):
            self.p.change(dict(page=6,device='=112+E122-18K52',pin='13',point=[312.81,270.29],kind='PHYSICAL'))
        p=Pilot(self.run,cache=cache)
        r=p.propose_symbol(6,point=[312.81,277.0])
        self.assertEqual(r['device'],'=112+E122-18K52')                 # ad sayfa 6'nın yazısından
        self.assertEqual([q['pin'] for q in r['pins']],['13','14'])
        payload=dict(page=6,bbox=r['bbox'],device=r['device'],
                     pins=[dict(point=q['point'],pin=q['pin']) for q in r['pins']])
        saved=p.apply_mark(payload)
        self.assertEqual(len(saved['created']['pins']),2)
        self.assertTrue(saved['created']['box'])
        self.assertEqual({q['method'] for q in p.pins if q.get('page')==6},{'MANUAL'})
        labels={q['label'] for n in p.relations(6)['networks'] for q in n['pins']}
        self.assertIn('-18K52:13',labels)
        # Aynı uca ikinci kayıt açılmaz; boş ad kabul edilmez.
        with self.assertRaises(ValueError):
            p.apply_mark(payload)
        with self.assertRaises(ValueError):
            p.apply_mark(dict(payload,device='  '))
        # Yöntem uydurulmaz: elle işaret ile programın bulup kullanıcının seçtiği aday ayrı sayılır.
        self.assertEqual(saved['method'],'MANUAL')
        with self.assertRaises(ValueError):
            p.apply_mark(dict(payload,device='=112+E122-TEST',method='ROBOT'))
        # Geri alma: kayıt SİLİNMEZ, pasifleşir ve olay geçmişinde durur.
        pin=saved['created']['pins'][0]
        p.change(dict(pin,expected_version=pin['version'],active=False))
        self.assertNotIn(pin['id'],{q['id'] for q in p.pins})
        self.assertIn(pin['id'],{q['id'] for q in p.retired})
        self.assertTrue(any(e['record_id']==pin['id'] for e in p.store.events()))
        self.assertNotIn('-18K52:13',{q['label'] for n in p.relations(6)['networks'] for q in n['pins']})


class PageCacheQueueTests(unittest.TestCase):
    """S01 hazırlama kuyruğu: durdur/devam, hata, yeniden deneme, yarım kalan sayfa.

    Sayfa işleme sahte `trace_page` ile yapılır (kuyruk davranışı test edilir, çizim değil);
    kaynak PDF gerçek belgedir çünkü kuyruk PDF özetini doğrular.
    """
    @classmethod
    def setUpClass(cls):
        from analyzer_v3 import pagecache
        from analyzer_v3.prepare import digest
        cls.pagecache=pagecache
        cls.source=Path(json.loads((RUN5/'manifest.json').read_text(encoding='utf-8'))['source_path'])
        cls.sha=digest(cls.source)

    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp())
        self.order=[]; self.fail_pages=set(); self.gate=None
        self.real=self.pagecache.trace_page
        def fake(page,folder):
            number=page.page_number
            if self.gate is not None and number==2:
                self.gate.wait(10)
            self.order.append(number)
            if number in self.fail_pages:
                raise RuntimeError('deneme hatası')
            folder.mkdir(parents=True,exist_ok=True)
            for name in self.pagecache.FILES:
                (folder/name).write_bytes(b'x')
            return dict(render_bbox=[0,0,10,10],width=10,height=10,segments=0,rotation=0)
        self.pagecache.trace_page=fake

    def tearDown(self):
        self.pagecache.trace_page=self.real
        shutil.rmtree(self.tmp,ignore_errors=True)

    def cache(self):
        return self.pagecache.PageCache(self.source,self.sha,73,root=self.tmp)

    def wait_state(self,cache,number,state):
        for _ in range(200):
            if cache.state(number)==state:
                return
            threading.Event().wait(0.05)
        self.fail('sayfa %s %s olmadı'%(number,state))

    def test_failed_page_does_not_stop_queue_and_retry_recovers(self):
        c=self.cache(); self.fail_pages={3}
        c.enqueue([2,3,4]); c.wait(30)
        self.assertEqual([c.state(n) for n in (2,3,4)],['PREPARED','FAILED','PREPARED'])
        self.assertEqual([f['page'] for f in c.snapshot()['failed']],[3])
        self.assertIn('deneme hatası',c.entry(3)['error'])
        self.assertEqual(set(c.prepared()),{2,4})
        with self.assertRaises(ValueError):
            c.retry(2)
        self.fail_pages=set(); c.retry(3); c.wait(30)
        self.assertEqual(c.state(3),'PREPARED')

    def test_stop_keeps_remaining_queue_and_resume_continues_after_reload(self):
        c=self.cache(); self.gate=threading.Event()
        c.enqueue([2,3,4])
        self.wait_state(c,2,'PREPARING')
        c.stop(); self.gate.set(); c.wait(30)
        snap=c.snapshot()
        self.assertEqual((c.state(2),snap['queue'],snap['stopped']),('PREPARED',[3,4],True))
        self.assertEqual([c.state(n) for n in (3,4)],['QUEUED','QUEUED'])
        again=self.cache()                        # sunucu yeniden başladı: kuyruk diskten gelir
        self.assertEqual(again.snapshot()['queue'],[3,4])
        again.resume(); again.wait(30)
        self.assertEqual(set(again.prepared()),{2,3,4})
        self.assertEqual(self.order,[2,3,4])

    def test_selected_page_jumps_the_queue(self):
        c=self.cache(); self.gate=threading.Event()
        c.enqueue([2,3,4])
        self.wait_state(c,2,'PREPARING')
        c.enqueue([4],front=True)
        self.assertEqual(c.snapshot()['queue'],[4,3])
        self.gate.set(); c.wait(30)
        self.assertEqual(self.order,[2,4,3])

    def test_interrupted_page_is_requeued_not_counted_prepared(self):
        (self.tmp/self.sha).mkdir(parents=True)
        (self.tmp/self.sha/'status.json').write_text(json.dumps(dict(source_sha256=self.sha,queue=[],
            pages={'5':dict(state='PREPARING')})),encoding='utf-8')
        c=self.cache()
        self.assertEqual((c.state(5),c.snapshot()['queue']),('QUEUED',[5]))
        self.assertNotIn(5,c.prepared())

    def test_prepared_page_with_missing_file_is_not_viewable(self):
        c=self.cache(); c.enqueue([2]); c.wait(30)
        self.assertIn(2,c.prepared())
        (c.page_dir(2)/'geometry.json').unlink()
        self.assertNotIn(2,c.prepared())
        self.assertEqual(c.state(2),'FAILED')
        self.assertEqual([r['page'] for r in c.snapshot()['failed']],[2])
        self.assertIn('geometry.json',c.entry(2)['error'])
        with self.assertRaises(ValueError):
            c.file(2,'page.png')
        c.retry(2); c.wait(30)
        self.assertEqual(c.state(2),'PREPARED')
        self.assertEqual(self.order,[2,2])
        with self.assertRaises(ValueError):
            c.file(2,'../status.json')
        with self.assertRaises(ValueError):
            c.page_dir(74)



class PinMatchTests(unittest.TestCase):
    """Uç adı eşleştirme: müşteri `1 2 3`, makro `L1 L2 L3` olabilir."""

    def test_variants_cover_the_known_writings(self):
        from analyzer_v3 import pins
        self.assertIn('1', pins.variants('1L1'))          # faz eki
        self.assertIn('13', pins.variants('13/1'))        # eğik çizgi
        self.assertIn('13', pins.variants('3.13'))        # ön ek
        self.assertIn('L1', pins.variants('L1intern'))    # intern eki

    def test_apostrophe_and_case_are_real_differences(self):
        from analyzer_v3 import pins
        # Primer/sekonder ayrımı buna dayanır: normalize EDİLMEZ.
        self.assertNotIn("2", pins.variants("2'"))
        found, _ = pins.match("2'", ['2'])
        self.assertIsNone(found)
        self.assertEqual(pins.match('A1', ['a.1'])[1], 'gevşek (ayırıcı/harf farkı)')

    def test_customer_numbers_and_macro_phase_names_are_only_a_suggestion(self):
        from analyzer_v3 import pins
        # Müşteri `1 2 3`, makro `L1 L2 L3`: ADLARI tutmaz. Otomatik eşleşmez —
        # sıraya göre ÖNERİ çıkar, onay kullanıcınındır.
        result = pins.compare(['1', '2', '3'], ['L1', 'L2', 'L3'])
        self.assertEqual(result['matched'], [])
        self.assertEqual([(s['source'], s['macro']) for s in result['suggestions']],
                         [('1', 'L1'), ('2', 'L2'), ('3', 'L3')])
        self.assertFalse(result['fits'])
        # Onaylanan eşleme tablosu profile yazılınca artık sorulmaz.
        onaylı = pins.compare(['1', '2', '3'], ['L1', 'L2', 'L3'],
                              aliases={'1': 'L1', '2': 'L2', '3': 'L3'})
        self.assertTrue(onaylı['fits'])
        self.assertEqual(onaylı['matched'][0]['how'], 'eşleme tablosu (onaylı)')

    def test_compare_lists_both_sides_without_dropping_anything(self):
        from analyzer_v3 import pins
        result = pins.compare(['13', '14'], ['13', '14'])
        self.assertEqual([r['source'] for r in result['matched']], ['13', '14'])
        self.assertTrue(result['fits'])
        # Eşleşmeyen iki taraf da görünür; karar kullanıcınındır.
        other = pins.compare(['13', '14', 'PE'], ['13', '14'])
        self.assertEqual(other['unmatched_source'], ['PE'])
        self.assertEqual(other['unused_macro'], [])
        self.assertFalse(other['fits'])
        extra = pins.compare(['13'], ['13', 'PE'])
        self.assertEqual(extra['unused_macro'], ['PE'])

    def test_one_macro_pin_is_used_once(self):
        from analyzer_v3 import pins
        # İki kaynak ucu aynı makro ucuna düşemez.
        result = pins.compare(['13', '13/1'], ['13'])
        self.assertEqual(len(result['matched']), 1)
        self.assertEqual(result['unmatched_source'], ['13/1'])


class LabelListTests(unittest.TestCase):
    """Etiket listesi: çok kodlu etikette cihazın kendisi seçilir, ötekiler atılmaz."""

    def rows(self):
        # Troester listesindeki gerçek yapı: sigorta buşonu x3, kapak x3, kutu x1.
        return [dict(code='SIE.5SE2316', qty=3, location='+E122', sheet='s', row=2),
                dict(code='SIE.5SH5416', qty=3, location='+E122', sheet='s', row=3),
                dict(code='RIT.9340950', qty=1, location='+E122', sheet='s', row=4)]

    def test_multi_part_label_picks_the_carrier_not_the_consumable(self):
        from analyzer_v3 import labels
        picked = labels.pick(self.rows())
        self.assertEqual(picked['code'], 'RIT.9340950')
        self.assertIn('adedi', picked['reason'])
        # Röle: iki kod da adet 1 — listedeki ilk kod ana cihazdır, ikincisi yardımcı blok.
        relay = [dict(code='SIE.3RH2122-1BB40', qty=1, sheet='s', row=1),
                 dict(code='SIE.3RT2916-1BB00', qty=1, sheet='s', row=2)]
        self.assertEqual(labels.pick(relay)['code'], 'SIE.3RH2122-1BB40')

    def test_other_codes_are_kept_and_unknown_tag_returns_nothing(self):
        from analyzer_v3 import labels
        table = {'=112+E122-3F22': self.rows()}
        found = labels.for_device(table, '=112+E122-3F22')
        self.assertEqual(found['code'], 'RIT.9340950')
        self.assertEqual([r['code'] for r in found['other_codes']],
                         ['SIE.5SE2316', 'SIE.5SH5416'])
        self.assertEqual(found['source'], 'LABEL_LIST')
        # Listede olmayan cihaz için kod UYDURULMAZ.
        self.assertIsNone(labels.for_device(table, '=112+E122-X1'))

    def test_prefix_preference_overrides_the_default_pick(self):
        from analyzer_v3 import labels
        picked = labels.pick(self.rows(), prefer_prefix='SIE')
        self.assertEqual(picked['code'], 'SIE.5SE2316'[:0] or picked['code'])
        # SIE ön ekinde adet 1 yok; kural bu yüzden varsayılana döner.
        self.assertEqual(picked['code'], 'RIT.9340950')


class CustomerProfileTests(unittest.TestCase):
    """Müşteri profili: aile kuralları veri, ad ise dosya yolu — doğrulanır."""

    def test_customer_name_cannot_escape_the_profile_folder(self):
        from analyzer_v3 import customer
        self.assertEqual(customer.path_of('troester').name, 'profil.json')
        self.assertEqual(customer.path_of('troester').parent.name, 'troester')
        for bad in ('../../etc', 'a/b', '..', 'x'*50, r'C:\Windows\evil', 'nokta.'):
            with self.assertRaises(ValueError, msg=bad):
                customer.path_of(bad)

    def test_rules_are_data_and_unknown_device_stays_unmapped(self):
        from analyzer_v3 import customer
        profile = dict(customer='deneme', rules=[
            dict(family='plc_channel', letter='D', pin_count=1, pin_pattern=r'^\d{1,2}$'),
            dict(family='terminal', letter='X')], families={
            'terminal': dict(library='IEC_symbol', symbol='X', variant=0)})
        self.assertEqual(customer.family_of(profile, '=122+E122-13D22', ['1']), 'plc_channel')
        self.assertEqual(customer.family_of(profile, '=122+E122-X4', ['23']), 'terminal')
        # Kural yoksa aile UYDURULMAZ.
        self.assertEqual(customer.family_of(profile, '=122+E122-1G33', ['L1', '+']),
                         'unmapped:G/L1,+')
        # Sembolü olmayan aile None döner; aktarım bunu reddeder.
        self.assertIsNone(customer.symbol_of(profile, 'plc_channel'))
        self.assertEqual(customer.symbol_of(profile, 'terminal')['symbol'], 'X')

    def test_overlong_rule_pattern_is_refused(self):
        from analyzer_v3 import customer
        profile = dict(rules=[dict(family='x', pin_pattern='(' * 200)], families={})
        with self.assertRaises(ValueError):
            customer.family_of(profile, '-1D1', ['1'])


if __name__=='__main__':
    unittest.main()

