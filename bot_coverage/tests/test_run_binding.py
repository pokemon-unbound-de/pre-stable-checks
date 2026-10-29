from replay_checks import png
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from run_binding import inspect_binding
from coverage_check import main, PNG


class BindingTest(unittest.TestCase):
    def setUp(self):
        self.artifacts = {'druckerlog.txt':'b'*64, 'mgba.log':'c'*64,'DONE':'d'*64,'1.png':'e'*64}
        self.receipt = dict(schema=1,run_id='fresh-123',scenario='menu',
                            launched_rom_sha256='a'*64,artifacts=self.artifacts.copy())

    def inspect(self, receipt=None, **kwargs):
        args = dict(receipt=self.receipt if receipt is None else receipt,
                    expected_run_id='fresh-123',scenario='menu',rom_sha256='a'*64,
                    actual_artifacts=self.artifacts)
        return inspect_binding(**{**args,**kwargs})

    def test_match(self):
        self.assertEqual(self.inspect(),[])

    def test_stale_run_id(self):
        self.assertIn('binding_run_id_mismatch', self.inspect(expected_run_id='fresh-456'))

    def test_wrong_scenario_and_rom(self):
        self.assertIn('binding_scenario_mismatch',self.inspect(scenario='other'))
        self.assertIn('binding_rom_mismatch',self.inspect(rom_sha256='f'*64))

    def test_missing_receipt(self):
        self.assertEqual(inspect_binding(None,'fresh-123','menu','a'*64,self.artifacts),['binding_missing'])

    def test_mixed_artifact(self):
        self.assertIn('binding_artifact_hash_mismatch',self.inspect(actual_artifacts={**self.artifacts,'1.png':'f'*64}))

    def test_artifact_set_changes(self):
        for actual in ({'DONE':'d'*64},{**self.artifacts,'2.png':'f'*64}):
            self.assertIn('binding_artifact_set_mismatch',self.inspect(actual_artifacts=actual))

    def test_invalid_hash(self):
        receipt=copy.deepcopy(self.receipt)
        receipt['artifacts']['1.png']='not a hash'
        self.assertIn('binding_artifacts_invalid',self.inspect(receipt))

    def test_cli_bound_artifacts_and_old_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rom=root/'fixture.bin';rom.write_bytes(b'synthetic, not ROM')
            digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
            manifest=dict(schema=1,scenario='menu',rom_sha256=digest(rom),expected_bp='08001234',min_screenshots=1)
            (root/'manifest.json').write_text(json.dumps(manifest))
            (root/'druckerlog.txt').write_text('12 BP 00 0 0 08001234 8 BBFF')
            (root/'mgba.log').write_text('OK')
            (root/'DONE').touch()
            (root/'1.png').write_bytes(png())
            receipt=dict(schema=1,run_id='fresh-123',scenario='menu',launched_rom_sha256=digest(rom),
                         artifacts={name:digest(root/name) for name in ('druckerlog.txt','mgba.log','DONE','1.png')})
            args=['--manifest',str(root/'manifest.json'),'--rom',str(rom),'--run-dir',str(root),'--require-binding','--run-id','fresh-123']
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(args),2)
            self.assertIn('binding_missing',out.getvalue())
            (root/'run_evidence.json').write_text(json.dumps(receipt))
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(args),0)
            self.assertEqual(json.loads(out.getvalue())['binding'],'matched')
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(args[:-1]+['fresh-456']),2)
            self.assertIn('binding_run_id_mismatch',out.getvalue())
            (root/'1.png').write_bytes(png()+b'changed')
            with redirect_stdout(StringIO()) as out:
                self.assertEqual(main(args),2)
            self.assertIn('binding_artifact_hash_mismatch',out.getvalue())
            with redirect_stderr(StringIO()):
                self.assertEqual(main(args[:-2]),1)
