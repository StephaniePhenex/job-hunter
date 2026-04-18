# Resume files (local)

Put one resume per file here. Supported formats:

- **`.docx`** (Word 2007+, recommended if your CVs are Word files)
- **`.md`** or **`.txt`** (UTF-8 plain text)

Legacy **`.doc`** (Word 97–2003) is not supported — open in Word and **Save As → .docx**.

The **filename without extension** becomes the resume `id` (normalized to lowercase; non-alphanumeric runs become `-`).

Examples: `fullstack.docx`, `frontend.md`, `product-manager.txt`

These merge with `resumes:` in `user_profile.yaml`. If the same `id` exists in both, **the file here wins**.

Changes are picked up after **restarting uvicorn** (same as YAML profile reload).

This directory is gitignored except for `.gitkeep` and this README.
