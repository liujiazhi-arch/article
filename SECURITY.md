# Security Policy

This project is local-first. GitHub is used for source code, documentation, CI, Release assets, and sanitized issue reports; it is not a place to upload thesis files, repaired drafts, API keys, local logs, runtime cache, state databases, or unchecked feedback packages.

## Reporting

For privacy or security issues, open a GitHub issue with a sanitized description, version number, environment, and the minimal steps needed to reproduce the problem. Do not attach real thesis documents, repaired documents, PDFs, API keys, local logs, screenshots containing sensitive content, or unchecked feedback archives.

If a feedback package is needed, inspect the archive before sharing it. The feedback package should not contain thesis text, repaired drafts, PDFs, page images, API keys, or private local paths.

## Local Configuration

Keep real local configuration in ignored files such as `.env`, `.env.*`, `*.env`, or `article-local.env`. The committed `.env.example` is only a public template.

Detailed privacy and secret-handling guidance is in [docs/SECURITY.md](docs/SECURITY.md) and [docs/PRIVACY.md](docs/PRIVACY.md).
