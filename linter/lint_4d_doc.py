#!/usr/bin/env python3
"""Lint the Markdown documentation of 4D classes.

This linter pairs each 4D class source file (``Project/Sources/Classes/*.4dm``)
with its Markdown documentation (``Documentation/Classes/<ClassName>.md``) and
checks a set of configurable rules.

Visibility convention (4D): a class, function, computed property or constructor
whose name starts with ``_`` is considered *private* and is not required to be
documented. Private classes are skipped entirely.

Rules (each can be turned on/off on the command line or in a YAML config):

  class-documented              (default: on)   Public class must have a doc file.
  class-title                   (default: on)   Doc's first heading must be the class name.
  function-documented           (default: on)   Each public function has its own title in the doc.
  computed-property-documented  (default: on)   Each public computed property is mentioned in the doc.
  linked-classes                (default: off)  Other classes used in the constructor/functions are linked.
  constructor-documented        (default: off)  The class constructor is documented.

Usage:
  python3 scripts/lint_4d_doc.py [PATH] [options]

  PATH    Base directory of the 4D project (default: current working directory).

Examples:
  python3 scripts/lint_4d_doc.py
  python3 scripts/lint_4d_doc.py /path/to/4D-AIKit
  python3 scripts/lint_4d_doc.py --enable linked-classes,constructor-documented
  python3 scripts/lint_4d_doc.py --disable class-title
  python3 scripts/lint_4d_doc.py --config scripts/4d-doc-lint.yml
  python3 scripts/lint_4d_doc.py --format json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import quoteattr as xml_attr

TOOL_NAME = "4d-doc-lint"
TOOL_VERSION = "1.0.0"
TOOL_URI = "https://github.com/doc4d/scripts"

OUTPUT_FORMATS = ("text", "table", "json", "sarif", "checkstyle", "junit", "csv", "xml")

# --------------------------------------------------------------------------- #
# Rule registry
# --------------------------------------------------------------------------- #

# key -> (default_enabled, one-line description)
RULES: "dict[str, tuple[bool, str]]" = {
    "class-documented": (True, "Public class must have a Markdown documentation file."),
    "class-title": (True, "Documentation's first heading must be the class name."),
    "function-documented": (True, "Each public function must be documented with its own title."),
    "computed-property-documented": (True, "Each public computed property must be mentioned in the doc."),
    "linked-classes": (False, "Other classes used in constructor/functions must be linked in the doc."),
    "constructor-documented": (False, "The class constructor must be documented."),
}

DEFAULT_SOURCE_DIR = "Project/Sources/Classes"
DEFAULT_DOCS_DIR = "Documentation/Classes"
DEFAULT_CONFIG_NAMES = (".4d-doc-lint.yml", ".4d-doc-lint.yaml", "4d-doc-lint.yml")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Member:
    name: str
    line: int
    signature: str = ""


@dataclass
class ClassInfo:
    name: str
    path: Path
    is_private: bool
    extends: "str | None" = None
    has_constructor: bool = False
    constructor_line: "int | None" = None
    functions: "list[Member]" = field(default_factory=list)          # public + private regular functions
    computed: "dict[str, Member]" = field(default_factory=dict)      # name -> member (getter/setter merged)
    referenced: "dict[str, int]" = field(default_factory=dict)       # cs.<Name> used inside members -> first line


@dataclass
class Finding:
    rule: str
    path: Path
    line: int
    message: str


# --------------------------------------------------------------------------- #
# 4D source parsing
# --------------------------------------------------------------------------- #

RE_EXTENDS = re.compile(r"^\s*Class\s+extends\s+(\w+)", re.IGNORECASE)
RE_CONSTRUCTOR = re.compile(r"^\s*Class\s+constructor\b(.*)$", re.IGNORECASE)
RE_GETTER = re.compile(r"^\s*Function\s+get\s+(\w+)\b(.*)$", re.IGNORECASE)
RE_SETTER = re.compile(r"^\s*Function\s+set\s+(\w+)\b(.*)$", re.IGNORECASE)
RE_FUNCTION = re.compile(r"^\s*Function\s+(\w+)\b(.*)$", re.IGNORECASE)
RE_CS_REF = re.compile(r"\bcs(?::C\d+)?\.([A-Za-z_]\w*)")


def is_private(name: str) -> bool:
    return name.startswith("_")


def parse_4d_class(path: Path) -> ClassInfo:
    """Parse a .4dm class file into a ClassInfo."""
    name = path.stem
    info = ClassInfo(name=name, path=path, is_private=is_private(name))

    in_member = False  # are we currently inside a constructor/function body?

    text = path.read_text(encoding="utf-8", errors="replace")
    for idx, raw in enumerate(text.splitlines(), start=1):
        m = RE_EXTENDS.match(raw)
        if m:
            info.extends = m.group(1)
            in_member = False
            continue

        m = RE_CONSTRUCTOR.match(raw)
        if m:
            info.has_constructor = True
            info.constructor_line = idx
            in_member = True
            _collect_refs(info, raw, idx)
            continue

        m = RE_GETTER.match(raw)
        if m:
            _add_computed(info, m.group(1), idx, raw)
            in_member = True
            _collect_refs(info, raw, idx)
            continue

        m = RE_SETTER.match(raw)
        if m:
            _add_computed(info, m.group(1), idx, raw)
            in_member = True
            _collect_refs(info, raw, idx)
            continue

        m = RE_FUNCTION.match(raw)
        if m:
            info.functions.append(Member(name=m.group(1), line=idx, signature=raw.strip()))
            in_member = True
            _collect_refs(info, raw, idx)
            continue

        # Body line of the current member: collect class references.
        if in_member:
            _collect_refs(info, raw, idx)

    return info


def _add_computed(info: ClassInfo, name: str, line: int, raw: str) -> None:
    if name not in info.computed:
        info.computed[name] = Member(name=name, line=line, signature=raw.strip())


def _collect_refs(info: ClassInfo, raw: str, line: int) -> None:
    for ref in RE_CS_REF.findall(raw):
        if ref == info.name:
            continue
        info.referenced.setdefault(ref, line)


# --------------------------------------------------------------------------- #
# Markdown doc parsing
# --------------------------------------------------------------------------- #

RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_LINK = re.compile(r"\]\(([^)\s]+)")
RE_MD_FILE = re.compile(r"([A-Za-z_]\w*)\.md", re.IGNORECASE)
RE_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class DocInfo:
    path: Path
    exists: bool
    empty: bool
    text: str = ""
    headings: "list[tuple[int, str, int]]" = field(default_factory=list)  # (level, text, line)
    md_refs: "set[str]" = field(default_factory=set)                       # lowercased "name.md" found anywhere


def analyze_doc(path: Path) -> DocInfo:
    if not path.exists():
        return DocInfo(path=path, exists=False, empty=True)

    text = path.read_text(encoding="utf-8", errors="replace")
    doc = DocInfo(path=path, exists=True, empty=(text.strip() == ""), text=text)

    in_fence = False
    for idx, raw in enumerate(text.splitlines(), start=1):
        if RE_FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        hm = RE_HEADING.match(raw)
        if hm:
            doc.headings.append((len(hm.group(1)), hm.group(2).strip(), idx))

    for ref in RE_MD_FILE.findall(text):
        doc.md_refs.add((ref + ".md").lower())

    return doc


def _norm_heading(text: str) -> str:
    """Lowercase a heading and strip markdown emphasis / backticks / trailing ()."""
    t = text.strip().lower()
    t = t.replace("`", "").replace("*", "").replace("_", "").strip()
    if t.endswith("()"):
        t = t[:-2].strip()
    return t


def heading_contains_name(text: str, name: str) -> bool:
    """True if the class name appears as a whole word in the heading text."""
    return re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", text, re.IGNORECASE) is not None


def constructor_documented(doc: DocInfo) -> bool:
    return any("constructor" in t.lower() for _, t, _ in doc.headings)


def mentioned_as_word(doc: DocInfo, name: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", doc.text, re.IGNORECASE) is not None


# --------------------------------------------------------------------------- #
# Linting
# --------------------------------------------------------------------------- #

def lint_class(cls: ClassInfo, doc: DocInfo, enabled: "dict[str, bool]",
               documented_classes: "set[str]") -> "list[Finding]":
    findings: "list[Finding]" = []

    # Rule 1: public class must be documented.
    if not doc.exists or doc.empty:
        if enabled["class-documented"]:
            where = os.path.relpath(doc.path) if doc.exists else doc.path.name
            reason = "documentation file is empty" if doc.exists else "no documentation file"
            findings.append(Finding(
                "class-documented", cls.path, 1,
                f"Public class '{cls.name}' is undocumented ({reason}; expected {doc.path})",
            ))
        # Without a doc we cannot evaluate content rules.
        return findings

    # Rule 2: doc's title (first heading) must name the class.
    if enabled["class-title"]:
        first = doc.headings[0] if doc.headings else None
        if first is None:
            findings.append(Finding(
                "class-title", doc.path, 1,
                f"Documentation has no heading; expected a title naming the class '{cls.name}'",
            ))
        elif not heading_contains_name(first[1], cls.name):
            findings.append(Finding(
                "class-title", doc.path, first[2],
                f"Documentation title is '{first[1]}'; it must contain the class name '{cls.name}'",
            ))

    # Rule 3: each public function documented with a title.
    if enabled["function-documented"]:
        for fn in cls.functions:
            if is_private(fn.name):
                continue
            if not _function_documented(doc, fn.name):
                findings.append(Finding(
                    "function-documented", cls.path, fn.line,
                    f"Public function '{fn.name}()' has no title in {os.path.relpath(doc.path)}",
                ))

    # Rule 4: each public computed property mentioned somewhere.
    if enabled["computed-property-documented"]:
        for name, member in cls.computed.items():
            if is_private(name):
                continue
            if not mentioned_as_word(doc, name):
                findings.append(Finding(
                    "computed-property-documented", cls.path, member.line,
                    f"Public computed property '{name}' is not mentioned in {os.path.relpath(doc.path)}",
                ))

    # Rule 5: other classes used must be linked.
    if enabled["linked-classes"]:
        for ref_name, ref_line in sorted(cls.referenced.items(), key=lambda kv: kv[1]):
            if ref_name == cls.name or is_private(ref_name):
                continue
            if ref_name not in documented_classes:
                continue  # only require links to classes that actually have a doc page
            if (ref_name + ".md").lower() not in doc.md_refs:
                findings.append(Finding(
                    "linked-classes", cls.path, ref_line,
                    f"Class '{ref_name}' is used by '{cls.name}' but not linked in {os.path.relpath(doc.path)}",
                ))

    # Rule 6: constructor documented.
    if enabled["constructor-documented"] and cls.has_constructor:
        if not constructor_documented(doc):
            findings.append(Finding(
                "constructor-documented", cls.path, cls.constructor_line or 1,
                f"Constructor of '{cls.name}' is not documented in {os.path.relpath(doc.path)}",
            ))

    return findings


def _function_documented(doc: DocInfo, fname: str) -> bool:
    target = fname.lower()
    for _, htext, _ in doc.headings:
        if _norm_heading(htext) == target:
            return True
    # Fallback: a bold signature line like **create**( ... )
    bold = re.compile(r"^\*\*\s*" + re.escape(fname) + r"\s*\*\*\s*\(", re.IGNORECASE | re.MULTILINE)
    return bool(bold.search(doc.text))


# --------------------------------------------------------------------------- #
# Config / CLI
# --------------------------------------------------------------------------- #

def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError("config root must be a mapping")
        return data
    except ImportError:
        return _load_yaml_minimal(path)


def _load_yaml_minimal(path: Path) -> dict:
    """Tiny fallback parser for the limited config schema (no PyYAML installed)."""
    data: dict = {}
    current: "dict | None" = None

    def coerce(v: str):
        s = v.strip().strip('"').strip("'")
        low = s.lower()
        if low in ("true", "yes", "on"):
            return True
        if low in ("false", "no", "off"):
            return False
        return s

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indented = line[0] in " \t"
        if ":" not in line:
            continue
        key, _, val = line.strip().partition(":")
        key = key.strip()
        val = val.strip()
        if indented and current is not None:
            current[key] = coerce(val)
        elif val == "":
            current = {}
            data[key] = current
        else:
            current = None
            data[key] = coerce(val)
    return data


def parse_rule_list(values: "list[str] | None") -> "list[str]":
    result: "list[str]" = []
    for v in values or []:
        for part in re.split(r"[,\s]+", v):
            part = part.strip()
            if part:
                result.append(part)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint_4d_doc.py",
        description="Lint the Markdown documentation of 4D classes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Rules:\n" + "\n".join(
            f"  {k:<30} {'on ' if d else 'off'}  {desc}" for k, (d, desc) in RULES.items()
        ),
    )
    p.add_argument("path", nargs="?", default=".", help="Base directory of the 4D project (default: cwd).")
    p.add_argument("-c", "--config", help="Path to a YAML config file.")
    p.add_argument("--source-dir", help=f"Classes source dir, relative to PATH (default: {DEFAULT_SOURCE_DIR}).")
    p.add_argument("--docs-dir", help=f"Docs dir, relative to PATH (default: {DEFAULT_DOCS_DIR}).")
    p.add_argument("--enable", action="append", metavar="RULES",
                   help="Comma/space separated rule(s) to enable. Repeatable.")
    p.add_argument("--disable", action="append", metavar="RULES",
                   help="Comma/space separated rule(s) to disable. Repeatable.")
    p.add_argument("--all", action="store_true", help="Enable every rule.")
    p.add_argument("--format", "-f", choices=OUTPUT_FORMATS, default="text",
                   help="Output format (default: text). Human: text, table. "
                        "Machine: json, sarif, checkstyle, junit, csv, xml.")
    p.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                   help="Colorize text/table output (default: auto = on when stdout is a TTY).")
    p.add_argument("--list-rules", action="store_true", help="List available rules and exit.")
    p.add_argument("--exit-zero", action="store_true", help="Always exit 0, even when warnings are found.")
    return p


def resolve_enabled(args: argparse.Namespace, config: dict) -> "dict[str, bool]":
    enabled = {k: default for k, (default, _) in RULES.items()}

    cfg_rules = config.get("rules") or {}
    if isinstance(cfg_rules, dict):
        for k, v in cfg_rules.items():
            if k in enabled:
                enabled[k] = bool(v)
            else:
                print(f"warning: unknown rule in config: {k}", file=sys.stderr)
    elif isinstance(cfg_rules, list):  # list of enabled rule names
        for k in enabled:
            enabled[k] = k in cfg_rules

    if args.all:
        enabled = {k: True for k in enabled}

    unknown: "list[str]" = []
    for k in parse_rule_list(args.enable):
        if k in enabled:
            enabled[k] = True
        else:
            unknown.append(k)
    for k in parse_rule_list(args.disable):
        if k in enabled:
            enabled[k] = False
        else:
            unknown.append(k)
    if unknown:
        print(f"error: unknown rule(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available rules: {', '.join(RULES)}", file=sys.stderr)
        sys.exit(2)

    return enabled


def find_config(base: Path, explicit: "str | None") -> "Path | None":
    if explicit:
        cfg = Path(explicit)
        if not cfg.exists():
            print(f"error: config file not found: {explicit}", file=sys.stderr)
            sys.exit(2)
        return cfg
    for name in DEFAULT_CONFIG_NAMES:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        for k, (default, desc) in RULES.items():
            print(f"{k:<30} {'on ' if default else 'off'}  {desc}")
        return 0

    base = Path(args.path).resolve()
    if not base.is_dir():
        print(f"error: not a directory: {base}", file=sys.stderr)
        return 2

    config_path = find_config(base, args.config)
    config = _load_yaml(config_path) if config_path else {}

    source_rel = args.source_dir or config.get("source_dir") or DEFAULT_SOURCE_DIR
    docs_rel = args.docs_dir or config.get("docs_dir") or DEFAULT_DOCS_DIR
    source_dir = (base / source_rel) if not os.path.isabs(source_rel) else Path(source_rel)
    docs_dir = (base / docs_rel) if not os.path.isabs(docs_rel) else Path(docs_rel)

    if not source_dir.is_dir():
        print(f"error: source directory not found: {source_dir}", file=sys.stderr)
        print("       Use --source-dir to point at the 4D classes folder.", file=sys.stderr)
        return 2

    enabled = resolve_enabled(args, config)

    class_files = sorted(source_dir.glob("*.4dm"))
    classes = [parse_4d_class(p) for p in class_files]

    # Set of class names that have a (non-empty) doc page — used by rule 5.
    documented_classes = {
        c.name for c in classes
        if (docs_dir / f"{c.name}.md").exists()
        and (docs_dir / f"{c.name}.md").read_text(encoding="utf-8", errors="replace").strip()
    }

    findings: "list[Finding]" = []
    for cls in classes:
        if cls.is_private:
            continue  # private classes are not required to be documented
        doc = analyze_doc(docs_dir / f"{cls.name}.md")
        findings.extend(lint_class(cls, doc, enabled, documented_classes))

    findings.sort(key=lambda f: (str(f.path), f.line, f.rule))
    return report(findings, base, args, enabled, len(classes))


class Palette:
    """ANSI colors, with a no-op mode when color is disabled."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _w(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, t):    return self._w("1", t)
    def dim(self, t):     return self._w("2", t)
    def red(self, t):     return self._w("31", t)
    def green(self, t):   return self._w("32", t)
    def yellow(self, t):  return self._w("33", t)
    def blue(self, t):    return self._w("34", t)
    def magenta(self, t): return self._w("35", t)
    def cyan(self, t):    return self._w("36", t)


