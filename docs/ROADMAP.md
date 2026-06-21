# Roadmap

This roadmap keeps the project focused on a local-first thesis format workflow. New public promises should only be added after runtime rules, tests, packaging, and release evidence exist.

## Current Beta

- Stabilize the Windows `lnu-thesis-local-windows.zip` package.
- Keep the student path simple: download, extract, double-click, upload `.docx`, download repaired copy, manually verify in Word/WPS.
- Improve GitHub presentation with screenshots, clear Release instructions, repository topics, and support docs.
- Keep update checking manual and metadata-only.

## Near Term

- Improve troubleshooting guidance for Windows startup, `.docx` compatibility, and Word/WPS rendering differences.
- Keep release evidence tied to CI, bundle smoke, browser smoke, and clean Windows smoke.
- Add only runtime rules that are connected to tests and `config/capability_matrix.md`.

## macOS Packaging

macOS support should be staged:

1. Source install for developers using Python 3.11 or 3.12.
2. Experimental `.app` that starts the local service and opens the browser.
3. Signed and notarized `.dmg` after Gatekeeper, first launch, exit behavior, and clean-machine smoke are verified.

Apple Silicon should be handled first. Intel builds can follow only if there is a real user need. Do not describe the macOS package as a formal Mac application until signing and notarization are complete.

## Out Of Scope For Current Beta

- Automatic updater
- Signed Windows `.exe` / `.msi`
- Signed/notarized macOS `.dmg`
- Cloud processing of thesis documents
- Additional school profiles that are not wired into runtime tests
