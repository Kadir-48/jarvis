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

if __name__ == "__main__":
    unittest.main()
