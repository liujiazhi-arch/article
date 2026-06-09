from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib
from typing import Callable, Iterable


WHITE_LUMA_THRESHOLD = 245


@dataclass(frozen=True)
class PageImageMetrics:
    width: int
    height: int
    ink_count: int
    row_ink_counts: tuple[int, ...]
    bbox: tuple[int, int, int, int] | None

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def ink_ratio(self) -> float:
        if self.pixel_count <= 0:
            return 0.0
        return self.ink_count / self.pixel_count

    @property
    def content_area_ratio(self) -> float:
        if self.pixel_count <= 0 or self.bbox is None:
            return 0.0
        left, top, right, bottom = self.bbox
        return ((right - left + 1) * (bottom - top + 1)) / self.pixel_count


def read_page_image_metrics(
    image_path: str,
    *,
    read_with_pillow_fn: Callable[[str], PageImageMetrics] | None = None,
    read_png_metrics_fn: Callable[[str], PageImageMetrics] | None = None,
) -> PageImageMetrics:
    read_with_pillow_fn = read_with_pillow_fn or read_with_pillow
    read_png_metrics_fn = read_png_metrics_fn or read_png_metrics
    path = Path(image_path)
    if path.suffix.lower() == ".png":
        return read_png_metrics_fn(image_path)
    try:
        return read_with_pillow_fn(image_path)
    except ImportError:
        return read_png_metrics_fn(image_path)
    except Exception:
        return read_png_metrics_fn(image_path)


def read_with_pillow(image_path: str) -> PageImageMetrics:
    from PIL import Image

    with Image.open(image_path) as image:
        rgba_image = image.convert("RGBA")
        width, height = rgba_image.size
        pixel_rows = (
            (y, (rgba_image.getpixel((x, y)) for x in range(width)))
            for y in range(height)
        )
        return _measure_image_pixels(width, height, pixel_rows)


def read_png_metrics(image_path: str) -> PageImageMetrics:
    width, height, color_type, bit_depth, raw_rows, palette = decode_png(Path(image_path).read_bytes())
    white_row = white_png_row(width, color_type, bit_depth)

    pixel_rows = (
        (y, iter_png_pixels(row, width, color_type, bit_depth, palette))
        for y, row in enumerate(raw_rows)
        if white_row is None or row != white_row
    )
    return _measure_image_pixels(width, height, pixel_rows)


def _measure_image_pixels(
    width: int,
    height: int,
    indexed_pixel_rows: Iterable[tuple[int, Iterable[tuple[int, int, int, int]]]],
) -> PageImageMetrics:
    rows = [0] * height
    ink_count = 0
    bbox = _Bbox()
    for y, pixel_row in indexed_pixel_rows:
        for x, pixel in enumerate(pixel_row):
            r, g, b, alpha = pixel
            if is_ink(r, g, b, alpha):
                rows[y] += 1
                ink_count += 1
                bbox.add(x, y)
    return PageImageMetrics(width, height, ink_count, tuple(rows), bbox.as_tuple())


def white_png_row(width: int, color_type: int, bit_depth: int) -> bytes | None:
    if bit_depth != 8:
        return None
    if color_type == 0:
        return b"\xff" * width
    if color_type == 2:
        return b"\xff\xff\xff" * width
    if color_type == 4:
        return b"\xff\xff" * width
    if color_type == 6:
        return b"\xff\xff\xff\xff" * width
    return None


def decode_png(data: bytes) -> tuple[int, int, int, int, list[bytes], list[tuple[int, int, int]]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG file")

    offset = 8
    width = height = color_type = bit_depth = None
    interlace = 0
    palette: list[tuple[int, int, int]] = []
    idat_parts: list[bytes] = []

    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk")
        chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + chunk_length]
        offset += 12 + chunk_length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"PLTE":
            palette = [
                tuple(chunk_data[index : index + 3])  # type: ignore[arg-type]
                for index in range(0, len(chunk_data), 3)
                if len(chunk_data[index : index + 3]) == 3
            ]
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None or bit_depth is None:
        raise ValueError("missing PNG header")
    if interlace:
        raise ValueError("interlaced PNG is not supported")
    if bit_depth not in {8, 16}:
        raise ValueError(f"unsupported PNG bit depth: {bit_depth}")

    channel_count = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channel_count is None:
        raise ValueError(f"unsupported PNG color type: {color_type}")

    bytes_per_sample = 2 if bit_depth == 16 else 1
    bytes_per_pixel = channel_count * bytes_per_sample
    stride = width * bytes_per_pixel
    inflated = zlib.decompress(b"".join(idat_parts))
    expected = height * (stride + 1)
    if len(inflated) < expected:
        raise ValueError("truncated PNG image data")

    rows: list[bytes] = []
    previous = bytes(stride)
    position = 0
    for _row_index in range(height):
        filter_type = inflated[position]
        encoded = inflated[position + 1 : position + 1 + stride]
        decoded = unfilter_png_row(filter_type, encoded, previous, bytes_per_pixel)
        rows.append(decoded)
        previous = decoded
        position += stride + 1

    return width, height, color_type, bit_depth, rows, palette


def unfilter_png_row(filter_type: int, row: bytes, previous: bytes, bytes_per_pixel: int) -> bytes:
    result = bytearray(row)
    for index, value in enumerate(result):
        left = result[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            continue
        if filter_type == 1:
            result[index] = (value + left) & 0xFF
        elif filter_type == 2:
            result[index] = (value + up) & 0xFF
        elif filter_type == 3:
            result[index] = (value + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            result[index] = (value + paeth(left, up, up_left)) & 0xFF
        else:
            raise ValueError(f"unsupported PNG filter type: {filter_type}")
    return bytes(result)


def paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left


def iter_png_pixels(
    row: bytes,
    width: int,
    color_type: int,
    bit_depth: int,
    palette: list[tuple[int, int, int]],
):
    sample_size = 2 if bit_depth == 16 else 1
    step = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type] * sample_size
    for x in range(width):
        offset = x * step
        values = [sample_to_byte(row[offset + index : offset + index + sample_size]) for index in range(0, step, sample_size)]
        if color_type == 0:
            gray = values[0]
            yield gray, gray, gray, 255
        elif color_type == 2:
            yield values[0], values[1], values[2], 255
        elif color_type == 3:
            palette_index = values[0]
            r, g, b = palette[palette_index] if palette_index < len(palette) else (255, 255, 255)
            yield r, g, b, 255
        elif color_type == 4:
            gray, alpha = values
            yield gray, gray, gray, alpha
        elif color_type == 6:
            yield values[0], values[1], values[2], values[3]


def sample_to_byte(sample: bytes) -> int:
    if len(sample) == 2:
        return sample[0]
    return sample[0]


def is_ink(r: int, g: int, b: int, alpha: int) -> bool:
    if alpha < 16:
        return False
    luma = (299 * r + 587 * g + 114 * b) // 1000
    return luma < WHITE_LUMA_THRESHOLD


class _Bbox:
    def __init__(self) -> None:
        self.left: int | None = None
        self.top: int | None = None
        self.right: int | None = None
        self.bottom: int | None = None

    def add(self, x: int, y: int) -> None:
        self.left = x if self.left is None else min(self.left, x)
        self.top = y if self.top is None else min(self.top, y)
        self.right = x if self.right is None else max(self.right, x)
        self.bottom = y if self.bottom is None else max(self.bottom, y)

    def as_tuple(self) -> tuple[int, int, int, int] | None:
        if self.left is None or self.top is None or self.right is None or self.bottom is None:
            return None
        return self.left, self.top, self.right, self.bottom
