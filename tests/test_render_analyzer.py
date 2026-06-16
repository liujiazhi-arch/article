import struct
import zlib

from thesis_tool import render_image_metrics
import thesis_tool.render_analyzer as render_analyzer
from thesis_tool.render_analyzer import analyze_page_images, analyze_render_pages


def _write_rgb_png(path, width, height, rectangles):
    rows = []
    white_row = bytes((255, 255, 255)) * width
    for y in range(height):
        row = bytearray(white_row)
        for left, top, right, bottom, color in rectangles:
            if top <= y < bottom:
                row[left * 3 : right * 3] = bytes(color) * (right - left)
        rows.append(b"\x00" + bytes(row))

    raw = zlib.compress(b"".join(rows))

    def chunk(chunk_type, payload):
        return (
            struct.pack(">I", len(payload))
            + chunk_type
            + payload
            + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


def _text_line_rectangles(start_y, end_y, *, width=700):
    rectangles = []
    for y in range(start_y, end_y, 18):
        rectangles.append((70, y, width - 70, y + 3, (30, 30, 30)))
    return rectangles


def _finding_ids(result):
    return [finding["id"] for finding in result["findings"]]


def test_analyze_page_images_flags_blank_page(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, [])

    result = analyze_page_images([str(image_path)], evidence_source="test-images")

    assert _finding_ids(result) == ["blank_page"]
    assert result["findings"][0]["page"] == 1
    assert result["findings"][0]["evidence_source"] == "test-images"
    assert result["summary"]["blank_page_count"] == 1
    assert result["summary"]["highest_severity"] == "warning"


def test_analyze_page_images_prefers_builtin_png_reader(tmp_path, monkeypatch):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, [])
    pillow_calls = []

    def fail_if_pillow_is_used(path):
        pillow_calls.append(path)
        raise AssertionError("Pillow should not be used for supported PNG files")

    monkeypatch.setattr(render_analyzer, "_read_with_pillow", fail_if_pillow_is_used)

    result = analyze_page_images([str(image_path)], evidence_source="test-images")

    assert pillow_calls == []
    assert _finding_ids(result) == ["blank_page"]


def test_analyze_page_images_rejects_invalid_png_without_pillow(tmp_path, monkeypatch):
    image_path = tmp_path / "page-1.png"
    image_path.write_bytes(b"not a png")
    pillow_calls = []

    def fail_if_pillow_is_used(path):
        pillow_calls.append(path)
        raise AssertionError("Pillow should not be used for invalid PNG files")

    monkeypatch.setattr(render_analyzer, "_read_with_pillow", fail_if_pillow_is_used)

    result = analyze_page_images([str(image_path)], evidence_source="manual-pdf")

    assert pillow_calls == []
    assert _finding_ids(result) == ["render_suspect"]
    assert result["summary"]["failed_page_count"] == 1


def test_render_image_metrics_keeps_png_suffix_on_builtin_reader(tmp_path):
    image_path = tmp_path / "page-1.png"
    calls = []
    metrics = render_image_metrics.PageImageMetrics(1, 1, 0, (0,), None)

    def fail_if_pillow_is_used(path):
        calls.append(("pillow", path))
        raise AssertionError("Pillow should not be used for PNG suffix inputs")

    def fake_png_reader(path):
        calls.append(("png", path))
        return metrics

    result = render_image_metrics.read_page_image_metrics(
        str(image_path),
        read_with_pillow_fn=fail_if_pillow_is_used,
        read_png_metrics_fn=fake_png_reader,
    )

    assert result is metrics
    assert calls == [("png", str(image_path))]


def test_render_image_metrics_falls_back_to_png_reader_for_non_png_when_pillow_fails(tmp_path):
    image_path = tmp_path / "page-1.tiff"
    calls = []
    metrics = render_image_metrics.PageImageMetrics(1, 1, 0, (0,), None)

    def fail_pillow(path):
        calls.append(("pillow", path))
        raise ImportError("Pillow unavailable")

    def fake_png_reader(path):
        calls.append(("png", path))
        return metrics

    result = render_image_metrics.read_page_image_metrics(
        str(image_path),
        read_with_pillow_fn=fail_pillow,
        read_png_metrics_fn=fake_png_reader,
    )

    assert result is metrics
    assert calls == [("pillow", str(image_path)), ("png", str(image_path))]


