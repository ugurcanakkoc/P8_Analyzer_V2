import json
import shutil
import unittest

from analyzer_v3 import customer, layout

TEMPLATE = dict(frame='T',
                rows=[dict(label='Sigorta, MKŞ', y=248.0), dict(label="PLC IO'ları", y=240.0),
                      dict(label='Kontak, Sensör', y=212.0), dict(label="PLC IO'ları", y=72.0)],
                rails={'L1': 284.0}, area=dict(x0=42, x1=384, y0=16, y1=292),
                columns=dict(pitch=40, lines=[52, 92, 132]), pin_marks=[dict(y=236, xs=[84, 124])])
PLC = dict(symbol='PLC_CBOX', box_half_mm=4, facing_by_io={'input': 'Up', 'output': 'Down'},
           template_row_by_io={'output': "PLC IO'ları#1", 'input': "PLC IO'ları#2"})
PROFILE = dict(families=dict(fuse_1pole=dict(symbol='F1', template_row='Sigorta, MKŞ'),
                             contact_no=dict(symbol='S', template_row='Kontak, Sensör'),
                             plc_channel=PLC, tnode_down=dict(symbol='TLRU')),
               plc_io_by_part={'DI': 'input', 'DQ': 'output'})


def device(oid, family, pins, part=None):
    return dict(id=oid, kind='DEVICE', family=family, part_number=part, device_tag='-' + oid,
                pins=[dict(name=name, point_mm=list(xy)) for name, xy in pins])


def junction(oid, xy):
    return dict(id=oid, kind='JUNCTION', family='tnode_down', point_mm=list(xy))


