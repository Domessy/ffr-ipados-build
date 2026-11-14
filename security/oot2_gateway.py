#!/usr/bin/env python3
"""Title-scoped SSH gateway for ONE original Switch 2 Ocarina NUP.

No Nintendo keys are required for a NUP. No shell command or arbitrary path
is accepted, and output/caches never share another game's workspace.
"""
from pathlib import Path
import json
import re
try:
    from .oot2_nup_info import TITLE, VERSION, SUPER, inspect, selected_romfs_bytes, release_identity, NupInvalid
except ImportError:  # forced-command gateway runs as a standalone script
    from oot2_nup_info import TITLE, VERSION, SUPER, inspect, selected_romfs_bytes, release_identity, NupInvalid

HOME = Path.home()
ROOT = HOME / "portage-ipados" / "oot-switch2"
SOURCE_LINK = ROOT / "source"
CACHE = ROOT / "shader-cache"
CONFLICTS = ROOT / "shader-cache-conflicts"
OUTPUT = ROOT / "resultats"

ROUTES = frozenset({
    "oot2-fullwarm-v8-info", "oot2-fullwarm-v8-read-kit", "oot2-fullwarm-v8-read-cache",
    "oot2-fullwarm-v8-write-cache", "oot2-fullwarm-v8-write-log", "oot2-fullwarm-v8-write-slim",
    "oot2-aot-v8-info", "oot2-aot-v8-read-input", "oot2-aot-v8-read-cache",
    "oot2-aot-v8-write-slim", "oot2-aot-v8-write-cache", "oot2-aot-v8-write-log",
    "oot2-diagnose-v1", "oot2-probe-v1", "oot2-manifest-v1", "oot2-space-v1",
    "oot2-read-nup", "oot2-read-cache", "oot2-write-cache",
    "oot2-write-ipa", "oot2-write-log",
    "oot2-read-metal-snapshot-v1",
    "oot2-metal-snapshot-info-v1",
    "oot2-release-preflight-v1",
    "oot2-read-resume-v5", "oot2-resume-v5-info",
    "oot2-read-resume-v6", "oot2-resume-v6-info",
    "oot2-read-resume-v8", "oot2-resume-v8-info",
    "oot2-write-host-kit-v7", "oot2-write-slim-v7", "oot2-local-bundle-v7-ready",
    "oot2-write-host-kit-v8", "oot2-write-slim-v8", "oot2-local-bundle-v8-ready",
    "oot2-write-host-kit-v1",
    "oot2-write-host-kit-v5", "oot2-write-host-kit-v6", "oot2-write-slim-v6", "oot2-local-bundle-v6-ready",
})