def _want_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _relposix(path: Path, base: Path) -> str:
    return os.path.relpath(path, base).replace(os.sep, "/")


def report(findings: "list[Finding]", base: Path, args: argparse.Namespace,
           enabled: "dict[str, bool]", n_classes: int) -> int:
    rows = [
        {"rule": f.rule, "path": _relposix(f.path, base), "line": f.line, "message": f.message}
        for f in findings
    ]
    active = [k for k in RULES if enabled[k]]

    renderers = {
        "text": _render_text,
        "table": _render_table,
        "json": _render_json,
        "sarif": _render_sarif,
        "checkstyle": _render_checkstyle,
        "junit": _render_junit,
        "csv": _render_csv,
        "xml": _render_xml,
    }
    out = renderers[args.format](rows, active, enabled, n_classes, args)
    if out:
        sys.stdout.write(out if out.endswith("\n") else out + "\n")

    if args.exit_zero:
        return 0
    return 1 if findings else 0


# ---- human-readable ------------------------------------------------------- #

def _render_text(rows, active, enabled, n_classes, args) -> str:
    c = Palette(_want_color(args.color))
    lines = []
    for r in rows:
        loc = c.cyan(f"{r['path']}:{r['line']}")
        rule = c.yellow(f"[{r['rule']}]")
        lines.append(f"{loc}: {rule} {r['message']}")
    if rows:
        files = len({r["path"] for r in rows})
        lines.append("")
        lines.append(c.bold(c.red(f"{len(rows)} warning(s)")) +
                     f" in {files} file(s). Active rules: {', '.join(active)}")
    else:
        lines.append(c.bold(c.green("No documentation issues found")) +
                     f" ({n_classes} classes, active rules: {', '.join(active)}).")
    return "\n".join(lines)


