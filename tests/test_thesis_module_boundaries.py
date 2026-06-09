from __future__ import annotations

import ast
import inspect
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_thesis_rule_registries_do_not_import_audit_or_copy_globals():
    for path in sorted((PROJECT_ROOT / "scripts" / "thesis_rules").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "import audit_thesis" not in source, path
        assert "_load_audit" not in source, path
        assert "globals()[" not in source, path


def test_audit_thesis_does_not_store_rule_checker_bodies():
    source = (PROJECT_ROOT / "scripts" / "audit_thesis.py").read_text(encoding="utf-8")
    assert "\ndef check_" not in source


def test_audit_rule_checker_bodies_live_in_domain_modules():
    shared_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py").read_text(encoding="utf-8")
    common_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_common.py").read_text(encoding="utf-8")
    lnu_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_lnu.py").read_text(encoding="utf-8")

    assert "\ndef check_" not in shared_source
    assert "\ndef check_p01" in common_source
    assert "\ndef check_lnu_abs01" in lnu_source


def test_int_parsing_helper_lives_in_thesis_utils():
    import _thesis_utils
    import reference_numbering_utils
    from thesis_rules import audit_checkers

    audit_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py").read_text(encoding="utf-8")
    reference_source = (PROJECT_ROOT / "scripts" / "reference_numbering_utils.py").read_text(encoding="utf-8")

    assert "\ndef parse_int" not in audit_source
    assert "\ndef _parse_int" not in reference_source
    assert _thesis_utils.parse_int("42") == 42
    assert _thesis_utils.parse_int(None) is None
    assert _thesis_utils.parse_int("bad") is None
    assert audit_checkers.parse_int is _thesis_utils.parse_int
    assert reference_numbering_utils.parse_int is _thesis_utils.parse_int


def test_post_verify_notice_renderer_lives_in_apply_guard_module():
    import thesis_workbench
    from article_engine import service
    from thesis_tool import apply_guard

    workbench_source = (PROJECT_ROOT / "scripts" / "thesis_workbench.py").read_text(encoding="utf-8")
    service_source = (PROJECT_ROOT / "scripts" / "article_engine" / "service.py").read_text(encoding="utf-8")

    assert "\ndef _render_post_verify_notice" not in workbench_source
    assert "\ndef _render_post_verify_notice" not in service_source
    assert thesis_workbench._render_post_verify_notice is apply_guard.render_post_verify_notice
    assert service._render_post_verify_notice is apply_guard.render_post_verify_notice


def test_thesis_fix_modules_do_not_import_fix_or_copy_all_globals():
    for path in sorted((PROJECT_ROOT / "scripts" / "thesis_fix").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "import fix_thesis" not in source, path
        assert "_load_deps" not in source, path
        assert "dir(" not in source, path
        assert "globals()[" not in source, path


def test_fix_runtime_profile_scope_helpers_live_in_runtime_module():
    import fix_thesis
    from thesis_fix import runtime as fix_runtime

    source = (PROJECT_ROOT / "scripts" / "fix_thesis.py").read_text(encoding="utf-8")

    assert "\nclass FixRuntime" not in source
    assert "\nclass ScopeFlags" not in source
    assert "\ndef build_fix_runtime" not in source
    assert fix_thesis.FixRuntime is fix_runtime.FixRuntime
    assert fix_thesis.ScopeFlags is fix_runtime.ScopeFlags
    assert fix_thesis.build_fix_runtime is fix_runtime.build_fix_runtime
    assert fix_runtime.normalize_scopes("heading,reference") == {"headings", "references"}
    flags = fix_runtime.build_scope_flags({"toc"})
    assert flags.toc is True
    assert flags.page is False
    assert flags.abstract is False
    assert flags.headings is False


def test_reference_numbering_helpers_live_in_reference_numbering_module():
    import fix_thesis
    import reference_numbering_utils
    from thesis_fix import reference_numbering
    from thesis_rules import audit_lnu

    source = (PROJECT_ROOT / "scripts" / "fix_thesis.py").read_text(encoding="utf-8")
    audit_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_lnu.py").read_text(encoding="utf-8")

    assert "\ndef ensure_reference_number_spacing" not in source
    assert "\ndef normalize_reference_number_leading_zeros" not in source
    assert "\ndef paragraph_has_reference_tab" not in source
    assert "\ndef _remove_tab_after_ref_number" not in source
    assert "\ndef _inject_tab_after_ref_number" not in source
    assert 're.compile(r"^\\[[1-9]\\d{0,2}\\] \\S")' not in audit_source
    assert fix_thesis.ensure_reference_number_spacing is reference_numbering.ensure_reference_number_spacing
    assert fix_thesis.normalize_reference_number_leading_zeros is reference_numbering.normalize_reference_number_leading_zeros
    assert fix_thesis.paragraph_has_reference_tab is reference_numbering.paragraph_has_reference_tab
    assert reference_numbering.paragraph_has_reference_tab is reference_numbering_utils.paragraph_has_reference_tab
    assert audit_lnu.paragraph_has_reference_tab is reference_numbering_utils.paragraph_has_reference_tab


def test_citation_helpers_live_in_citations_module():
    import fix_thesis
    from thesis_fix import citations

    source = (PROJECT_ROOT / "scripts" / "fix_thesis.py").read_text(encoding="utf-8")

    assert "\ndef fix_superscript_fonts" not in source
    assert "\ndef split_inline_citations" not in source
    assert "\ndef _citation_run_numbers" not in source
    assert "\ndef _format_citation_numbers" not in source
    assert "\ndef _merge_adjacent_superscript_citation_runs" not in source
    assert "\ndef move_superscript_citations_before_terminal_punct" not in source
    assert fix_thesis.fix_superscript_fonts is citations.fix_superscript_fonts
    assert fix_thesis.split_inline_citations is citations.split_inline_citations
    assert fix_thesis.move_superscript_citations_before_terminal_punct is citations.move_superscript_citations_before_terminal_punct


def test_citation_text_rules_live_in_shared_text_utils():
    import citation_text_utils
    import reorder_references_by_appearance
    from thesis_fix import citations
    from thesis_rules import audit_checkers, audit_common, audit_lnu

    fix_source = (PROJECT_ROOT / "scripts" / "thesis_fix" / "citations.py").read_text(encoding="utf-8")
    audit_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_common.py").read_text(encoding="utf-8")
    audit_lnu_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_lnu.py").read_text(encoding="utf-8")
    reorder_source = (PROJECT_ROOT / "scripts" / "reorder_references_by_appearance.py").read_text(encoding="utf-8")

    assert "\ndef _format_citation_numbers" not in fix_source
    assert "\ndef _format_citation_numbers" not in audit_source
    assert "\ndef _citation_numbers_from_token" not in audit_source
    assert "\ndef _expand_citation_numbers" not in audit_lnu_source
    assert "\ndef _expand_citation_numbers" not in reorder_source
    assert "\ndef _compress_citation_numbers" not in reorder_source
    assert "_CITATION_NUM_RE = re.compile" not in audit_lnu_source
    assert "CITATION_RE = re.compile" not in reorder_source
    assert 're.compile(r"\\[\\d{1,3}' not in fix_source
    assert 're.compile(r"\\[\\d{1,3}' not in audit_source
    assert citations.CITATION_RUN_RE is citation_text_utils.CITATION_TOKEN_RE
    assert audit_common._CITATION_TOKEN_RE is citation_text_utils.CITATION_TOKEN_RE
    assert audit_common.INLINE_CITATION_PAT is citation_text_utils.CITATION_TOKEN_RE
    assert audit_lnu._CITATION_NUM_RE is citation_text_utils.CITATION_NUMBER_GROUP_RE
    assert reorder_references_by_appearance.CITATION_RE is citation_text_utils.CITATION_NUMBER_GROUP_RE
    assert reorder_references_by_appearance._compress_citation_numbers is citation_text_utils.format_citation_numbers
    assert audit_checkers.is_citation_run_text("[1]") is True


def test_num_cjk_spacing_rules_live_in_shared_text_spacing_utils():
    import fix_thesis
    import text_spacing_utils
    from thesis_rules import audit_checkers

    checked_sources = [
        PROJECT_ROOT / "scripts" / "fix_thesis.py",
        PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py",
    ]

    for path in checked_sources:
        source = path.read_text(encoding="utf-8")
        assert "\ndef _starts_with_num_cjk_exception" not in source
        assert "\ndef _needs_num_cjk_space" not in source
        assert "\nNUM_CJK_EXCEPTIONS =" not in source
        assert "\nNUM_CJK_LEFT_EXCEPTIONS =" not in source
    assert fix_thesis._needs_num_cjk_space is text_spacing_utils.needs_num_cjk_space
    assert audit_checkers._needs_num_cjk_space is text_spacing_utils.needs_num_cjk_space
    assert fix_thesis.NUM_CJK_EXCEPTIONS is text_spacing_utils.NUM_CJK_EXCEPTIONS
    assert audit_checkers.NUM_CJK_LEFT_EXCEPTIONS is text_spacing_utils.NUM_CJK_LEFT_EXCEPTIONS


def test_table_figure_xml_helpers_live_in_shared_xml_helper_module():
    import fix_thesis
    from sections import _xml_helpers
    from thesis_rules import audit_lnu

    fix_source = (PROJECT_ROOT / "scripts" / "fix_thesis.py").read_text(encoding="utf-8")
    audit_lnu_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_lnu.py").read_text(encoding="utf-8")
    dependency_source = inspect.getsource(fix_thesis._configure_thesis_fix_dependencies)
    tables_figures_source = (PROJECT_ROOT / "scripts" / "thesis_fix" / "tables_figures.py").read_text(encoding="utf-8")

    assert "\ndef _get_paragraph_spacing_twips" not in fix_source
    assert "\ndef _set_paragraph_spacing_attrs" not in fix_source
    assert "\ndef _set_onoff_property" not in fix_source
    assert "\ndef _set_paragraph_pagination_flags" not in fix_source
    assert "\ndef _set_table_row_cant_split" not in fix_source
    assert "\ndef _onoff_enabled" not in audit_lnu_source
    assert "\ndef _paragraph_onoff_enabled" not in audit_lnu_source
    assert "\ndef _table_row_cant_split_enabled" not in audit_lnu_source
    assert '"_get_paragraph_spacing_twips"' not in dependency_source
    assert '"_set_paragraph_spacing_attrs"' not in dependency_source
    assert '"_set_paragraph_pagination_flags"' not in dependency_source
    assert '"_set_table_row_cant_split"' not in dependency_source
    assert '"_get_paragraph_spacing_twips"' not in tables_figures_source
    assert '"_set_paragraph_spacing_attrs"' not in tables_figures_source
    assert '"_set_paragraph_pagination_flags"' not in tables_figures_source
    assert '"_set_table_row_cant_split"' not in tables_figures_source
    assert '"_set_onoff_property"' not in tables_figures_source
    assert "from sections._xml_helpers import" in tables_figures_source
    assert fix_thesis._get_paragraph_spacing_twips is _xml_helpers.get_paragraph_spacing_twips
    assert fix_thesis._set_paragraph_spacing_attrs is _xml_helpers.set_paragraph_spacing_attrs
    assert fix_thesis._set_onoff_property is _xml_helpers.set_onoff_property
    assert fix_thesis._set_paragraph_pagination_flags is _xml_helpers.set_paragraph_pagination_flags
    assert fix_thesis._set_table_row_cant_split is _xml_helpers.set_table_row_cant_split
    assert audit_lnu._paragraph_onoff_enabled is _xml_helpers.paragraph_onoff_enabled
    assert audit_lnu._table_row_cant_split_enabled is _xml_helpers.table_row_cant_split_enabled


def test_run_text_helper_lives_in_shared_xml_helper_module():
    import fix_thesis
    from sections import _xml_helpers
    from thesis_fix import citations, reference_numbering
    from thesis_rules import audit_checkers

    checked_sources = [
        PROJECT_ROOT / "scripts" / "fix_thesis.py",
        PROJECT_ROOT / "scripts" / "thesis_fix" / "citations.py",
        PROJECT_ROOT / "scripts" / "thesis_fix" / "reference_numbering.py",
        PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py",
    ]

    for path in checked_sources:
        assert "\ndef get_run_text" not in path.read_text(encoding="utf-8")
    assert fix_thesis.get_run_text is _xml_helpers.get_run_text
    assert citations.get_run_text is _xml_helpers.get_run_text
    assert reference_numbering.get_run_text is _xml_helpers.get_run_text
    assert audit_checkers.get_run_text is _xml_helpers.get_run_text


def test_superscript_helper_lives_in_shared_xml_helper_module():
    import fix_thesis
    from sections import _xml_helpers
    from thesis_fix import citations
    from thesis_rules import audit_checkers

    checked_sources = [
        PROJECT_ROOT / "scripts" / "fix_thesis.py",
        PROJECT_ROOT / "scripts" / "thesis_fix" / "citations.py",
        PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py",
    ]

    for path in checked_sources:
        assert "\ndef is_superscript" not in path.read_text(encoding="utf-8")
    assert fix_thesis.is_superscript is _xml_helpers.is_superscript
    assert citations.is_superscript is _xml_helpers.is_superscript
    assert audit_checkers.is_superscript is _xml_helpers.is_superscript


def test_updated_parts_are_built_by_output_parts_module_without_private_wrapper():
    source = (PROJECT_ROOT / "scripts" / "fix_thesis.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_defs = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    fix_docx_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "fix_docx"
    )

    direct_calls = [
        node
        for node in ast.walk(fix_docx_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "build_updated_parts"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "fix_output_parts"
    ]

    assert "_build_updated_parts" not in function_defs
    assert len(direct_calls) == 1
    assert direct_calls[0].args == []
    assert {keyword.arg for keyword in direct_calls[0].keywords} == {
        "ctx",
        "toc_parts",
        "footer_builder",
        "settings_builder",
    }


def test_workflow_render_functions_delegate_to_renderer_module():
    from thesis_tool import workflow, workflow_renderers

    source = (PROJECT_ROOT / "scripts" / "thesis_tool" / "workflow.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    renderer_names = [
        "render_scope_plan",
        "render_scope_verify",
        "render_document_diagnostics",
        "render_document_diagnostics_compact",
        "render_document_preflight",
        "render_document_preflight_compact",
        "render_document_normalize",
        "render_document_normalize_compact",
    ]

    for name in renderer_names:
        wrapper = functions[name]
        direct_calls = [
            node
            for node in ast.walk(wrapper)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == name
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "workflow_renderers"
        ]
        wrapper_source = inspect.getsource(getattr(workflow, name))

        assert len(direct_calls) == 1
        assert hasattr(workflow_renderers, name)
        assert "建议按范围处理" not in wrapper_source
        assert "范围复查结果" not in wrapper_source
        assert "表格内伪标题候选" not in wrapper_source
        assert "风险摘要" not in wrapper_source
        assert "预检变化" not in wrapper_source


def test_render_analyzer_image_metrics_live_in_image_metrics_module():
    from thesis_tool import render_analyzer, render_image_metrics

    analyzer_source = (PROJECT_ROOT / "scripts" / "thesis_tool" / "render_analyzer.py").read_text(encoding="utf-8")
    read_metrics_source = inspect.getsource(render_analyzer._read_page_image_metrics)

    assert "\nclass PageImageMetrics" not in analyzer_source
    assert "\ndef _read_with_pillow" not in analyzer_source
    assert "\ndef _read_png_metrics" not in analyzer_source
    assert "\ndef _decode_png" not in analyzer_source
    assert "\nclass _Bbox" not in analyzer_source
    assert "render_image_metrics.read_page_image_metrics" in read_metrics_source
    assert render_analyzer.PageImageMetrics is render_image_metrics.PageImageMetrics
    assert render_analyzer._read_with_pillow is render_image_metrics.read_with_pillow
    assert render_analyzer._read_png_metrics is render_image_metrics.read_png_metrics
    assert render_analyzer._decode_png is render_image_metrics.decode_png
