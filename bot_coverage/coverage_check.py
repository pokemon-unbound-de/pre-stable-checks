"""Isolated scenario coverage pilot; no text gates or release authorization."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from run_binding import inspect_binding
from png_evidence import PNG, png_structure_ok

ADDRESS = re.compile(r'^(?:0x)?([0-9a-fA-F]{8})$')
BP = re.compile(r'^\d+\s+BP\s+[0-9A-Fa-f]{2}\s+\d+\s+\d+\s+(?P<address>[0-9A-Fa-f]{8})\s+\d+\s+(?P<hex>[0-9A-Fa-f]+)(?:\s+(?P<height>\d+))?\s*$')
FATAL = re.compile(r'\b(?:fatal|panic|segmentation fault|assertion failed|illegal opcode|stub software interrupt)\b|Traceback \(most recent call last\)',re.I)

def validate(m):
    if not isinstance(m,dict) or type(m.get('schema')) is not int or m['schema']!=1:
        raise ValueError('schema must be 1')
    if not isinstance(m.get('scenario'),str) or not m['scenario'].strip():
        raise ValueError('scenario required')
    if not isinstance(m.get('rom_sha256'),str) or not re.fullmatch(r'[0-9a-fA-F]{64}',m['rom_sha256']):
        raise ValueError('invalid SHA-256')
    if 'expected_bp' in m and (not isinstance(m['expected_bp'],str) or not ADDRESS.fullmatch(m['expected_bp'])):
        raise ValueError('invalid BP address')
    if 'expected_hex' in m:
        value=m['expected_hex']
        if not isinstance(value,str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}){4,4096}',value):
            raise ValueError('expected_hex must contain 4..4096 complete bytes')
        buffer=m.get('expected_buffer_bp')
        if not isinstance(buffer,str) or not ADDRESS.fullmatch(buffer):
            raise ValueError('explicit RAM BP address required for hex evidence')
        if not 0x02000000<=int(ADDRESS.fullmatch(buffer).group(1),16)<0x04000000:
            raise ValueError('hex evidence BP must be in RAM')
    elif 'expected_buffer_bp' in m:
        raise ValueError('buffer BP without hex evidence')
    if 'expected_bp' not in m and 'expected_hex' not in m:
        raise ValueError('target BP or explicit buffer hex evidence required')
    if type(m.get('min_screenshots')) is not int or m['min_screenshots']<1:
        raise ValueError('positive screenshot count required')
    return ADDRESS.fullmatch(m['expected_bp']).group(1).upper() if 'expected_bp' in m else None

def inspect_run(manifest,rom_sha256,textlog,emulator_log,done,screenshot_count,runner_findings=(),invalid_screenshot_count=0):
    target=validate(manifest)
    reasons=[]
    if rom_sha256.lower()!=manifest['rom_sha256'].lower(): reasons.append('rom_hash_mismatch')
    if textlog is None: reasons.append('textlog_missing')
    elif not textlog.strip(): reasons.append('textlog_empty')
    records=[]
    for line in (textlog or '').splitlines():
        match=BP.fullmatch(line)
        if match:
            try:raw=bytes.fromhex(match.group('hex'))
            except ValueError:continue
            records.append((match.group('address').upper(),raw))
    evidence='bp_address' if target and any(address==target for address,_ in records) else 'missing'
    if evidence=='missing' and 'expected_hex' in manifest:
        buffer=ADDRESS.fullmatch(manifest['expected_buffer_bp']).group(1).upper()
        needle=bytes.fromhex(manifest['expected_hex'])
        if any(address==buffer and needle in raw for address,raw in records):evidence='buffer_hex'
    if evidence=='missing': reasons.append('target_bp_missing')
    if not done: reasons.append('done_missing')
    if 'ABSTURZ.txt' in runner_findings: reasons.append('runner_crash')
    if 'FREEZE.txt' in runner_findings: reasons.append('runner_freeze')
    if screenshot_count<manifest['min_screenshots']: reasons.append('screenshots_insufficient')
    if invalid_screenshot_count: reasons.append('screenshots_invalid')
    if emulator_log is None: reasons.append('emulator_log_missing')
    elif not emulator_log.strip(): reasons.append('emulator_log_empty')
    if any(FATAL.search(log or '') for log in (emulator_log,textlog)): reasons.append('fatal_log')
    return dict(schema=1,scenario=manifest['scenario'],coverage='red' if reasons else 'green',
                reasons=reasons,screenshots=screenshot_count,invalid_screenshots=invalid_screenshot_count,
                target_evidence=evidence,release_authorization=False)

def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()

def read_log(path):
    return path.read_text(encoding='utf-8',errors='strict') if path.is_file() else None

def load_manifest(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate manifest key')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--rom',required=True,type=Path)
    p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--require-binding',action='store_true')
    p.add_argument('--run-id',default=None,help='fresh expected run ID supplied by runner')
    a=p.parse_args(argv)
    try:
        m=load_manifest(a.manifest);validate(m)
        if not a.run_dir.is_dir(): raise ValueError('run directory missing')
        if bool(a.require_binding) != bool(a.run_id):
            raise ValueError('--require-binding and --run-id must be used together')
        count=0
        invalid_count=0
        artifacts = []
        folder=a.run_dir
        if folder.is_dir():
            for path in folder.iterdir():
                if path.is_file() and path.suffix.lower()=='.png':
                    artifacts.append(path)  # Binding includes invalid files as actually present.
                    if png_structure_ok(path):
                        count+=1
                    else:
                        invalid_count+=1
        rom_sha256 = file_hash(a.rom)
        result=inspect_run(m,rom_sha256,read_log(a.run_dir/'druckerlog.txt'),
                           read_log(a.run_dir/'mgba.log'),(a.run_dir/'DONE').is_file(),count,
                           runner_findings=[name for name in ('ABSTURZ.txt','FREEZE.txt')
                                            if (a.run_dir/name).exists()],invalid_screenshot_count=invalid_count)
        result['binding'] = 'unchecked'
        if a.require_binding:
            receipt_path = a.run_dir/'run_evidence.json'
            receipt = load_manifest(receipt_path) if receipt_path.is_file() else None
            artifacts.extend(a.run_dir/name for name in
                             ('druckerlog.txt','mgba.log','DONE','ABSTURZ.txt','FREEZE.txt')
                             if (a.run_dir/name).is_file())
            hashes = {path.name:file_hash(path) for path in artifacts}
            reasons = inspect_binding(receipt,a.run_id,m['scenario'],rom_sha256,hashes)
            result['reasons'].extend(reasons)
            result['binding'] = 'failed' if reasons else 'matched'
            if reasons:
                result['coverage'] = 'red'
    except (ValueError,OSError,TypeError) as error:
        print(json.dumps(dict(coverage='invalid_input',error_type=type(error).__name__)),file=sys.stderr)
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0 if result['coverage']=='green' else 2

if __name__=='__main__': sys.exit(main())
