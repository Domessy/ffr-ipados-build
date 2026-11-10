"""Validate bundling with synthetic unsigned apps and exact RomFS identity."""
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from security import oot2_local_bundle as b

class LocalBundleTests(unittest.TestCase):
    def fixture(self, root):
        root=Path(root).resolve(); img=root/'RomFS.img'; data=b'private synthetic data'
        index=b'index bytes'
        img.write_bytes(struct.pack('<8sQQQ',b'DMROMFS1',32+len(data),len(index),1)+data+index)
        ident=b.identity(img)
        meta=root/'romfs.json'; meta.write_text(json.dumps({'bytes':img.stat().st_size,'identity':ident,'sha256':hashlib.sha256(img.read_bytes()).hexdigest()}))
        slim=root/'slim.ipa'; prefix='Payload/DmIOS.app/'
        members={prefix+'Info.plist':plistlib.dumps({'CFBundleIdentifier':b.BUNDLE_ID,'CFBundleExecutable':'DmIOS'}),prefix+'DmIOS':b'unchanged signed executable',prefix+'dm/shaders.img':b'compiled shaders unchanged',prefix+'romfs.id':f'DMROMFSID1 title={b.TITLE} size={ident[0]} index={ident[1]}'.encode()}
        with zipfile.ZipFile(slim,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('Payload/',b''); z.writestr(prefix,b'')
            for n,v in members.items(): z.writestr(n,v)
        return slim,img,meta,root/'full.ipa',members

    def test_all_compiled_inputs_and_romfs_are_byte_exact(self):
        with tempfile.TemporaryDirectory() as t:
            slim,img,meta,output,members=self.fixture(t)
            original=slim.read_bytes(); stats=b.bundle(slim,img,meta,output)
            self.assertFalse(stats['signing_performed'])
            self.assertEqual(slim.read_bytes(),original)
            with zipfile.ZipFile(output) as z:
                self.assertIsNone(z.testzip())
                for n,v in members.items():self.assertEqual(z.read(n),v)
                self.assertEqual(z.read('Payload/DmIOS.app/romfs.img'),img.read_bytes())

    def test_zip64_recompression_has_matching_local_and_central_sizes(self):
        # Exercise ZIP64 without multi-GB fixtures. Source compressed bytes and
        # header offsets change during repacking, so its extra cannot be reused.
        with tempfile.TemporaryDirectory() as t, patch.object(zipfile, 'ZIP64_LIMIT', 64):
            slim,img,meta,output,members=self.fixture(t)
            with zipfile.ZipFile(slim) as z:
                self.assertTrue(any(i.extra for i in z.infolist()))
            b.bundle(slim,img,meta,output)
            b.validate_zip_headers(output)
            with zipfile.ZipFile(output) as z:
                self.assertIsNone(z.testzip())
                for n,v in members.items(): self.assertEqual(z.read(n),v)
                for i in z.infolist():
                    self.assertLessEqual(sum(k == 1 for k,_ in b.extra_fields(i.extra)),1)

    def test_validator_rejects_legacy_repacking_of_zip64_metadata(self):
        with tempfile.TemporaryDirectory() as t, patch.object(zipfile, 'ZIP64_LIMIT', 64):
            slim,_,_,output,_=self.fixture(t)
            with zipfile.ZipFile(slim) as src, zipfile.ZipFile(output,'w') as dst:
                for member in src.infolist():
                    # Previous buggy implementation retained ZIP64 source sizes/offsets.
                    with src.open(member) as inp, dst.open(member,'w',force_zip64=True) as out:
                        out.write(inp.read())
            with self.assertRaisesRegex(ValueError,'ZIP'):
                b.validate_zip_headers(output)

    def test_expected_shader_chain_is_checked_before_publication(self):
        with tempfile.TemporaryDirectory() as t:
            slim,img,meta,output,_=self.fixture(t)
            with self.assertRaisesRegex(ValueError,'shader chain'):
                b.bundle(slim,img,meta,output,expected_chain='bc8830d4ba5a')
            self.assertFalse(output.exists())
            with zipfile.ZipFile(slim,'a') as z:
                z.writestr('Payload/DmIOS.app/msl/b-bc8830d4ba5a.img',b'unchanged compiled image')
            b.bundle(slim,img,meta,output,expected_chain='bc8830d4ba5a')
            b.validate_zip_headers(output)

    def test_wrong_image_and_cut_transfer_preserve_previous_output(self):
        with tempfile.TemporaryDirectory() as t:
            slim,img,meta,output,_=self.fixture(t); output.write_bytes(b'previous IPA')
            d=json.loads(meta.read_text());d['identity'][1]='bad';meta.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'identity'):b.bundle(slim,img,meta,output)
            self.assertEqual(output.read_bytes(),b'previous IPA')
            slim.write_bytes(slim.read_bytes()[:100])
            d['identity']=b.identity(img);meta.write_text(json.dumps(d))
            with self.assertRaises(zipfile.BadZipFile):b.bundle(slim,img,meta,output)
            self.assertEqual(output.read_bytes(),b'previous IPA')

    def test_body_hash_mismatch_does_not_publish(self):
        with tempfile.TemporaryDirectory() as t:
            slim,img,meta,output,_=self.fixture(t)
            data=bytearray(img.read_bytes());data[32]^=1;img.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'bytes changed'):b.bundle(slim,img,meta,output)
            self.assertFalse(output.exists())

    def test_different_slim_identity_and_unsafe_zip_paths_fail(self):
        with tempfile.TemporaryDirectory() as t:
            slim,img,meta,output,_=self.fixture(t)
            with zipfile.ZipFile(slim,'a') as z:z.writestr('../escape',b'bad')
            with self.assertRaisesRegex(ValueError,'member path'):b.bundle(slim,img,meta,output)
            self.assertFalse(output.exists())