def _render_table(rows, active, enabled, n_classes, args) -> str:
    c = Palette(_want_color(args.color))
    if not rows:
        return (c.bold(c.green("No documentation issues found")) +
                f" ({n_classes} classes checked).")

    headers = ["Rule", "Location", "Message"]
    data = [[r["rule"], f"{r['path']}:{r['line']}", r["message"]] for r in rows]
    widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    # Cap the message column so the table stays readable.
    widths[2] = min(widths[2], 80)

    def hline(left, mid, right):
        return left + mid.join("─" * (w + 2) for w in widths) + right

    def fmt_row(cells, colorize=None):
        out = []
        for i, cell in enumerate(cells):
            text = cell if len(cell) <= widths[i] else cell[: widths[i] - 1] + "…"
            pad = " " * (widths[i] - len(text))
            if colorize:
                text = colorize(i, text)
            out.append(f" {text}{pad} ")
        return "│" + "│".join(out) + "│"

    def color_cell(i, text):
        if i == 0:
            return c.yellow(text)
        if i == 1:
            return c.cyan(text)
        return text

    lines = [hline("┌", "┬", "┐"),
             fmt_row(headers, lambda i, t: c.bold(t)),
             hline("├", "┼", "┤")]
    lines += [fmt_row(row, color_cell) for row in data]
    lines.append(hline("└", "┴", "┘"))
    files = len({r["path"] for r in rows})
    lines.append("")
    lines.append(c.bold(c.red(f"{len(rows)} warning(s)")) +
                 f" in {files} file(s). Active rules: {', '.join(active)}")
    return "\n".join(lines)