def test_render_image_metrics_accumulates_ink_rows_and_bbox_from_indexed_pixels():
    metrics = render_image_metrics._measure_image_pixels(
        4,
        3,
        [
            (0, [(255, 255, 255, 255), (30, 30, 30, 255), (255, 255, 255, 0), (246, 246, 246, 255)]),
            (2, [(255, 255, 255, 255), (255, 255, 255, 255), (0, 0, 0, 255), (255, 255, 255, 255)]),
        ],
    )

    assert metrics.width == 4
    assert metrics.height == 3
    assert metrics.ink_count == 2
    assert metrics.row_ink_counts == (1, 0, 1)
    assert metrics.bbox == (1, 0, 2, 2)


def test_analyze_page_images_ignores_large_bottom_blank_region(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, _text_line_rectangles(80, 560))

    result = analyze_page_images([str(image_path)], evidence_source="word-pdf")

    assert "large_blank_region" not in _finding_ids(result)
    assert result["findings"] == []
    assert "large_blank_count" not in result["summary"]
    assert "large_blank_bottom_count" not in result["summary"]
    assert "large_blank_middle_count" not in result["summary"]


def test_analyze_render_pages_filters_large_blank_region_from_public_results(tmp_path, monkeypatch):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, _text_line_rectangles(80, 560))

    monkeypatch.setattr(
        render_analyzer,
        "_analyze_page_metrics",
        lambda *args, **kwargs: [
            {
                "id": "large_blank_region",
                "severity": "warning",
                "page": 1,
                "region": {"x": 0.08, "y": 0.72, "w": 0.84, "h": 0.28},
                "bbox": {"x": 0.08, "y": 0.72, "w": 0.84, "h": 0.28},
                "message": "页底存在大块连续空白。",
                "suggested_scope": "figures_tables",
                "image_path": str(image_path),
            }
        ],
    )

    result = analyze_render_pages([str(image_path)], page_texts={1: "正文内容"}, evidence_source="word-pdf")

    assert result["findings"] == []
    assert result["summary"]["finding_count"] == 0
    assert "large_blank_count" not in result["summary"]
    assert "large_blank_bottom_count" not in result["summary"]
    assert "large_blank_middle_count" not in result["summary"]
    assert result["layout_score"]["score"] == 100


def test_analyze_render_pages_flags_isolated_chinese_punctuation_line(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(image_path)],
        page_texts={1: "研究结果如下\n，\n后续内容继续说明"},
        evidence_source="word-pdf",
    )

    assert _finding_ids(result) == ["isolated_punctuation"]
    finding = result["findings"][0]
    assert finding["rule_id"] == "render.isolated_punctuation"
    assert finding["severity"] == "warning"
    assert finding["page"] == 1
    assert finding["punctuation"] == "，"
    assert finding["classification"] == "render_text_flow"
    assert result["summary"]["isolated_punctuation_count"] == 1
    assert result["summary"]["highest_severity"] == "warning"


def test_analyze_page_images_flags_tiny_content_as_render_suspect(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, [(320, 120, 350, 145, (20, 20, 20))])

    result = analyze_page_images([str(image_path)], evidence_source="manual-pdf")

    assert _finding_ids(result) == ["render_suspect"]
    assert result["summary"]["render_suspect_count"] == 1
    assert result["summary"]["failed_page_count"] == 0


