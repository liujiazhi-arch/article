from __future__ import annotations

import os
import shutil
import tempfile

from docx import Document

from thesis_fix.dependencies import require


def _apply_lnu_postpasses(ctx):
    (
        fix_lnu_abs01,
        fix_lnu_abs02,
        fix_lnu_abs03,
        fix_lnu_ack01,
        fix_lnu_conc01,
        fix_lnu_ref01,
        fix_lnu_ref02,
        fix_lnu_ref04,
        fix_lnu_s03,
        fix_lnu_tb03,
        fix_lnu_title01,
        insert_missing_caption_reference_leads,
        is_lnu_profile,
        normalize_lnu_figure_block_layout,
        normalize_lnu_table_block_layout,
        normalize_toc_entry_paragraphs,
        normalize_toc_title_paragraph,
        promote_post_caption_reference_blocks,
        protect_object_blocks_from_pagination,
        rebalance_figure_blocks_for_layout,
        rebalance_table_blocks_for_layout,
        remove_duplicate_body_toc_title,
        remove_synthetic_caption_reference_leads,
        renumber_lnu_captions,
    ) = require(
        "fix_lnu_abs01",
        "fix_lnu_abs02",
        "fix_lnu_abs03",
        "fix_lnu_ack01",
        "fix_lnu_conc01",
        "fix_lnu_ref01",
        "fix_lnu_ref02",
        "fix_lnu_ref04",
        "fix_lnu_s03",
        "fix_lnu_tb03",
        "fix_lnu_title01",
        "insert_missing_caption_reference_leads",
        "is_lnu_profile",
        "normalize_lnu_figure_block_layout",
        "normalize_lnu_table_block_layout",
        "normalize_toc_entry_paragraphs",
        "normalize_toc_title_paragraph",
        "promote_post_caption_reference_blocks",
        "protect_object_blocks_from_pagination",
        "rebalance_figure_blocks_for_layout",
        "rebalance_table_blocks_for_layout",
        "remove_duplicate_body_toc_title",
        "remove_synthetic_caption_reference_leads",
        "renumber_lnu_captions",
    )
    if not is_lnu_profile(ctx.runtime):
        return

    title_targets = None
    s03_targets = None
    if ctx.runtime.requested_scopes is not None:
        title_targets = set()
        s03_targets = set()
        if ctx.scope_flags.abstract:
            title_targets.add("摘要")
        if ctx.scope_flags.toc:
            title_targets.add("目录")
        if ctx.scope_flags.headings:
            s03_targets.update({"参考文献", "致谢", "附录"})
        if ctx.scope_flags.acknowledgement:
            title_targets.add("致谢")
            s03_targets.add("致谢")
        if ctx.scope_flags.references:
            s03_targets.add("参考文献")
        if ctx.scope_flags.appendix:
            s03_targets.add("附录")
    if ctx.scope_flags.abstract:
        fix_lnu_abs01(ctx.document_root, ctx.cfg)
        fix_lnu_abs02(ctx.document_root, ctx.cfg)
        fix_lnu_abs03(ctx.document_root, ctx.cfg)
    if ctx.scope_flags.headings or ctx.scope_flags.references or ctx.scope_flags.acknowledgement or ctx.scope_flags.appendix:
        fix_lnu_s03(ctx.document_root, ctx.cfg, allowed_titles=s03_targets)
    if ctx.scope_flags.acknowledgement:
        fix_lnu_ack01(ctx.document_root, ctx.cfg)
    if ctx.scope_flags.references:
        fix_lnu_ref01(ctx.document_root, ctx.cfg)
        fix_lnu_ref02(ctx.document_root, ctx.cfg)
        fix_lnu_ref04(ctx.document_root, ctx.cfg)
    if ctx.scope_flags.headings:
        fix_lnu_conc01(ctx.document_root, ctx.cfg)
    if ctx.scope_flags.abstract or ctx.scope_flags.toc or ctx.scope_flags.acknowledgement:
        fix_lnu_title01(ctx.document_root, ctx.cfg, allowed_titles=title_targets)
    if ctx.scope_flags.figures:
        fix_lnu_tb03(ctx.document_root, ctx.cfg)
        renumber_lnu_captions(ctx.document_root, ctx.style_map)
        promote_post_caption_reference_blocks(
            ctx.document_root,
            cfg=ctx.cfg,
            style_map=ctx.style_map,
            runtime=ctx.runtime,
        )
        rebalance_table_blocks_for_layout(
            ctx.document_root,
            style_map=ctx.style_map,
            cfg=ctx.cfg,
            runtime=ctx.runtime,
        )
        rebalance_figure_blocks_for_layout(
            ctx.document_root,
            style_map=ctx.style_map,
            cfg=ctx.cfg,
            runtime=ctx.runtime,
        )
    if ctx.scope_flags.toc:
        remove_duplicate_body_toc_title(ctx.document_root, ctx.style_map)
        normalize_toc_title_paragraph(ctx.document_root, ctx.style_map, ctx.cfg)
        normalize_toc_entry_paragraphs(ctx.document_root, ctx.style_map, ctx.cfg)
    if ctx.scope_flags.figures:
        remove_synthetic_caption_reference_leads(ctx.document_root, ctx.style_map)
        insert_missing_caption_reference_leads(ctx.document_root, cfg=ctx.cfg, style_map=ctx.style_map, runtime=ctx.runtime)
        normalize_lnu_figure_block_layout(
            ctx.document_root,
            style_map=ctx.style_map,
            cfg=ctx.cfg,
            runtime=ctx.runtime,
        )
        normalize_lnu_table_block_layout(
            ctx.document_root,
            style_map=ctx.style_map,
            cfg=ctx.cfg,
            runtime=ctx.runtime,
        )
        protect_object_blocks_from_pagination(
            ctx.document_root,
            style_map=ctx.style_map,
            cfg=ctx.cfg,
            runtime=ctx.runtime,
        )

def _postprocess_lnu_reference_order(output_path, runtime, cfg):
    (
        _cleanup_docx_hidden_page_number_artifacts,
        is_lnu_profile,
        is_scope_enabled,
        reorder_references_in_document,
    ) = require(
        "_cleanup_docx_hidden_page_number_artifacts",
        "is_lnu_profile",
        "is_scope_enabled",
        "reorder_references_in_document",
    )
    if not is_lnu_profile(runtime):
        return
    if not is_scope_enabled(runtime.requested_scopes, "references"):
        return
    trailing_space = bool(cfg.get("ref_number_trailing_space", cfg.get("ref_use_tab", False)))
    document = Document(output_path)
    reorder_references_in_document(document, trailing_space=trailing_space)
    temp_output = tempfile.NamedTemporaryFile(prefix="lnu_refseq_", suffix=".docx", delete=False)
    temp_output.close()
    try:
        document.save(temp_output.name)
        shutil.move(temp_output.name, output_path)
        _cleanup_docx_hidden_page_number_artifacts(output_path)
    finally:
        if os.path.exists(temp_output.name):
            os.remove(temp_output.name)
