"""Regression checks for the static checker; site sources stay unchanged."""

import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from scripts import check_site


class CheckerTests(unittest.TestCase):
    def run_check(self, transform=None, *, css_transform=None, tracked_paths=None):
        original_read = check_site.read_text
        original_git = check_site.run_git

        def read_text(relative):
            source = original_read(relative)
            if transform and relative == "index.html":
                return transform(source)
            if css_transform and relative == "styles.css":
                return css_transform(source)
            return source

        def run_git(*args):
            if tracked_paths is not None and args == ("ls-files", "-z"):
                return subprocess.CompletedProcess(
                    ["git", *args], 0, "\0".join(tracked_paths) + "\0", ""
                )
            return original_git(*args)

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(check_site, "read_text", side_effect=read_text), patch.object(
            check_site, "run_git", side_effect=run_git
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = check_site.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_ordinary_site_passes(self):
        result, stdout, stderr = self.run_check()
        self.assertEqual(result, 0, stderr)
        self.assertIn("PASS:", stdout)
        self.assertEqual(stderr, "")

    def test_output_limits_assurance_to_keyword_and_structure_checks(self):
        result, stdout, stderr = self.run_check()
        self.assertEqual(result, 0, stderr)
        self.assertIn("keyword/structure checks only", stdout)
        self.assertIn("not runtime behavior or policy correctness", stdout)
        self.assertIn("not publication approval", stdout)

    def test_duplicate_attributes_are_rejected(self):
        for element in (
            '<a href="javascript:alert(1)" href="privacy.html">probe</a>',
            '<a href="privacy.html" HREF="javascript:alert(1)">probe</a>',
            '<p id="first" id="second">probe</p>',
            '<p class="first" CLASS="second">probe</p>',
            '<meta name="first" name="second" />',
        ):
            with self.subTest(element=element):
                result, _, stderr = self.run_check(
                    lambda source: source.replace("</main>", element + "</main>", 1)
                )
                self.assertEqual(result, 1, "duplicate attributes bypassed the checker")
                self.assertIn("duplicate attribute", stderr)

    def test_unneeded_elements_are_rejected(self):
        for element in (
            '<iframe srcdoc="&lt;img src=x onerror=alert(1)&gt;"></iframe>',
            '<object data="https://example.invalid/probe.html"></object>',
            '<embed src="https://example.invalid/probe.html">',
            '<style>body { background: url(https://example.invalid/probe.png) }</style>',
            '<style>body { color: red }</style>',
            '<script src="styles.css"></script>',
            '<form action="https://example.invalid/"></form>',
            '<base href="https://example.invalid/">',
            '<img src="styles.css">',
            '<source src="styles.css" />',
            '<video poster="https://example.invalid/probe.png"></video>',
            '<audio src="https://example.invalid/probe.mp3"></audio>',
            '<svg><image href="https://example.invalid/probe.png" /></svg>',
            '<math></math>',
            '<template><p>probe</p></template>',
        ):
            with self.subTest(element=element):
                result, _, stderr = self.run_check(
                    lambda source: source.replace("</main>", element + "</main>", 1)
                )
                self.assertEqual(result, 1, "unneeded element bypassed the checker")
                self.assertIn("element is not allowed", stderr)

    def test_unneeded_attributes_are_rejected(self):
        for element in (
            '<p style="background-image: url(https://example.invalid/probe.png)">probe</p>',
            '<p STYLE="color: red">probe</p>',
            '<p style>probe</p>',
            '<a href="privacy.html" style="">probe</a>',
            '<a href="privacy.html" ping="https://example.invalid/">probe</a>',
            '<a href="privacy.html" attributionsrc="https://example.invalid/">probe</a>',
            '<body background="https://example.invalid/probe.png">',
            '<p src="https://example.invalid/probe.png">probe</p>',
            '<meta http-equiv="refresh" content="0;url=https://example.invalid/">',
            '<link rel="stylesheet" href="styles.css" imagesrcset="https://example.invalid/probe.png">',
        ):
            with self.subTest(element=element):
                result, _, stderr = self.run_check(
                    lambda source: source.replace("</main>", element + "</main>", 1)
                )
                self.assertEqual(result, 1, "unneeded attribute bypassed the checker")
                self.assertIn("attribute is not allowed", stderr)

    def test_only_site_stylesheet_link_is_allowed(self):
        for element in (
            '<link rel="preconnect" href="https://example.invalid/">',
            '<link rel="dns-prefetch" href="//example.invalid/">',
            '<link rel="preload" href="https://example.invalid/probe.png">',
            '<link rel="modulepreload" href="https://example.invalid/probe.js">',
            '<link rel="prefetch" href="https://example.invalid/probe.html">',
            '<link rel="stylesheet prefetch" href="styles.css">',
            '<link rel="stylesheet" href="README.md">',
            '<link rel="stylesheet" href="https://example.invalid/probe.css">',
        ):
            with self.subTest(element=element):
                result, _, stderr = self.run_check(
                    lambda source: source.replace("</head>", element + "</head>", 1)
                )
                self.assertEqual(result, 1, "unneeded link resource bypassed the checker")
                self.assertIn("only the site stylesheet link is allowed", stderr)

    def test_stylesheet_resource_and_obfuscation_syntax_is_rejected(self):
        for rule in (
            'body { background: url(https://example.invalid/probe.png) }',
            r'body { background: url(\68 ttps://example.invalid/probe.png) }',
            r'body { background: u\72l(https://example.invalid/probe.png) }',
            r'body { background: \000075rl(//example.invalid/probe.png) }',
            'body { background: url(/**/https://example.invalid/probe.png) }',
            'body { background: url/**/(https://example.invalid/probe.png) }',
            '@import "https://example.invalid/probe.css";',
            r'@im\70ort "https://example.invalid/probe.css";',
            r'@\69mport "//example.invalid/probe.css";',
            '@import/**/"https://example.invalid/probe.css";',
            'body { background: image-set("https://example.invalid/probe.png" 1x) }',
            'body { background: -webkit-image-set("https://example.invalid/probe.png" 1x) }',
            'body { background: image("https://example.invalid/probe.png") }',
            'body { background: url(styles.css) }',
            '@import "styles.css";',
            r'body { color: r\65 d }',
            '/* Even harmless comments are outside this site stylesheet policy. */',
        ):
            with self.subTest(rule=rule):
                result, _, stderr = self.run_check(
                    css_transform=lambda source: source + "\n" + rule
                )
                self.assertEqual(result, 1, "stylesheet resource syntax bypassed the checker")
                self.assertIn("stylesheet resource-loading syntax", stderr)

    def test_unexpected_tracked_paths_are_rejected(self):
        tracked = check_site.run_git("ls-files", "-z")
        self.assertEqual(tracked.returncode, 0, tracked.stderr)
        paths = [path for path in tracked.stdout.split("\0") if path]
        for extra in (
            "config.json", "logs/session.log", "secrets/settings.json",
            ".local/STATUS.md", ".env",
        ):
            with self.subTest(extra=extra):
                result, _, stderr = self.run_check(tracked_paths=[*paths, extra])
                self.assertEqual(result, 1, "extra tracked path bypassed the publication gate")
                self.assertIn("unexpected tracked path", stderr)
                self.assertIn(extra, stderr)

    def test_missing_tracked_manifest_entries_are_rejected(self):
        manifest = (
            ".gitignore", ".nojekyll", "CNAME", "index.html", "privacy.html", "terms.html",
            "styles.css", "README.md", "scripts/check_site.py", "scripts/preview_site.py",
            "tests/test_check_site.py", "tests/test_preview_site.py",
        )
        for missing in manifest:
            with self.subTest(missing=missing):
                result, _, stderr = self.run_check(
                    tracked_paths=[path for path in manifest if path != missing]
                )
                self.assertEqual(result, 1, "incomplete tracked manifest bypassed the gate")
                self.assertIn(f"missing tracked manifest path: {missing}", stderr)

    def test_inline_event_handler_is_rejected(self):
        result, _, stderr = self.run_check(
            lambda source: source.replace("<body>", '<body onload="void(0)">', 1)
        )
        self.assertEqual(result, 1, "inline onload bypassed the structural checker")
        self.assertIn("inline event handler", stderr)

    def test_executable_links_are_rejected(self):
        for link in (
            "javascript:void(0)",
            "JaVaScRiPt:void(0)",
            "java&#x09;script:void(0)",
            "&#x6a;avascript:void(0)",
            "vbscript:msgbox(0)",
            "data:text/html,probe",
        ):
            with self.subTest(link=link):
                result, _, stderr = self.run_check(
                    lambda source: source.replace(
                        "</main>", f'<a href="{link}">Probe</a></main>', 1
                    )
                )
                self.assertEqual(result, 1, "executable link bypassed the structural checker")
                self.assertIn("unsafe link scheme", stderr)

    def test_external_srcset_is_rejected(self):
        for element in (
            '<img srcset="https://example.invalid/probe.png 1x">',
            '<img srcset="styles.css 1x, https://example.invalid/probe.png 2x">',
            '<source srcset="//example.invalid/probe.png 1x">',
        ):
            with self.subTest(element=element):
                result, _, stderr = self.run_check(
                    lambda source: source.replace("</main>", element + "</main>", 1)
                )
                self.assertEqual(result, 1, "external srcset bypassed the structural checker")
                self.assertIn("external asset is not allowed", stderr)


if __name__ == "__main__":
    unittest.main()
