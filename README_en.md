<div align="center">

# NCUE Course MCP

**A zero-runtime-dependency MCP server that turns NCUE's public course schedule search into structured tools.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-stdio-5A67D8?style=flat-square)](https://modelcontextprotocol.io)
[![Dependencies](https://img.shields.io/badge/Runtime-0%20Dependencies-success?style=flat-square)](pyproject.toml)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

[繁體中文](README.md) · **English**

[Features](#features) · [How It Works](#how-it-works) · [Getting Started](#getting-started) · [MCP Configuration](#mcp-configuration) · [Tool Reference](#tool-reference) · [Development](#development)

</div>

---

## Overview

NCUE Course MCP connects to the public course schedule search page of National Changhua University of Education (NCUE), handles form tokens, cookie sessions, staged class-list loading, and HTML table parsing, then exposes the result as clean JSON through MCP tools.

Official source page:

- https://webapt.ncue.edu.tw/deanv2/other/ob010

> This project is not affiliated with NCUE. It simply wraps the public query page for automation-friendly MCP usage.

---

## Features

| Feature | Description |
| --- | --- |
| **Query Option Discovery** | Reads available years, semesters, branches, weekdays, English-taught, and distance-learning options from the official page |
| **Staged Class Loading** | Loads class IDs by `year + semester + branch` |
| **Course Search** | Supports class, weekday, course code, course name, teacher, English-taught flag, and distance-learning flag |
| **HTML Table Parsing** | Converts the official course table HTML into structured JSON |
| **Meeting-Time Parsing** | Parses text like `(四) 05-07 資工電腦教室(二)` into weekday, periods, period count, and place |
| **Historical Pattern Analysis** | Estimates likely future courses from historical same-semester offerings |
| **Zero Runtime Dependencies** | Uses only the Python standard library at runtime |

---

## How It Works

The official page is an ASP.NET MVC form. A query requires a `__RequestVerificationToken`, then an AJAX POST with the selected search fields.

```text
MCP Client
   │
   │ tools/call
   ▼
NCUE Course MCP
   │
   ├─ GET  /deanv2/other/ob010
   │      Fetch cookie session and __RequestVerificationToken
   │
   ├─ GET  /DEANV2/Other/OB010/GetJson_ddl_scj_cls_id
   │      Load class options by year, semester, and branch
   │
   └─ POST /DEANV2/Other/OB010
          Query course HTML and parse it into JSON
```

### Staged Loading

The only staged field currently detected is the class selector:

| Field | Label | Depends On | MCP Tool |
| --- | --- | --- | --- |
| `sel_cls_id` | Class ID / 修課班別 | `sel_yms_year`, `sel_yms_smester`, `sel_cls_branch` | `ncue_list_classes` |

Official endpoint:

```text
https://webapt.ncue.edu.tw/DEANV2/Other/OB010/GetJson_ddl_scj_cls_id
```

---

## Getting Started

### Prerequisites

- Python **3.10** or newer
- Network access to `webapt.ncue.edu.tw`

### Installation

```bash
git clone <repository-url>
cd ncue-course-mcp
python -m pip install -e .
```

### Direct Tool Test

```bash
ncue-course-mcp --tool ncue_list_classes --args '{"year":114,"semester":1,"branch":"D","keyword":"資工"}'
```

If JSON quoting is awkward in your shell, use an argument file:

```bash
ncue-course-mcp --tool ncue_search_courses --args-file examples/query-d540mn1a.json
```

---

## MCP Configuration

After installing the package:

```json
{
  "mcpServers": {
    "ncue-course-query": {
      "command": "ncue-course-mcp",
      "args": []
    }
  }
}
```

To run directly from source without installation:

```json
{
  "mcpServers": {
    "ncue-course-query": {
      "command": "python",
      "args": [
        "<absolute-path-to-repository>\\scripts\\run_mcp_server.py"
      ]
    }
  }
}
```

Example configs are available in [`examples/`](examples/).

---

## Tool Reference

| Tool | Purpose | Common Arguments |
| --- | --- | --- |
| `ncue_list_query_options` | Lists official query fields and staged-loading details | `refresh` |
| `ncue_list_classes` | Loads available class IDs | `year`, `semester`, `branch`, `keyword` |
| `ncue_search_courses` | Searches courses and returns structured rows | `year`, `semester`, `branch`, `class_id`, `weekday`, `course_name`, `teacher_name` |
| `ncue_analyze_first_semester_pattern` | Analyzes historical same-semester patterns and estimates target-term courses | `class_id`, `start_year`, `end_year`, `exclusion_year`, `target_year` |

### `ncue_search_courses` Example

```json
{
  "year": 114,
  "semester": 1,
  "branch": "D",
  "class_id": "D540MN1A"
}
```

Common fields:

| Argument | Description |
| --- | --- |
| `year` | ROC academic year, such as `114` |
| `semester` | `1` first semester, `2` second semester, `3` summer course, `4` summer program |
| `branch` | `D` day division, `N` in-service master's program |
| `class_id` | Class ID, such as `D540MN1A` |
| `weekday` | `1` to `6`; empty string means all weekdays |
| `course_code` | Course-code keyword |
| `course_name` | Course-name keyword |
| `teacher_name` | Teacher-name keyword |
| `english` | `Y`, `N`, or empty string |
| `distance` | `Y`, `N`, or empty string |

### `ncue_analyze_first_semester_pattern` Example

```json
{
  "class_id": "D540MN1A",
  "start_year": 112,
  "end_year": 114,
  "semester": 1,
  "exclusion_year": 114,
  "exclusion_semester": 2,
  "target_year": 115,
  "target_semester": 1
}
```

Prediction rule:

- More appearances in the analyzed same-semester range means higher likelihood.
- Courses found in the exclusion term are downgraded.
- Courses that appear every analyzed year stay high-likelihood even if they also appear in the exclusion term, because they look fixed or recurring.

---

## Project Structure

```text
.
├── src/ncue_course_mcp/
│   ├── client.py            # Official-page client, parser, and analysis logic
│   ├── server.py            # stdio MCP server
│   └── __main__.py          # python -m ncue_course_mcp
├── scripts/
│   ├── run_mcp_server.py    # Source-tree launcher before package installation
│   └── analyze_d540mn1a.py  # Example historical analysis script
├── tests/                   # Network-free unit tests
├── examples/                # MCP configs and query argument examples
├── pyproject.toml
└── README.md
```

---

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

The test suite avoids network calls. It checks HTML parsing, meeting-time parsing, and MCP JSON-RPC response shapes.

### Local MCP Smoke Test

```powershell
$env:PYTHONPATH='src'
python -m ncue_course_mcp --tool ncue_search_courses --args-file examples/query-d540mn1a.json
```

---

## Notes

- Runtime has no third-party dependencies.
- The server does not require user-provided login cookies.
- Local scrape outputs under `output/` are ignored by `.gitignore`.
- Parser updates may be required if NCUE changes the official form or table HTML.

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

<div align="center">

Made for structured course queries with Python + MCP.

</div>