# ---- machine-readable ----------------------------------------------------- #

def _render_json(rows, active, enabled, n_classes, args) -> str:
    return json.dumps({
        "summary": {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "warnings": len(rows),
            "classes_checked": n_classes,
            "rules": {k: enabled[k] for k in RULES},
        },
        "findings": rows,
    }, indent=2)


def _render_sarif(rows, active, enabled, n_classes, args) -> str:
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": TOOL_NAME,
                "version": TOOL_VERSION,
                "informationUri": TOOL_URI,
                "rules": [
                    {
                        "id": k,
                        "name": k,
                        "shortDescription": {"text": desc},
                        "defaultConfiguration": {"level": "warning", "enabled": enabled[k]},
                    }
                    for k, (_, desc) in RULES.items()
                ],
            }},
            "results": [
                {
                    "ruleId": r["rule"],
                    "level": "warning",
                    "message": {"text": r["message"]},
                    "locations": [{"physicalLocation": {
                        "artifactLocation": {"uri": r["path"]},
                        "region": {"startLine": r["line"]},
                    }}],
                }
                for r in rows
            ],
        }],
    }
    return json.dumps(sarif, indent=2)


def _render_checkstyle(rows, active, enabled, n_classes, args) -> str:
    by_file: "dict[str, list]" = {}
    for r in rows:
        by_file.setdefault(r["path"], []).append(r)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<checkstyle version="4.3">']
    for path in sorted(by_file):
        out.append(f"  <file name={xml_attr(path)}>")
        for r in by_file[path]:
            out.append(
                f'    <error line="{r["line"]}" severity="warning" '
                f"message={xml_attr(r['message'])} source={xml_attr(r['rule'])}/>"
            )
        out.append("  </file>")
    out.append("</checkstyle>")
    return "\n".join(out)


