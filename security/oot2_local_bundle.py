#!/usr/bin/env python3
"""Complete the unsigned OOT2 IPA on CachyOS from a validated slim app and RomFS.

No signing, device access or modification of original inputs. Identity follows
nxnative dm/tools/romfs_image.py (size + FNV-1a header/index); full image SHA256
binds the local prepared input. The app's executable and resources stay byte exact.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import tempfile
import time
import zipfile

TITLE = '0400486024DEC000'
BUNDLE_ID = 'org.nxnative.0400486024dec000'


def identity(path):
    size = path.stat().st_size
    with path.open('rb') as f:
        head = f.read(32)
        if len(head) != 32: raise ValueError('RomFS header')
        magic, offset, length, _ = struct.unpack('<8sQQQ', head)
        if magic != b'DMROMFS1' or offset < 32 or offset > size or length != size-offset:
            raise ValueError('RomFS incomplete')
        value = 0xcbf29ce484222325
        def mix(data):
            nonlocal value
            for (word,) in struct.iter_unpack('<Q', data):
                value = ((value ^ word)*0x100000001b3) & ((1<<64)-1)
        mix(head); f.seek(offset)
        left = length
        while left:
            block=f.read(min(left, 8<<20))
            if not block: raise ValueError('RomFS truncated index')
            left-=len(block)
            if not left: block+=b'\0'*((-len(block))%8)
            mix(block)
    return size, f'{value:016x}'


def parse_identity(data):
    parts=data.decode('ascii').strip().split()
    if not parts or parts[0] != 'DMROMFSID1': raise ValueError('RomFS identity format')
    fields=dict(x.split('=',1) for x in parts[1:])
    if fields.get('title') != TITLE: raise ValueError('RomFS title')
    return int(fields['size']), fields['index']


def regular(path):
    if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file():
        raise ValueError('local bundle input path')


def extra_fields(data):
    while data:
        if len(data) < 4: raise ValueError('ZIP extra field truncated')
        kind, size = struct.unpack_from('<HH', data)
        if len(data) < 4 + size: raise ValueError('ZIP extra field truncated')
        yield kind, data[4:4+size]
        data = data[4+size:]


def validate_zip_headers(path):
    """Independent local/central checks: Python's reader tolerates stale ZIP64 sizes."""
    with zipfile.ZipFile(path) as archive, open(path, 'rb') as raw:
        for member in archive.infolist():
            fields = list(extra_fields(member.extra))
            if sum(kind == 1 for kind, _ in fields) > 1:
                raise ValueError('ZIP duplicate central ZIP64 fields')
            raw.seek(member.header_offset)
            header = raw.read(30)
            if len(header) != 30: raise ValueError('ZIP local header truncated')
            sig, version, flags, method, tm, date, crc, packed, size, nlen, elen = struct.unpack('<4s5H3I2H', header)
            if sig != b'PK\x03\x04' or flags & 9 or flags != member.flag_bits or method != member.compress_type:
                raise ValueError('ZIP local header flags or method')
            name, extra = raw.read(nlen), raw.read(elen)
            if name.decode('utf-8' if flags & 0x800 else 'cp437') != member.filename:
                raise ValueError('ZIP local member name')
            zip64 = [value for kind, value in extra_fields(extra) if kind == 1]
            if len(zip64) > 1: raise ValueError('ZIP duplicate local ZIP64 fields')
            if size == 0xffffffff or packed == 0xffffffff:
                values = zip64[0] if zip64 else b''
                if size == 0xffffffff:
                    if len(values) < 8: raise ValueError('ZIP local ZIP64 size missing')
                    size, = struct.unpack_from('<Q', values); values = values[8:]
                if packed == 0xffffffff:
                    if len(values) < 8: raise ValueError('ZIP local ZIP64 compressed size missing')
                    packed, = struct.unpack_from('<Q', values)
            if (size, packed, crc) != (member.file_size, member.compress_size, member.CRC):
                raise ValueError('ZIP local/central sizes or CRC differ')


