# Troubleshooting

This page is for common Windows local web package and `.docx` workflow failures. Do not upload real thesis files, repaired drafts, API keys, logs, or unchecked feedback packages to public GitHub issues.

## Zip Was Not Extracted

Run the tool only after fully extracting `article-local-windows.zip`. Do not double-click `启动论文格式检查.bat` inside the zip preview window.

Expected extracted files include:

- `启动论文格式检查.bat`
- `导出反馈包.bat`
- `快速开始.txt`
- `app/`
- `data/`

## Windows SmartScreen Warning

The current Beta is a Windows zip + bat local web package, not a signed `.exe` or `.msi` installer. Windows may show a warning before running downloaded scripts. Confirm that the file came from this project's GitHub Release page before continuing.

## Port 8000 Is Occupied

If the black command window says port 8000 is occupied, close the program using that port and try again. If you do not know which program is using it, restart Windows and double-click `启动论文格式检查.bat` again.

## Invalid `.docx`

The uploaded file must be a real Word/WPS `.docx` package. A renamed `.doc`, PDF, zip, temporary file, or corrupted document will be rejected. Open the file in Word/WPS and save it again as `.docx`.

## Directory Page Numbers Need Review

When TOC repair is enabled, the tool writes visible automatic TOC field results directly. If the body is edited again and pagination changes, update the TOC field in Word/WPS and review the page numbers. WPS/Word final rendering is still required before submission.

## WPS And Word Render Differently

OOXML structure checks cannot fully replace final rendering. Always open the repaired copy in the same software used for submission and manually confirm directory, pagination, figures, formulas, tables, and references.

## Feedback Package Privacy Check

If reporting a problem, run `导出反馈包.bat` only when needed and inspect the generated archive before sharing. Public issues should contain version, operating system, Word/WPS version, sanitized error text, and screenshots that do not show private thesis content.
