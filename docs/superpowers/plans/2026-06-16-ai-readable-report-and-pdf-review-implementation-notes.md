# AI-Readable Report And PDF Review Implementation Notes

## Real PDF Calibration

Command:

```bash
python3 scripts/thesis_tool/render_verify.py \
  "/Users/apple/Desktop/本科毕业论文/20221303306-刘佳轾-不同改性方法对鹿皮明胶功能特性和结构特性的影响研究.docx" \
  --profile lnu \
  --rendered-pdf "/Users/apple/Desktop/本科毕业论文/20221303306-刘佳轾-不同改性方法对鹿皮明胶功能特性和结构特性的影响研究.pdf" \
  --output-dir /tmp/article_render_check
```

Observed public findings:

- 4 `render.isolated_punctuation` findings on PDF pages 15, 16, 18, and 19.
- 8 `render.toc_page_number_mismatch` findings on the directory page.
- No `render.formula_number_split_page` finding in this submitted PDF.
- No `render.heading_orphan_at_page_bottom` finding in this submitted PDF.
- No public large-blank finding or wording in generated Markdown reports.

Calibration notes:

- The directory mismatch findings are plausible because the PDF text layer maps directory entries to headings with different printed page numbers.
- The isolated punctuation findings are plausible candidates for manual PDF spot check; they are warnings because the text layer can detect standalone punctuation but cannot prove the Word editing cause.
- No false positive was recorded for large blank areas because those findings are filtered out of public output.
- No false negative is known from this smoke run. Formula split and heading orphan checks remain conservative and may miss cases when the PDF text layer omits formulas, headings, or text-box content.