def _render_junit(rows, active, enabled, n_classes, args) -> str:
    n = len(rows)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<testsuites name={xml_attr(TOOL_NAME)} tests="{n}" failures="{n}">',
           f'  <testsuite name={xml_attr(TOOL_NAME)} tests="{n}" failures="{n}" '
           f'errors="0" skipped="0">']
    if not rows:
        # Emit a single passing test so consumers see a green suite.
        out[1] = f'<testsuites name={xml_attr(TOOL_NAME)} tests="1" failures="0">'
        out[2] = (f'  <testsuite name={xml_attr(TOOL_NAME)} tests="1" failures="0" '
                  f'errors="0" skipped="0">')
        out.append(f'    <testcase classname={xml_attr(TOOL_NAME)} '
                   f'name="all documentation rules"/>')
    for r in rows:
        name = f"{r['rule']} @ {r['path']}:{r['line']}"
        out.append(f"    <testcase classname={xml_attr(r['path'])} name={xml_attr(name)}>")
        out.append(f"      <failure message={xml_attr(r['message'])} "
                   f"type={xml_attr(r['rule'])}>{xml_escape(r['message'])}</failure>")
        out.append("    </testcase>")
    out.append("  </testsuite>")
    out.append("</testsuites>")
    return "\n".join(out)


def _render_csv(rows, active, enabled, n_classes, args) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["rule", "path", "line", "message"])
    for r in rows:
        w.writerow([r["rule"], r["path"], r["line"], r["message"]])
    return buf.getvalue()


def _render_xml(rows, active, enabled, n_classes, args) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<lint tool={xml_attr(TOOL_NAME)} version={xml_attr(TOOL_VERSION)} '
           f'warnings="{len(rows)}" classesChecked="{n_classes}">']
    for r in rows:
        out.append(
            f'  <finding rule={xml_attr(r["rule"])} path={xml_attr(r["path"])} '
            f'line="{r["line"]}">{xml_escape(r["message"])}</finding>'
        )
    out.append("</lint>")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