def bundle(slim, romfs, manifest, output, expected_chain=None):
    slim,romfs,manifest,output=map(Path,(slim,romfs,manifest,output))
    for p in (slim,romfs,manifest): regular(p)
    if output in (slim,romfs,manifest) or output.is_symlink() or output.parent.is_symlink():
        raise ValueError('local bundle output')
    meta=json.loads(manifest.read_text())
    actual=identity(romfs)
    if list(actual) != meta['identity'] or romfs.stat().st_size != meta['bytes']:
        raise ValueError('local RomFS identity changed')
    with zipfile.ZipFile(slim) as src:
        names=src.namelist()
        if len(names)!=len(set(names)) or len(names)>10000: raise ValueError('IPA duplicate or excessive members')
        infos=[n for n in names if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/')==2]
        if len(infos)!=1: raise ValueError('IPA app layout')
        prefix=infos[0][:-len('Info.plist')]
        for z in src.infolist():
            if ((not z.filename.startswith(prefix) and not (z.is_dir() and prefix.startswith(z.filename))) or '..' in Path(z.filename).parts
                or '\\' in z.filename or z.flag_bits&1
                or stat.S_ISLNK(z.external_attr>>16)):
                raise ValueError('IPA member path')
        if expected_chain is not None and prefix+'msl/b-'+expected_chain+'.img' not in names:
            raise ValueError('IPA shader chain')
        if prefix+'romfs.img' in names: raise ValueError('IPA already bundled')
        info=plistlib.loads(src.read(infos[0]))
        if info.get('CFBundleIdentifier') != BUNDLE_ID: raise ValueError('IPA bundle identity')
        executable=prefix+info['CFBundleExecutable']
        if executable not in names or src.getinfo(executable).file_size==0: raise ValueError('IPA executable')
        if parse_identity(src.read(prefix+'romfs.id')) != actual: raise ValueError('slim IPA needs another RomFS')
        fd,temp=tempfile.mkstemp(prefix='.oot2-bundle-',suffix='.ipa',dir=output.parent)
        os.close(fd)
        digest=hashlib.sha256()
        try:
            print('OOT2 local assembly: copying compiled app resources.', flush=True)
            with zipfile.ZipFile(temp,'w',allowZip64=True) as dst:
                for z in src.infolist():
                    target = copy.copy(z)
                    # Sizes/offsets belong to this new archive, not the source's ZIP64 extra.
                    target.extra = b''.join(struct.pack('<HH', kind, len(value)) + value
                                            for kind, value in extra_fields(z.extra) if kind != 1)
                    with src.open(z) as inp, dst.open(target,'w',force_zip64=True) as out:
                        shutil.copyfileobj(inp,out,1<<20)
                z=zipfile.ZipInfo(prefix+'romfs.img'); z.compress_type=zipfile.ZIP_STORED
                z.external_attr=(stat.S_IFREG|0o644)<<16
                with romfs.open('rb') as inp, dst.open(z,'w',force_zip64=True) as out:
                    done=0; report=time.monotonic()+10
                    while block:=inp.read(8<<20):
                        out.write(block); digest.update(block); done+=len(block)
                        if time.monotonic()>=report:
                            print(f'OOT2 local assembly: {done/1024**3:.2f}/{actual[0]/1024**3:.2f} GiB ({100*done/actual[0]:.1f}%)',flush=True)
                            report=time.monotonic()+10
            if digest.hexdigest()!=meta['sha256']: raise ValueError('RomFS bytes changed')
            with zipfile.ZipFile(temp) as check:
                if check.getinfo(prefix+'romfs.img').file_size!=actual[0] or len(check.infolist())!=len(names)+1:
                    raise ValueError('completed IPA directory differs')
            validate_zip_headers(temp)
            os.chmod(temp,0o600)
            with open(temp,'rb') as f: os.fsync(f.fileno())
            os.replace(temp,output)
            print('OOT2 local assembly: 100%; complete archive published.',flush=True)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    return {'ipa_bytes':output.stat().st_size,'romfs_bytes':actual[0],
            'compiled_resources_copied_exactly':True,'romfs_sha256':digest.hexdigest(),
            'signing_performed':False,'device_changed':False}