def nup_file():
    documents = (HOME / "Documents").resolve(strict=True)
    if not SOURCE_LINK.is_symlink():
        raise ValueError("source")
    folder = SOURCE_LINK.resolve(strict=True)
    if (not folder.is_dir() or folder.parent != documents
            or folder.name.casefold() != "the legend of zelda ocarina of time"):
        raise ValueError("source")
    files = sorted(p for p in folder.iterdir() if p.suffix.casefold() == ".nup")
    # Local selection is never supplied by the SSH client. Bind it to the
    # validated container's size and TOC, preserving every original NUP.
    selector = SOURCE_LINK.parent / "selected-nup.json"
    if selector.exists() or selector.is_symlink():
        if selector.is_symlink() or not selector.is_file() or selector.stat().st_size > 4096:
            raise ValueError("selection")
        try:
            chosen = json.loads(selector.read_text())
            if (not isinstance(chosen, dict) or set(chosen) != {"filename", "bytes", "toc_sha256"}
                    or not isinstance(chosen["filename"], str)
                    or chosen["filename"] in ("", ".", "..")
                    or "/" in chosen["filename"] or "\\" in chosen["filename"]
                    or type(chosen["bytes"]) is not int
                    or not isinstance(chosen["toc_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", chosen["toc_sha256"])):
                raise ValueError("selection")
            file = folder / chosen["filename"]
            if file not in files:
                raise ValueError("selection")
            inspect(file)  # Includes actual TOC digest verification.
            with file.open("rb") as stream:
                header = SUPER.unpack(stream.read(SUPER.size))
            if file.stat().st_size != chosen["bytes"] or header[5].hex() != chosen["toc_sha256"]:
                raise ValueError("selection")
        except (OSError, ValueError, TypeError, KeyError):
            raise ValueError("selection") from None
        return file
    if len(files) != 1:
        raise ValueError("count")
    file = files[0]
    inspect(file)
    return file


def diagnose():
    source = nup = False
    reason = "none"
    try:
        documents = (HOME / "Documents").resolve(strict=True)
        folder = SOURCE_LINK.resolve(strict=True) if SOURCE_LINK.is_symlink() else None
        source = bool(folder and folder.is_dir() and folder.parent == documents
                      and folder.name.casefold() == "the legend of zelda ocarina of time")
        if source:
            nup_file()
            nup = True
        else:
            reason = "source"
    except NupInvalid as exc:
        reason = exc.reason
    except (OSError, ValueError) as exc:
        reason = str(exc) if str(exc) in ("source", "count", "selection") else "source"
    print(f"OOT2_DIAG_V1 source={'ok' if source else 'fail'} "
          f"nup={'ok' if nup else 'fail'} reason={reason}")
    return 0


def dispatch(command, parent):
    if command not in ROUTES:
        return 126
    if command.startswith('oot2-fullwarm-v8-'):
        try:
            from .oot2_ipad_aot import digest, inspect_ipa, CHAIN, GPU
        except ImportError:
            from oot2_ipad_aot import digest, inspect_ipa, CHAIN, GPU
        kit = OUTPUT / 'OOT2HostKit-v8.tar.zst'
        cache = OUTPUT / 'OOT2Fullwarm-v8-g17g-cache.tar.gz'
        if command == 'oot2-fullwarm-v8-info':
            if kit.is_symlink() or cache.is_symlink(): raise ValueError('full prewarm symlink')
            print('OOT2_FULLWARM_V8', kit.stat().st_size, digest(kit),
                  cache.stat().st_size if cache.exists() else 0, digest(cache) if cache.exists() else '-')
            return 0
        if command in ('oot2-fullwarm-v8-read-kit', 'oot2-fullwarm-v8-read-cache'):
            parent.send_file(kit if command.endswith('-kit') else cache)
            return 0
        previous = parent.OUTPUT; parent.OUTPUT = OUTPUT
        try:
            if command == 'oot2-fullwarm-v8-write-cache':
                try:
                    from .oot2_pipeline_cache import receive_cache
                except ImportError:
                    from oot2_pipeline_cache import receive_cache
                receive_cache(parent, cache, fullwarm=True)
            elif command == 'oot2-fullwarm-v8-write-log': parent.receive_file('oot2-fullwarm-v8-private.log', 32 << 20)
            else:
                import zipfile, hashlib
                name = 'ZeldaOcarinaOfTime-v8-fullwarm-slim.ipa'
                parent.receive_file(name, 16 << 30)
                prefix = inspect_ipa(OUTPUT / name)
                with zipfile.ZipFile(OUTPUT / name) as z:
                    report = json.loads(z.read(prefix + 'pso/fullwarm.json'))
                    if report['chain'] != CHAIN or report['gpu'] != GPU or report['platform'] != 'ios':
                        raise ValueError('full prewarm target')
                    coverage = report['coverage']
                    try:
                        from .oot2_fullwarm import validate_render_coverage
                    except ImportError:
                        from oot2_fullwarm import validate_render_coverage
                    validate_render_coverage(coverage)
                    if (coverage['failed_tasks'] or coverage['stale_keys'] or not coverage['render_rows'] or not coverage['mesh_rows']
                        or coverage['mesh_rows'] != coverage['emitted_mesh']
                        or coverage['periods'] != len(report['archives'])): raise ValueError('full prewarm coverage')
                    z.getinfo(prefix + 'pso/' + GPU + '.mtl4a')
                    for filename, meta in report['archives'].items():
                        if not re.fullmatch(GPU + r'-prewarm-[0-9]{5}\.mtl4a', filename): raise ValueError('full prewarm filename')
                        item = z.getinfo(prefix + 'pso/' + filename)
                        if item.file_size != meta['bytes'] or item.file_size < 32: raise ValueError('full prewarm size')
                        h = hashlib.sha256()
                        with z.open(item) as stream:
                            while block := stream.read(8 << 20): h.update(block)
                        if h.hexdigest() != meta['sha256']: raise ValueError('full prewarm checksum')
                try:
                    from .oot2_local_bundle import bundle
                except ImportError:
                    from oot2_local_bundle import bundle
                stats = bundle(OUTPUT / name, ROOT / 'local-bundle-v6/extract/v131072/RomFS.img',
                    ROOT / 'local-bundle-v6/romfs-manifest.json',
                    OUTPUT / 'ZeldaOcarinaOfTime-ipad-v8-fullwarm-livecontainer.ipa', expected_chain=CHAIN)
                (OUTPUT / 'ipad-v8-fullwarm-local-bundle-result.json').write_text(json.dumps(stats, indent=2) + '\n')
                print('OOT2_FULLWARM_LOCAL_BUNDLE_OK', stats['ipa_bytes'])
        finally: parent.OUTPUT = previous
        return 0
    if command.startswith('oot2-aot-v8-'):
        try:
            from .oot2_ipad_aot import digest, inspect_ipa, CHAIN, GPU
        except ImportError:
            from oot2_ipad_aot import digest, inspect_ipa, CHAIN, GPU
        source = OUTPUT / 'ZeldaOcarinaOfTime-v8-aot-input.ipa'
        cache = OUTPUT / 'OOT2Aot-v8-g17g-cache.tar.gz'
        if command == 'oot2-aot-v8-info':
            inspect_ipa(source)
            if source.is_symlink() or cache.is_symlink(): raise ValueError('AOT input symlink')
            print('OOT2_AOT_V8', source.stat().st_size, digest(source),
                  cache.stat().st_size if cache.exists() else 0,
                  digest(cache) if cache.exists() else '-')
            return 0
        if command in ('oot2-aot-v8-read-input', 'oot2-aot-v8-read-cache'):
            parent.send_file(source if command.endswith('-input') else cache)
            return 0
        previous = parent.OUTPUT
        parent.OUTPUT = OUTPUT
        try:
            if command == 'oot2-aot-v8-write-cache':
                try:
                    from .oot2_pipeline_cache import receive_cache
                except ImportError:
                    from oot2_pipeline_cache import receive_cache
                receive_cache(parent, cache)
            elif command == 'oot2-aot-v8-write-log': parent.receive_file('oot2-aot-v8-private.log', 32 << 20)
            else:
                name = 'ZeldaOcarinaOfTime-v8-aot-slim.ipa'
                parent.receive_file(name, 16 << 30)
                prefix = inspect_ipa(OUTPUT / name)
                import zipfile
                with zipfile.ZipFile(OUTPUT / name) as z:
                    z.getinfo(prefix + 'pso/' + GPU + '.mtl4a')
                try:
                    from .oot2_local_bundle import bundle
                except ImportError:
                    from oot2_local_bundle import bundle
                stats = bundle(OUTPUT / name,
                               ROOT / 'local-bundle-v6/extract/v131072/RomFS.img',
                               ROOT / 'local-bundle-v6/romfs-manifest.json',
                               OUTPUT / 'ZeldaOcarinaOfTime-ipad-v8-aot-livecontainer.ipa', expected_chain=CHAIN)
                (OUTPUT / 'ipad-v8-aot-local-bundle-result.json').write_text(json.dumps(stats, indent=2) + '\n')
                print('OOT2_AOT_LOCAL_BUNDLE_OK', stats['ipa_bytes'])
        finally:
            parent.OUTPUT = previous
        return 0
    if command == "oot2-diagnose-v1":
        return diagnose()
    if command == "oot2-probe-v1":
        nup_file()
        print("OOT2_GATEWAY_V1")
        return 0
    if command == "oot2-release-preflight-v1":
        print("OOT2_RELEASE_READY_V1", release_identity(nup_file()))
        return 0
    if command == "oot2-manifest-v1":
        size, base, selected, count = inspect(nup_file())
        print(f"{TITLE:016X}", f"v{VERSION}", size, base, selected, count)
        return 0
    if command == "oot2-space-v1":
        path = nup_file()
        # Numeric-only reply, no filenames, path disclosure or game payload.
        print("OOT2_SPACE_V1", path.stat().st_size, selected_romfs_bytes(path))
        return 0
    if command == "oot2-read-nup":
        parent.send_file(nup_file())
        return 0
    if command in ("oot2-read-metal-snapshot-v1", "oot2-metal-snapshot-info-v1", "oot2-read-resume-v5", "oot2-resume-v5-info", "oot2-read-resume-v6", "oot2-resume-v6-info", "oot2-read-resume-v8", "oot2-resume-v8-info"):
        try:
            from .oot2_cache_snapshot import snapshot
        except ImportError:
            from oot2_cache_snapshot import snapshot
        resume = ("v8" if command in ("oot2-read-resume-v8", "oot2-resume-v8-info") else
                  "v6" if command in ("oot2-read-resume-v6", "oot2-resume-v6-info") else
                  "v5" if command in ("oot2-read-resume-v5", "oot2-resume-v5-info") else None)
        archive, stats = (snapshot(ROOT / ("cache-resume-" + resume), ROOT / ("cache-transfer-resume-" + resume), translations=True)
                          if resume else snapshot(CACHE, ROOT / "cache-transfer"))
        if command in ("oot2-metal-snapshot-info-v1", "oot2-resume-v5-info", "oot2-resume-v6-info", "oot2-resume-v8-info"):
            print("OOT2_METAL_SNAPSHOT_V1", archive.stat().st_size,
                  stats["sqlite_bytes"], stats["entries"])
        else:
            parent.send_file(archive)
        return 0
    if command in ("oot2-local-bundle-v6-ready", "oot2-local-bundle-v7-ready", "oot2-local-bundle-v8-ready"):
        try:
            from .oot2_local_bundle import identity, regular
        except ImportError:
            from oot2_local_bundle import identity, regular
        image = ROOT / "local-bundle-v6/extract/v131072/RomFS.img"
        meta = ROOT / "local-bundle-v6/romfs-manifest.json"
        regular(image); regular(meta)
        data = json.loads(meta.read_text())
        if data['source_identity'] != release_identity(nup_file()) or list(identity(image)) != data['identity']:
            raise ValueError('local bundle input identity')
        print('OOT2_LOCAL_BUNDLE_READY_' + command.rsplit('-', 2)[1].upper(), image.stat().st_size)
        return 0
    previous = parent.CACHE, parent.CONFLICTS, parent.OUTPUT
    try:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = CACHE, CONFLICTS, OUTPUT
        if command == "oot2-read-cache":
            parent.read_cache()
        elif command == "oot2-write-cache":
            parent.write_cache()
        elif command in ("oot2-write-slim-v6", "oot2-write-slim-v7", "oot2-write-slim-v8"):
            version = command.rsplit("-", 1)[1]
            filename = "ZeldaOcarinaOfTime-" + version + "-slim.ipa"
            parent.receive_file(filename, 8 * 1024**3)
            try:
                from .oot2_local_bundle import bundle
            except ImportError:
                from oot2_local_bundle import bundle
            chains = {"v7": "bc8830d4ba5a", "v8": "d24f05cf9d78"}
            args = {"expected_chain": chains[version]} if version in chains else {}
            stats = bundle(OUTPUT / filename,
                           ROOT / "local-bundle-v6/extract/v131072/RomFS.img",
                           ROOT / "local-bundle-v6/romfs-manifest.json",
                           OUTPUT / "ZeldaOcarinaOfTime.ipa", **args)
            (OUTPUT / ("ipad-" + version + "-local-bundle-result.json")).write_text(json.dumps(stats, indent=2) + "\n")
            print("OOT2_LOCAL_BUNDLE_OK", stats["ipa_bytes"])
        elif command == "oot2-write-ipa":
            parent.receive_file("ZeldaOcarinaOfTime.ipa", 50 * 1024**3)
        elif command == "oot2-write-log":
            parent.receive_file("oot2-build.log", 32 * 1024**2)
        elif command in ("oot2-write-host-kit-v1", "oot2-write-host-kit-v5", "oot2-write-host-kit-v6", "oot2-write-host-kit-v7", "oot2-write-host-kit-v8"):
            filename = ("OOT2HostKit-v8.tar.zst" if command.endswith("-v8") else "OOT2HostKit-v7.tar.zst" if command.endswith("-v7") else "OOT2HostKit-v6.tar.zst" if command.endswith("-v6") else "OOT2HostKit-v5.tar.zst" if command.endswith("-v5") else "OOT2HostKit-v4.tar.zst")
            parent.receive_file(filename, 1 * 1024**3)
        return 0
    finally:
        parent.CACHE, parent.CONFLICTS, parent.OUTPUT = previous
