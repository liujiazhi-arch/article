from __future__ import annotations

import re

from citation_text_utils import (
    CITATION_TOKEN_RE,
    citation_numbers_from_token as _citation_numbers_from_token,
    format_citation_numbers as _format_citation_numbers,
)
from _thesis_utils import NSMAP, W_NS, _looks_like_toc_entry, get_paragraph_text
from frontmatter_utils import (
    is_cn_keywords_paragraph_text,
    is_keyword_paragraph_text,
    is_toc_entry_style as is_toc_entry_style_shared,
    is_toc_heading_style as is_toc_heading_style_shared,
)
from thesis_rules.audit_checkers import *
from thesis_rules.audit_checkers import (
    _compact_table_cell_text,
    _needs_cjk_latin_space,
    _needs_num_cjk_space,
)

_CITATION_TOKEN_RE = CITATION_TOKEN_RE
INLINE_CITATION_PAT = CITATION_TOKEN_RE
_PU01_CJK_RE = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_PU01_HALF_PUNCT_RE = re.compile(
    rf"(?<={_PU01_CJK_RE})[,;:]|[,;:](?={_PU01_CJK_RE})|(?<={_PU01_CJK_RE})\.(?!\d)|\.(?={_PU01_CJK_RE})"
)

def check_p01(document_root, contexts, style_map, cfg):
    invalid = []
    min_margin, max_margin = cfg["margin_range"]
    exact_expected = {
        "top": cfg.get("margin_fix_top"),
        "bottom": cfg.get("margin_fix_bottom"),
        "left": cfg.get("margin_fix_left"),
        "right": cfg.get("margin_fix_right"),
    }
    use_exact_by_side = len({value for value in exact_expected.values() if value is not None}) > 1
    # 只检查正文节页边距，跳过封面节（第一个 inline sectPr）
    body = document_root.find("w:body", NSMAP)
    sect_prs_to_check = []
    if body is not None:
        main_sect = body.find("w:sectPr", NSMAP)
        if main_sect is not None:
            pg_mar = main_sect.find("w:pgMar", NSMAP)
            if pg_mar is not None:
                sect_prs_to_check.append(pg_mar)
        inline_sects = [
            p.find("w:pPr/w:sectPr", NSMAP)
            for p in body.findall("w:p", NSMAP)
        ]
        inline_sects = [s for s in inline_sects if s is not None]
        for s in inline_sects[1:]:  # 跳过第一个（封面节）
            pg_mar = s.find("w:pgMar", NSMAP)
            if pg_mar is not None:
                sect_prs_to_check.append(pg_mar)
    else:
        sect_prs_to_check = document_root.findall(".//w:sectPr/w:pgMar", NSMAP)
    pg_margins = sect_prs_to_check
    for idx, pg_mar in enumerate(pg_margins, start=1):
        bad_attrs = []
        for attr_name in ("left", "right", "top", "bottom"):
            attr_val = parse_int(get_w_attr(pg_mar, attr_name))
            if attr_val is None:
                bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
                continue
            if use_exact_by_side:
                expected_val = exact_expected.get(attr_name)
                if expected_val is None or attr_val != expected_val:
                    bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
                continue
            if not (min_margin <= attr_val <= max_margin):
                bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
        if bad_attrs:
            invalid.append(f"第{idx}个节页边距异常：{', '.join(bad_attrs)}")

    if invalid:
        return False, invalid, f"节属性 {len(invalid)} 处"
    return True, [], "全部节属性"

def check_t01(document_root, contexts, style_map):
    cjk_re = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
    bad_runs = []
    positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            if is_citation_run_text(run_text):
                continue
            if not cjk_re.search(run_text):
                continue  # 纯ASCII run 无需检查 eastAsia
            east_asia = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="eastAsia")
            if east_asia not in ("宋体", "SimSun"):
                bad_runs.append(
                    f"第{ctx['index']}段存在 {len(bad_runs) + 1} 处正文 run 的 eastAsia 不是宋体/SimSun，示例{excerpt(run_text)}"
                )
                positions.append(ctx["index"])
                if len(bad_runs) >= 5:
                    break
        if len(bad_runs) >= 5:
            break

    total = 0
    affected_positions = set()
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            if is_citation_run_text(run_text):
                continue
            if not cjk_re.search(run_text):
                continue
            east_asia = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="eastAsia")
            if east_asia not in ("宋体", "SimSun"):
                total += 1
                affected_positions.add(ctx["index"])

    if total:
        issues = [f"{total} 个正文 run 的 eastAsia 不是宋体/SimSun。"]
        issues.extend(bad_runs[:3])
        return False, issues, summarize_positions(sorted(affected_positions))
    return True, [], "全部正文段落"

