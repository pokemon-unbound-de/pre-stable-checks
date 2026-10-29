"""Core PNG framing/CRC checks; no screenshot-content or raster decoder claims."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from coverage_check import main
from png_evidence import PNG, png_structure_ok
from replay_checks import png, fixture, sha


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def header(width=1, height=1, depth=8, color=2, compression=0, filtering=0, interlace=0):
    return chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color, compression, filtering, interlace))


def image(head=None, middle=None, ending=None):
    return PNG + (head if head is not None else header()) + (middle if middle is not None else chunk(b'IDAT', zlib.compress(b'\0\0\0\0'))) + (ending if ending is not None else chunk(b'IEND', b''))


class PNGStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.png'

    def inspect(self, data):
        self.path.write_bytes(data)
        return png_structure_ok(self.path)

    def test_complete_rgb_rgba_grayscale_and_indexed_headers(self):
        self.assertTrue(self.inspect(png()))
        for color in (0, 2, 4, 6):
            with self.subTest(color=color):self.assertTrue(self.inspect(image(head=header(color=color))))
        self.assertTrue(self.inspect(image(head=header(depth=1, color=3), middle=chunk(b'PLTE', b'\0\0\0') + chunk(b'IDAT', zlib.compress(b'\0\0')))))

    def test_every_truncation_and_signature_only_are_rejected(self):
        valid = png()
        for end in range(len(valid)):
            with self.subTest(end=end):self.assertFalse(self.inspect(valid[:end]))
        self.assertFalse(self.inspect(PNG + b'fixture'))

    def test_crc_errors_rejected(self):
        for offset in (20, 45, -1):
            data = bytearray(png());data[offset] ^= 1
            with self.subTest(offset=offset):self.assertFalse(self.inspect(data))

    def test_required_core_chunks_and_order(self):
        for data in (
            image(head=b''), image(middle=b''), image(ending=b''),
            image(middle=header() + chunk(b'IDAT', b'data')),
            PNG + chunk(b'IDAT', b'data') + header() + chunk(b'IEND', b''),
            image(ending=chunk(b'IEND', b'bad')), png() + b'trailing',
        ):
            with self.subTest(length=len(data)):self.assertFalse(self.inspect(data))

    def test_empty_and_split_idat(self):
        self.assertFalse(self.inspect(image(middle=chunk(b'IDAT', b''))))
        data = zlib.compress(b'\0\0\0\0')
        self.assertTrue(self.inspect(image(middle=chunk(b'IDAT', b'') + chunk(b'IDAT', data[:2]) + chunk(b'IDAT', data[2:]))))
        self.assertFalse(self.inspect(image(middle=chunk(b'IDAT', data[:2]) + chunk(b'tEXt', b'x\0y') + chunk(b'IDAT', data[2:]))))

    def test_invalid_dimensions_and_header_modes(self):
        for changes in ({'width':0}, {'height':0}, {'width':0x80000000}, {'color':1}, {'color':2,'depth':1}, {'compression':1}, {'filtering':1}, {'interlace':2}):
            with self.subTest(changes=changes):self.assertFalse(self.inspect(image(head=header(**changes))))
        self.assertTrue(self.inspect(image(head=header(interlace=1))))

    def test_palette_requirements_and_position(self):
        palette = chunk(b'PLTE', b'\0\0\0')
        idat = chunk(b'IDAT', zlib.compress(b'\0\0'))
        self.assertFalse(self.inspect(image(head=header(color=3))))
        self.assertFalse(self.inspect(image(head=header(color=3), middle=idat+palette)))
        self.assertFalse(self.inspect(image(head=header(color=0), middle=palette+idat)))
        self.assertFalse(self.inspect(image(middle=palette+palette+idat)))
        self.assertFalse(self.inspect(image(head=header(depth=1,color=3), middle=chunk(b'PLTE', b'\0'*9)+idat)))

    def test_stream_large_ancillary_data_and_chunk_framing(self):
        self.assertTrue(self.inspect(image(middle=chunk(b'tEXt', b'note\0'+b'x'*150000)+chunk(b'IDAT', zlib.compress(b'\0'*4)))))
        for bad in (chunk(b'ABCD', b'data'), chunk(b'12!?', b'data'), struct.pack('>I',0x80000000)+b'IDAT'):
            with self.subTest(bad=bad[:8]):self.assertFalse(self.inspect(image(middle=bad)))

    def test_raster_decode_is_explicitly_outside_scope(self):
        # Correct framing/CRC alone does not prove a decoder can display pixels.
        self.assertTrue(self.inspect(image(middle=chunk(b'IDAT', b'not a zlib stream'))))

    def test_corrupt_file_is_red_even_if_required_good_count_met(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fixture(root)
            (root/'extra.PNG').write_bytes(PNG)
            args=['--manifest',str(root/'manifest.json'),'--rom',str(root/'synthetic.bin'),'--run-dir',str(root)]
            with redirect_stdout(StringIO()) as out:self.assertEqual(main(args),2)
            report=json.loads(out.getvalue())
            self.assertEqual(report['screenshots'],17)
            self.assertEqual(report['invalid_screenshots'],1)
            self.assertIn('screenshots_invalid',report['reasons'])

    def test_corrupt_images_with_matching_receipt_are_red(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fixture(root)
            for path in root.glob('*.png'):path.write_bytes(PNG)
            receipt=json.loads((root/'run_evidence.json').read_text())
            receipt['artifacts']={name:sha(root/name) for name in receipt['artifacts']}
            (root/'run_evidence.json').write_text(json.dumps(receipt))
            args=['--manifest',str(root/'manifest.json'),'--rom',str(root/'synthetic.bin'),'--run-dir',str(root),'--require-binding','--run-id','synthetic-current']
            with redirect_stdout(StringIO()) as out:self.assertEqual(main(args),2)
            report=json.loads(out.getvalue())
            self.assertEqual(report['binding'],'matched')
            self.assertEqual(report['screenshots'],0)
            self.assertEqual(report['invalid_screenshots'],17)
            self.assertIn('screenshots_invalid',report['reasons'])
            self.assertFalse(report['release_authorization'])


if __name__ == '__main__':unittest.main()
