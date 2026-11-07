import json
import unittest
from security.oot2_memory_report import jetsam, runtime


class MemoryReportTests(unittest.TestCase):
    def test_apple_two_objects_units_and_aggregation(self):
        report = {'memoryStatus': {'pageSize': 16384, 'memoryPages': {'free': 64}},
                  'processes': [{'name': 'LiveContainer', 'reason': 'vm-pageshortage', 'rpages': 128, 'lifetimeMax': 192},
                                {'name': 'MTLCompilerService', 'rpages': 32}, {'name': 'other', 'rpages': 1000}]}
        r = jetsam('{}\n' + json.dumps(report))
        self.assertEqual(r['free_mib'], 1)
        self.assertEqual(r['LiveContainer'][0]['resident_mib'], 2)
        self.assertEqual(r['compiler_resident_mib'], .5)

    def test_pinned_host_mislabels_footprint_as_resident(self):
        r = runtime('memory up to frame 300: resident 3634 MB, GPU allocated 2682 MB')
        self.assertEqual(r['footprint_mib']['peak_sampled'], 3634)
        self.assertNotIn('rss_mib', r)

    def test_numeric_only_new_samples_and_slope(self):
        r = runtime('[oot2-mem] sample=1 frame=300 seconds=100 rss_mib=8 footprint_mib=10 metal_mib=20\n'
                    '[oot2-mem] sample=2 frame=600 seconds=160 rss_mib=9 footprint_mib=15 metal_mib=30 private=SECRET')
        self.assertEqual(r['footprint_mib_per_minute'], 5)
        self.assertNotIn('SECRET', json.dumps(r))

    def test_empty_log_does_not_claim_zero_memory(self):
        self.assertEqual(runtime('nothing')['sample_count'], 0)
        self.assertNotIn('footprint_mib', runtime('nothing'))
