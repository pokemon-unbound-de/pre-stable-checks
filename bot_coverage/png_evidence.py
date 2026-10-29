"""PNG core structure and chunk CRC checks, not a pixel/image-content decoder.

Reference: https://www.w3.org/TR/png/ (signature, critical chunks, CRC).
"""
import struct
import zlib

PNG = b'\x89PNG\r\n\x1a\n'
DEPTHS = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8},
          4: {8, 16}, 6: {8, 16}}
CRITICAL = {b'IHDR', b'PLTE', b'IDAT', b'IEND'}


def png_structure_ok(path):
    """Stream bounded-size blocks; do not allocate/decompress image pixels.

    File IO errors propagate as input errors. Malformed structure returns False.
    Compressed raster data and ancillary-chunk semantics are intentionally opaque.
    """
    with path.open('rb') as stream:
        if stream.read(8) != PNG:
            return False
        header = None
        palette = False
        idat_seen = False
        idat_finished = False
        idat_bytes = 0
        while True:
            framing = stream.read(8)
            if len(framing) != 8:
                return False
            length, kind = struct.unpack('>I4s', framing)
            if length > 0x7fffffff or not all(65 <= c <= 90 or 97 <= c <= 122 for c in kind):
                return False
            if header is None and (kind != b'IHDR' or length != 13):
                return False
            if kind == b'IHDR' and (header is not None or length != 13):
                return False
            if kind == b'PLTE' and (palette or idat_seen or length == 0 or length > 768 or length % 3):
                return False
            if kind == b'IDAT' and idat_finished:
                return False
            if kind == b'IEND' and length != 0:
                return False
            if kind[0] < 97 and kind not in CRITICAL:
                return False  # An unknown critical chunk cannot be understood here.
            crc = zlib.crc32(kind)
            remaining = length
            data = bytearray()
            while remaining:
                block = stream.read(min(remaining, 65536))
                if not block:
                    return False
                crc = zlib.crc32(block, crc)
                if kind == b'IHDR':
                    data.extend(block)  # Exactly13 bytes, never image-sized allocation.
                remaining -= len(block)
            checksum = stream.read(4)
            if len(checksum) != 4 or struct.unpack('>I', checksum)[0] != crc & 0xffffffff:
                return False
            if kind == b'IHDR':
                width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', data)
                if not (0 < width <= 0x7fffffff and 0 < height <= 0x7fffffff):
                    return False
                if depth not in DEPTHS.get(color, set()) or compression != 0 or filtering != 0 or interlace not in (0, 1):
                    return False
                header = (depth, color)
            elif kind == b'PLTE':
                if header[1] in (0, 4) or (header[1] == 3 and length // 3 > 2 ** header[0]):
                    return False
                palette = True
            elif kind == b'IDAT':
                if header[1] == 3 and not palette:
                    return False
                idat_seen = True
                idat_bytes += length
            elif kind == b'IEND':
                return idat_seen and idat_bytes > 0 and not stream.read(1)
            if idat_seen and kind != b'IDAT':
                idat_finished = True
