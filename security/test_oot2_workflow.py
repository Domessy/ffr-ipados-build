#!/usr/bin/env python3
"""Production-workflow contracts; no secrets or game files required."""
from pathlib import Path
import re
import os
import subprocess
import tempfile
import textwrap
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/".github/workflows/build-oot2.yml"
REFERENCE = ROOT/".github/workflows/build-dread.yml"
REF = re.compile(r"\$\{\{\s*secrets\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
EXPECTED = {"FFR_TS_AUTHKEY","FFR_SSH_KEY","FFR_SSH_KNOWN_HOSTS",
            "FFR_TS_HOST","FFR_SSH_USER"}


class WorkflowContractTests(unittest.TestCase):
    def test_resume_snapshot_is_explicit_and_keeps_default_metal_validation(self):
        workflow = BUILD.read_text()
        self.assertIn('          - resume-v5', workflow)
        self.assertIn('          - resume-v6', workflow)
        self.assertIn('[[ "$OOT2_RUNTIME_VARIANT" = ipad-v6 ]]', workflow)
        self.assertIn('SNAPSHOT_ROUTE=oot2-resume-v6-info', workflow)
        self.assertIn('[[ "$OOT2_RUNTIME_VARIANT" = ipad-v5 ]]', workflow)
        self.assertIn('SNAPSHOT_ROUTE=oot2-resume-v5-info', workflow)
        self.assertIn('if [ "$SNAPSHOT_ROLE" = metal-snapshot ]; then', workflow)

    def test_snapshot_restore_executes_with_system_bash(self):
        # Execute the production snapshot branch, including nounset, with tiny
        # stand-ins for network/files. /bin/bash is 3.2 on the macOS runners.
        workflow = BUILD.read_text()
        step = workflow.split('      - name: Restaurer le cache de shaders OOT2', 1)[1]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])
        branch = script[script.index('if [ "$OOT2_CACHE_RESTORE" = metal-snapshot ]'):]
        branch = branch.split('elif [ "$OOT2_CACHE_RESTORE" = empty ]; then', 1)[0] + 'fi\n'
        setup = r'''
set -euo pipefail
export DMSH_CAS="$RUNNER_TEMP/cas.db"
ssh() { printf '%s\n' "$*" >> "$CALLS"; printf 'OOT2_METAL_SNAPSHOT_V1 1 1 1\n'; }
df() { printf 'Filesystem blocks Used Available Capacity Mounted\nfixture 999999999 0 999999999 0%% /\n'; }
python3() {
  printf 'python' >> "$CALLS"
  printf ' <%s>' "$@" >> "$CALLS"
  printf '\n' >> "$CALLS"
  case "$1" in
    security/oot2_transfer.py) touch "$4" ;;
    security/oot2_cache_snapshot.py) return "$ACCEPT_STATUS" ;;
    *) return 99 ;;
  esac
}
zstd() { printf 'fixture'; }
'''
        print(subprocess.check_output(['/bin/bash', '--version'], text=True).splitlines()[0])
        with tempfile.TemporaryDirectory() as temp:
            calls = Path(temp)/'calls'
            cases = [('metal-snapshot', 'ipad-v7', 'oot2-metal-snapshot-info-v1', False),
                     ('resume-v5', 'ipad-v5', 'oot2-resume-v5-info', True),
                     ('resume-v6', 'ipad-v6', 'oot2-resume-v6-info', True),
                     ('resume-v8', 'ipad-v8', 'oot2-resume-v8-info', True)]
            for mode, variant, route, translations in cases:
                for accept_status in (0, 42):
                    with self.subTest(mode=mode, accept_status=accept_status):
                        calls.write_text('')
                        env = {**os.environ, 'RUNNER_TEMP': temp, 'CALLS': str(calls),
                               'OOT2_CACHE_RESTORE': mode, 'OOT2_RUNTIME_VARIANT': variant,
                               'ACCEPT_STATUS': str(accept_status)}
                        result = subprocess.run(['/bin/bash', '-c', setup + branch], env=env,
                                                text=True, capture_output=True)
                        self.assertEqual(result.returncode, accept_status, result.stderr)
                        log = calls.read_text().splitlines()
                        self.assertIn(route, log[0])
                        self.assertIn(f'<{mode}>', log[1])
                        expected = f'python <security/oot2_cache_snapshot.py> <accept> <{temp}>'
                        if translations:
                            expected += ' <--translations>'
                        self.assertEqual(log[-1], expected)
            for mode in ('resume-v5', 'resume-v6', 'resume-v8'):
                with self.subTest(wrong_variant=mode):
                    calls.write_text('')
                    env = {**os.environ, 'RUNNER_TEMP': temp, 'CALLS': str(calls),
                           'OOT2_CACHE_RESTORE': mode, 'OOT2_RUNTIME_VARIANT': 'ipad-v7',
                           'ACCEPT_STATUS': '0'}
                    result = subprocess.run(['/bin/bash', '-c', setup + branch], env=env,
                                            text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(calls.read_text(), '')
        # Confirm the old command really fails on the target shell; Linux Bash
        # has different empty-array behavior, so it cannot prove this regression.
        if sys.platform == 'darwin':
            old = subprocess.run(['/bin/bash', '-uc',
                                  'ACCEPT_ARGS=(); printf "%s" "${ACCEPT_ARGS[@]}"'],
                                 text=True, capture_output=True)
            self.assertNotEqual(old.returncode, 0)
            self.assertIn('unbound variable', old.stderr)

    def test_ipad_v7_default_and_earlier_preparations_are_explicit(self):
        workflow = BUILD.read_text()
        self.assertIn('default: ipad-v8', workflow)
        self.assertIn('          - ipad-v7', workflow)
        self.assertIn('ccd834e06a3938834bb5579e2ccc6a0ad13d3970', workflow)
        self.assertIn('oot2_prepare_ipad_v8.py', workflow)
        self.assertIn('IPA_ROUTE=oot2-write-slim-v8', workflow)
        self.assertIn('KIT_ROUTE=oot2-write-host-kit-v8', workflow)
        self.assertIn('default: metal-snapshot', workflow)
        self.assertIn('2f131edc1b4586f89dd20b0d3de8e4f92ac3f74b', workflow)
        self.assertIn('oot2_prepare_ipad_v7.py', workflow)
        self.assertIn('IPA_ROUTE=oot2-write-slim-v7', workflow)
        self.assertIn('KIT_ROUTE=oot2-write-host-kit-v7', workflow)
        self.assertIn('oot2_prepare_ipad_v6.py', workflow)
        self.assertIn('8d5d4f1b04610fef5a96521c72a4263d68794959', workflow)
        self.assertIn('python3 security/oot2_prepare_ipad_v5.py', workflow)
        self.assertLess(workflow.index('python3 security/oot2_prepare_ipad_v5.py'),
                        workflow.index('Restaurer le cache de shaders OOT2'))
        self.assertIn('KIT_ROUTE=oot2-write-host-kit-v1', workflow)
        self.assertIn('KIT_ROUTE=oot2-write-host-kit-v5', workflow)
        manifest = (ROOT/'security/oot2_ipad_v5_manifest.json').read_text()
        self.assertIn('disabled until missing mkcpre2.py', manifest)

    def test_runner_cleanup_preflight_precedes_all_large_transfers(self):
        workflow = BUILD.read_text()
        preflight = workflow.index('oot2-release-preflight-v1')
        self.assertLess(preflight, workflow.index('Restaurer le cache de shaders OOT2'))
        self.assertLess(preflight, workflow.index('Transferer uniquement le NUP'))
        self.assertIn('echo "OOT2_NUP_ID=$RELEASE_ID" >> "$GITHUB_ENV"', workflow)

    def test_network_secret_names_match_working_dread(self):
        workflow=BUILD.read_text()
        known=REFERENCE.read_text()
        self.assertEqual(set(REF.findall(workflow)),EXPECTED)
        self.assertEqual(set(REF.findall(workflow)),set(REF.findall(known)))
        self.assertIn("TS_AUTHKEY: ${{ secrets.FFR_TS_AUTHKEY }}",workflow)
        self.assertIn('--authkey="$TS_AUTHKEY"',workflow)
        self.assertNotIn("AUTWONDEREY",workflow)

    def test_preflight_before_any_private_transfer(self):
        workflow=BUILD.read_text()
        check=workflow.index("Verifier les secrets reseau avant toute installation couteuse")
        install=workflow.index("Installer les dependances nxnative")
        network=workflow.index("Connecter Tailscale")
        meta=workflow.index("Verifier le NUP et la capacite disque")
        transfer=workflow.index("Transferer uniquement le NUP")
        self.assertTrue(check < install < network < meta < transfer)
        self.assertIn("OOT2_GATEWAY_V1",workflow)
        self.assertEqual(workflow.count("required=$(( NUP_BYTES + ROMFS_BYTES + 12 * 1024**3 ))"),2)
        self.assertEqual(workflow.count("oot2-space-v1"),2)
        self.assertIn('if [ "$free_kb" -lt 95000000 ]; then',workflow)
        self.assertIn("source_bytes=$NUP_BYTES",workflow)

    def test_standalone_manifest_is_accepted_in_both_gates(self):
        workflow = BUILD.read_text()
        self.assertEqual(workflow.count('"$BASE" =~ ^[01]$'), 2)
        self.assertNotIn('"$BASE" == 1', workflow)

    def test_ephemeral_mmap_release_is_before_transfer_and_opt_in(self):
        workflow = BUILD.read_text()
        patch_call = workflow.index("python3 security/oot2_patch_nup_release.py")
        transfer = workflow.index("Transferer uniquement le NUP")
        self.assertLess(patch_call, transfer)
        self.assertIn("security/test_oot2_patch_nup_release.py", workflow)
        script = (ROOT/"security/run_oot2.py").read_text()
        self.assertIn("OOT2_RELEASE_EPHEMERAL_NUP=str(NUP)", script)
        patch_script = (ROOT/"security/oot2_patch_nup_release.py").read_text()
        self.assertIn('fam["nup"].close()', patch_script)
        self.assertIn("candidate.unlink()", patch_script)
        self.assertIn('OOT2_RELEASE_EPHEMERAL_NUP_ID', patch_script)
        self.assertIn("fam['nup'].toc_sha.hex()", patch_script)
        self.assertNotIn("25020741061", patch_script)

    def test_one_nup_without_keys(self):
        workflow=BUILD.read_text()
        self.assertIn("security/oot2_transfer.py nup",workflow)
        self.assertIn("security/oot2_nup_info.py",workflow)
        self.assertIn("OcarinaOfTime.nup",workflow)
        self.assertIn("security/run_oot2.py",workflow)
        for forbidden in ("oot2-read-keys","oot2-prod.keys","NSPS","FFR_TS_AUTWONDEREY"):
            self.assertNotIn(forbidden,workflow)

    def test_sqlite_cache_is_validated_before_game_transfer(self):
        workflow = BUILD.read_text()
        restore = workflow.index("Restaurer le cache de shaders OOT2")
        transfer = workflow.index("Transferer uniquement le NUP")
        self.assertLess(restore, transfer)
        self.assertIn("oot2_sqlite_cas.py prepare", workflow)
        self.assertIn('"$RUNNER_TEMP/oot2-shader-cas/cas.db"', workflow)
        self.assertIn("nxnative/dm/tools/shader_cache.py", workflow)
        self.assertIn("PRAGMA quick_check", workflow)
        runner = (ROOT/"security/run_oot2.py").read_text()
        self.assertIn('CAS_DB = CACHE / "cas.db"', runner)
        self.assertIn('DMSH_CAS=str(CAS_DB)', runner)
        self.assertIn('"oot2_sqlite_cas.py"', runner)
        self.assertNotIn('DMSH_CAS=str(CACHE)', runner)

    def test_pin_and_metal_chain(self):
        workflow=BUILD.read_text()
        m=re.search(r'NXNATIVE_SHA="([^"]+)"',workflow)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(1),r"^[0-9a-f]{40}$")
        self.assertEqual(m.group(1),"c229bd7d52e30f072362e31c7b1e3206d107d4cd")
        self.assertIn("Xcode 27.2",workflow)
        self.assertIn("Apple metal version 32023.922 (metalfe-32023.922.4)",workflow)
        self.assertIn("--check-metal",workflow)
        script=(ROOT/"security/run_oot2.py").read_text()
        self.assertIn('"--platform", "ios"',script)
        self.assertIn('"-p", "v131072"',script)
        self.assertIn('ZeldaOcarinaOfTime.ipa',script)
        self.assertNotIn('"--platform", "mac-app"',script)


if __name__=="__main__":
    unittest.main()
