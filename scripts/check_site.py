#!/usr/bin/env python3
"""Keyword/structure checks, not runtime or policy correctness assurance."""

from __future__ import annotations

import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
PAGES = ("index.html", "privacy.html", "terms.html")
REQUIRED_FILES = (*PAGES, "styles.css", "CNAME", ".nojekyll", "README.md")
ALLOWED_TAGS = {
    "html", "head", "meta", "title", "link", "body", "a", "header", "nav",
    "main", "p", "h1", "h2", "section", "strong", "footer",
}
GLOBAL_ATTRIBUTES = {"id", "class", "aria-label", "aria-labelledby", "aria-current"}
TAG_ATTRIBUTES = {
    "html": {"lang"},
    "meta": {"charset", "name", "content"},
    "link": {"rel", "href"},
    "a": {"href", "rel"},
}
TRACKED_MANIFEST = {
    ".gitignore", ".nojekyll", "CNAME", "index.html", "privacy.html", "terms.html",
    "styles.css", "README.md", "scripts/check_site.py", "scripts/preview_site.py",
    "tests/test_check_site.py", "tests/test_preview_site.py",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.assets: list[str] = []
        self.ids: set[str] = set()
        self.tags: list[str] = []
        self.text: list[str] = []
        self.event_handlers: list[str] = []
        self.duplicate_attributes: list[str] = []
        self.policy_failures: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        if tag not in ALLOWED_TAGS:
            self.policy_failures.append(f"element is not allowed: <{tag}>")
        self.event_handlers.extend(name for name, _ in attrs if name.startswith("on"))
        seen: set[str] = set()
        for name, _ in attrs:
            if name in seen:
                self.duplicate_attributes.append(f"<{tag}> {name}")
            seen.add(name)
            if name not in GLOBAL_ATTRIBUTES | TAG_ATTRIBUTES.get(tag, set()):
                self.policy_failures.append(f"attribute is not allowed: <{tag}> {name}")
        values = dict(attrs)
        if tag == "link" and (
            (values.get("rel") or "").casefold().split() != ["stylesheet"]
            or values.get("href") != "styles.css"
        ):
            self.policy_failures.append("only the site stylesheet link is allowed")
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"script", "img", "iframe", "source"} and values.get("src"):
            self.assets.append(values["src"] or "")
        if tag in {"img", "source"}:
            for candidate in (values.get("srcset") or "").split(","):
                if candidate.strip():
                    self.assets.append(candidate.split()[0])
        if tag == "link" and "stylesheet" in (values.get("rel") or "").lower().split():
            self.assets.append(values.get("href") or "")

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    if failures:
        return report(failures)

    parsers: dict[str, PageParser] = {}
    for relative in PAGES:
        source = read_text(relative)
        parser = PageParser()
        try:
            parser.feed(source)
            parser.close()
        except Exception as exc:  # HTMLParser reports malformed input here.
            failures.append(f"{relative}: HTML parse failed: {exc}")
            continue
        parsers[relative] = parser
        text = " ".join(" ".join(parser.text).replace("’", "'").split()).casefold()
        for tag in ("html", "head", "body", "header", "nav", "main", "footer"):
            if tag not in parser.tags:
                failures.append(f"{relative}: missing semantic <{tag}> element")
        if "lang=en" not in source.casefold() and "lang=\"en\"" not in source.casefold():
            failures.append(f"{relative}: declare the document language as English")
        if "name=\"viewport\"" not in source.casefold():
            failures.append(f"{relative}: missing mobile viewport metadata")
        if "<script" in source.casefold():
            failures.append(f"{relative}: scripts are not allowed on this static information site")
        if "<form" in source.casefold():
            failures.append(f"{relative}: forms are not allowed on this information site")
        for handler in parser.event_handlers:
            failures.append(f"{relative}: inline event handler is not allowed: {handler}")
        for attribute in parser.duplicate_attributes:
            failures.append(f"{relative}: duplicate attribute is not allowed: {attribute}")
        failures.extend(f"{relative}: {failure}" for failure in parser.policy_failures)

        for asset in parser.assets:
            parsed = urlsplit(asset)
            if parsed.scheme or parsed.netloc or asset.startswith("//"):
                failures.append(f"{relative}: external asset is not allowed: {asset}")
            elif not local_target(relative, parsed.path).is_file():
                failures.append(f"{relative}: missing local asset: {asset}")

        if not any(link.split("#", 1)[0] == "privacy.html" for link in parser.links) and relative == "index.html":
            failures.append("index.html: missing privacy policy navigation link")
        if not any(link.split("#", 1)[0] == "terms.html" for link in parser.links) and relative == "index.html":
            failures.append("index.html: missing terms navigation link")

        requirements = {
            "index.html": ("Pol's Hermes", "owner-only", "Gmail", "calendar"),
            "privacy.html": (
                "read-only", "calendar", "task", "advertising", "data broker",
                "Google Account", "Limited Use", "retention", "github.com/polmonta",
            ),
            "terms.html": ("private", "not affiliated", "Google", "Nous", "as-is"),
        }
        for phrase in requirements[relative]:
            if phrase.casefold() not in text:
                failures.append(f"{relative}: missing required keyword: {phrase}")

    for relative, parser in parsers.items():
        for link in parser.links:
            parsed = urlsplit(link)
            if parsed.scheme and parsed.scheme not in {"http", "https", "mailto", "tel"}:
                failures.append(f"{relative}: unsafe link scheme is not allowed: {link}")
                continue
            if parsed.scheme or parsed.netloc or link.startswith("//"):
                continue
            target = local_target(relative, parsed.path)
            if not target.exists():
                failures.append(f"{relative}: broken internal link: {link}")
            elif parsed.fragment and target.suffix.lower() in {".html", ".htm"}:
                target_name = target.relative_to(ROOT).as_posix()
                target_parser = parsers.get(target_name)
                if target_parser is None:
                    target_parser = PageParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                if unquote(parsed.fragment) not in target_parser.ids:
                    failures.append(f"{relative}: missing fragment target: {link}")

    css = read_text("styles.css").casefold()
    # This stylesheet needs no resources, escapes, or comments. Reject those
    # constructs outright rather than attempting a general CSS sanitizer.
    if (
        "\\" in css
        or "/*" in css
        or "*/" in css
        or re.search(r"@import\b|url\s*\(|(?:-webkit-)?image(?:-set)?\s*\(", css)
    ):
        failures.append("styles.css: stylesheet resource-loading syntax, escapes, and comments are not allowed")

    if (ROOT / "CNAME").read_text(encoding="utf-8").splitlines() != ["hermes.montanera.cat"]:
        failures.append("CNAME must contain only hermes.montanera.cat")
    if (ROOT / ".nojekyll").read_bytes():
        failures.append(".nojekyll must be empty")

    readme = read_text("README.md").casefold()
    for phrase in ("github pages", "content review", "python3 scripts/check_site.py", "hermes.montanera.cat"):
        if phrase not in readme:
            failures.append(f"README.md: missing deployment/check guidance: {phrase}")

    ignore_check = run_git("check-ignore", "--quiet", ".local/STATUS.md")
    if ignore_check.returncode != 0:
        failures.append(".local/STATUS.md is not ignored by Git")
    tracked = run_git("ls-files", "-z")
    if tracked.returncode != 0:
        failures.append("could not inspect tracked files with git ls-files")
    else:
        tracked_paths = {path for path in tracked.stdout.split("\0") if path}
        for path in sorted(tracked_paths - TRACKED_MANIFEST):
            failures.append(f"unexpected tracked path (outside publication manifest): {path}")
        for path in sorted(TRACKED_MANIFEST - tracked_paths):
            failures.append(f"missing tracked manifest path: {path}")

    if failures:
        return report(failures)
    print(f"PASS: {len(REQUIRED_FILES)} required files present")
    print(f"PASS: {len(PAGES)} HTML pages, semantic structure, required keywords, and internal links")
    print("PASS: static HTML restrictions and local asset-reference checks")
    print("PASS: CNAME and .nojekyll contents")
    print("PASS: private status path ignored and tracked files match the exact publication manifest")
    print("PASS: README includes local verification and deployment guidance")
    print("NOTE: keyword/structure checks only; not runtime behavior or policy correctness, and not publication approval")
    return 0


def local_target(source_page: str, path: str) -> Path:
    if not path:
        return ROOT / source_page
    target = ROOT / unquote(path.lstrip("/")) if path.startswith("/") else ROOT / Path(source_page).parent / unquote(path)
    target = target.resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return ROOT / "__outside_site__"
    if target.is_dir():
        return target / "index.html"
    return target


def report(failures: list[str]) -> int:
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    print(f"{len(failures)} check(s) failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