def test_analyze_page_images_accepts_normal_page_without_severe_findings(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_page_images([str(image_path)], evidence_source="word-pdf")

    assert result["findings"] == []
    assert result["summary"]["finding_count"] == 0
    assert result["summary"]["highest_severity"] is None


def test_analyze_page_images_reports_unreadable_image(tmp_path):
    image_path = tmp_path / "page-1.png"
    image_path.write_bytes(b"not a png")

    result = analyze_page_images([str(image_path)], evidence_source="manual-pdf")

    assert _finding_ids(result) == ["render_suspect"]
    assert result["findings"][0]["severity"] == "error"
    assert result["summary"]["failed_page_count"] == 1


def test_analyze_render_pages_omits_chapter_break_blank_from_findings(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "上一章结尾文字", 2: "第 2 章 实验材料与方法\n2.1 材料"},
        evidence_source="word-pdf",
    )

    assert result["findings"] == []
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["summary"]["expected_blank_count"] == 0


def test_analyze_render_pages_omits_blank_before_figure_from_findings(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "结果显示不同处理组存在差异。", 2: "图 3.2 不同改性方法的结构变化\n注：A 为对照组。"},
        evidence_source="word-pdf",
    )

    assert result["findings"] == []
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["summary"]["object_flow_issue_count"] == 0


def test_analyze_render_pages_omits_isolated_heading_blank_from_findings(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "3.2 改性鹿皮明胶功能特性", 2: "改性后样品的乳化性和起泡性均发生变化。"},
        evidence_source="word-pdf",
    )

    assert result["findings"] == []
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["summary"]["heading_break_issue_count"] == 0


def test_analyze_render_pages_flags_formula_number_split_across_pages(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 870))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "样品溶胀率按下式计算\nSR = (Wt - W0) / W0 × 100%", 2: "（1.1）\n式中，W0 为初始质量。"},
        evidence_source="manual-pdf",
    )

    assert "formula_number_split_page" in _finding_ids(result)
    finding = next(item for item in result["findings"] if item["id"] == "formula_number_split_page")
    assert finding["rule_id"] == "render.formula_number_split_page"
    assert finding["page"] == 2
    assert finding["previous_page"] == 1
    assert "（1.1）" in finding["formula_number"]
    assert result["summary"]["formula_number_split_count"] == 1


def test_analyze_render_pages_flags_heading_orphan_when_text_and_image_agree(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 520))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "3.2 改性鹿皮明胶功能特性", 2: "改性后样品的乳化性和起泡性均发生变化。"},
        evidence_source="manual-pdf",
    )

    assert "heading_orphan_at_page_bottom" in _finding_ids(result)
    finding = next(item for item in result["findings"] if item["id"] == "heading_orphan_at_page_bottom")
    assert finding["rule_id"] == "render.heading_orphan_at_page_bottom"
    assert finding["page"] == 1
    assert finding["heading_text"] == "3.2 改性鹿皮明胶功能特性"
    assert result["summary"]["heading_break_issue_count"] == 1


def test_analyze_render_pages_omits_plain_blank_region_from_findings(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={
            1: "结果显示不同处理组存在差异，并在本页末尾自然结束。",
            2: "下一页继续描述统计分析过程和实验观察结果。",
        },
        evidence_source="word-pdf",
    )

    assert result["findings"] == []
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["summary"]["suspicious_blank_count"] == 0
    assert result["layout_score"]["score"] == 100
    assert result["layout_score"]["penalty"] == 0


def test_analyze_render_pages_does_not_score_ordinary_layout_whitespace_as_actionable(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    page3 = tmp_path / "page-3.png"
    page4 = tmp_path / "page-4.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))
    _write_rgb_png(page3, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page4, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2), str(page3), str(page4)],
        page_texts={
            1: "第一章结尾文字",
            2: "第 2 章 实验材料与方法",
            3: "结果显示不同处理组存在差异。",
            4: "图 3.2 不同改性方法的结构变化",
        },
        evidence_source="word-pdf",
    )

    assert result["summary"]["expected_blank_count"] == 0
    assert result["summary"]["object_flow_issue_count"] == 0
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["layout_score"] == {
        "score": 100,
        "penalty": 0,
        "expected_blank_count": 0,
        "actionable_finding_count": 0,
        "object_flow_issue_count": 0,
        "heading_break_issue_count": 0,
        "render_integrity_issue_count": 0,
    }
