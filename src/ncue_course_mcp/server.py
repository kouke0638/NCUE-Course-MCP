from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any, Callable

from .client import NCUECourseClient


SERVER_NAME = "ncue-course-query"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


client = NCUECourseClient()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def tool_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json_text(value)}],
        "isError": is_error,
    }


def ncue_list_query_options(args: dict[str, Any]) -> dict[str, Any]:
    return client.list_query_options(refresh=bool(args.get("refresh", False)))


def ncue_list_classes(args: dict[str, Any]) -> dict[str, Any]:
    year = int(args["year"])
    semester = int(args["semester"])
    branch = str(args.get("branch", "D") or "D")
    include_empty = bool(args.get("include_empty", False))
    keyword = str(args.get("keyword", "") or "").strip()
    limit = args.get("limit")
    result = client.list_classes(year=year, semester=semester, branch=branch, include_empty=include_empty)
    if keyword:
        result["classes"] = [
            item
            for item in result["classes"]
            if keyword.lower() in item["text"].lower() or keyword.lower() in item["value"].lower()
        ]
        result["count"] = len(result["classes"])
        result["filtered_by_keyword"] = keyword
    if limit is not None:
        max_items = max(0, int(limit))
        original_count = len(result["classes"])
        result["classes"] = result["classes"][:max_items]
        result["returned_count"] = len(result["classes"])
        result["truncated"] = original_count > max_items
    return result


def ncue_search_courses(args: dict[str, Any]) -> dict[str, Any]:
    result = client.search_courses(
        year=int(args["year"]),
        semester=int(args["semester"]),
        branch=str(args.get("branch", "D") or "D"),
        class_id=str(args.get("class_id", "") or ""),
        weekday=str(args.get("weekday", "") or ""),
        course_code=str(args.get("course_code", "") or ""),
        course_name=str(args.get("course_name", "") or ""),
        teacher_name=str(args.get("teacher_name", "") or ""),
        english=str(args.get("english", "") or ""),
        distance=str(args.get("distance", "") or ""),
        refresh_token=bool(args.get("refresh_token", False)),
    )
    max_results = args.get("max_results")
    if max_results is not None:
        max_items = max(0, int(max_results))
        original_count = len(result["courses"])
        result["courses"] = result["courses"][:max_items]
        result["returned_count"] = len(result["courses"])
        result["truncated"] = original_count > max_items
    return result


def ncue_analyze_first_semester_pattern(args: dict[str, Any]) -> dict[str, Any]:
    result = client.analyze_first_semester_pattern(
        class_id=str(args["class_id"]),
        branch=str(args.get("branch", "D") or "D"),
        start_year=int(args.get("start_year", 112)),
        end_year=int(args.get("end_year", 114)),
        semester=int(args.get("semester", 1)),
        exclusion_year=int(args["exclusion_year"]) if args.get("exclusion_year") is not None else None,
        exclusion_semester=int(args.get("exclusion_semester", 2)),
        target_year=int(args["target_year"]) if args.get("target_year") is not None else None,
        target_semester=int(args["target_semester"]) if args.get("target_semester") is not None else None,
    )
    max_predictions = args.get("max_predictions")
    if max_predictions is not None:
        max_items = max(0, int(max_predictions))
        original_count = len(result["predictions"])
        result["predictions"] = result["predictions"][:max_items]
        result["returned_prediction_count"] = len(result["predictions"])
        result["predictions_truncated"] = original_count > max_items
    return result


