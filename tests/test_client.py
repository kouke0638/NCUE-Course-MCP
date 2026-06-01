import unittest

from ncue_course_mcp.client import parse_course_rows, parse_meetings


class ClientParsingTest(unittest.TestCase):
    def test_parse_meetings_splits_multiple_slots(self) -> None:
        meetings = parse_meetings("(三) 09 資工研討室(一) (四) 09 資工研討室(一)")

        self.assertEqual(
            meetings,
            [
                {
                    "weekday": "星期三",
                    "weekday_short": "三",
                    "periods": "09",
                    "period_count": 1,
                    "place": "資工研討室(一)",
                },
                {
                    "weekday": "星期四",
                    "weekday_short": "四",
                    "periods": "09",
                    "period_count": 1,
                    "place": "資工研討室(一)",
                },
            ],
        )

    def test_parse_course_rows_extracts_course_table(self) -> None:
        html = """
        <table id="table1">
          <thead>
            <tr>
              <th>序號</th><th>課程代碼</th><th>開課班別(代表)</th><th>課程名稱</th>
              <th>教學大綱</th><th>課程性質</th><th>課程性質2</th><th>全英語</th>
              <th>學分</th><th>教師姓名</th><th>上課大樓</th><th>上課節次+地點</th>
              <th>上限</th><th>登記</th><th>選上</th><th>可跨班</th><th>備註</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td>54046</td>
              <td>資工碩一</td>
              <td><strong>數位積體電路設計</strong><br><small>Digital Integrated Circuit Design</small></td>
              <td>中文下載<br>No file</td>
              <td>系選修</td>
              <td></td>
              <td>否</td>
              <td>3</td>
              <td>易昶霈</td>
              <td>工學院</td>
              <td>(四) 05-07 資工電腦教室(二)</td>
              <td>20</td>
              <td>17</td>
              <td>9</td>
              <td>限本系</td>
              <td></td>
            </tr>
          </tbody>
        </table>
        """

        rows = parse_course_rows(114, 1, html)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].code, "54046")
        self.assertEqual(rows[0].name_zh, "數位積體電路設計")
        self.assertEqual(rows[0].name_en, "Digital Integrated Circuit Design")
        self.assertEqual(rows[0].meetings[0]["weekday"], "星期四")
        self.assertEqual(rows[0].meetings[0]["period_count"], 3)


if __name__ == "__main__":
    unittest.main()
