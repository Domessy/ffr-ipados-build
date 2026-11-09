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
