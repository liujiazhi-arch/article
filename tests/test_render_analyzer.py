import struct
import zlib

from thesis_tool.render_analyzer import analyze_page_images, analyze_render_pages


def _write_rgb_png(path, width, height, rectangles):
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            color = (255, 255, 255)
            for left, top, right, bottom, candidate_color in rectangles:
                if left <= x < right and top <= y < bottom:
                    color = candidate_color
                    break
            row.extend(color)
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


def test_analyze_page_images_flags_large_bottom_blank_region(tmp_path):
    image_path = tmp_path / "page-1.png"
    _write_rgb_png(image_path, 700, 1000, _text_line_rectangles(80, 560))

    result = analyze_page_images([str(image_path)], evidence_source="word-pdf")

    assert "large_blank_region" in _finding_ids(result)
    finding = result["findings"][0]
    assert finding["page"] == 1
    assert finding["suggested_scope"] == "figures_tables"
    assert finding["region"]["y"] > 0.55
    assert result["summary"]["large_blank_count"] == 1
    assert result["summary"]["large_blank_bottom_count"] == 1


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


def test_analyze_render_pages_marks_chapter_break_blank_as_expected(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "上一章结尾文字", 2: "第 2 章 实验材料与方法\n2.1 材料"},
        evidence_source="word-pdf",
    )

    finding = result["findings"][0]
    assert finding["classification"] == "expected_chapter_break"
    assert finding["actionable"] is False
    assert finding["suggested_scope"] is None
    assert "下一页为章节起始页" in finding["reason"]
    assert result["summary"]["actionable_finding_count"] == 0
    assert result["summary"]["expected_blank_count"] == 1


def test_analyze_render_pages_marks_blank_before_figure_as_object_flow(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "结果显示不同处理组存在差异。", 2: "图 3.2 不同改性方法的结构变化\n注：A 为对照组。"},
        evidence_source="word-pdf",
    )

    finding = result["findings"][0]
    assert finding["classification"] == "suspicious_object_flow"
    assert finding["actionable"] is True
    assert finding["suggested_scope"] == "figures_tables"
    assert "--layout-rebalance" in finding["suggested_action"]
    assert result["summary"]["actionable_finding_count"] == 1
    assert result["summary"]["object_flow_issue_count"] == 1


def test_analyze_render_pages_marks_isolated_heading_as_heading_break(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    _write_rgb_png(page1, 700, 1000, _text_line_rectangles(80, 540))
    _write_rgb_png(page2, 700, 1000, _text_line_rectangles(80, 870))

    result = analyze_render_pages(
        [str(page1), str(page2)],
        page_texts={1: "3.2 改性鹿皮明胶功能特性", 2: "改性后样品的乳化性和起泡性均发生变化。"},
        evidence_source="word-pdf",
    )

    finding = result["findings"][0]
    assert finding["classification"] == "suspicious_heading_break"
    assert finding["actionable"] is True
    assert finding["suggested_scope"] == "headings"
    assert "pageBreakBefore" in finding["suggested_action"]
    assert result["summary"]["heading_break_issue_count"] == 1


def test_analyze_render_pages_scores_actionable_layout_findings_only(tmp_path):
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

    assert result["summary"]["expected_blank_count"] == 1
    assert result["summary"]["object_flow_issue_count"] == 1
    assert result["layout_score"] == {
        "score": 88,
        "penalty": 12,
        "expected_blank_count": 1,
        "actionable_finding_count": 1,
        "object_flow_issue_count": 1,
        "heading_break_issue_count": 0,
        "render_integrity_issue_count": 0,
    }
