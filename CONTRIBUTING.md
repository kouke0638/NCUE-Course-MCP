# Contributing

Thanks for helping improve NCUE Course MCP.

## Local Setup

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

## Guidelines

- Keep runtime dependencies at zero unless a dependency removes meaningful maintenance burden.
- Prefer parser tests with small local HTML fixtures instead of tests that depend on the live NCUE website.
- Do not commit generated scrape outputs from `output/`.
- Keep MCP tool responses structured and stable; add fields rather than renaming existing fields when possible.

## Before Opening a Pull Request

Run:

```bash
python -m unittest discover -s tests
python -m py_compile src/ncue_course_mcp/client.py src/ncue_course_mcp/server.py
```
