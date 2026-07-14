# Real DOCX Samples

This directory defines the real dirty DOCX sample intake process.

- `private/` is ignored and may contain original user-provided documents for local debugging only.
- `public_downloads/` is ignored and may contain public Apache POI/docx4j sample downloads.
- `sanitized/` is ignored by default. Sanitized samples may be committed only after manual privacy review.
- `manifest.yaml` records required categories and policy.

`docx_sample_intake.py` only scrubs package metadata and a small set of known author markers. It does not redact body text, images, comments, revisions, or other embedded content. Treat every output as private until a person has reviewed the full package and reduced it to a non-identifying minimal reproduction. Never commit an original thesis.

Use:

```bash
python3 scripts/docx_sample_intake.py ~/Desktop/sample.docx \
  --sample-id wps-section-break-001 \
  --category section_break \
  --source-app WPS \
  --output-dir tests/real_docx_samples/sanitized \
  --manifest-jsonl tests/real_docx_samples/sanitized/manifest.jsonl
```

Public sample stress pool:

```bash
python3 scripts/fetch_public_docx_samples.py
python3 -m pytest tests/test_real_docx_sample_intake.py tests/test_docx_compat_samples.py -q
```
