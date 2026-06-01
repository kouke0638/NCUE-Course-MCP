import json
import unittest

from ncue_course_mcp.server import handle_request, list_tools, tool_result


class ServerProtocolTest(unittest.TestCase):
    def test_tools_list_contains_expected_tools(self) -> None:
        names = {tool["name"] for tool in list_tools()}

        self.assertEqual(
            names,
            {
                "ncue_list_query_options",
                "ncue_list_classes",
                "ncue_search_courses",
                "ncue_analyze_first_semester_pattern",
            },
        )

    def test_initialize_response(self) -> None:
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        )

        self.assertIsNotNone(response)
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["serverInfo"]["name"], "ncue-course-query")

    def test_tool_result_is_mcp_content_text(self) -> None:
        response = tool_result({"ok": True})

        self.assertFalse(response["isError"])
        self.assertEqual(response["content"][0]["type"], "text")
        self.assertEqual(json.loads(response["content"][0]["text"]), {"ok": True})

    def test_unknown_method_returns_json_rpc_error(self) -> None:
        response = handle_request({"jsonrpc": "2.0", "id": 9, "method": "unknown/method"})

        self.assertIsNotNone(response)
        self.assertEqual(response["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
