import hashlib,json,tempfile,unittest
from pathlib import Path
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
from coverage_check import inspect_run,main,PNG

class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.manifest=dict(schema=1,scenario='synthetic-menu',rom_sha256='a'*64,expected_bp='08001234',min_screenshots=1)
        self.kw=dict(manifest=self.manifest,rom_sha256='a'*64,textlog='12 BP 00 0 0 08001234 30 BBFF',emulator_log='Started\nStopped',done=True,screenshot_count=1)
    def run_check(self,**updates): return inspect_run(**{**self.kw,**updates})
    def test_target_reached(self):
        self.assertEqual(self.run_check()['coverage'],'green')
        self.assertFalse(self.run_check()['release_authorization'])
    def test_text_without_target_red(self):
        result=self.run_check(textlog='12 TEXT harmless synthetic text')
        self.assertEqual(result['coverage'],'red')
        self.assertIn('target_bp_missing',result['reasons'])
    def test_missing_evidence(self):
        for change,reason in [({'done':False},'done_missing'),({'screenshot_count':0},'screenshots_insufficient'),({'textlog':None},'textlog_missing'),({'emulator_log':None},'emulator_log_missing'),({'rom_sha256':'b'*64},'rom_hash_mismatch')]:
            self.assertIn(reason,self.run_check(**change)['reasons'])
    def test_fatal(self):
        for field in ('textlog','emulator_log'):
            self.assertIn('fatal_log',self.run_check(**{field:self.kw[field]+'\nFATAL crash'})['reasons'])
    def test_exact_bp_field(self):
        for line in ('12 TEXT 08001234','12 BP 00 0 0 08001235 30 08001234','prefix 12 BP 00 0 0 08001234 30 BBFF'):
            self.assertIn('target_bp_missing',self.run_check(textlog=line)['reasons'])
    def test_case(self):
        self.manifest['expected_bp']='0x0800abcd'
        self.assertEqual(self.run_check(textlog='12 BP 00 0 0 0800ABCD 30 BBFF',rom_sha256='A'*64)['coverage'],'green')
    def test_invalid_manifest(self):
        for field,value in [('expected_bp','1234'),('rom_sha256','abc'),('min_screenshots',0),('min_screenshots',True)]:
            with self.assertRaises(ValueError): self.run_check(manifest={**self.manifest,field:value})
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'screenshots').mkdir()
            rom=root/'synthetic.bin';rom.write_bytes(b'synthetic fixture, not a ROM')
            self.manifest['rom_sha256']=hashlib.sha256(rom.read_bytes()).hexdigest()
            manifest=root/'manifest.json';manifest.write_text(json.dumps(self.manifest))
            args=['--manifest',str(manifest),'--rom',str(rom),'--run-dir',str(root)]
            (root/'DONE').touch();(root/'mgba.log').write_text('OK')
            (root/'screenshots/test.png').write_bytes(PNG+b'fixture')
            for log,code in [(self.kw['textlog'],0),('12 TEXT hello',2)]:
                (root/'druckerlog.txt').write_text(log)
                with redirect_stdout(StringIO()) as out: self.assertEqual(main(args),code)
                self.assertNotIn('hello',out.getvalue())
            (root/'screenshots/test.png').write_bytes(b'fake png')
            (root/'druckerlog.txt').write_text(self.kw['textlog'])
            with redirect_stdout(StringIO()) as out: self.assertEqual(main(args),2)
            self.assertIn('screenshots_insufficient',out.getvalue())
            manifest.write_text('{}')
            with redirect_stderr(StringIO()): self.assertEqual(main(args),1)

    def test_empty_logs_fail_closed(self):
        for field in ('emulator_log', 'textlog'):
            for value in ('', ' \n\t'):
                result = self.run_check(**{field: value})
                self.assertEqual(result['coverage'], 'red')
                self.assertIn(field + '_empty', result['reasons'])

    def test_duplicate_manifest_keys_rejected(self):
        from coverage_check import load_manifest
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text('{"expected_bp":"08001234","expected_bp":"08005678"}')
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_manifest_json_order_irrelevant(self):
        from coverage_check import load_manifest
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps(dict(reversed(list(self.manifest.items())))))
            self.assertEqual(load_manifest(path), self.manifest)
