"""Reproduce coverage/binding cases using synthetic files; no emulator or ROM."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import time
import zlib
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from coverage_check import main as check


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png():
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
            + chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00')) + chunk(b'IEND',b''))


def fixture(root):
    (root/'synthetic.bin').write_bytes(b'SYNTHETIC FIXTURE - NOT A GAME ROM')
    manifest=dict(schema=1,scenario='synthetic-menu',rom_sha256=sha(root/'synthetic.bin'),
                  expected_bp='08001234',min_screenshots=17)
    (root/'manifest.json').write_text(json.dumps(manifest))
    (root/'druckerlog.txt').write_text('12 BP 00 0 0 08001234 8 BBFF')
    (root/'mgba.log').write_text('Synthetic runner stopped normally')
    (root/'DONE').touch()
    for i in range(17):
        (root/f'{i:04}.png').write_bytes(png())
    (root/'_duplikate').mkdir()
    (root/'_duplikate/old.png').write_bytes(png())
    names=['druckerlog.txt','mgba.log','DONE']+[f'{i:04}.png' for i in range(17)]
    receipt=dict(schema=1,run_id='synthetic-current',scenario='synthetic-menu',
                 launched_rom_sha256=manifest['rom_sha256'],artifacts={name:sha(root/name) for name in names})
    (root/'run_evidence.json').write_text(json.dumps(receipt))


def mutate(root, name):
    if name=='text_without_target':
        (root/'druckerlog.txt').write_text('12 TEXT harmless synthetic text')
    elif name=='wrong_rom':
        (root/'synthetic.bin').write_bytes(b'DIFFERENT SYNTHETIC FIXTURE')
    elif name=='done_missing':
        (root/'DONE').unlink()
    elif name=='only_duplicate_images':
        for path in root.glob('*.png'): path.unlink()
    elif name=='changed_image':
        (root/'0000.png').write_bytes(png()+b'changed synthetic content')
    elif name=='receipt_missing':
        (root/'run_evidence.json').unlink()
    elif name=='old_run':
        receipt=json.loads((root/'run_evidence.json').read_text())
        receipt['run_id']='synthetic-previous'
        (root/'run_evidence.json').write_text(json.dumps(receipt))
    elif name in ('illegal_opcode','stub_interrupt','empty_log'):
        text={'illegal_opcode':'Illegal opcode','stub_interrupt':'Stub software interrupt','empty_log':''}[name]
        (root/'mgba.log').write_text(text)
    elif name in ('crash_marker','freeze_marker'):
        (root/('ABSTURZ.txt' if name=='crash_marker' else 'FREEZE.txt')).touch()


CASES=[('valid_bound',0,None),('text_without_target',2,'target_bp_missing'),
       ('wrong_rom',2,'rom_hash_mismatch'),('done_missing',2,'done_missing'),
       ('only_duplicate_images',2,'screenshots_insufficient'),
       ('changed_image',2,'binding_artifact_hash_mismatch'),
       ('receipt_missing',2,'binding_missing'),('old_run',2,'binding_run_id_mismatch'),
       ('illegal_opcode',2,'fatal_log'),('stub_interrupt',2,'fatal_log'),
       ('empty_log',2,'emulator_log_empty'),('crash_marker',2,'runner_crash'),
       ('freeze_marker',2,'runner_freeze')]


def run():
    results=[]
    for name, expected, reason in CASES:
        with tempfile.TemporaryDirectory(prefix='synthetic-coverage-') as tmp:
            root=Path(tmp)
            fixture(root)
            mutate(root,name)
            args=['--manifest',str(root/'manifest.json'),'--rom',str(root/'synthetic.bin'),
                  '--run-dir',str(root),'--require-binding','--run-id','synthetic-current']
            started=time.perf_counter()
            with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()):
                code=check(args)
            elapsed=time.perf_counter()-started
            report=json.loads(out.getvalue())
            matched=code==expected and (reason is None or reason in report['reasons'])
            results.append(dict(case=name,expected_exit=expected,actual_exit=code,
                                matched=matched,check_ms=round(elapsed*1000,3)))
    return dict(synthetic=True,emulator_executed=False,real_runner_integration=False,
                cases=len(results),passed=sum(r['matched'] for r in results),
                false_green=sum(r['expected_exit']==2 and r['actual_exit']==0 for r in results),results=results)


if __name__=='__main__':
    result=run()
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['passed']==result['cases'] else 1)
