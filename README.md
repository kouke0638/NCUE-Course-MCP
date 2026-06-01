<div align="center">

# NCUE Course MCP

**一個零執行期依賴的 MCP Server，將彰師大公開課表查詢系統包裝成結構化工具。**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-stdio-5A67D8?style=flat-square)](https://modelcontextprotocol.io)
[![Dependencies](https://img.shields.io/badge/Runtime-0%20Dependencies-success?style=flat-square)](pyproject.toml)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

**繁體中文** · [English](README_en.md)

[功能](#功能) · [運作方式](#運作方式) · [快速開始](#快速開始) · [MCP-設定](#mcp-設定) · [工具說明](#工具說明) · [開發](#開發)

</div>

---

## 概覽

NCUE Course MCP 會連到彰師大教務系統的公開課表查詢頁，處理表單 token、cookie session、分段載入班別清單與課表 HTML 解析，並透過 MCP tools 回傳乾淨的 JSON。

官方資料來源：

- https://webapt.ncue.edu.tw/deanv2/other/ob010

> 本專案與國立彰化師範大學無官方隸屬關係；它只是把公開查詢頁整理成方便自動化使用的 MCP 工具。

---

## 功能

| 功能 | 說明 |
| --- | --- |
| **查詢條件探索** | 從官方頁面讀取可用學年、學期、日夜間別、星期、全英語與遠距選項 |
| **分段載入班別** | 依 `學年 + 學期 + 日夜間別` 載入「修課班別」清單 |
| **課表查詢** | 支援班別、星期、課程代碼、課名、教師、全英語、遠距等條件 |
| **HTML 表格解析** | 將官方課表 HTML 轉成結構化 JSON |
| **節次解析** | 將 `(四) 05-07 資工電腦教室(二)` 解析成星期、節次、節數、地點 |
| **歷年規律分析** | 依同一班別歷年同學期開課紀錄，推估目標學期可能課程 |
| **零執行期依賴** | Runtime 只使用 Python 標準函式庫 |

---

## 運作方式

官方頁面是一個 ASP.NET MVC 表單。查詢時需要先取得 `__RequestVerificationToken`，再用 AJAX POST 送出查詢條件。

```text
MCP Client
   │
   │ tools/call
   ▼
NCUE Course MCP
   │
   ├─ GET  /deanv2/other/ob010
   │      取得 cookie session 與 __RequestVerificationToken
   │
   ├─ GET  /DEANV2/Other/OB010/GetJson_ddl_scj_cls_id
   │      依學年、學期、日夜間別載入班別清單
   │
   └─ POST /DEANV2/Other/OB010
          查詢課表 HTML，解析成 JSON
```

### 分段載入欄位

目前確認只有「修課班別」是分段載入：

| 欄位 | 官方名稱 | 依賴條件 | MCP 工具 |
| --- | --- | --- | --- |
| `sel_cls_id` | 修課班別 | `sel_yms_year`, `sel_yms_smester`, `sel_cls_branch` | `ncue_list_classes` |

官方端點：

```text
https://webapt.ncue.edu.tw/DEANV2/Other/OB010/GetJson_ddl_scj_cls_id
```

---

## 快速開始

### 需求

- Python **3.10** 或更新版本
- 可連線到 `webapt.ncue.edu.tw`

### 安裝

```bash
git clone <repository-url>
cd ncue-course-mcp
python -m pip install -e .
```

### 直接測試工具

```bash
ncue-course-mcp --tool ncue_list_classes --args '{"year":114,"semester":1,"branch":"D","keyword":"資工"}'
```

如果 shell 對 JSON quote 不友善，可以改用檔案：

```bash
ncue-course-mcp --tool ncue_search_courses --args-file examples/query-d540mn1a.json
```

---

## MCP 設定

安裝 package 後：

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

不安裝、直接從原始碼資料夾啟動：

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

範例設定放在 [`examples/`](examples/)。

---

## 工具說明

| Tool | 用途 | 常用參數 |
| --- | --- | --- |
| `ncue_list_query_options` | 列出官方查詢條件與分段載入資訊 | `refresh` |
| `ncue_list_classes` | 載入修課班別清單 | `year`, `semester`, `branch`, `keyword` |
| `ncue_search_courses` | 查詢課表並回傳結構化課程資料 | `year`, `semester`, `branch`, `class_id`, `weekday`, `course_name`, `teacher_name` |
| `ncue_analyze_first_semester_pattern` | 分析歷年同學期規律並推估目標學期 | `class_id`, `start_year`, `end_year`, `exclusion_year`, `target_year` |

### `ncue_search_courses` 範例

```json
{
  "year": 114,
  "semester": 1,
  "branch": "D",
  "class_id": "D540MN1A"
}
```

常用條件：

| 參數 | 說明 |
| --- | --- |
| `year` | 民國學年，例如 `114` |
| `semester` | `1` 第一學期、`2` 第二學期、`3` 暑修班、`4` 暑期班 |
| `branch` | `D` 日間部、`N` 碩士在職專班 |
| `class_id` | 修課班別代碼，例如 `D540MN1A` |
| `weekday` | `1` 到 `6`；空字串代表不限 |
| `course_code` | 課程代碼關鍵字 |
| `course_name` | 課程名稱關鍵字 |
| `teacher_name` | 教師姓名關鍵字 |
| `english` | `Y`、`N` 或空字串 |
| `distance` | `Y`、`N` 或空字串 |

### `ncue_analyze_first_semester_pattern` 範例

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

推估規則：

- 分析區間同一學期出現年數越多，機率越高。
- 排除學期已開過的課會降權。
- 若分析區間每年同學期都出現，即使排除學期也出現，仍視為固定或常態課。

---

## 專案結構

```text
.
├── src/ncue_course_mcp/
│   ├── client.py            # 官方頁面 client、parser、分析邏輯
│   ├── server.py            # stdio MCP server
│   └── __main__.py          # python -m ncue_course_mcp
├── scripts/
│   ├── run_mcp_server.py    # 未安裝 package 時的啟動 wrapper
│   └── analyze_d540mn1a.py  # 資工碩一歷年分析範例腳本
├── tests/                   # 無網路單元測試
├── examples/                # MCP 設定與查詢參數範例
├── pyproject.toml
└── README.md
```

---

## 開發

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

測試不依賴網路；目前主要覆蓋 HTML parser、節次解析與 MCP JSON-RPC 回應格式。

### 本機 MCP Smoke Test

```powershell
$env:PYTHONPATH='src'
python -m ncue_course_mcp --tool ncue_search_courses --args-file examples/query-d540mn1a.json
```

---

## 注意事項

- Runtime 沒有第三方依賴。
- 不需要使用者提供登入 cookie。
- `output/` 是本機抓取輸出，已在 `.gitignore` 排除。
- 如果彰師大官方頁面欄位或表格 HTML 改版，parser 可能需要更新。

---

## 授權

本專案採用 **MIT License**，詳見 [LICENSE](LICENSE)。

<div align="center">

Made for structured course queries with Python + MCP.

</div>
