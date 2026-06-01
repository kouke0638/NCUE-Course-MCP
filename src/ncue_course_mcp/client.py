from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from typing import Any


BASE_URL = "https://webapt.ncue.edu.tw"
PAGE_URL = f"{BASE_URL}/deanv2/other/ob010"
POST_URL = f"{BASE_URL}/DEANV2/Other/OB010"
CLASS_OPTIONS_URL = f"{BASE_URL}/DEANV2/Other/OB010/GetJson_ddl_scj_cls_id"

BRANCHES = {"D": "日間部(教務處)", "N": "碩士在職專班(進修學院)"}
SEMESTERS = {
    "1": "第一學期",
    "2": "第二學期",
    "3": "暑修班(教務處、進修學院)",
    "4": "暑期班(進修學院)",
}
YES_NO = {"": "不限", "Y": "是", "N": "否"}
WEEKDAYS = {
    "": "不限",
    "1": "星期一",
    "2": "星期二",
    "3": "星期三",
    "4": "星期四",
    "5": "星期五",
    "6": "星期六",
}
WEEKDAY_NAMES = {
    "一": "星期一",
    "二": "星期二",
    "三": "星期三",
    "四": "星期四",
    "五": "星期五",
    "六": "星期六",
    "日": "星期日",
}


@dataclass
class CourseRow:
    year: int
    semester: int
    code: str
    class_name: str
    name_zh: str
    name_en: str
    syllabus: str
    category: str
    category2: str
    english: str
    credits: str
    teachers: str
    building: str
    time_place: str
    limit: str
    registered: str
    enrolled: str
    cross_class: str
    remark: str
    meetings: list[dict[str, Any]]


@dataclass
class PageState:
    token: str
    html: str
    fetched_at: str


class SelectParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.selects: dict[str, dict[str, Any]] = {}
        self._select_key: str | None = None
        self._current_option: dict[str, Any] | None = None
        self._option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "select":
            key = attrs_dict.get("id") or attrs_dict.get("name")
            if key:
                self._select_key = key
                self.selects[key] = {
                    "id": attrs_dict.get("id"),
                    "name": attrs_dict.get("name"),
                    "options": [],
                }
            return
        if tag == "option" and self._select_key:
            self._current_option = {
                "value": attrs_dict.get("value", ""),
                "selected": "selected" in attrs_dict,
                "disabled": "disabled" in attrs_dict,
            }
            self._option_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._select_key and self._current_option is not None:
            self._current_option["text"] = clean_text("".join(self._option_text))
            self.selects[self._select_key]["options"].append(self._current_option)
            self._current_option = None
            self._option_text = []
        elif tag == "select":
            self._select_key = None

    def handle_data(self, data: str) -> None:
        if self._current_option is not None:
            self._option_text.append(data)


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.table_depth = 0
        self.in_tr = False
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("id") == "table1":
            self.in_table = True
            self.table_depth = 1
            return
        if self.in_table and tag == "table":
            self.table_depth += 1
        if self.in_table and tag == "tr":
            self.in_tr = True
            self.current_row = []
        if self.in_tr and tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []
        if self.in_cell and tag == "br":
            self.current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"td", "th"}:
            self.current_row.append(clean_text("".join(self.current_cell)))
            self.current_cell = []
            self.in_cell = False
        elif self.in_table and tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_tr = False
        elif self.in_table and tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def split_course_name(value: str) -> tuple[str, str]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return "", ""
    return lines[0], " ".join(lines[1:])


def count_periods(periods: str) -> int:
    if "-" not in periods:
        return 1
    start, end = periods.split("-", 1)
    if start.isdigit() and end.isdigit():
        return max(1, int(end) - int(start) + 1)
    return 1


