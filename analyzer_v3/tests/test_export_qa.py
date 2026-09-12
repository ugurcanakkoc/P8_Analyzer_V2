"""Synthetic contract/negative tests. Not PDF truth and not an EPLAN runtime test."""
import copy
import unittest

from analyzer_v3 import eplan_export as x


class ExportValidationTests(unittest.TestCase):
    def setUp(self):
        self.pkg = dict(document_sha256='source', payload_sha256='payload', pages=[dict(
            physical_page=4, objects=[dict(id='f', kind='DEVICE', family='fuse_1pole',
                device_tag='=112+E122-F1', pins=[dict(name='1', point_mm=[10,20])]),
                dict(id='x', kind='DEVICE', family='terminal', device_tag='=112+E122-X1',
                     terminal='4', pins=[dict(name='4', point_mm=[10,40])])])],
            expected_links=[dict(page=4, a='f#1', b='x#4')])
        self.rb = dict(contract='uvp.pdf2p8.readback', contract_version='1.0',
            document_sha256='source', package_sha256='payload', import_ok=True,
            pages=[dict(physical_page=4, functions=[
                dict(name='=112+E122-F1', pins=[dict(name='1', location=[10,20])]),
                dict(name='=112+E122-X1:4', pins=[dict(name='4', location=[10,40])])])],
            interruption_points=[], connections=[dict(physical_page=4,
                start=dict(function='=112+E122-F1', pin='1', location=[10,20]),
                end=dict(function='=112+E122-X1:4', pin='4', location=[10,40]))])

    def test_complete_means_only_declared_local_fixture_not_document_accuracy(self):
        result = x.compare(self.pkg, self.rb)
        self.assertTrue(result['complete'])
        self.assertEqual(result['verification_scope'],'DECLARED_LOCAL_LINKS_AND_PIN_INVENTORY')

    def test_missing_blank_and_wrong_pin_identity_never_pass(self):
        for value in (None, '', '9'):
            with self.subTest(pin=value):
                rb = copy.deepcopy(self.rb)
                rb['connections'][0]['start'].update(pin=value, function='WRONG')
                result = x.compare(self.pkg, rb)
                self.assertFalse(result['complete'])
                self.assertEqual(result['found'],0)
        del rb['connections'][0]['start']['pin']
        self.assertFalse(x.compare(self.pkg, rb)['complete'])

    def test_matching_lines_without_pin_inventory_do_not_pass(self):
        self.rb['pages'] = []
        result = x.compare(self.pkg, self.rb)
        self.assertTrue(result['local_geometry_complete'])
        self.assertFalse(result['identity_complete'])
        self.assertFalse(result['complete'])

    def test_source_and_host_result_must_match(self):
        for field in ('document_sha256', 'package_sha256', 'contract', 'import_ok'):
            rb = copy.deepcopy(self.rb)
            del rb[field]
            self.assertFalse(x.compare(self.pkg, rb)['complete'], field)

    def test_local_connections_are_not_cross_page_proof(self):
        self.pkg['pages'][0]['objects'].append(dict(id='ip', kind='INTERRUPTION',
            name='L1', point_mm=[50,50]))
        result = x.compare(self.pkg, self.rb)
        self.assertTrue(result['local_geometry_complete'])
        self.assertFalse(result['complete'])
        self.assertTrue(any('PARTNER' in s for s in result['evidence_issues']))

    def test_nonfinite_and_malformed_positions_are_reported_not_accepted(self):
        for value in ([float('nan'),20], [10,float('inf')], [10], '10,20', None):
            self.rb['connections'][0]['start']['location'] = value
            self.assertFalse(x.compare(self.pkg, self.rb)['complete'])

    def test_inventory_pin_displaced_from_expected_location_fails(self):
        self.rb['pages'][0]['functions'][0]['pins'][0]['location'] = [10,23]
        self.assertFalse(x.compare(self.pkg, self.rb)['complete'])

    def test_duplicate_inventory_pin_is_not_hidden(self):
        self.rb['pages'][0]['functions'].append(copy.deepcopy(self.rb['pages'][0]['functions'][0]))
        self.assertFalse(x.compare(self.pkg, self.rb)['complete'])

    def test_empty_package_does_not_pass(self):
        self.pkg['expected_links'] = []
        self.rb['connections'] = []
        self.assertFalse(x.compare(self.pkg, self.rb)['complete'])


class SourceRouteTests(unittest.TestCase):
    def test_two_junctions_preserve_own_drops_not_star_from_first(self):
        net = dict(id='P24',potential='P24',edges=[[0,10,10,10], [10,10,20,10],
            [20,10,30,10], [10,10,10,30], [20,10,20,40]])
        anchors = dict(left=[0,10], j1=[10,10], j2=[20,10], right=[30,10],
                       pin1=[10,30], pin2=[20,40])
        links, issues = x._drawn_links(net, anchors,4,100)
        pairs = {frozenset((r['a'],r['b'])) for r in links}
        self.assertEqual(len(links),5)
        self.assertEqual(issues,[])
        self.assertIn(frozenset(('j2','pin2')),pairs)
        self.assertNotIn(frozenset(('j1','pin2')),pairs)

    def test_bent_wire_preserves_corner(self):
        net = dict(id='n', edges=[[0,0,10,0],[10,0,10,20]])
        links, issues = x._drawn_links(net, {'a':[0,0],'b':[10,20]},4,100)
        self.assertEqual(issues,[])
        self.assertEqual(links[0]['polyline_pt'],[[0,0],[10,0],[10,20]])

    def test_gap_not_bridged_by_same_network_membership(self):
        net = dict(id='n', edges=[[0,0,10,0],[12,0,20,0]])
        links, issues = x._drawn_links(net, {'a':[0,0],'b':[20,0]},4,100)
        self.assertEqual(links,[])
        self.assertTrue(issues)

    def test_unmarked_branch_cannot_be_guessed_as_daisy_chain(self):
        net = dict(id='n',edges=[[0,0,10,0],[10,0,20,0],[10,0,10,20]])
        links, issues = x._drawn_links(net, {'a':[0,0],'b':[20,0],'c':[10,20]},4,100)
        self.assertEqual(links,[])
        self.assertTrue(issues)

    def test_potential_name_does_not_join_unrelated_continuations(self):
        def end(identity, ref, target, opposite):
            return dict(id=identity,kind='INTERRUPTION',name='L1',reference=ref,
                        target_page=target,target_reference=opposite,verified=True)
        first, second, external = end('a','/4.11',5,'/3.19'), end('b','/3.19',4,'/4.11'), end('c','/5.11',6,'/4.19')
        body = dict(document_sha256='source', pages=[dict(physical_page=4,objects=[first]),
                                                     dict(physical_page=5,objects=[second,external])])
        x._continuation_ids(body)
        self.assertEqual(first['import_name'], second['import_name'])
        self.assertNotEqual(first['import_name'], external['import_name'])
        self.assertFalse(external['partner_in_package'])
        self.assertEqual(len(body['expected_continuations']),1)


if __name__ == '__main__':
    unittest.main()