TOOLS: dict[str, dict[str, Any]] = {
    "ncue_list_query_options": {
        "description": "列出彰師大課表查詢可用條件，並標示哪個欄位需要分段載入。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "refresh": {"type": "boolean", "description": "重新讀取官方查詢頁，更新 token 與選項。"}
            },
            "additionalProperties": False,
        },
        "handler": ncue_list_query_options,
    },
    "ncue_list_classes": {
        "description": "依學年、學期、日夜間別載入可查詢的修課班別清單。這是官方頁面的分段載入選項。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "民國學年，例如 114。"},
                "semester": {"type": "integer", "enum": [1, 2, 3, 4], "description": "1=第一學期, 2=第二學期, 3=暑修班, 4=暑期班。"},
                "branch": {"type": "string", "enum": ["D", "N"], "default": "D", "description": "D=日間部, N=碩士在職專班。"},
                "keyword": {"type": "string", "description": "用班別名稱或代碼過濾，例如 資工 或 D540。"},
                "include_empty": {"type": "boolean", "default": False, "description": "是否包含官方空白選項。"},
                "limit": {"type": "integer", "description": "最多回傳幾筆班別。"},
            },
            "required": ["year", "semester"],
            "additionalProperties": False,
        },
        "handler": ncue_list_classes,
    },
    "ncue_search_courses": {
        "description": "查詢彰師大開課課表，可用學年、學期、班別、星期、課程代碼、課名、教師、全英語、遠距等條件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "民國學年，例如 114。"},
                "semester": {"type": "integer", "enum": [1, 2, 3, 4], "description": "1=第一學期, 2=第二學期, 3=暑修班, 4=暑期班。"},
                "branch": {"type": "string", "enum": ["D", "N"], "default": "D"},
                "class_id": {"type": "string", "description": "修課班別代碼，例如 D540MN1A；留空代表不限。"},
                "weekday": {"type": "string", "enum": ["", "1", "2", "3", "4", "5", "6"], "description": "上課星期，空字串代表不限。"},
                "course_code": {"type": "string", "description": "課程代碼關鍵字。"},
                "course_name": {"type": "string", "description": "課程名稱關鍵字。"},
                "teacher_name": {"type": "string", "description": "教師姓名關鍵字。"},
                "english": {"type": "string", "enum": ["", "Y", "N"], "description": "全英語授課篩選。"},
                "distance": {"type": "string", "enum": ["", "Y", "N"], "description": "遠距授課篩選。"},
                "refresh_token": {"type": "boolean", "default": False, "description": "查詢前重新取得官方表單 token。"},
                "max_results": {"type": "integer", "description": "最多回傳幾筆課程。"},
            },
            "required": ["year", "semester"],
            "additionalProperties": False,
        },
        "handler": ncue_search_courses,
    },
    "ncue_analyze_first_semester_pattern": {
        "description": "分析某班別歷年同一學期開課與星期分布，並用排除學期降權規則推估下一學期可能開課。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "class_id": {"type": "string", "description": "修課班別代碼，例如 D540MN1A。"},
                "branch": {"type": "string", "enum": ["D", "N"], "default": "D"},
                "start_year": {"type": "integer", "default": 112, "description": "分析起始民國學年。"},
                "end_year": {"type": "integer", "default": 114, "description": "分析結束民國學年。"},
                "semester": {"type": "integer", "enum": [1, 2, 3, 4], "default": 1, "description": "要分析的學期，預設第一學期。"},
                "exclusion_year": {"type": "integer", "description": "排除/降權參考學年；預設 end_year。"},
                "exclusion_semester": {"type": "integer", "enum": [1, 2, 3, 4], "default": 2, "description": "排除/降權參考學期，預設第二學期。"},
                "target_year": {"type": "integer", "description": "要順手查詢是否已正式公布的目標學年；預設 end_year+1。"},
                "target_semester": {"type": "integer", "enum": [1, 2, 3, 4], "description": "目標學期；預設同 semester。"},
                "max_predictions": {"type": "integer", "description": "最多回傳幾筆推估課程。"},
            },
            "required": ["class_id"],
            "additionalProperties": False,
        },
        "handler": ncue_analyze_first_semester_pattern,
    },
}


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": spec["description"],
            "inputSchema": spec["inputSchema"],
        }
        for name, spec in TOOLS.items()
    ]


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    is_notification = "id" not in message

    try:
        if method == "initialize":
            params = message.get("params") or {}
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }
        if method in {"notifications/initialized", "initialized"}:
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": list_tools()}}
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name not in TOOLS:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": tool_result({"error": f"Unknown tool: {name}"}, is_error=True),
                }
            handler: Callable[[dict[str, Any]], dict[str, Any]] = TOOLS[name]["handler"]
            return {"jsonrpc": "2.0", "id": request_id, "result": tool_result(handler(args))}
        if method == "shutdown":
            return {"jsonrpc": "2.0", "id": request_id, "result": None}
        if is_notification:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    except Exception as exc:
        if method == "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": tool_result(
                    {
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                    is_error=True,
                ),
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": str(exc), "data": traceback.format_exc()},
        }


def read_message() -> dict[str, Any] | None:
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None
    while first_line in {b"\r\n", b"\n"}:
        first_line = sys.stdin.buffer.readline()
        if not first_line:
            return None

    if first_line.lower().startswith(b"content-length:"):
        headers = [first_line]
        while True:
            line = sys.stdin.buffer.readline()
            if not line or line in {b"\r\n", b"\n"}:
                break
            headers.append(line)
        length = None
        for header in headers:
            name, _, value = header.decode("ascii", errors="ignore").partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
                break
        if length is None:
            raise RuntimeError("Missing Content-Length header.")
        payload = sys.stdin.buffer.read(length)
        return json.loads(payload.decode("utf-8"))

    return json.loads(first_line.decode("utf-8"))


def write_message(message: dict[str, Any]) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def serve_stdio() -> None:
    while True:
        message = read_message()
        if message is None:
            return
        response = handle_request(message)
        if response is not None:
            write_message(response)


def run_direct_tool(tool_name: str, args_json: str) -> None:
    if tool_name not in TOOLS:
        raise SystemExit(f"Unknown tool: {tool_name}")
    args = json.loads(args_json) if args_json else {}
    handler: Callable[[dict[str, Any]], dict[str, Any]] = TOOLS[tool_name]["handler"]
    print(json_text(handler(args)))


def main() -> None:
    parser = argparse.ArgumentParser(description="NCUE course query MCP server")
    parser.add_argument("--tool", help="Run a tool directly instead of starting MCP stdio.")
    parser.add_argument("--args", default="{}", help="JSON arguments for --tool.")
    parser.add_argument("--args-file", help="Read JSON arguments for --tool from a file.")
    parsed = parser.parse_args()
    if parsed.tool:
        args_json = parsed.args
        if parsed.args_file:
            with open(parsed.args_file, "r", encoding="utf-8") as file:
                args_json = file.read()
        run_direct_tool(parsed.tool, args_json)
        return
    serve_stdio()


if __name__ == "__main__":
    main()