class TemplateLayoutTests(unittest.TestCase):
    def test_second_row_with_same_name_is_counted_from_top(self):
        self.assertEqual(layout.row_y(TEMPLATE, "PLC IO'ları#2"), 72.0)
        self.assertIsNone(layout.row_y(TEMPLATE, "PLC IO'ları#3"))

    def test_device_centre_sits_on_its_row_and_page_snaps_to_columns(self):
        fuse = device('F1', 'fuse_1pole', [('1', (50.35, 238.8)), ('2', (50.35, 226.8))])
        report = layout.apply([fuse], [], TEMPLATE, PROFILE)
        self.assertEqual([p['point_mm'] for p in fuse['pins']], [[52.0, 254.0], [52.0, 242.0]])
        self.assertEqual(fuse['pins'][0]['source_point_mm'], [50.35, 238.8])
        self.assertEqual(report['dx_mm'], 1.65)

    def test_plc_box_centres_on_io_row_with_pin_on_facing_edge(self):
        di = device('DI1', 'plc_channel', [('1', (70.35, 209.0))], part='DI')
        dq = device('DQ1', 'plc_channel', [('1', (110.35, 209.0))], part='DQ')
        layout.apply([di, dq], [], TEMPLATE, PROFILE)
        self.assertEqual(di['pins'][0]['point_mm'], [84.0, 76.0])     # alt satır 72, uç yukarıda
        self.assertEqual(dq['pins'][0]['point_mm'], [124.0, 236.0])   # üst satır 240, uç aşağıda
        self.assertEqual((di['io'], dq['io']), ('input', 'output'))

    def test_extra_pin_of_a_box_does_not_vote_for_the_grid(self):
        # İki ek uç (9, 11) oy verseydi kutu başı 74'e kayardı; yalnız kutu başı oy verir.
        first = device('D1', 'plc_channel', [('1', (70.35, 209.0))], part='DQ')
        extras = [device('D%d' % n, 'plc_channel', [(str(n), (x, 209.0))], part='DQ')
                  for n, x in ((9, 80.35), (11, 160.35))]
        for extra in extras:
            extra['pins'][0]['box_role'] = 'extra'
        layout.apply([first] + extras, [], TEMPLATE, PROFILE)
        self.assertEqual(first['pins'][0]['point_mm'][0], 84.0)

    def test_nodes_follow_linked_pin_rail_or_stay(self):
        dq = device('DQ1', 'plc_channel', [('1', (70.35, 209.0))], part='DQ')
        beside = junction('j1', (100.0, 209.0))    # yatay: yeni yüksekliği alır
        below = junction('j2', (70.35, 190.0))     # dik: aynı dy
        rail = junction('j3', (150.0, 255.0))      # L1 barası: şablon barasına
        loose = junction('j4', (200.0, 150.0))     # bağsız: yerinde kalır
        links = [dict(a='DQ1#1', b='j1'), dict(a='DQ1#1', b='j2'), dict(a='j3', b='j5', potential='L1')]
        objects = [dq, beside, below, rail, loose, junction('j5', (300.0, 255.0))]
        report = layout.apply(objects, links, TEMPLATE, PROFILE)
        self.assertEqual(beside['point_mm'], [113.65, 236.0])
        self.assertEqual(below['point_mm'], [84.0, 217.0])
        self.assertEqual(rail['point_mm'][1], 284.0)
        self.assertEqual(loose['point_mm'], [213.65, 150.0])
        self.assertEqual(report['nodes_unresolved'], ['j4'])
        self.assertEqual(links[0]['polyline_mm'], [[84.0, 236.0], [113.65, 236.0]])

    def test_flipped_input_mirrors_offset_and_node_on_pin_sticks(self):
        # Müşteride DI teli aşağı iniyordu; şablonda uç yukarı bakar: tel ucu ucun üstüne aynalanır.
        di = device('DI1', 'plc_channel', [('1', (70.35, 209.0))], part='DI')
        di['pins'][0]['wire_direction'] = 'Down'
        under = junction('j1', (70.35, 190.0))
        on_pin = junction('j2', (70.35, 209.0))    # bağı yok ama tam ucun üstünde
        corner = junction('j3', (40.0, 180.0))     # L biçimli bağ
        links = [dict(a='DI1#1', b='j1'), dict(a='j3', b='DI1#1')]
        report = layout.apply([di, under, on_pin, corner], links, TEMPLATE, PROFILE)
        self.assertEqual(di['pins'][0]['point_mm'], [84.0, 76.0])
        self.assertEqual(under['point_mm'][1], 95.0)
        self.assertEqual(on_pin['point_mm'], [84.0, 76.0])
        self.assertEqual(corner['point_mm'][1], 105.0)
        self.assertEqual(report['nodes_unresolved'], [])

    def test_second_device_in_same_slot_keeps_source_spacing(self):
        top = device('S1', 'contact_no', [('13', (70.0, 200.0)), ('14', (70.0, 188.0))])
        low = device('S2', 'contact_no', [('13', (70.0, 150.0)), ('14', (70.0, 138.0))])
        report = layout.apply([top, low], [], TEMPLATE, PROFILE)
        self.assertEqual(top['pins'][0]['point_mm'][1] - low['pins'][0]['point_mm'][1], 50.0)
        self.assertEqual(report['slot_followers'], 1)

    def test_device_without_row_or_unknown_io_stays_and_is_reported(self):
        unknown = device('D?', 'plc_channel', [('1', (70.35, 209.0))], part='???')
        report = layout.apply([unknown], [], TEMPLATE, PROFILE)
        self.assertEqual(unknown['pins'][0]['point_mm'], [70.35, 209.0])
        self.assertEqual(report['devices_without_row'], ['D?'])

    def test_profile_without_template_has_no_layout(self):
        self.assertIsNone(layout.load(dict(families={})))

    def test_profile_loader_and_saver_keep_layout_keys(self):
        # Ölçüm: load() yalnız rules/families döndürüyordu; şablon hiçbir sayfaya uygulanmadı.
        name = 'zz-test-layout'
        file = customer.path_of(name)
        file.parent.mkdir(parents=True, exist_ok=True)
        try:
            file.write_text(json.dumps(dict(customer=name, families={}, template='T1',
                                            plc_io_by_part={'P': 'input'})), encoding='utf-8')
            loaded = customer.load(name)
            self.assertEqual((loaded['template'], loaded['plc_io_by_part']), ('T1', {'P': 'input'}))
            customer.save(name, [], {}, 'yeniden yazıldı')
            self.assertEqual(customer.load(name)['template'], 'T1')
        finally:
            shutil.rmtree(file.parent, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
