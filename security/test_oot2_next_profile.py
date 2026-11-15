import unittest
from security.oot2_next_profile import validate

class ProfileDeltaTests(unittest.TestCase):
    table='a\tb\tcompute\t1111111111111111\t/x/agl_ndsr.pck#NDSR@0x10\na\tb\tcompute\t2222222222222222\t/x/agl_ndsr_vr.pck#NDSR@0x20\n'
    before=['#define OTHER 1','#define DM_GAME_UPSCALER_KEYS "1111111111111111"','#define DM_GAME_UPSCALER_N 1']
    after=['#define OTHER 1','#define DM_GAME_UPSCALER_KEYS "1111111111111111,2222222222222222"','#define DM_GAME_UPSCALER_N 2']
    def test_only_measured_expansion_allowed(self):
        r=validate(self.before,self.after,self.table);self.assertEqual((r['before_count'],r['after_count']),(1,2))
    def test_other_profile_changes_rejected(self):
        with self.assertRaisesRegex(ValueError,'unrelated'):validate(self.before,['#define OTHER 2']+self.after[1:],self.table)
    def test_unrelated_shader_or_count_rejected(self):
        for lines in (self.after[:-1]+['#define DM_GAME_UPSCALER_N 3'],[self.after[0],self.before[1],self.after[2]]):
            with self.assertRaises(ValueError):validate(self.before,lines,self.table)
    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):validate(self.before,self.after+[self.after[-1]],self.table)
