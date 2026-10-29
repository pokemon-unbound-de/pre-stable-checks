import unittest
from replay_checks import run, png


class ReplayTest(unittest.TestCase):
    def test_file_replay_matrix(self):
        result=run()
        self.assertEqual(result['cases'],14)
        self.assertEqual(result['passed'],14)
        self.assertEqual(result['false_green'],0)
        truncated=next(r for r in result['results'] if r['case']=='truncated_png_bound')
        self.assertEqual(truncated['binding'],'matched')
        self.assertEqual(truncated['invalid_screenshots'],17)
        self.assertFalse(result['emulator_executed'])
        self.assertFalse(result['real_runner_integration'])

    def test_png_fixture_is_complete(self):
        import struct,zlib
        data=png()
        self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
        offset=8
        kinds=[]
        while offset<len(data):
            size=struct.unpack('>I',data[offset:offset+4])[0]
            kind=data[offset+4:offset+8]
            payload=data[offset+8:offset+8+size]
            crc=struct.unpack('>I',data[offset+8+size:offset+12+size])[0]
            self.assertEqual(zlib.crc32(kind+payload)&0xffffffff,crc)
            if kind==b'IDAT': self.assertEqual(zlib.decompress(payload),b'\x00\x00\x00\x00')
            kinds.append(kind)
            offset+=12+size
        self.assertEqual(kinds,[b'IHDR',b'IDAT',b'IEND'])
