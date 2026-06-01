from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ncue_course_mcp.client import NCUECourseClient  # noqa: E402


CLASS_ID = "D540MN1A"
CLASS_NAME = "資工碩一"
TERMS = [(112, 1), (113, 1), (114, 1), (114, 2), (115, 1)]
CSV_FIELDS = [
    "year",
    "semester",
    "code",
    "class_name",
    "name_zh",
    "name_en",
    "category",
    "category2",
    "english",
    "credits",
    "teachers",
    "building",
    "time_place",
    "limit",
    "registered",
    "enrolled",
    "cross_class",
    "remark",
    "meetings_json",
]


def write_csv(path: Path, courses: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for course in courses:
            row = {field: course.get(field, "") for field in CSV_FIELDS}
            row["meetings_json"] = json.dumps(course.get("meetings", []), ensure_ascii=False)
            writer.writerow(row)


def write_report(path: Path, analysis: dict[str, object], counts: dict[str, int]) -> None:
    lines = [
        "# 彰師大資工碩一課表分析",
        "",
        f"- 抓取時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 資料來源：{analysis['source_url']}",
        f"- 查詢班別：{CLASS_ID}（{CLASS_NAME}）",
        f"- 各學期筆數：{', '.join(f'{term}: {count}' for term, count in counts.items())}",
        "",
        "## 112-114 第一學期整體星期分布（以節數計）",
        "",
        str(analysis["overall_weekday_period_distribution_text"]),
        "",
        "## 115 第一學期可能開課推估",
        "",
        str(analysis["prediction_rule"]),
        "",
        "| 推估 | 課程 | 依據 | 主要星期 | 常見節次 | 114 第二學期已開 |",
        "|---|---|---|---|---|---|",
    ]

    for item in analysis["predictions"]:
        prediction = item if isinstance(item, dict) else {}
        common_slots = "、".join(
            f"{slot['slot']} x{slot['count']}"
            for slot in prediction.get("common_slots", [])[:2]
            if isinstance(slot, dict)
        )
        years = "、".join(str(year) for year in prediction.get("years", []))
        lines.append(
            "| {likelihood} | {name} | {years} | {weekday} | {slots} | {excluded} |".format(
                likelihood=prediction.get("likelihood", ""),
                name=prediction.get("name", ""),
                years=years,
                weekday=prediction.get("primary_weekday", ""),
                slots=common_slots,
                excluded="是" if prediction.get("appeared_in_exclusion_term") else "否",
            )
        )

    target = analysis["target_term"]
    official_count = target["official_count"] if isinstance(target, dict) else 0
    lines.extend(["", "## 115 第一學期系統目前查詢結果", ""])
    if official_count:
        lines.append(f"系統目前已有 {official_count} 筆 115 第一學期資料。")
    else:
        lines.append("系統目前查不到 115 第一學期此班別課程資料。")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    client = NCUECourseClient()
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    all_courses: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    for year, semester in TERMS:
        result = client.search_courses(year=year, semester=semester, branch="D", class_id=CLASS_ID)
        courses = result["courses"]
        all_courses.extend(courses)
        counts[f"{year}-{semester}"] = int(result["count"])

    analysis = client.analyze_first_semester_pattern(
        class_id=CLASS_ID,
        branch="D",
        start_year=112,
        end_year=114,
        semester=1,
        exclusion_year=114,
        exclusion_semester=2,
        target_year=115,
        target_semester=1,
    )

    csv_path = out_dir / "ncue_d540mn1a_courses.csv"
    report_path = out_dir / "ncue_d540mn1a_analysis.md"
    write_csv(csv_path, all_courses)
    write_report(report_path, analysis, counts)

    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print(f"Wrote {csv_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