def check_t02(document_root, contexts, style_map):
    total = 0
    samples = []
    positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            ascii_font = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="ascii")
            hansi_font = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="hAnsi")
            if ascii_font != "Times New Roman" or hansi_font != "Times New Roman":
                total += 1
                positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(
                        f"第{ctx['index']}段 run '{excerpt(run_text)}' 的 ascii={ascii_font}、hAnsi={hansi_font}"
                    )

    if total:
        issues = [f"{total} 个正文 run 的西文字体不是 Times New Roman。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部正文段落"

def check_t03(document_root, contexts, style_map, cfg):
    total = 0
    samples = []
    positions = []
    min_size, max_size = cfg["body_size_range"]
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            size_val = get_effective_run_size(run_elem, style_map, ctx["elem"])
            if size_val is None or not (min_size <= size_val <= max_size):
                total += 1
                positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段 run '{excerpt(run_text)}' 的字号为 {size_val}")

    if total:
        issues = [f"{total} 个正文 run 的字号不在 {min_size}~{max_size} 范围内。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部正文段落"

def check_t04(document_root, contexts, style_map, cfg=None):
    bad_positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        line_val = get_paragraph_line_spacing(ctx["elem"], style_map)
        if line_val != 360:
            bad_positions.append(ctx["index"])
            continue
        if spacing is not None and get_w_attr(spacing, "line") is not None and get_w_attr(spacing, "lineRule") != "auto":
            bad_positions.append(ctx["index"])
            continue
        if cfg and cfg.get("check_snap_to_grid"):
            snap = ctx["elem"].find("w:pPr/w:snapToGrid", NSMAP)
            snap_val = get_w_attr(snap, "val") if snap is not None else None
            if snap_val in {"1", "true", "True", "on"}:
                bad_positions.append(ctx["index"])
    if bad_positions:
        return (
            False,
            [f"{len(bad_positions)} 个正文段落的行距不是 360、lineRule 不是 auto，或未关闭 snapToGrid 网格对齐。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部正文段落"

def check_t05(document_root, contexts, style_map):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        jc_val = get_w_attr(ctx["elem"].find("w:pPr/w:jc", NSMAP), "val")
        if jc_val == "center":
            continue
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        first_line = parse_int(get_w_attr(ind, "firstLine"))
        if first_line is None or not (420 <= first_line <= 480):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段首行缩进为 {get_w_attr(ind, 'firstLine')}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落首行缩进不在 420~480 范围内。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部正文段落"

def check_t06(document_root, contexts, style_map):
    bad_positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        jc_val = get_w_attr(ctx["elem"].find("w:pPr/w:jc", NSMAP), "val")
        if jc_val == "center":
            continue
        jc = ctx["elem"].find("w:pPr/w:jc", NSMAP)
        if get_w_attr(jc, "val") != "both":
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个正文段落未设置两端对齐。"], summarize_positions(bad_positions)
    return True, [], "全部正文段落"

def check_sp01(document_root, contexts, style_map):
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        elem = ctx["elem"].find("w:pPr/w:autoSpaceDE", NSMAP)
        val = get_w_attr(elem, "val") if elem is not None else "1"
        if val != "0":
            bad.append(ctx["index"])
    if bad:
        return False, [f"{len(bad)} 个正文段落未关闭中英文自动间距（autoSpaceDE≠0）。"], summarize_positions(bad)
    return True, [], "全部正文段落"

def check_sp02(document_root, contexts, style_map):
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        elem = ctx["elem"].find("w:pPr/w:autoSpaceDN", NSMAP)
        val = get_w_attr(elem, "val") if elem is not None else "1"
        if val != "0":
            bad.append(ctx["index"])
    if bad:
        return False, [f"{len(bad)} 个正文段落未关闭中数字自动间距（autoSpaceDN≠0）。"], summarize_positions(bad)
    return True, [], "全部正文段落"

def check_sp_cjk_latin(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    evidence = []
    for ctx in contexts:
        if ctx.get("section") != "body":
            continue
        if ctx.get("protected") or ctx.get("kind") in {"reference", "caption", "h1", "h2", "h3", "h4"}:
            continue
        matches = find_missing_spacing_pairs_with_positions(ctx.get("text", ""), _needs_cjk_latin_space)
        if cfg and cfg.get("relax_body_spacing_rules"):
            matches = [match for match in matches if not re.search(r"\b\d+\s*T\b", match["excerpt"])]
        if cfg and cfg.get("relax_strain_suffix_t_spacing"):
            matches = [match for match in matches if not is_relaxed_strain_suffix_t_excerpt(match["excerpt"])]
        if matches:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段存在中英文紧邻：{excerpt(matches[0]['excerpt'])}")
            evidence.append(
                {
                    "paragraph_index": ctx["index"],
                    "section": ctx.get("section"),
                    "module": ctx.get("module"),
                    "kind": ctx.get("kind"),
                    "text": ctx.get("text", ""),
                    "tokens": [
                        {
                            "text": f"{match['left']}{match['right']}",
                            "bad_part": f"{match['left']}{match['right']}",
                            "actual": "missing_space",
                            "expected": "space_between_cjk_latin",
                            "start": match["start"],
                            "end": match["end"],
                        }
                        for match in matches
                    ],
                }
            )
    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落存在中英文字符间距缺失。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions), evidence
    return True, [], "正文段落中英文间距正常"

def check_sp_num_cjk(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    evidence = []
    for ctx in contexts:
        if ctx.get("section") != "body":
            continue
        if ctx.get("protected") or ctx.get("kind") in {"reference", "caption", "h1", "h2", "h3", "h4"}:
            continue
        matches = find_missing_spacing_pairs_with_positions(ctx.get("text", ""), _needs_num_cjk_space)
        if cfg and cfg.get("relax_body_spacing_rules"):
            matches = [match for match in matches if not re.search(r"(图|表|式)\d", match["excerpt"])]
        if matches:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段存在中文与数字紧邻：{excerpt(matches[0]['excerpt'])}")
            evidence.append(
                {
                    "paragraph_index": ctx["index"],
                    "section": ctx.get("section"),
                    "module": ctx.get("module"),
                    "kind": ctx.get("kind"),
                    "text": ctx.get("text", ""),
                    "tokens": [
                        {
                            "text": f"{match['left']}{match['right']}",
                            "bad_part": f"{match['left']}{match['right']}",
                            "actual": "missing_space",
                            "expected": "space_between_number_and_cjk",
                            "start": match["start"],
                            "end": match["end"],
                        }
                        for match in matches
                    ],
                }
            )
    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落存在中文与数字间距缺失。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions), evidence
    return True, [], "正文段落中文与数字间距正常"

def check_heading(contexts, heading_kind, expected_jc, require_size, expected_font=None, require_bold=False):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_heading_audit_context(ctx, heading_kind):
            continue
        jc = ctx["elem"].find("w:pPr/w:jc", NSMAP)
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        first_line = get_w_attr(ind, "firstLine")
        jc_val = get_w_attr(jc, "val")
        if expected_jc == "left" and jc_val is None:
            jc_val = "left"
        heading_ok = jc_val == expected_jc and (first_line in (None, "0"))

        run_ok = True
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            if not get_run_text(run_elem).strip():
                continue
            if require_bold and not is_bold(run_elem):
                run_ok = False
                break
            if not require_bold and is_bold(run_elem):
                run_ok = False
                break
            if require_size is not None:
                sz = run_elem.find("w:rPr/w:sz", NSMAP)
                if get_w_attr(sz, "val") != str(require_size):
                    run_ok = False
                    break
            if expected_font is not None:
                r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
                ea_font = get_w_attr(r_fonts, "eastAsia") if r_fonts is not None else None
                if ea_font is not None and ea_font != expected_font:
                    run_ok = False
                    break

        if not (heading_ok and run_ok):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段标题'{excerpt(ctx['text'])}'格式不符合要求")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个 {heading_kind} 段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部对应标题"

def check_heading_num_space(contexts):
    bad_positions = []
    issues = []

    for ctx in contexts:
        if ctx.get("kind") not in {"h2", "h3", "h4"}:
            continue
        if not is_heading_audit_context(ctx, ctx.get("kind")):
            continue
        text = ctx.get("text", "") or ""
        # 贪婪提取编号部分（防止回溯误判），再检测后续字符
        num_match = re.match(r"^(\d+(?:\s*\.\s*\d+)+)(.*)", text, re.DOTALL)
        if not num_match:
            continue
        num_prefix = num_match.group(1)
        rest = num_match.group(2)
        # 编号内部有乱空格（如 "1.1 .2"）
        has_inner_dot_space = (
            re.search(r"\s+\.", num_prefix) is not None
            or re.search(r"\.\s+", num_prefix) is not None
        )
        # 编号后紧跟非空字符（缺少空格）
        has_missing_gap = bool(rest) and not rest[0].isspace()
        if not (has_missing_gap or has_inner_dot_space):
            continue
        bad_positions.append(ctx["index"])
        if len(issues) < 5:
            issues.append(f"第{ctx['index']}段标题「{excerpt(text)}」编号格式不规范")

    if bad_positions:
        issues.insert(0, f"{len(bad_positions)} 个标题段落编号格式不规范。")
        return False, issues, summarize_positions(bad_positions)
    return True, [], "二三四级标题编号与文字间距合规"

def check_c01(document_root, contexts, style_map):
    count = 0
    for run_elem in document_root.findall(".//w:r", NSMAP):
        if is_superscript(run_elem) and re.search(r"\[\d+\]", get_run_text(run_elem)):
            count += 1

    if count == 0:
        return False, ["全文未发现任何上标格式的方括号引用。"], "全文"
    return True, [], f"发现 {count} 处上标引用"

def check_c02(document_root, contexts, style_map):
    total = 0
    samples = []
    positions = []
    paragraph_lookup = {}
    for ctx in contexts:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            paragraph_lookup[id(run_elem)] = ctx["index"]

    for run_elem in document_root.findall(".//w:r", NSMAP):
        run_text = get_run_text(run_elem)
        if not (is_superscript(run_elem) and re.search(r"\[\d+\]", run_text)):
            continue
        r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
        ascii_font = get_w_attr(r_fonts, "ascii")
        hansi_font = get_w_attr(r_fonts, "hAnsi")
        east_asia = get_w_attr(r_fonts, "eastAsia")
        if ascii_font != "Times New Roman" or hansi_font != "Times New Roman" or east_asia != "Times New Roman":
            total += 1
            para_index = paragraph_lookup.get(id(run_elem))
            if para_index is not None:
                positions.append(para_index)
            if len(samples) < 3:
                samples.append(
                    f"上标引用'{excerpt(run_text)}'字体为 ascii={ascii_font}、hAnsi={hansi_font}、eastAsia={east_asia}"
                )

    if total:
        issues = [f"{total} 个上标引用 run 的字体不是 Times New Roman。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部上标引用"

def _has_misgrouped_superscript_citations(p_elem):
    runs = [run_elem for run_elem in p_elem.findall("w:r", NSMAP)]
    index = 0
    while index < len(runs):
        run_elem = runs[index]
        run_text = get_run_text(run_elem)
        if not is_superscript(run_elem) or not _CITATION_TOKEN_RE.fullmatch(run_text or ""):
            index += 1
            continue

        numbers = _citation_numbers_from_token(run_text)
        group_end = index
        while group_end + 1 < len(runs):
            next_run = runs[group_end + 1]
            next_text = get_run_text(next_run)
            if not is_superscript(next_run) or not _CITATION_TOKEN_RE.fullmatch(next_text or ""):
                break
            numbers.extend(_citation_numbers_from_token(next_text))
            group_end += 1

        if group_end > index:
            return True
        if _format_citation_numbers(numbers) != run_text:
            return True
        index += 1
    return False

def check_c03(document_root, contexts, style_map):
    bad_positions = []
    samples = []
    for ctx in contexts:
        merged_parts = []
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text:
                continue
            if is_superscript(run_elem):
                run_text = re.sub(r"\[(\d{1,3})\]", r"⟦\1⟧", run_text)
            merged_parts.append(run_text)

        merged_text = "".join(merged_parts)
        misplaced = re.search(r"[。！？]\s*(?:⟦\d{1,3}⟧|\[\d{1,3}\])", merged_text)
        misgrouped = _has_misgrouped_superscript_citations(ctx["elem"])
        if misplaced or misgrouped:
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                preview = re.sub(r"⟦(\d{1,3})⟧", r"[\1]", merged_text)
                if misplaced:
                    samples.append(f"第{ctx['index']}段'{excerpt(preview)}'中引用位于句末标点之后")
                else:
                    samples.append(f"第{ctx['index']}段'{excerpt(preview)}'中连续引用未合并或未按范围规范")

    if bad_positions:
        return (
            False,
            [f"{len(set(bad_positions))} 处上标引用位置或编号组合格式不规范，应位于标点前，并按 [1,2] / [1-3] 规范合并。"] + samples,
            summarize_positions(bad_positions),
        )
    return True, [], "全部上标引用"

def check_r01(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    expected = cfg["ref_hanging"]
    for ctx in references:
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        hanging = parse_int(get_w_attr(ind, "hanging"))
        left = parse_int(get_w_attr(ind, "left"))
        if hanging != expected or left != expected:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return (
            False,
            [f"{len(bad_positions)} 个参考文献段落未设置对称悬挂缩进（hanging=left，应为{expected}）。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"

def check_r02(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    for ctx in references:
        if cfg["ref_use_tab"]:
            tabs = ctx["elem"].find("w:pPr/w:tabs", NSMAP)
            found = False
            if tabs is not None:
                for tab in tabs.findall("w:tab", NSMAP):
                    pos = parse_int(get_w_attr(tab, "pos"))
                    if get_w_attr(tab, "val") == "left" and pos is not None and pos >= cfg["ref_tab_min"]:
                        found = True
                        break
            if found:
                continue
        else:
            text = ctx["text"].replace("\u00a0", " ")
            has_tab = ctx["elem"].find(".//w:tab", NSMAP) is not None
            if not has_tab and re.match(r"^\[\d{1,3}\]\s+\S", text):
                continue
        bad_positions.append(ctx["index"])

    if bad_positions:
        if cfg["ref_use_tab"]:
            return (
                False,
                [f"{len(bad_positions)} 个参考文献段落缺少有效的左对齐制表位（pos >= {cfg['ref_tab_min']}）。"],
                summarize_positions(bad_positions),
            )
        return (
            False,
            [f"{len(bad_positions)} 个参考文献段落缺少编号后空格分隔，或仍在使用制表位。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"

def check_r03(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    expected_line = cfg.get("ref_line_spacing") or 240
    for ctx in references:
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        line_val = parse_int(get_w_attr(spacing, "line"))
        if line_val != expected_line:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个参考文献段落行距不是 {expected_line}。"], summarize_positions(bad_positions)
    return True, [], "全部参考文献段落"

def check_r04(document_root, contexts, style_map):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    samples = []
    for ctx in references:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if re.search(r"\[\d+\]", run_text) and is_superscript(run_elem):
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段参考文献引用'{excerpt(run_text)}'仍为上标")
                break

    if bad_positions:
        issues = [f"{len(bad_positions)} 个参考文献段落中的 [N] 引用仍为上标。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部参考文献段落"

def check_c04(document_root, contexts, style_map):
    """检查正文中是否有 [N] 引用混在正文 run 里（未拆出单独上标 run）。"""
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not INLINE_CITATION_PAT.search(run_text):
                continue
            # 如果整个 run 是独立引用 run 且已是上标，跳过
            if is_citation_run_text(run_text) and is_superscript(run_elem):
                continue
            # 引用混在正文 run 中（非纯引用 run），或纯引用 run 但不是上标
            if not is_superscript(run_elem):
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(
                        f"第{ctx['index']}段 run [{excerpt(run_text)}] 含引用但未设上标"
                    )
                break

    if bad_positions:
        issues = [
            f"{len(bad_positions)} 个正文段落存在未上标的嵌入引用 [N]（引用混在正文 run 中，未拆出独立上标 run）。"
        ]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部正文段落"

def check_r05(document_root, contexts, style_map, cfg):
    """检查参考文献制表位是否足够宽以对齐两位数编号（[10]+）。
    [10] 占约4字符，需要制表位 >= 480 twips；建议 560。
    """
    if not cfg["ref_use_tab"]:
        return True, [], "当前 Profile 使用空格分隔参考文献编号"

    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    for ctx in references:
        tabs = ctx["elem"].find("w:pPr/w:tabs", NSMAP)
        ok = False
        if tabs is not None:
            for tab in tabs.findall("w:tab", NSMAP):
                pos = parse_int(get_w_attr(tab, "pos"))
                if get_w_attr(tab, "val") == "left" and pos is not None and pos >= cfg["ref_tab_min"]:
                    ok = True
                    break
        if not ok:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return (
            False,
            [
                f"{len(bad_positions)} 个参考文献段落的制表位 pos < {cfg['ref_tab_min']}，导致 [10]+ 编号与 [1]-[9] 不对齐。"
                f" 建议制表位 pos={cfg['ref_hanging']}，hanging={cfg['ref_hanging']}，left={cfg['ref_hanging']}。"
            ],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"

def _caption_title_runs(p_elem):
    runs = []
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        runs.append(run_elem)
        if run_elem.find("w:br", NSMAP) is not None or run_elem.find("w:cr", NSMAP) is not None:
            break
    return runs


def check_caption_format(contexts, prefix, label, cfg, style_map=None):
    captions = [ctx for ctx in contexts if ctx["kind"] == "caption" and ctx["text"].strip().startswith(prefix)]
    bad_positions = []
    samples = []
    min_size, max_size = cfg["caption_size_range"]
    sep_pattern = re.escape(cfg["caption_number_sep"])
    text_pattern = re.compile(rf"^{prefix}\s*\d+(?:{sep_pattern}\d+)?")

    for ctx in captions:
        problems = []
        jc_val = get_paragraph_alignment(ctx["elem"])
        if jc_val != "center":
            problems.append(f"对齐={jc_val or 'left(default)'}")

        run_sizes = [
            get_effective_run_size(run_elem, style_map, ctx["elem"])
            for run_elem in _caption_title_runs(ctx["elem"])
            if get_run_text(run_elem).strip()
        ]
        if not run_sizes or any(size is None or not (min_size <= size <= max_size) for size in run_sizes):
            problems.append(f"字号不在 {min_size}~{max_size}")

        if not text_pattern.match(ctx["text"].strip()):
            problems.append("题注编号格式异常")

        if problems:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段{label}'{excerpt(ctx['text'])}'存在问题：{'，'.join(problems)}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个{label}段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], f"全部{label}"

def check_f01(document_root, contexts, style_map, cfg):
    return check_caption_format(contexts, "图", "图题", cfg, style_map)

def check_f02(document_root, contexts, style_map, cfg):
    return check_caption_format(contexts, "表", "表题", cfg, style_map)

def check_tb01(document_root, contexts, style_map):
    tables = get_non_equation_layout_tables(document_root)
    if not tables:
        return True, [], "文档无表格或仅含公式布局表"

    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        tbl_borders = tbl_elem.find("w:tblPr/w:tblBorders", NSMAP)
        problems = []
        for border_name, label in (("top", "顶线"), ("bottom", "底线")):
            border_elem = tbl_borders.find(f"w:{border_name}", NSMAP) if tbl_borders is not None else None
            border_size = parse_int(get_w_attr(border_elem, "sz"))
            if border_size is None or border_size < 10:
                problems.append(f"{label}线宽={get_w_attr(border_elem, 'sz')}")
        for border_name, label in (("left", "左竖线"), ("right", "右竖线"), ("insideV", "内部竖线")):
            border_elem = tbl_borders.find(f"w:{border_name}", NSMAP) if tbl_borders is not None else None
            if border_elem is None:
                continue
            border_val = get_w_attr(border_elem, "val")
            if border_val not in ("nil", "none"):
                problems.append(f"{label}未关闭(val={border_val})")
        if problems:
            bad_tables.append(table_index)
            issues.append(f"第{table_index}个表存在问题：{'，'.join(problems)}")

    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表"

def check_h04(document_root, contexts, style_map, cfg):
    headings = [ctx for ctx in contexts if is_heading_audit_context(ctx, "h4")]
    if not headings:
        return True, [], "文档无四级标题"

    bad_positions = []
    samples = []
    expected_size = cfg["h4_size"]
    for ctx in headings:
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        run_sizes = [get_run_size(run_elem) for run_elem in get_non_empty_runs(ctx["elem"])]
        run_ok = bool(run_sizes)
        if run_ok:
            for run_elem in get_non_empty_runs(ctx["elem"]):
                if cfg.get("h4_bold", False):
                    if not is_bold(run_elem):
                        run_ok = False
                        break
                elif is_bold(run_elem):
                    run_ok = False
                    break
                if get_run_size(run_elem) != expected_size:
                    run_ok = False
                    break
                expected_h4_font = cfg.get("h4_font", "宋体") or "宋体"
                r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
                east_asia = get_w_attr(r_fonts, "eastAsia") if r_fonts is not None else None
                if east_asia and east_asia not in (expected_h4_font, "SimSun"):
                    run_ok = False
                    break
        expected_indent = cfg.get("h4_indent")
        if expected_indent is None:
            indent_ok = first_line in (None, "0")
        else:
            indent_ok = first_line == str(expected_indent)

        if jc_val != "left" or not indent_ok or not run_ok:
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(
                    f"第{ctx['index']}段四级标题'{excerpt(ctx['text'])}'格式不符合要求"
                    f"（firstLine={first_line}，应为{expected_indent if expected_indent is not None else 0}）"
                )

    if bad_positions:
        issues = [f"{len(bad_positions)} 个 h4 段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部四级标题"

def check_s01(document_root, contexts, style_map, cfg=None):
    """检查各级标题的段前/段后间距是否合规。"""
    issues = []
    affected_positions = []
    paragraph_tag = f"{{{W_NS}}}p"
    table_tag = f"{{{W_NS}}}tbl"
    body = document_root.find("w:body", NSMAP)
    body_children = list(body) if body is not None else []
    child_index = {id(elem): idx for idx, elem in enumerate(body_children)}

    def _preceded_by_table_gap_budget(p_elem) -> bool:
        idx = child_index.get(id(p_elem))
        if idx is None:
            return False
        scan_idx = idx - 1
        while scan_idx >= 0:
            candidate = body_children[scan_idx]
            if candidate.tag == table_tag:
                return True
            if candidate.tag != paragraph_tag:
                scan_idx -= 1
                continue
            if get_paragraph_text(candidate).strip():
                return False
            scan_idx -= 1
        return False

    def _heading_spec(level, label):
        if cfg and any(key in cfg for key in (f"{level}_spacing_before", f"{level}_spacing_after")):
            expected_before = int(cfg.get(f"{level}_spacing_before", 0) or 0)
            expected_after = int(cfg.get(f"{level}_spacing_after", 0) or 0)
            return dict(label=label, exact_before=expected_before, exact_after=expected_after)
        return dict(label=label, before_min=80, before_max=200, after_min=80, after_max=200)

    HEADING_SPECS = {
        "h1": _heading_spec("h1", "一级标题"),
        "h2": _heading_spec("h2", "二级标题"),
        "h3": _heading_spec("h3", "三级标题"),
    }

    for kind, spec in HEADING_SPECS.items():
        headings = [ctx for ctx in contexts if is_heading_audit_context(ctx, kind)]
        if not headings:
            continue
        label = spec["label"]
        for ctx in headings:
            spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
            before = parse_int(get_w_attr(spacing, "before")) if spacing is not None else None
            after  = parse_int(get_w_attr(spacing, "after"))  if spacing is not None else None

            bad_msgs = []
            if "exact_before" in spec:
                if before != spec["exact_before"]:
                    bad_msgs.append(f"段前={before}，应为{spec['exact_before']}")
                if after != spec["exact_after"]:
                    bad_msgs.append(f"段后={after}，应为{spec['exact_after']}")
            else:
                if before is None:
                    bad_msgs.append("段前未设置（应≥{}twips）".format(spec["before_min"]))
                elif before < spec["before_min"]:
                    bad_msgs.append("段前={}，低于{}".format(before, spec["before_min"]))
                elif before > spec["before_max"] and not _preceded_by_table_gap_budget(ctx["elem"]):
                    bad_msgs.append("段前={}，过大（上限{}）".format(before, spec["before_max"]))

                if after is None:
                    bad_msgs.append("段后未设置（应≥{}twips）".format(spec["after_min"]))
                elif after < spec["after_min"]:
                    bad_msgs.append("段后={}，低于{}".format(after, spec["after_min"]))
                elif after > spec["after_max"]:
                    bad_msgs.append("段后={}，过大（上限{}）".format(after, spec["after_max"]))

            if bad_msgs:
                affected_positions.append(ctx["index"])
                if len(issues) < 4:
                    issues.append("第{}段{}：{}".format(ctx["index"], label, "；".join(bad_msgs)))

    if affected_positions:
        total = len(affected_positions)
        issues.insert(0, "{}个标题段落间距不符合规范。".format(total))
        return False, issues, summarize_positions(affected_positions)
    return True, [], "各级标题段前段后间距合规"

def check_s03(document_root, contexts, style_map):
    """检查正文段落的段前/段后是否为0（辽大：正文段前=0，段后=0）。"""
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        if spacing is None:
            continue
        before = parse_int(get_w_attr(spacing, "before"))
        after  = parse_int(get_w_attr(spacing, "after"))
        msgs = []
        if before is not None and before > 60:
            msgs.append("段前={}（应为0）".format(before))
        if after is not None and after > 60:
            msgs.append("段后={}（应为0）".format(after))
        if msgs:
            bad.append((ctx["index"], "；".join(msgs)))

    if bad:
        issues = ["{} 个正文段落段前/段后间距不为0。".format(len(bad))]
        issues.extend("第{}段：{}".format(i, m) for i, m in bad[:4])
        return False, issues, summarize_positions([i for i, _ in bad])
    return True, [], "正文段前段后均为0"

def check_s02(document_root, contexts, style_map):
    h1_contexts = [ctx for ctx in contexts if is_heading_audit_context(ctx, "h1")]
    if len(h1_contexts) <= 1:
        return True, [], "文档仅有一个一级标题"

    bad_positions = []
    for ctx in h1_contexts[1:]:
        page_break = ctx["elem"].find("w:pPr/w:pageBreakBefore", NSMAP)
        if page_break is None or get_w_attr(page_break, "val") == "0":
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个非首个一级标题缺少章节首页分页设置。"], summarize_positions(bad_positions)
    return True, [], "全部非首个一级标题已分页"

def check_fn01(document_root, contexts, style_map, footnotes_root):
    if footnotes_root is None:
        return True, [], "文档无脚注文件"

    issues = []
    affected_ids = []
    for footnote_elem in footnotes_root.findall(".//w:footnote", NSMAP):
        footnote_id = get_w_attr(footnote_elem, "id")
        if footnote_id in ("-1", "0"):
            continue
        for run_elem in footnote_elem.findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            size_val = get_run_size(run_elem)
            if size_val is None or size_val < 16:
                affected_ids.append(footnote_id)
                if len(issues) < 5:
                    issues.append(f"脚注 {footnote_id} 中 run '{excerpt(run_text)}' 字号为 {size_val}，低于 16。")
                break

    if affected_ids:
        return False, issues, "脚注 " + "、".join(sorted(set(affected_ids))[:5])
    return True, [], "全部脚注字号正常"

def check_pg01(document_root, contexts, style_map, cfg=None):
    issues = []
    zip_path = getattr(document_root, "_zip_path", None)
    passed = False
    affected = "全文"

    def _iter_footer_page_paragraphs():
        if not zip_path:
            return []
        paragraphs = []
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                footer_files = [n for n in zf.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
                for fname in footer_files:
                    with zf.open(fname) as f:
                        footer_root = ET.parse(f).getroot()
                    for p in footer_root.findall(".//w:p", NSMAP):
                        has_page = any("PAGE" in (it.text or "").upper() for it in p.findall(".//w:instrText", NSMAP))
                        if has_page:
                            paragraphs.append((fname, p))
        except Exception:
            return []
        return paragraphs

    for instr_text in document_root.findall(".//w:instrText", NSMAP):
        if "PAGE" in (instr_text.text or "").upper():
            passed = True
            affected = "发现 PAGE 域"
            break
    if not passed and zip_path:
        for fname, _ in _iter_footer_page_paragraphs():
            passed = True
            affected = f"{fname} 中发现 PAGE 域"
            break
    if not passed:
        return False, ["文档中未发现 PAGE 页码域。"], "全文"

    page_style = (cfg or {}).get("pg01_format")
    if page_style in {"em_dash", "hyphen_wrap"}:
        wrap_char = "—" if page_style == "em_dash" else "-"
        expected = "—N—" if page_style == "em_dash" else "-N-"
        found_wrapped = False
        if zip_path:
            footer_paragraphs = _iter_footer_page_paragraphs()
            for _, p in footer_paragraphs:
                all_text = "".join(t.text or "" for t in p.findall(".//w:t", NSMAP))
                if wrap_char in all_text:
                    found_wrapped = True
                    break
        else:
            found_wrapped = any(wrap_char in (t.text or "") for t in document_root.findall(f".//{{{W_NS}}}t"))
        if not found_wrapped:
            issues.append(f"页码格式应为 {expected}，页脚中未检测到包围符号")
            passed = False

    expected_font = (cfg or {}).get("page_number_font")
    expected_size = parse_int((cfg or {}).get("page_number_size"))
    if expected_font or expected_size:
        footer_paragraphs = _iter_footer_page_paragraphs()
        for fname, paragraph in footer_paragraphs:
            for run_elem in paragraph.findall(".//w:r", NSMAP):
                if not (
                    run_elem.find("w:fldChar", NSMAP) is not None
                    or run_elem.find("w:instrText", NSMAP) is not None
                    or get_run_text(run_elem).strip()
                ):
                    continue
                east_asia = get_effective_run_font(run_elem, style_map, attr_name="eastAsia")
                size_val = get_effective_run_size(run_elem, style_map)
                if expected_font and east_asia != expected_font:
                    issues.append(f"页码字体应为 {expected_font}，实际为 {east_asia or '未设置'} ({fname})")
                    passed = False
                    break
                if expected_size is not None and size_val not in (expected_size, None):
                    issues.append(f"页码字号应为 {expected_size} half-pts，实际为 {size_val} ({fname})")
                    passed = False
                    break
            if not passed and issues:
                break

    return passed, issues, affected

def check_p03(document_root, contexts, style_map, cfg):
    """P03: 页码段落必须居中对齐。"""
    zip_path = getattr(document_root, "_zip_path", None)
    if zip_path is None:
        return True, [], "无法访问页脚文件（跳过）"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            footer_files = [n for n in zf.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
            if not footer_files:
                return True, [], "文档无页脚"
            issues = []
            for fname in footer_files:
                with zf.open(fname) as f:
                    footer_root = ET.parse(f).getroot()
                for p in footer_root.findall(".//w:p", NSMAP):
                    has_page = any(
                        "PAGE" in (it.text or "").upper()
                        for it in p.findall(".//w:instrText", NSMAP)
                    )
                    if not has_page:
                        continue
                    jc = p.find("w:pPr/w:jc", NSMAP)
                    jc_val = get_w_attr(jc, "val") if jc is not None else None
                    if jc_val != "center":
                        issues.append(f"页码段落对齐方式为 {jc_val or '默认（左对齐）'}，应为居中")
    except Exception as e:
        return True, [], f"页脚解析失败（{e}），跳过"
    if issues:
        return False, issues, "页脚页码段落"
    return True, [], "页码居中正常"

def check_ref01(document_root, contexts, style_map):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    samples = []

    for ctx in references:
        text = ctx["text"].replace("\u00a0", " ")
        body_text = re.sub(r"^\[\d+\]\s*", "", text).strip()
        if not body_text:
            continue
        expected = "。" if is_mostly_cjk(body_text) else "."
        if not body_text.rstrip().endswith(expected):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段参考文献'{excerpt(body_text)}'结尾应为'{expected}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个参考文献段落末尾标点不符合语言规范。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部参考文献标点正常"

def _get_run_text_local(run_elem, w_ns):
    parts = []
    for text_elem in run_elem.findall(f".//{{{w_ns}}}t"):
        if text_elem.text:
            parts.append(text_elem.text)
    return "".join(parts)

def _is_run_bold_active(rpr, w_ns):
    if rpr is None:
        return False
    bold_elem = rpr.find(f"{{{w_ns}}}b")
    if bold_elem is None:
        return False
    return bold_elem.get(f"{{{w_ns}}}val", "1") not in ("0", "false", "False", "off")

def _collect_cn_keyword_style_issues(p_elem, cfg):
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    label_len = len("关键词")
    kw_font = cfg.get("kw_font") if cfg else None
    kw_bold = cfg.get("kw_bold") if cfg else None
    kw_size = cfg.get("kw_half_points") if cfg else None
    content_font = (
        (cfg or {}).get("abstract_body_font")
        or (cfg or {}).get("body_font")
        or "宋体"
    )
    issues = []
    consumed = 0

    for run_elem in p_elem.findall(f".//{{{w_ns}}}r"):
        run_text = _get_run_text_local(run_elem, w_ns)
        if not run_text:
            continue

        start = consumed
        end = consumed + len(run_text)
        consumed = end

        rpr = run_elem.find(f"{{{w_ns}}}rPr")
        fonts = rpr.find(f"{{{w_ns}}}rFonts") if rpr is not None else None
        east_asia = fonts.get(f"{{{w_ns}}}eastAsia") if fonts is not None else None
        size_elem = rpr.find(f"{{{w_ns}}}sz") if rpr is not None else None
        size_val = size_elem.get(f"{{{w_ns}}}val") if size_elem is not None else None
        bold_active = _is_run_bold_active(rpr, w_ns)

        if start < label_len < end:
            issues.append(f"关键词标签与内容应分开设置：标签用{kw_font or '黑体'}，内容用{content_font}")
            continue

        in_label = end <= label_len
        if in_label:
            if kw_font and east_asia != kw_font:
                issues.append(f"关键词标签字体应为{kw_font}，实为{east_asia or '未设置'}")
            if kw_bold is True and not bold_active:
                issues.append("关键词标签应加粗")
            if kw_bold is False and bold_active:
                issues.append("关键词标签不应加粗")
            if kw_size and size_val and int(size_val) != kw_size:
                issues.append(f"关键词标签字号应为{kw_size} half-pts，实为{size_val}")
            continue

        if east_asia != content_font:
            issues.append(f"关键词内容字体应为{content_font}，实为{east_asia or '未设置'}")
        if bold_active:
            issues.append("关键词内容不应加粗")
        if kw_size and size_val and int(size_val) != kw_size:
            issues.append(f"关键词内容字号应为{kw_size} half-pts，实为{size_val}")

    return issues

def _expected_keyword_separator(text, cfg):
    if is_cn_keywords_paragraph_text(text):
        return str((cfg or {}).get("kw_cn_separator", "；") or "；")
    return str((cfg or {}).get("kw_en_separator", "; ") or "; ")

def check_kw01(document_root, contexts, style_map, cfg):
    keyword_contexts = []
    for ctx in contexts:
        stripped = ctx["text"].strip()
        if is_keyword_paragraph_text(stripped):
            keyword_contexts.append(ctx)

    if not keyword_contexts:
        return True, [], "未发现关键词段落"

    bad_positions = []
    samples = []
    for ctx in keyword_contexts:
        text = ctx["text"].strip()
        payload = re.sub(r"^(关键词|key\s*words?)\s*[：:]\s*", "", text, count=1, flags=re.IGNORECASE).strip()
        problems = []
        expected_separator = _expected_keyword_separator(text, cfg)
        if text.endswith(("。", ".")):
            problems.append("末尾带句号")
        keywords = [item.strip() for item in re.split(r"[；;]", payload) if item.strip()]
        if len(keywords) >= 2:
            if expected_separator.strip() == "；":
                if "；" not in payload or ";" in payload:
                    problems.append("分隔符应为中文分号“；”")
            elif ";" not in payload and "；" not in payload:
                problems.append(f"分隔符应为“{expected_separator.strip()}”或中文分号“；”")
        elif "；" not in payload and ";" not in payload:
            problems.append("缺少分号分隔")
        if not (cfg["kw_min"] <= len(keywords) <= cfg["kw_max"]):
            problems.append(f"关键词数量为 {len(keywords)}")
        if problems:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段关键词'{excerpt(text)}'存在问题：{'，'.join(problems)}")
    issues = []
    affected_positions = list(bad_positions)
    kw_font = cfg.get("kw_font") if cfg else None
    kw_bold_req = cfg.get("kw_bold") if cfg else None
    kw_hp = cfg.get("kw_half_points") if cfg else None
    if kw_font or kw_hp or kw_bold_req is not None:
        for ctx in keyword_contexts:
            text = ctx.get("text", "")
            if is_keyword_paragraph_text(text):
                p_elem = ctx.get("elem")
                if p_elem is None:
                    continue
                is_cn_keywords = is_cn_keywords_paragraph_text(text)
                if is_cn_keywords:
                    issues.extend(_collect_cn_keyword_style_issues(p_elem, cfg))

    if bad_positions:
        issues = [f"{len(bad_positions)} 个关键词段落格式不符合要求。"] + samples + issues
    if issues:
        issues = list(dict.fromkeys(issues))
        if not affected_positions and keyword_contexts:
            affected_positions = [keyword_contexts[0]["index"]]
        return False, issues, summarize_positions(affected_positions)
    return True, [], "全部关键词段落"

def check_kw02(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    for ctx in contexts:
        text = (ctx.get("text") or "").strip()
        if not is_cn_keywords_paragraph_text(text):
            continue
        if re.search(r"[。，；：！？\.,:;!?]\s*$", text):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段关键词末尾有标点：{excerpt(text)}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个关键词段落末尾存在多余标点。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "关键词段落末尾无多余标点"

def check_eq01(document_root, contexts, style_map):
    """公式段落（含 m:oMath）必须居中、无首行缩进。"""
    def is_display_equation_context(ctx):
        if ctx["elem"].find(".//m:oMath", MNSMAP) is None:
            return False
        compact_text = re.sub(r"\s+", "", ctx["text"] or "")
        if not compact_text:
            return True
        if re.fullmatch(r"[（(]?\d+(?:[.\-]\d+)*[)）]?", compact_text):
            return True
        return False

    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_display_equation_context(ctx):
            continue
        if paragraph_in_equation_layout_table(document_root, ctx.get("elem")):
            continue
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        if jc_val != "center" or first_line not in (None, "0"):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段公式段落对齐={jc_val}，firstLine={first_line}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个公式段落未居中或有首行缩进。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部公式段落"

def _has_right_tab(p_elem):
    tabs = p_elem.find("w:pPr/w:tabs", NSMAP)
    if tabs is None:
        return False
    return any(get_w_attr(tab, "val") == "right" for tab in tabs.findall("w:tab", NSMAP))


def _equation_number_patterns(cfg):
    sep = re.escape((cfg or {}).get("eq_number_sep", "-"))
    strict = re.compile(rf"^[（(]\s*(\d+){sep}(\d+)\s*[)）]$")
    loose = re.compile(r"^[（(]\s*(\d+)([.\-])(\d+)\s*[)）]$")
    inline = re.compile(rf"[（(]\s*(\d+){sep}(\d+)\s*[)）]")
    inline_loose = re.compile(r"[（(]\s*(\d+)([.\-])(\d+)\s*[)）]")
    return strict, loose, inline, inline_loose


def _equation_number_alignment_ok(p_elem, style_map):
    jc_val = get_paragraph_alignment(p_elem, style_map)
    return jc_val in ("right", "distribute") or _has_right_tab(p_elem)


def _ctx_for_paragraph(p_elem, ctx_by_elem):
    return ctx_by_elem.get(id(p_elem))


def _equation_record(position, number_text, major, minor, number_p, source):
    return {
        "position": position,
        "number_text": number_text,
        "major": major,
        "minor": minor,
        "number_p": number_p,
        "source": source,
    }


def _collect_equation_table_records(document_root, contexts, strict_num_re, loose_num_re):
    ctx_by_elem = {id(ctx.get("elem")): ctx for ctx in contexts if ctx.get("elem") is not None}
    records = []
    table_paragraph_ids = set()
    format_issues = []
    for tbl in document_root.findall(".//w:tbl", NSMAP):
        if not is_equation_layout_table(tbl):
            continue
        cells = tbl.findall("w:tr/w:tc", NSMAP)
        number_p = cells[-1].find("w:p", NSMAP) if cells else None
        number_text = _compact_table_cell_text(cells[-1]) if cells else ""
        for p_elem in tbl.findall(".//w:p", NSMAP):
            table_paragraph_ids.add(id(p_elem))
        ctx = None
        for p_elem in tbl.findall(".//w:p", NSMAP):
            candidate = _ctx_for_paragraph(p_elem, ctx_by_elem)
            if candidate is not None:
                ctx = candidate
                break
        loose_match = loose_num_re.fullmatch(number_text)
        strict_match = strict_num_re.fullmatch(number_text)
        if loose_match and not strict_match:
            position = ctx.get("index") if ctx else None
            format_issues.append((position, number_text))
            continue
        if strict_match:
            position = ctx.get("index") if ctx else None
            records.append(
                _equation_record(
                    position,
                    number_text,
                    int(strict_match.group(1)),
                    int(strict_match.group(2)),
                    number_p,
                    "table",
                )
            )
    return records, table_paragraph_ids, format_issues


def _collect_inline_equation_records(contexts, table_paragraph_ids, inline_num_re, inline_loose_num_re):
    records = []
    missing_positions = []
    format_issues = []
    consumed_number_context_ids = set()
    for index, ctx in enumerate(contexts):
        p_elem = ctx.get("elem")
        if p_elem is None or id(p_elem) in table_paragraph_ids:
            continue
        if id(ctx) in consumed_number_context_ids:
            continue
        has_math = (
            p_elem.find(".//m:oMath", MNSMAP) is not None
            or p_elem.find(".//m:oMathPara", MNSMAP) is not None
        )
        if not has_math:
            continue
        text = re.sub(r"\s+", "", ctx.get("text") or get_paragraph_text(p_elem))
        strict_match = inline_num_re.search(text)
        if strict_match:
            records.append(
                _equation_record(
                    ctx.get("index"),
                    strict_match.group(0),
                    int(strict_match.group(1)),
                    int(strict_match.group(2)),
                    p_elem,
                    "paragraph",
                )
            )
            continue
        if inline_loose_num_re.search(text):
            format_issues.append((ctx.get("index"), text))
            continue
        next_record = _record_from_following_number_context(ctx, contexts, index, inline_num_re, table_paragraph_ids)
        if next_record is not None:
            records.append(next_record)
            consumed_number_context_ids.add(id(contexts[index + 1]))
            continue
        if _is_display_equation_without_number(ctx, text):
            missing_positions.append(ctx.get("index"))
    return records, missing_positions, format_issues


def _record_from_following_number_context(ctx, contexts, index, inline_num_re, table_paragraph_ids):
    if index + 1 >= len(contexts):
        return None
    next_ctx = contexts[index + 1]
    next_elem = next_ctx.get("elem")
    if next_elem is None or id(next_elem) in table_paragraph_ids:
        return None
    number_text = re.sub(r"\s+", "", next_ctx.get("text") or get_paragraph_text(next_elem))
    match = inline_num_re.fullmatch(number_text)
    if not match:
        return None
    return _equation_record(
        next_ctx.get("index") or ctx.get("index"),
        match.group(0),
        int(match.group(1)),
        int(match.group(2)),
        next_elem,
        "following_paragraph",
    )


def _is_display_equation_without_number(ctx, compact_text):
    if not compact_text:
        return True
    if len(compact_text) <= 3:
        return True
    if re.fullmatch(r"[A-Za-zα-ωΑ-Ω]\d*", compact_text):
        return True
    return False


def _check_equation_number_sequence(records, cfg):
    sep = (cfg or {}).get("eq_number_sep", "-")
    issues = []
    positions = []
    previous_by_major = {}
    for record in sorted(records, key=lambda item: item["position"] or 0):
        major = record["major"]
        minor = record["minor"]
        previous = previous_by_major.get(major)
        if previous is not None:
            prev_minor = previous["minor"]
            if minor <= prev_minor:
                issues.append(
                    f"第{record['position']}段公式编号顺序异常：{record['number_text']} 出现在 {previous['number_text']} 之后。"
                )
                if record["position"] is not None:
                    positions.append(record["position"])
            elif minor != prev_minor + 1:
                expected = f"({major}{sep}{prev_minor + 1})"
                issues.append(
                    f"第{record['position']}段公式编号可能跳号：{previous['number_text']} 后出现 {record['number_text']}，应核对是否缺少 {expected}。"
                )
                if record["position"] is not None:
                    positions.append(record["position"])
        previous_by_major[major] = record
    return issues, positions


def check_eq02(document_root, contexts, style_map, cfg=None):
    """公式编号应右对齐，并按同一章内出现顺序连续递增。"""
    strict_num_re, loose_num_re, inline_num_re, inline_loose_num_re = _equation_number_patterns(cfg)
    records, table_paragraph_ids, table_format_issues = _collect_equation_table_records(
        document_root, contexts, strict_num_re, loose_num_re
    )
    inline_records, missing_positions, inline_format_issues = _collect_inline_equation_records(
        contexts, table_paragraph_ids, inline_num_re, inline_loose_num_re
    )
    records.extend(inline_records)

    bad_positions = []
    issues = []
    for record in records:
        if record["number_p"] is not None and _equation_number_alignment_ok(record["number_p"], style_map):
            continue
        position = record["position"]
        if position is not None:
            bad_positions.append(position)
            issues.append(f"第{position}段公式编号 {record['number_text']} 未右对齐。")
        else:
            issues.append(f"公式编号 {record['number_text']} 未右对齐。")

    if missing_positions:
        positions = [pos for pos in missing_positions if pos is not None]
        bad_positions.extend(positions)
        issues.append(f"{len(missing_positions)} 个公式块缺少公式编号。")
        for pos in positions[:3]:
            issues.append(f"第{pos}段含公式但缺少公式编号。")

    format_issues = table_format_issues + inline_format_issues
    if format_issues:
        expected = "(X.Y)" if (cfg or {}).get("eq_number_sep") == "." else "(X-Y)"
        for position, number_text in format_issues[:3]:
            label = f"第{position}段" if position is not None else "公式块"
            issues.append(f"{label}公式编号格式异常：{number_text}，应为 {expected}。")
            if position is not None:
                bad_positions.append(position)

    sequence_issues, sequence_positions = _check_equation_number_sequence(records, cfg)
    if sequence_issues:
        issues.extend(sequence_issues[:3])
        bad_positions.extend(sequence_positions)

    if issues:
        summary_positions = [pos for pos in bad_positions if pos is not None]
        return False, issues, summarize_positions(summary_positions)
    return True, [], "全部公式编号"

def check_eq03(document_root, contexts, style_map, cfg=None):
    """正文中引用公式应使用 profile 约定的 '式(X-Y)' / '式(X.Y)' 格式。"""
    sep = re.escape((cfg or {}).get("eq_number_sep", "-"))
    bad_pat = re.compile(r"式(?:[（(])?\d+[.-]\d+")
    good_pat = re.compile(rf"式[（(]\d+{sep}\d+[)）]")
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        text = ctx["text"]
        if good_pat.search(text):
            continue
        if not bad_pat.search(text):
            continue
        bad_positions.append(ctx["index"])
        if len(samples) < 3:
            samples.append(f"第{ctx['index']}段公式引用格式异常：\"{excerpt(text)}\"")
    if bad_positions:
        expected = "式(X.Y)" if (cfg or {}).get("eq_number_sep") == "." else "式(X-Y)"
        issues = [f"{len(bad_positions)} 个正文段落的公式引用格式不符合 '{expected}' 规范。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部公式引用"

def _check_caption_numbering(contexts, prefix, label, cfg):
    """检查图/表题注是否使用章节编号格式（图X-Y / 表X-Y）。"""
    captions = [ctx for ctx in contexts if ctx["kind"] == "caption" and ctx["text"].strip().startswith(prefix)]
    if not captions:
        return True, [], f"文档无{label}"
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 1) or 1)
    gap_pattern = r" " * gap_spaces
    chapter_pat = re.compile(
        rf"^{prefix}\s*\d+{re.escape(cfg['caption_number_sep'])}\d+(?:{gap_pattern}).+"
    )
    bad_positions = []
    samples = []
    for ctx in captions:
        stripped = ctx["text"].strip()
        if not chapter_pat.match(stripped):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(
                    f"第{ctx['index']}段{label}\"{excerpt(stripped)}\"编号或题名空格不符合要求（应为{prefix}X{cfg['caption_number_sep']}Y后接{gap_spaces}个半角空格）"
                )
    if bad_positions:
        issues = [f"{len(bad_positions)} 个{label}编号或题名空格不是章节式（{prefix}X{cfg['caption_number_sep']}Y 后 {gap_spaces} 个半角空格）格式。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], f"全部{label}"

def _is_toc_heading_style(style_id, style_map):
    return is_toc_heading_style_shared(style_id, style_map)

def _is_toc_entry_style(style_id, style_map):
    return is_toc_entry_style_shared(style_id, style_map)

def check_f03(document_root, contexts, style_map, cfg):
    return _check_caption_numbering(contexts, "图", "图题", cfg)

def check_f04(document_root, contexts, style_map, cfg):
    return _check_caption_numbering(contexts, "表", "表题", cfg)

def check_body_font(document_root, contexts, style_map, cfg):
    """C01-ext: 正文中文应为宋体/SimSun"""
    issues = []
    expected_cn = cfg.get("body_font_cn", "宋体")
    checked = 0
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        p = ctx.get("elem")
        if p is None:
            continue
        checked += 1
        for run in p.findall(".//w:r", NSMAP):
            rpr = run.find("w:rPr", NSMAP)
            if rpr is None:
                continue
            fonts = rpr.find("w:rFonts", NSMAP)
            if fonts is None:
                continue
            east_asia = get_w_attr(fonts, "eastAsia")
            if east_asia and east_asia not in (expected_cn, "SimSun", ""):
                issues.append(f"正文中文字体应为{expected_cn}，实际={east_asia}")
                break
        if len(issues) >= 5:
            break
    return (len(issues) == 0), issues, f"抽查{checked}个正文段落"

def check_f05(document_root, contexts, style_map):
    """图表题注（caption 类段落）run 字体应为宋体+Times New Roman。"""
    captions = [
        ctx
        for ctx in contexts
        if ctx["kind"] == "caption" or ctx.get("module") in CAPTION_EN_MODULES | CAPTION_NOTE_MODULES
    ]
    if not captions:
        return True, [], "文档无图表题注"
    bad_positions = []
    samples = []
    for ctx in captions:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            east_asia = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="eastAsia")
            ascii_font = get_effective_run_font(run_elem, style_map, ctx["elem"], attr_name="ascii")
            has_cjk = bool(CJK_CHAR_RE.search(run_text))
            has_latin_or_digit = bool(re.search(r"[A-Za-z0-9]", run_text))
            east_asia_ok = east_asia in ("宋体", "SimSun")
            ascii_ok = ascii_font == "Times New Roman"
            if has_cjk and not east_asia_ok:
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段题注字体 eastAsia={east_asia}，ascii={ascii_font}")
                break
            if has_latin_or_digit and not ascii_ok:
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段题注字体 eastAsia={east_asia}，ascii={ascii_font}")
                break
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图表题注段落字体不符合宋体+Times New Roman要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图表题注"

def check_f06(document_root, contexts, style_map):
    """含图片（w:drawing）的段落应居中、无首行缩进。"""
    bad_positions = []
    samples = []
    for ctx in contexts:
        has_drawing = ctx["elem"].find(".//w:drawing", NSMAP) is not None
        if not has_drawing:
            continue
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        if jc_val != "center" or first_line not in (None, "0"):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段图片段落对齐={jc_val}，firstLine={first_line}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图片段落未居中或有首行缩进。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图片段落"

def check_f07(document_root, contexts, style_map):
    """图题/表题末尾不应以句号（。或.）结尾。"""
    captions = [
        ctx
        for ctx in contexts
        if ctx["kind"] == "caption" and ctx["text"].strip().startswith(("图", "表"))
    ]
    if not captions:
        return True, [], "文档无图表题"
    bad_positions = []
    samples = []
    for ctx in captions:
        stripped = ctx["text"].rstrip()
        if stripped.endswith("。") or stripped.endswith("."):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                label = "表题" if stripped.startswith("表") else "图题"
                samples.append(f"第{ctx['index']}段{label}\"{excerpt(stripped)}\"末尾有句号")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图题/表题末尾带有句号（题名不加句号）。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图表题"

def check_tb03_line(document_root, contexts, style_map):
    """三线表应有栏目线：第一行每个单元格底边框 sz >= 6（0.75pt）。"""
    tables = get_non_equation_layout_tables(document_root)
    if not tables:
        return True, [], "文档无表格或仅含公式布局表"
    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        rows = tbl_elem.findall("w:tr", NSMAP)
        if not rows:
            continue
        first_row = rows[0]
        cells = first_row.findall("w:tc", NSMAP)
        if not cells:
            continue
        row_has_bottom = False
        for cell in cells:
            bottom_border = cell.find("w:tcPr/w:tcBorders/w:bottom", NSMAP)
            if bottom_border is not None:
                sz = parse_int(get_w_attr(bottom_border, "sz"))
                val = get_w_attr(bottom_border, "val")
                if sz is not None and sz >= 6 and val not in ("nil", "none"):
                    row_has_bottom = True
                    break
        if not row_has_bottom:
            bad_tables.append(table_index)
            issues.append(f"第{table_index}个表格首行（表头）缺少底边框（栏目线），无法形成三线表中间分隔线")
    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表格"

def check_tb02_no_vline(document_root, contexts, style_map, cfg):
    """TB02: 三线表不应有内部竖线（insideV 应为 none 或不存在）"""
    tables = document_root.findall(".//w:tbl", NSMAP)
    if not tables:
        return True, [], "文档无表格"
    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        tbl_pr = tbl_elem.find("w:tblPr", NSMAP)
        if tbl_pr is None:
            continue
        tbl_borders = tbl_pr.find("w:tblBorders", NSMAP)
        if tbl_borders is None:
            continue
        inside_v = tbl_borders.find("w:insideV", NSMAP)
        if inside_v is not None:
            val = get_w_attr(inside_v, "val") or "none"
            sz_str = get_w_attr(inside_v, "sz") or "0"
            try:
                sz = int(sz_str)
            except ValueError:
                sz = 0
            if val not in ("none", "nil") and sz > 0:
                bad_tables.append(table_index)
                issues.append(f"第{table_index}个表格存在内部竖线（insideV val={val}, sz={sz}），三线表不应有竖线")
    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表格无多余竖线"

def check_tb03(document_root, contexts, style_map):
    """跨页表格应设置表头重复（w:tblHeader）。"""
    tables = document_root.findall(".//w:tbl", NSMAP)
    if not tables:
        return True, [], "文档无表格"
    bad_tables = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        rows = tbl_elem.findall("w:tr", NSMAP)
        if len(rows) < 6:
            continue
        first_row = rows[0]
        tbl_header = first_row.find("w:trPr/w:tblHeader", NSMAP)
        if tbl_header is None:
            bad_tables.append(table_index)
    if bad_tables:
        issues = [f"{len(bad_tables)} 个较长表格（>=6行）首行未设置 w:tblHeader，跨页时表头不会重复。"]
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], "全部较长表格"

def _has_half_width_punct_in_cjk_context(text: str) -> bool:
    return _PU01_HALF_PUNCT_RE.search(text or "") is not None

def check_pu01(document_root, contexts, style_map, cfg):
    """PU01: 中文正文中不应使用英文半角标点（,.;:） 代替全角标点（，。；：）"""
    skip_kinds = {"reference", "caption"}
    issues = []
    for ctx in contexts:
        if ctx.get("effective_section") not in {"body", "appendix"}:
            continue
        if ctx.get("kind") in skip_kinds:
            continue
        elem = ctx.get("elem")
        if elem is not None and elem.find(".//m:oMath", MNSMAP) is not None:
            continue
        txt = ctx.get("text", "")
        if _has_half_width_punct_in_cjk_context(txt):
            snippet = txt.strip()[:50]
            issues.append(f"第{ctx['index']}段正文中存在英文半角标点夹在中文字符中：{snippet}")
        if len(issues) >= 5:
            break
    if not issues:
        return True, [], "全文"
    return False, issues, f"{len(issues)} 处"

def check_pu02(document_root, contexts, style_map, cfg):
    """PU02: 省略号应使用 ……（中文），不得用 ......（英文点号）"""
    paras = document_root.findall(".//w:p", NSMAP)
    issues = []
    for p in paras:
        runs = p.findall(".//w:r", NSMAP)
        txt = "".join(get_run_text(r) for r in runs)
        if re.search(r"\.{3,}", txt):
            snippet = txt.strip()[:50]
            issues.append(f"省略号应用 ……（中文），不可用点号代替：{snippet}")
        if len(issues) >= 5:
            break
    if not issues:
        return True, [], "全文"
    return False, issues, f"{len(issues)} 处"

RULE_CHECKERS = {
    "P01": lambda doc, ctxs, sm, cfg: check_p01(doc, ctxs, sm, cfg),
    "T01": lambda doc, ctxs, sm, cfg: check_t01(doc, ctxs, sm),
    "T02": lambda doc, ctxs, sm, cfg: check_t02(doc, ctxs, sm),
    "T03": lambda doc, ctxs, sm, cfg: check_t03(doc, ctxs, sm, cfg),
    "T04": lambda doc, ctxs, sm, cfg: check_t04(doc, ctxs, sm, cfg),
    "T05": lambda doc, ctxs, sm, cfg: check_t05(doc, ctxs, sm),
    "T06": lambda doc, ctxs, sm, cfg: check_t06(doc, ctxs, sm),
    "H01": lambda doc, ctxs, sm, cfg: check_heading(ctxs, "h1", "center", cfg["h1_size"], expected_font=cfg.get("h1_font"), require_bold=cfg.get("h1_bold", False)),
    "H02": lambda doc, ctxs, sm, cfg: check_heading(ctxs, "h2", "left", cfg["h2_size"], expected_font=cfg.get("h2_font"), require_bold=cfg.get("h2_bold", False)),
    "H03": lambda doc, ctxs, sm, cfg: check_heading(ctxs, "h3", "left", cfg["h3_size"], expected_font=cfg.get("h3_font"), require_bold=cfg.get("h3_bold", False)),
    "C01": lambda doc, ctxs, sm, cfg: check_c01(doc, ctxs, sm),
    "C02": lambda doc, ctxs, sm, cfg: check_c02(doc, ctxs, sm),
    "C03": lambda doc, ctxs, sm, cfg: check_c03(doc, ctxs, sm),
    "C04": lambda doc, ctxs, sm, cfg: check_c04(doc, ctxs, sm),
    "R01": lambda doc, ctxs, sm, cfg: check_r01(doc, ctxs, sm, cfg),
    "R02": lambda doc, ctxs, sm, cfg: check_r02(doc, ctxs, sm, cfg),
    "R03": lambda doc, ctxs, sm, cfg: check_r03(doc, ctxs, sm, cfg),
    "R04": lambda doc, ctxs, sm, cfg: check_r04(doc, ctxs, sm),
    "R05": lambda doc, ctxs, sm, cfg: check_r05(doc, ctxs, sm, cfg),
    "F01": lambda doc, ctxs, sm, cfg: check_f01(doc, ctxs, sm, cfg),
    "F02": lambda doc, ctxs, sm, cfg: check_f02(doc, ctxs, sm, cfg),
    "TB01": lambda doc, ctxs, sm, cfg: check_tb01(doc, ctxs, sm),
    "H04": lambda doc, ctxs, sm, cfg: check_h04(doc, ctxs, sm, cfg),
    "S01": lambda doc, ctxs, sm, cfg: check_s01(doc, ctxs, sm, cfg),
    "S02": lambda doc, ctxs, sm, cfg: check_s02(doc, ctxs, sm),
    "S03": lambda doc, ctxs, sm, cfg: check_s03(doc, ctxs, sm),
    "FN01": lambda doc, ctxs, sm, cfg, footnotes_root: check_fn01(doc, ctxs, sm, footnotes_root),
    "PG01": lambda doc, ctxs, sm, cfg: check_pg01(doc, ctxs, sm, cfg),
    "P03": lambda doc, ctxs, sm, cfg: check_p03(doc, ctxs, sm, cfg),
    "REF01": lambda doc, ctxs, sm, cfg: check_ref01(doc, ctxs, sm),
    "KW01": lambda doc, ctxs, sm, cfg: check_kw01(doc, ctxs, sm, cfg),
    "EQ01": lambda doc, ctxs, sm, cfg: check_eq01(doc, ctxs, sm),
    "EQ02": lambda doc, ctxs, sm, cfg: check_eq02(doc, ctxs, sm, cfg),
    "EQ03": lambda doc, ctxs, sm, cfg: check_eq03(doc, ctxs, sm, cfg),
    "F03": lambda doc, ctxs, sm, cfg: check_f03(doc, ctxs, sm, cfg),
    "F04": lambda doc, ctxs, sm, cfg: check_f04(doc, ctxs, sm, cfg),
    "F05": lambda doc, ctxs, sm, cfg: check_f05(doc, ctxs, sm),
    "F06": lambda doc, ctxs, sm, cfg: check_f06(doc, ctxs, sm),
    "F07": lambda doc, ctxs, sm, cfg: check_f07(doc, ctxs, sm),
    "TB03_LINE": lambda doc, ctxs, sm, cfg: check_tb03_line(doc, ctxs, sm),
    "TB02": lambda doc, ctxs, sm, cfg: check_tb02_no_vline(doc, ctxs, sm, cfg),
    "TB03": lambda doc, ctxs, sm, cfg: check_tb03(doc, ctxs, sm),
    "SP01": lambda doc, ctxs, sm, cfg: check_sp01(doc, ctxs, sm),
    "SP02": lambda doc, ctxs, sm, cfg: check_sp02(doc, ctxs, sm),
    "SP_CJK_LATIN": lambda doc, ctxs, sm, cfg: check_sp_cjk_latin(doc, ctxs, sm, cfg),
    "SP_NUM_CJK": lambda doc, ctxs, sm, cfg: check_sp_num_cjk(doc, ctxs, sm, cfg),
    "KW02": lambda doc, ctxs, sm, cfg: check_kw02(doc, ctxs, sm, cfg),
    "PU02": lambda doc, ctxs, sm, cfg: check_pu02(doc, ctxs, sm, cfg),
    "PU01": lambda doc, ctxs, sm, cfg: check_pu01(doc, ctxs, sm, cfg),
}
