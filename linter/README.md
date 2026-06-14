# 4D documentation linter

`lint_4d_doc.py` checks that the Markdown documentation of the 4D classes stays
in sync with the code. It pairs each class source
(`Project/Sources/Classes/<Class>.4dm`) with its doc page
(`Documentation/Classes/<Class>.md`) and reports gaps.

## Visibility convention

A class, function, computed property or constructor whose name starts with `_`
is treated as **private** and is never required to be documented. Private
classes are skipped entirely.

## Rules

| Rule | Default | Checks |
|------|---------|--------|
| `class-documented` | on | A public class has a (non-empty) Markdown doc file. |
| `class-title` | on | The doc's first heading contains the class name. |
| `function-documented` | on | Every public function has its own title/heading in the doc. |
| `computed-property-documented` | on | Every public computed property (`Function get`/`set`) is mentioned in the doc. |
| `linked-classes` | **off** | Other classes used in the constructor/functions are linked (`[X](X.md)`) in the doc. |
| `constructor-documented` | **off** | The class constructor is documented (a heading containing "constructor"). |

## Usage

```bash
# Lint the project in the current directory with the default rules
python3 lint_4d_doc.py

# Lint a project elsewhere
python3 lint_4d_doc.py /path/to/4D-AIKit

# Turn the opt-in rules on
python3 lint_4d_doc.py --enable linked-classes,constructor-documented

# Turn a default rule off
python3 lint_4d_doc.py --disable class-title

# Enable everything
python3 lint_4d_doc.py --all

# Machine-readable output (for CI)
python3 lint_4d_doc.py --format json

# List the rules
python3 lint_4d_doc.py --list-rules
```

CLI flags: `--enable` / `--disable` accept comma- or space-separated rule names
and may be repeated. `--source-dir` / `--docs-dir` override the folders
(relative to the base path or absolute). `--exit-zero` always exits 0.

## Run without downloading (curl | python)

You can run the linter straight from GitHub without cloning this repo. Pipe the
raw script into Python and pass the project path (and any flags) after the `-`:

```bash
# Lint the project in the current directory
curl -fsSL https://raw.githubusercontent.com/doc4d/scripts/main/linter/lint_4d_doc.py | python3 -

# Lint a project elsewhere, with extra flags
curl -fsSL https://raw.githubusercontent.com/doc4d/scripts/main/linter/lint_4d_doc.py | python3 - /path/to/4D-AIKit --all

# Machine-readable output for CI
curl -fsSL https://raw.githubusercontent.com/doc4d/scripts/main/linter/lint_4d_doc.py | python3 - --format json
```

Everything after `python3 -` is forwarded to the script as normal CLI arguments.

## Output formats (`--format` / `-f`)

| Format | Audience | Notes |
|--------|----------|-------|
| `text` *(default)* | Humans | `path:line: [rule] message`, one per line. |
| `table` | Humans | Pretty Unicode table. |
| `json` | Automation | `{summary, findings[]}`. |
| `sarif` | GitHub code scanning, IDEs | SARIF 2.1.0. |
| `checkstyle` | Jenkins, many CI plugins | Checkstyle XML. |
| `junit` | CI test reporters | JUnit XML (one `<testcase>` per finding). |
| `csv` | Spreadsheets, dashboards | `rule,path,line,message`. |
| `xml` | Generic tooling | Simple `<lint><finding/></lint>`. |

`--color {auto,always,never}` controls ANSI colors for `text` and `table`
(default `auto`: on when stdout is a TTY and `NO_COLOR` is unset).

```bash
python3 lint_4d_doc.py --format table
python3 lint_4d_doc.py --format sarif      > results.sarif
python3 lint_4d_doc.py --format checkstyle > checkstyle.xml
python3 lint_4d_doc.py --format junit      > junit.xml
python3 lint_4d_doc.py --format csv        > report.csv
```

## Config file

Rules and folders can also be set in YAML. A file named `.4d-doc-lint.yml`
(or `.4d-doc-lint.yaml`, `4d-doc-lint.yml`) at the base path is auto-loaded;
otherwise pass `--config <file>`. See [`4d-doc-lint.yml`](4d-doc-lint.yml) for a
template.

Precedence (lowest → highest): built-in defaults → config file → CLI flags.

PyYAML is used when available; a small built-in fallback parser covers the
config schema when it is not installed.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | No warnings (or `--exit-zero`). |
| `1` | One or more warnings found. |
| `2` | Bad usage (unknown rule, missing source dir, …). |
