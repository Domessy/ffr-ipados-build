#!/usr/bin/env python3
"""Recover complete v9 app entries from a truncated private transfer.

Copies compressed bytes verbatim, checks every retained file's decoded CRC,
then supplies a new ZIP directory. Incomplete entries are never included.
This produces an unwarmed checkpoint, never a validated final delivery.
"""
import argparse
import binascii
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import tempfile
import zipfile
import zlib
try:
    from .oot2_ipad_aot import inspect_ipa
    from .oot2_local_bundle import validate_zip_headers
    from .oot2_prepare_ipad_v9 import CHAIN
except ImportError:
    from oot2_ipad_aot import inspect_ipa
    from oot2_local_bundle import validate_zip_headers
    from oot2_prepare_ipad_v9 import CHAIN
MAX32=0xffffffff

def recover(source, output):
    source,output=Path(source),Path(output)
    if source.is_symlink() or not source.is_file() or output.exists() or output.is_symlink():raise ValueError('recovery input/output')
    entries=[];total=0;end=0;info=None;limit=source.stat().st_size
    with source.open('rb') as f:
        while f.tell()+30<=limit:
            offset=f.tell();header=f.read(30)
            if header[:4]!=b'PK\x03\x04':break
            sig,v,flags,method,tm,date,crc,packed,size,nl,el=struct.unpack('<4s5H3I2H',header)
            name=f.read(nl);extra=f.read(el);label=name.decode('utf-8' if flags&0x800 else 'cp437')
            if flags&9 or method not in (0,8) or not label.startswith('Payload/') or '..' in Path(label).parts or '\\' in label:raise ValueError('recovery ZIP member')
            pos=0;zip64=[]
            while pos<len(extra):
                if pos+4>len(extra):raise ValueError('recovery extra')
                kind,n=struct.unpack_from('<HH',extra,pos);data=extra[pos+4:pos+4+n];pos+=4+n
                if len(data)!=n:raise ValueError('recovery extra size')
                if kind==1:zip64.append(data)
            if len(zip64)>1:raise ValueError('recovery duplicate ZIP64')
            data=zip64[0] if zip64 else b''
            for field in ('size','packed'):
                value=size if field=='size' else packed
                if value==MAX32:
                    if len(data)<8:raise ValueError('recovery ZIP64')
                    value,=struct.unpack_from('<Q',data);data=data[8:]
                    if field=='size':size=value
                    else:packed=value
            if f.tell()+packed>limit:break
            if size>16<<30 or total+size>32<<30 or len(entries)>=10000:raise ValueError('recovery bounds')
            dec=zlib.decompressobj(-15) if method==8 else None
            left=packed;actual=0;check=0;small=bytearray() if label.endswith('.app/Info.plist') else None
            def consume(block):
                nonlocal actual,check
                actual+=len(block)
                if actual>size:raise ValueError('recovery decoded size')
                check=binascii.crc32(block,check)
                if small is not None:
                    if actual>1<<20:raise ValueError('recovery plist bound')
                    small.extend(block)
            while left:
                raw=f.read(min(left,1<<20));left-=len(raw)
                if not raw:raise ValueError('recovery source truncated')
                if dec:
                    consume(dec.decompress(raw,8<<20))
                    while dec.unconsumed_tail:consume(dec.decompress(dec.unconsumed_tail,8<<20))
                else:consume(raw)
            if dec:
                consume(dec.flush())
                if not dec.eof or dec.unused_data:raise ValueError('recovery deflate framing')
            if actual!=size or check!=crc:raise ValueError('recovery CRC')
            if small is not None:
                if info is not None:raise ValueError('recovery app count')
                info=(label[:-len('Info.plist')],plistlib.loads(small))
            entries.append((name,v,flags,method,tm,date,crc,packed,size,offset));total+=size;end=f.tell()
    if info is None:raise ValueError('recovery app info missing')
    prefix,plist=info;exe=prefix+plist['CFBundleExecutable']
    if plist.get('CFBundleIdentifier')!='org.nxnative.0400486024dec000':raise ValueError('recovery title')
    fd,temp=tempfile.mkstemp(prefix='.v9-recovery-',dir=output.parent)
    try:
        with os.fdopen(fd,'wb') as dst, source.open('rb') as src:
            left=end
            while left:
                block=src.read(min(left,8<<20));dst.write(block);left-=len(block)
            directory=dst.tell()
            for name,v,flags,method,tm,date,crc,packed,size,offset in entries:
                ext=b'';values=[]
                for n in (size,packed,offset):
                    if n>=MAX32:values.append(n)
                if values:ext=struct.pack('<HH',1,8*len(values))+struct.pack('<'+'Q'*len(values),*values)
                label=name.decode('utf-8' if flags&0x800 else 'cp437');isdir=label.endswith('/')
                mode=(stat.S_IFDIR|0o755) if isdir else stat.S_IFREG|(0o755 if label==exe else 0o644)
                dst.write(struct.pack('<4s6H3I5H2I',b'PK\x01\x02',0x032d,max(v,45 if ext else v),flags,method,tm,date,crc,min(packed,MAX32),min(size,MAX32),len(name),len(ext),0,0,0,(mode<<16)|(16 if isdir else 0),min(offset,MAX32)))
                dst.write(name);dst.write(ext)
            length=dst.tell()-directory;count=len(entries)
            if count>=65535 or directory>=MAX32 or length>=MAX32:
                zoff=dst.tell();dst.write(struct.pack('<4sQ2H2I4Q',b'PK\x06\x06',44,45,45,0,0,count,count,length,directory));dst.write(struct.pack('<4sIQI',b'PK\x06\x07',0,zoff,1))
            dst.write(struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,min(count,65535),min(count,65535),min(length,MAX32),min(directory,MAX32),0));dst.flush();os.fsync(dst.fileno())
        validate_zip_headers(temp);inspect_ipa(temp,expected_chain=CHAIN)
        with zipfile.ZipFile(temp) as z:
            if z.read(exe)[:8]!=bytes.fromhex('cffaedfe0c000001'):raise ValueError('recovery ARM64 host')
        os.link(temp,output)
    finally:Path(temp).unlink(missing_ok=True)
    return {'chain':CHAIN,'entries':len(entries),'decoded_bytes':total,'retained_source_bytes':end,'source_bytes':limit,'checkpoint_bytes':output.stat().st_size,'fullwarm_validated':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(recover(a.source,a.output),sort_keys=True))
