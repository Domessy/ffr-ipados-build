import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from security.oot2_pipeline_cache import inspect_cache, receive_cache


def fixture(path, groups=1, corrupt=False):
    with tarfile.open(path, 'w:gz') as archive:
        for index in range(groups):
            binary = bytes([index + 1]) * 64
            files = {'key': b'a' * 64, 'sha256': (('0' * 64) if corrupt else hashlib.sha256(binary).hexdigest()).encode(), 'applegpu_g17g.mtl4a': binary}
            for name, raw in files.items():
                member = tarfile.TarInfo(f'work/{index:05d}/{name}'); member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))


class PipelineCacheTests(unittest.TestCase):
    def parent(self, root, source):
        class Parent:
            def receive_file(self, name, limit): (root/name).write_bytes(source.read_bytes())
        return Parent()

    def test_empty_and_corrupt_uploads_never_replace_latest(self):
        for groups, corrupt in [(0, False), (1, True)]:
            with self.subTest(groups=groups, corrupt=corrupt), tempfile.TemporaryDirectory() as d:
                root=Path(d); latest=root/'latest'; source=root/'incoming'; fixture(latest); fixture(source,groups,corrupt)
                before=latest.read_bytes()
                with self.assertRaises(ValueError): receive_cache(self.parent(root,source),latest,True)
                self.assertEqual(latest.read_bytes(),before)
                self.assertEqual(len(list(root.glob('.latest.incoming-*'))),1)

    def test_regressing_group_count_never_replaces_latest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); latest=root/'latest'; source=root/'incoming'; fixture(latest,2); fixture(source,1)
            before=latest.read_bytes()
            with self.assertRaisesRegex(ValueError,'lose completed'): receive_cache(self.parent(root,source),latest,True)
            self.assertEqual(latest.read_bytes(),before)

    def test_valid_replacement_keeps_immutable_previous_version(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); latest=root/'latest'; source=root/'incoming'; fixture(latest,1); fixture(source,2)
            before=latest.read_bytes()
            self.assertEqual(receive_cache(self.parent(root,source),latest,True),2)
            self.assertEqual(inspect_cache(latest,True),2)
            previous=list(root.glob('latest.*.previous')); self.assertEqual(len(previous),1)
            self.assertEqual(previous[0].read_bytes(),before)
