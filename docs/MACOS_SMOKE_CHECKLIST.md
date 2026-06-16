# macOS Smoke Checklist

Use this only after a macOS experimental package exists. It does not replace unit tests, CI, or Windows smoke.

## Environment

- macOS version:
- Architecture: Apple Silicon / Intel
- Package type: source install / `.app` / `.dmg`
- Word/WPS version:
- Release tag:
- sha256:

## Steps

1. Start from a clean macOS user environment.
2. Launch the package for the first time.
3. Record any Gatekeeper or quarantine warning text.
4. Confirm the local service starts on `127.0.0.1`.
5. Confirm the browser opens automatically or the app shows the local URL clearly.
6. Upload a sanitized `.docx` sample.
7. Run audit / plan / apply / download.
8. Open the repaired copy in WPS/Word.
9. Manually check directory, pagination, figures, formulas, tables, and references.
10. Quit the app and confirm no unexpected background process remains.

## Evidence

Keep evidence private unless it is sanitized. Public GitHub issues or Release notes must not contain thesis text, repaired drafts, PDFs, local logs, API keys, feedback packages, private paths, or screenshots with sensitive content.
