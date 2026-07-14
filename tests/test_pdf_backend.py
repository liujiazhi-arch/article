from pathlib import Path
from types import SimpleNamespace

import pytest

from thesis_tool import pdf_backend


class _FakeTextPage:
    def __init__(self, chars, boxes):
        self.chars = chars
        self.boxes = boxes
        self.closed = False

    def count_chars(self):
        return len(self.chars)

    def get_text_range(self, index, _count):
        return self.chars[index]

    def get_charbox(self, index):
        return self.boxes[index]

    def close(self):
        self.closed = True


class _FakePage:
    def __init__(self, chars, boxes):
        self.text_page = _FakeTextPage(chars, boxes)
        self.closed = False

    def get_textpage(self):
        return self.text_page

    def get_bbox(self):
        return (10.0, 20.0, 585.0, 820.0)

    def get_size(self):
        return (800.0, 575.0)

    def get_rotation(self):
        return 90

    def close(self):
        self.closed = True


class _FakeDocument:
    def __init__(self, _path):
        self.pages = [
            _FakePage(
                ["题", "\r", "\n", "，"],
                [
                    (110.0, 320.0, 130.0, 340.0),
                    (0.0, 0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0, 0.0),
                    (110.0, 280.0, 115.0, 290.0),
                ],
            ),
            _FakePage([], []),
        ]

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def close(self):
        pass


class _FakePdfium:
    PdfDocument = _FakeDocument


class _TrackedImage:
    def __init__(self):
        self.closed = False
        self.saved = None

    def save(self, path, image_format):
        self.saved = (path, image_format)

    def close(self):
        self.closed = True


class _TrackedBitmap:
    def __init__(self, image):
        self.image = image
        self.closed = False

    def to_pil(self):
        return self.image

    def close(self):
        self.closed = True


class _RenderPage:
    def __init__(self):
        self.image = _TrackedImage()
        self.bitmap = _TrackedBitmap(self.image)
        self.scale = None
        self.closed = False

    def render(self, *, scale):
        self.scale = scale
        return self.bitmap

    def close(self):
        self.closed = True


class _TrackedDocument:
    def __init__(self, *pages):
        self.pages = list(pages)
        self.closed = False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    ("rotation", "page_size", "expected"),
    [
        (0, (100.0, 200.0), {"x": 0.1, "y": 0.85, "w": 0.2, "h": 0.1}),
        (90, (200.0, 100.0), {"x": 0.05, "y": 0.1, "w": 0.1, "h": 0.2}),
        (180, (100.0, 200.0), {"x": 0.7, "y": 0.05, "w": 0.2, "h": 0.1}),
        (270, (200.0, 100.0), {"x": 0.85, "y": 0.7, "w": 0.1, "h": 0.2}),
    ],
)
def test_normalized_charbox_handles_all_supported_rotations(rotation, page_size, expected):
    bbox = pdf_backend._normalized_charbox(
        (20.0, 30.0, 40.0, 50.0),
        (10.0, 20.0, 110.0, 220.0),
        page_size,
        rotation,
    )

    assert bbox == pytest.approx(expected, abs=1e-6)


def test_pdfium_line_boxes_normalize_crop_rotation_and_empty_text(monkeypatch, tmp_path):
    pdf_path = tmp_path / "proof.pdf"
    pdf_path.write_bytes(b"%PDF")
    monkeypatch.setattr(pdf_backend, "_load_pdfium", lambda: _FakePdfium)

    pages = pdf_backend.extract_pdf_line_boxes_with_pdfium(Path(pdf_path))

    assert pages[1][0]["text"] == "题"
    assert pages[1][0]["bbox"] == pytest.approx({"x": 0.375, "y": 100 / 575, "w": 0.025, "h": 20 / 575}, abs=1e-6)
    assert pages[1][1]["text"] == "，"
    assert pages[1][1]["bbox"] == pytest.approx({"x": 0.325, "y": 100 / 575, "w": 0.0125, "h": 5 / 575}, abs=1e-6)
    assert pages[2] == []


def test_pdfium_render_adapter_saves_pages_and_closes_native_resources(monkeypatch, tmp_path):
    page = _RenderPage()
    document = _TrackedDocument(page)
    monkeypatch.setattr(
        pdf_backend,
        "_load_pdfium",
        lambda: SimpleNamespace(PdfDocument=lambda _path: document),
    )

    pdf_backend.convert_pdf_with_pdfium("input.pdf", tmp_path)

    assert page.scale == pytest.approx(120 / 72)
    assert page.image.saved == (tmp_path / "page-1.png", "PNG")
    assert page.image.closed is True
    assert page.bitmap.closed is True
    assert page.closed is True
    assert document.closed is True


def test_pdfium_text_adapter_returns_page_text_and_closes_native_resources(monkeypatch, tmp_path):
    text_page = _FakeTextPage([], [])
    text_page.get_text_bounded = lambda: "第一页正文"
    page = _FakePage([], [])
    page.text_page = text_page
    document = _TrackedDocument(page)
    monkeypatch.setattr(
        pdf_backend,
        "_load_pdfium",
        lambda: SimpleNamespace(PdfDocument=lambda _path: document),
    )

    texts = pdf_backend.extract_pdf_text_pages_with_pdfium(tmp_path / "input.pdf")

    assert texts == ["第一页正文"]
    assert text_page.closed is True
    assert page.closed is True
    assert document.closed is True


@pytest.mark.parametrize(
    ("raw_box", "page_bbox", "page_size", "rotation"),
    [
        ((float("nan"), 0, 1, 1), (0, 0, 10, 10), (10, 10), 0),
        ((2, 2, 1, 3), (0, 0, 10, 10), (10, 10), 0),
        ((1, 1, 2, 2), (0, 0, 10, 10), (10, 10), 45),
        ((20, 20, 30, 30), (0, 0, 10, 10), (10, 10), 0),
    ],
)
def test_normalized_charbox_rejects_unusable_coordinates(raw_box, page_bbox, page_size, rotation):
    assert pdf_backend._normalized_charbox(raw_box, page_bbox, page_size, rotation) is None


def test_pdfium_page_lines_reject_a_line_when_any_visible_character_has_no_box():
    page = _FakePage(
        ["正", " ", "文"],
        [
            (110.0, 320.0, 130.0, 340.0),
            (0.0, 0.0, 0.0, 0.0),
            (130.0, 320.0, 120.0, 340.0),
        ],
    )

    assert pdf_backend._pdfium_page_lines(page, page.text_page) == []


def test_pdfium_line_extraction_degrades_only_the_broken_page(monkeypatch, tmp_path, caplog):
    broken_page = _FakePage([], [])

    def fail_text_page():
        raise RuntimeError("broken text layer")

    broken_page.get_textpage = fail_text_page
    good_page = _FakePage(["好"], [(110.0, 320.0, 130.0, 340.0)])
    document = _TrackedDocument(broken_page, good_page)
    monkeypatch.setattr(
        pdf_backend,
        "_load_pdfium",
        lambda: SimpleNamespace(PdfDocument=lambda _path: document),
    )

    with caplog.at_level("WARNING"):
        pages = pdf_backend.extract_pdf_line_boxes_with_pdfium(tmp_path / "broken.pdf")

    assert pages[1] == []
    assert pages[2][0]["text"] == "好"
    assert "第 1 页文字坐标" in caplog.text
    assert broken_page.closed is True
    assert good_page.text_page.closed is True
    assert good_page.closed is True
    assert document.closed is True
