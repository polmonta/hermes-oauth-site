"""Integration regression for a loopback, public-files-only preview."""

import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent


class PreviewTests(unittest.TestCase):
    def test_preview_serves_only_allowlisted_files_on_loopback(self):
        script = ROOT / "scripts" / "preview_site.py"
        self.assertTrue(script.is_file(), "the public-files-only preview helper is missing")
        spec = importlib.util.spec_from_file_location("preview_site", script)
        assert spec is not None and spec.loader is not None
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)

        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as scratch:
            root = Path(scratch)
            public = {
                "/": "index.html",
                "/index.html": "index.html",
                "/privacy.html": "privacy.html",
                "/terms.html": "terms.html",
                "/styles.css": "styles.css",
            }
            for filename in set(public.values()):
                (root / filename).write_text("public:" + filename, encoding="utf-8")
            (root / ".local").mkdir()
            (root / ".local" / "STATUS.md").write_text("PRIVATE", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("PRIVATE", encoding="utf-8")
            (root / "README.md").write_text("not a public page", encoding="utf-8")
            server = preview.make_server(root=root, port=0)
            self.assertEqual(server.server_address[0], "127.0.0.1")
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
            )
            thread.start()
            base = "http://127.0.0.1:" + str(server.server_port)
            try:
                for path, filename in public.items():
                    with self.subTest(public_path=path):
                        with urlopen(base + path, timeout=3) as response:
                            self.assertEqual(response.status, 200)
                            self.assertEqual(response.read(), ("public:" + filename).encode())
                for path in (
                    "/.local/STATUS.md", "/.git/config", "/README.md", "/scripts/",
                    "/tests/", "/../.local/STATUS.md", "/%2e%2e/.local/STATUS.md",
                    "/%2elocal/STATUS.md", "/unknown.html",
                ):
                    with self.subTest(private_path=path):
                        with self.assertRaises(HTTPError) as error:
                            urlopen(base + path, timeout=3)
                        self.assertEqual(error.exception.code, 404)
                        self.assertNotIn(b"PRIVATE", error.exception.read())
                        error.exception.close()
                (root / "styles.css").unlink()
                (root / "styles.css").symlink_to(root / ".local" / "STATUS.md")
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/styles.css", timeout=3)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            self.assertFalse(thread.is_alive(), "preview test listener did not stop")

    def test_readme_recommends_the_restricted_preview(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("python3 -m http.server", readme)
        self.assertIn("python3 scripts/preview_site.py", readme)
        self.assertIn("127.0.0.1", readme)
        self.assertIn("keyword", readme.casefold())
        self.assertIn("python3 -m unittest discover -s tests -v", readme)


if __name__ == "__main__":
    unittest.main()