def parse_meetings(time_place: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"\((?P<weekday>[一二三四五六日])\)\s*"
        r"(?P<periods>[0-9A-Z]{1,2}(?:-[0-9A-Z]{1,2})?)"
        r"\s*(?P<place>.*?)(?=\([一二三四五六日]\)\s*[0-9A-Z]{1,2}|$)"
    )
    meetings: list[dict[str, Any]] = []
    for match in pattern.finditer(time_place):
        weekday_short = match.group("weekday")
        periods = match.group("periods")
        meetings.append(
            {
                "weekday": WEEKDAY_NAMES.get(weekday_short, weekday_short),
                "weekday_short": weekday_short,
                "periods": periods,
                "period_count": count_periods(periods),
                "place": clean_text(match.group("place")),
            }
        )
    return meetings


def format_counter(counter: Counter[str]) -> str:
    order = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return "、".join(f"{day} {counter[day]}" for day in order if counter[day])


def likelihood(first_years: set[int], appeared_in_exclusion: bool, recent_year: int) -> str:
    count = len(first_years)
    if count >= 3:
        return "高"
    if appeared_in_exclusion:
        return "低"
    if count == 2:
        return "中高"
    if recent_year in first_years:
        return "中"
    return "低"


def course_row_to_dict(row: CourseRow) -> dict[str, Any]:
    return asdict(row)


class NCUECourseClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.page_state: PageState | None = None

    def _request(
        self,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        method: str | None = None,
    ) -> str:
        request_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "zh-TW,zh;q=0.9",
        }
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        with self.opener.open(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def get_page_state(self, refresh: bool = False) -> PageState:
        if self.page_state is not None and not refresh:
            return self.page_state
        content = self._request(PAGE_URL)
        match = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', content)
        if not match:
            raise RuntimeError("Cannot find __RequestVerificationToken in NCUE query page.")
        self.page_state = PageState(
            token=match.group(1),
            html=content,
            fetched_at=datetime.now().isoformat(timespec="seconds"),
        )
        return self.page_state

    def list_query_options(self, refresh: bool = False) -> dict[str, Any]:
        page = self.get_page_state(refresh=refresh)
        parser = SelectParser()
        parser.feed(page.html)

        def options_for(select_id: str, fallback: dict[str, str] | None = None) -> list[dict[str, Any]]:
            select = parser.selects.get(select_id)
            if select:
                return select["options"]
            return [{"value": value, "text": text, "selected": False, "disabled": False} for value, text in (fallback or {}).items()]

        return {
            "source_url": PAGE_URL,
            "fetched_at": page.fetched_at,
            "staged_loading": [
                {
                    "field": "sel_cls_id",
                    "label": "修課班別",
                    "endpoint": CLASS_OPTIONS_URL,
                    "depends_on": ["sel_yms_year", "sel_yms_smester", "sel_cls_branch"],
                    "client_tool": "ncue_list_classes",
                }
            ],
            "fields": [
                {
                    "name": "sel_cls_branch",
                    "label": "日夜間別",
                    "type": "select",
                    "options": options_for("ddl_cls_branch", BRANCHES),
                },
                {
                    "name": "sel_yms_year",
                    "label": "學年",
                    "type": "select",
                    "options": options_for("ddl_yms_year"),
                },
                {
                    "name": "sel_yms_smester",
                    "label": "學期",
                    "type": "select",
                    "options": options_for("ddl_yms_smester", SEMESTERS),
                },
                {
                    "name": "sel_cls_id",
                    "label": "修課班別",
                    "type": "staged_select",
                    "options": "call ncue_list_classes(year, semester, branch)",
                },
                {
                    "name": "sel_sct_week",
                    "label": "上課時間/星期",
                    "type": "select",
                    "options": options_for("sel_sct_week", WEEKDAYS),
                },
                {
                    "name": "sel_scr_english",
                    "label": "全英語授課",
                    "type": "select",
                    "options": options_for("sel_scr_english", YES_NO),
                },
                {
                    "name": "sel_SCR_IS_DIS_LEARN",
                    "label": "遠距",
                    "type": "select",
                    "options": options_for("sel_SCR_IS_DIS_LEARN", YES_NO),
                },
                {"name": "scr_selcode", "label": "課程代碼", "type": "text"},
                {"name": "sub_name", "label": "課程名稱關鍵字", "type": "text"},
                {"name": "emp_name", "label": "老師姓名關鍵字", "type": "text"},
            ],
        }

    def list_classes(self, year: int, semester: int, branch: str = "D", include_empty: bool = False) -> dict[str, Any]:
        query = urllib.parse.urlencode({"year": str(year), "smester": str(semester), "CLS_BRANCH": branch})
        content = self._request(f"{CLASS_OPTIONS_URL}?{query}", headers={"Accept": "application/json, text/javascript, */*; q=0.01"})
        data = json.loads(content)
        classes = [
            {
                "value": item.get("Value", ""),
                "text": item.get("Text", ""),
                "selected": bool(item.get("Selected")),
                "disabled": bool(item.get("Disabled")),
            }
            for item in data
            if include_empty or item.get("Value")
        ]
        return {
            "source_url": CLASS_OPTIONS_URL,
            "year": year,
            "semester": semester,
            "branch": branch,
            "count": len(classes),
            "classes": classes,
        }

    def search_courses(
        self,
        *,
        year: int,
        semester: int,
        branch: str = "D",
        class_id: str = "",
        weekday: str = "",
        course_code: str = "",
        course_name: str = "",
        teacher_name: str = "",
        english: str = "",
        distance: str = "",
        refresh_token: bool = False,
    ) -> dict[str, Any]:
        page = self.get_page_state(refresh=refresh_token)
        payload = {
            "__RequestVerificationToken": page.token,
            "sel_cls_branch": branch,
            "sel_scr_english": english,
            "sel_SCR_IS_DIS_LEARN": distance,
            "sel_yms_year": str(year),
            "sel_yms_smester": str(semester),
            "scr_selcode": course_code,
            "sel_cls_id": class_id,
            "sel_sct_week": weekday,
            "sub_name": course_name,
            "emp_name": teacher_name,
            "CatchBot": "",
            "X-Requested-With": "XMLHttpRequest",
        }
        body = urllib.parse.urlencode(payload).encode("utf-8")
        content = self._request(
            POST_URL,
            data=body,
            method="POST",
            headers={
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": BASE_URL,
                "Referer": PAGE_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        courses = [course_row_to_dict(row) for row in parse_course_rows(year, semester, content)]
        return {
            "source_url": PAGE_URL,
            "query": {
                "year": year,
                "semester": semester,
                "branch": branch,
                "class_id": class_id,
                "weekday": weekday,
                "course_code": course_code,
                "course_name": course_name,
                "teacher_name": teacher_name,
                "english": english,
                "distance": distance,
            },
            "count": len(courses),
            "courses": courses,
        }

    def analyze_first_semester_pattern(
        self,
        *,
        class_id: str,
        branch: str = "D",
        start_year: int = 112,
        end_year: int = 114,
        semester: int = 1,
        exclusion_year: int | None = None,
        exclusion_semester: int = 2,
        target_year: int | None = None,
        target_semester: int | None = None,
    ) -> dict[str, Any]:
        if end_year < start_year:
            raise ValueError("end_year must be greater than or equal to start_year.")
        exclusion_year = exclusion_year if exclusion_year is not None else end_year
        target_year = target_year if target_year is not None else end_year + 1
        target_semester = target_semester if target_semester is not None else semester

        term_results: list[dict[str, Any]] = []
        all_rows: list[CourseRow] = []
        for year in range(start_year, end_year + 1):
            result = self.search_courses(year=year, semester=semester, branch=branch, class_id=class_id)
            term_results.append({"year": year, "semester": semester, "count": result["count"]})
            all_rows.extend(dict_to_course_row(row) for row in result["courses"])

        exclusion = self.search_courses(year=exclusion_year, semester=exclusion_semester, branch=branch, class_id=class_id)
        exclusion_names = {row["name_zh"] for row in exclusion["courses"]}
        current_target = self.search_courses(year=target_year, semester=target_semester, branch=branch, class_id=class_id)

        overall_weekday_periods: Counter[str] = Counter()
        by_course: dict[str, list[CourseRow]] = defaultdict(list)
        for row in all_rows:
            by_course[row.name_zh].append(row)
            for meeting in row.meetings:
                overall_weekday_periods[meeting["weekday"]] += int(meeting["period_count"])

        courses: list[dict[str, Any]] = []
        for name, rows in by_course.items():
            years = sorted({row.year for row in rows})
            teachers = sorted({teacher for row in rows for teacher in row.teachers.split("、") if teacher})
            weekday_periods: Counter[str] = Counter()
            slots: Counter[str] = Counter()
            observations = []
            for row in rows:
                observations.append(
                    {
                        "year": row.year,
                        "semester": row.semester,
                        "code": row.code,
                        "teachers": row.teachers,
                        "time_place": row.time_place,
                    }
                )
                for meeting in row.meetings:
                    weekday_periods[meeting["weekday"]] += int(meeting["period_count"])
                    slots[f"{meeting['weekday']} {meeting['periods']}"] += 1
            primary_weekday = weekday_periods.most_common(1)[0][0] if weekday_periods else ""
            appeared_in_exclusion = name in exclusion_names
            tier = likelihood(set(years), appeared_in_exclusion, end_year)
            courses.append(
                {
                    "name": name,
                    "years": years,
                    "teachers": teachers,
                    "primary_weekday": primary_weekday,
                    "weekday_period_distribution": dict(weekday_periods),
                    "weekday_period_distribution_text": format_counter(weekday_periods),
                    "common_slots": [{"slot": slot, "count": count} for slot, count in slots.most_common(5)],
                    "appeared_in_exclusion_term": appeared_in_exclusion,
                    "likelihood": tier,
                    "observations": observations,
                }
            )

        tier_order = {"高": 0, "中高": 1, "中": 2, "低": 3}
        courses.sort(key=lambda item: (tier_order[item["likelihood"]], -len(item["years"]), item["name"]))
        return {
            "source_url": PAGE_URL,
            "class_id": class_id,
            "branch": branch,
            "analyzed_terms": term_results,
            "exclusion_term": {"year": exclusion_year, "semester": exclusion_semester, "count": exclusion["count"]},
            "target_term": {"year": target_year, "semester": target_semester, "official_count": current_target["count"]},
            "overall_weekday_period_distribution": dict(overall_weekday_periods),
            "overall_weekday_period_distribution_text": format_counter(overall_weekday_periods),
            "prediction_rule": "出現年數越多機率越高；排除學期已開過者降權，但若分析區間每年同學期都開，仍視為固定/常態課。",
            "predictions": courses,
            "official_target_courses": current_target["courses"],
        }


def parse_course_rows(year: int, semester: int, content: str) -> list[CourseRow]:
    parser = TableParser()
    parser.feed(content)
    result: list[CourseRow] = []
    for row in parser.rows:
        if len(row) < 17 or row[0] == "序號":
            continue
        name_zh, name_en = split_course_name(row[3])
        time_place = row[11]
        result.append(
            CourseRow(
                year=year,
                semester=semester,
                code=row[1],
                class_name=row[2],
                name_zh=name_zh,
                name_en=name_en,
                syllabus=row[4],
                category=row[5],
                category2=row[6],
                english=row[7],
                credits=row[8],
                teachers=row[9].replace("\n", "、"),
                building=row[10],
                time_place=time_place,
                limit=row[12],
                registered=row[13],
                enrolled=row[14],
                cross_class=row[15],
                remark=row[16],
                meetings=parse_meetings(time_place),
            )
        )
    return result


def dict_to_course_row(data: dict[str, Any]) -> CourseRow:
    return CourseRow(
        year=int(data["year"]),
        semester=int(data["semester"]),
        code=str(data["code"]),
        class_name=str(data["class_name"]),
        name_zh=str(data["name_zh"]),
        name_en=str(data["name_en"]),
        syllabus=str(data["syllabus"]),
        category=str(data["category"]),
        category2=str(data["category2"]),
        english=str(data["english"]),
        credits=str(data["credits"]),
        teachers=str(data["teachers"]),
        building=str(data["building"]),
        time_place=str(data["time_place"]),
        limit=str(data["limit"]),
        registered=str(data["registered"]),
        enrolled=str(data["enrolled"]),
        cross_class=str(data["cross_class"]),
        remark=str(data["remark"]),
        meetings=list(data["meetings"]),
    )
