import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("mcp_server.py")
spec = importlib.util.spec_from_file_location("laika_mcp_server", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

class SafetyTests(unittest.TestCase):
    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            module.safe_path("Documents", "../../etc/passwd")
    def test_unknown_root_is_rejected(self):
        with self.assertRaises(ValueError):
            module.safe_path("Root", ".")
    def test_sensitive_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            module.safe_path("Documents", ".ssh/id_rsa")
    def test_tool_catalogue_has_no_shell_or_delete(self):
        names = {tool["name"] for tool in module.TOOLS}
        self.assertNotIn("run_command", names)
        self.assertNotIn("delete_file", names)
        self.assertNotIn("write_file", names)
    def test_open_file_blocks_scripts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "unsafe.sh"
            script.write_text("echo unsafe")
            previous = module.ROOTS["Documents"]
            module.ROOTS["Documents"] = root
            try:
                with self.assertRaises(ValueError):
                    module.open_file("Documents", "unsafe.sh")
            finally:
                module.ROOTS["Documents"] = previous

    def test_system_status_has_expected_fields(self):
        result = module.system_status()
        self.assertIn("architecture", result)
        self.assertIn("home_disk_gb", result)


class HTTPProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, payload=None, headers=None):
        from http.client import HTTPConnection
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = None if payload is None else __import__("json").dumps(payload)
        request_headers = {"Host": f"127.0.0.1:{self.port}"}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        connection.request("GET" if payload is None else "POST", path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.read()
        status = response.status
        connection.close()
        return status, result

    def test_health_endpoint(self):
        status, body = self.request("/health")
        self.assertEqual(status, 200)
        self.assertIn(b'"status": "ok"', body)

    def test_initialize_handshake(self):
        status, body = self.request("/mcp", {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}
        })
        self.assertEqual(status, 200)
        payload = __import__("json").loads(body)
        self.assertEqual(payload["id"], 1)
        self.assertIn("tools", payload["result"]["capabilities"])

    def test_rejects_untrusted_host_header(self):
        status, _ = self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                 {"Host": "attacker.example"})
        self.assertEqual(status, 403)

    def test_rejects_non_loopback_origin(self):
        status, _ = self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                 {"Origin": "https://attacker.example"})
        self.assertEqual(status, 403)

    def test_tools_list(self):
        status, body = self.request("/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(status, 200)
        names = {item["name"] for item in __import__("json").loads(body)["result"]["tools"]}
        self.assertIn("get_system_status", names)
        self.assertNotIn("run_command", names)


class ConfigurationTests(unittest.TestCase):
    def test_example_config_is_valid_and_uses_only_local_services(self):
        import tomllib
        config_path = Path(__file__).with_name("fono-config.toml.example")
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["assistant"]["backend"], "network")
        self.assertEqual(config["assistant"]["network"]["url"], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(config["assistant"]["network"]["model"], "qwen2.5:1.5b")
        self.assertEqual(config["stt"]["backend"], "local")
        self.assertEqual(config["stt"]["local"]["model"], "base")
        self.assertEqual(config["tts"]["backend"], "local")
        self.assertEqual(config["tts"]["local"]["engine"], "supertonic")
        self.assertTrue(config["wakeword"]["enabled"])
        self.assertEqual(config["wakeword"]["phrases"][0]["target"], "assistant")
        self.assertEqual(config["assistant"]["tools"]["mcp"][0]["url"], "http://127.0.0.1:8765/mcp")

if __name__ == "__main__":
    unittest.main()
