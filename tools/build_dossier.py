"""Build docs/AEROFLEET_DOSSIER.md: one file with everything about the project, for an external review.

Part I is docs/dossier/NARRATIVE.md (written by hand). Part II is assembled here from the repository's own files: the
declared-test registry from git, every result write-up, protocols, the paper and supplement, the code map, and the
team documents. Personal names, e-mail addresses and the paper's author block are removed.

    python tools/build_dossier.py
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "AEROFLEET_DOSSIER.md")

NAMES = ["Nagesh Chougule", "Vibhav Ambardekar", "Aditya Pathare", "Atharv Waghmare", "Shreyash Pawar",
         "Piyush Bhamare", "Chougule", "Ambardekar", "Pathare", "Waghmare", "Pawar", "Bhamare",
         "Aditya", "Atharv", "Shreyash", "Piyush", "Nagesh", "Vibhav"]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
MIS = re.compile(r"\b(MIS[^\n]{0,20}?)\d{6,12}\b")
TEST_SECRETS = re.compile(r"(?i)(password|passwd|token|api[_-]?key)\s*[:=]\s*\S+")


PUBLIC_EMAILS = {"aaib.moca@nic.in"}


def redact(text: str) -> str:
    text = EMAIL.sub(lambda m: m.group(0) if m.group(0).lower() in PUBLIC_EMAILS else "[e-mail removed]", text)
    text = re.sub(r"github\.com/[A-Za-z0-9_-]+/", "github.com/[owner]/", text)
    text = MIS.sub(r"\1[number removed]", text)
    text = TEST_SECRETS.sub(r"\1: [removed]", text)
    for n in NAMES:
        text = re.sub(rf"\b{re.escape(n)}\b", "[team member]" if " " not in n else "[name removed]", text)
    return text


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def demote(md: str, by: int = 2) -> str:
    """Push a file's headings down so they sit under the appendix heading."""
    return re.sub(r"^(#{1,6}) ", lambda m: "#" * min(6, len(m.group(1)) + by) + " ", md, flags=re.M)


def block(title: str, rel: str, body: str | None = None, lang: str = "") -> str:
    body = read(rel) if body is None else body
    if lang:
        return f"\n### {title}\n\n*Source: `{rel}`*\n\n```{lang}\n{body.rstrip()}\n```\n"
    return f"\n### {title}\n\n*Source: `{rel}`*\n\n{demote(body).rstrip()}\n"


def registry() -> str:
    lines = git("log", "--reverse", "--date=format:%Y-%m-%d %H:%M", "--pretty=%h|%ad|%s").splitlines()
    rows = [line.split("|", 2) for line in lines if re.match(r"^[0-9a-f]+\|[^|]+\|(Protocol|Results)", line)]
    out = ["| Commit | Date (IST) | Message |", "|---|---|---|"]
    out += [f"| `{h}` | {d} | {s.replace('|', '/')} |" for h, d, s in rows]
    return (f"{len(rows)} commits whose message starts with *Protocol:* (a test declared) or *Results:* (its result), "
            "in time order. Each result commit follows its declaration.\n\n" + "\n".join(out))


def drift_summary(text: str) -> str:
    """The drift catalogue check is 42 KB, mostly per-parameter rows; keep everything before the first long table."""
    keep, rows = [], 0
    for line in text.splitlines():
        rows = rows + 1 if line.startswith("|") else 0
        if rows > 12:
            continue
        keep.append(line)
    return "\n".join(keep[:220]) + "\n\n*(Per-parameter tables trimmed to 12 rows each and the file to 220 lines.)*"


def strip_authors(tex: str) -> str:
    tex = re.sub(r"% ---- Authors ----.*?(?=\\begin\{abstract\})", "% [author block removed]\n", tex, flags=re.S)
    return re.sub(r"\\author\{[^}]*\}", r"\\author{[removed]}", tex)


def figures() -> str:
    tex = read("docs/paper/latex/main.tex") + read("docs/paper/latex/supplement.tex")
    out = []
    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}(.*?)\\caption\{", tex, flags=re.S):
        start = m.end()
        depth, i = 1, start
        while depth and i < len(tex):
            depth += {"{": 1, "}": -1}.get(tex[i], 0)
            i += 1
        cap = re.sub(r"\s+", " ", tex[start:i - 1]).strip()
        out.append(f"- **`{m.group(1)}`**: {cap}")
    return ("Images cannot be uploaded with this file; Part I section 3 gives each figure's data as a table. Captions, "
            "as LaTeX:\n\n" + "\n".join(out))


def code_map() -> str:
    pats = ["aerofleet/assurance/*.py", "aerofleet/api/routes/*.py", "tools/*.py", "tauri-app/src/pages/*.tsx",
            "tauri-app/src/lib/*.ts", "tauri-app/src-tauri/src/*.rs"]
    out = ["| File | Lines | First line of its docstring |", "|---|---|---|"]
    total = 0
    for pat in pats:
        for p in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(p).startswith("._"):
                continue
            src = open(p, encoding="utf-8", errors="replace").read()
            n = src.count("\n")
            total += n
            m = re.search(r'^\s*(?:"""|/\*\*?|//)\s*(.+)', src)
            doc = (m.group(1) if m else "").strip().strip('"*/ ').replace("|", "/")[:110]
            out.append(f"| `{os.path.relpath(p, ROOT)}` | {n} | {doc} |")
    consts = []
    for p in sorted(glob.glob(os.path.join(ROOT, "aerofleet/assurance/*.py"))):
        if os.path.basename(p).startswith("._"):
            continue
        for line in open(p, encoding="utf-8", errors="replace"):
            if re.match(r"^[A-Z][A-Z0-9_]+\s*=\s*[-\d.(]", line):
                consts.append(f"{os.path.basename(p)}: {line.strip()[:120]}")
    return ("\n".join(out) + f"\n\nTotal: {total:,} lines in these files.\n\n#### Numeric constants in the assurance core\n\n"
            "```\n" + "\n".join(consts) + "\n```")


def tests_count() -> str:
    files = glob.glob(os.path.join(ROOT, "tests/**/test_*.py"), recursive=True)
    files = [f for f in files if not os.path.basename(f).startswith("._")]
    out = ["| Test file | Test functions |", "|---|---|"]
    for f in sorted(files):
        n = len(re.findall(r"^\s*(?:async )?def test_", open(f, encoding="utf-8", errors="replace").read(), flags=re.M))
        out.append(f"| `{os.path.relpath(f, ROOT)}` | {n} |")
    return "\n".join(out)


def main() -> None:
    commit = git("rev-parse", "--short", "HEAD").strip()
    parts = [read("docs/dossier/NARRATIVE.md").replace("DOSSIER_DATE", dt.date.today().isoformat())
             .replace("DOSSIER_COMMIT", commit)]

    parts.append("\n## Appendix A. Declared-test registry (from git)\n\n" + registry())

    parts.append(
        "\n## Appendix B. Every result write-up\n\n"
        "Copied verbatim from `research/results/`. *Historical note: pre-28-Nov result logs (such as SITL v2) refer to "
        "the green readiness state by its earlier UI label \"Ready\"; on 28 Nov the UI label was renamed to \"No rule fired\".*"
    )
    for p in sorted(glob.glob(os.path.join(ROOT, "research/results/**/*.md"), recursive=True)):
        if os.path.basename(p).startswith("._"):
            continue
        rel = os.path.relpath(p, ROOT)
        body = read(rel)
        if rel.endswith("drift_catalogue_check.md"):
            body = drift_summary(body)
        parts.append(block(rel.replace("research/results/", ""), rel, body))

    parts.append("\n## Appendix C. Test protocols and the model README\n")
    for rel in ["research/sitl_check/PROTOCOL.md", "research/sitl_check/PROTOCOL_v2.md", "research/vr_study/PROTOCOL.md",
                "research/normal_flight/README.md"]:
        parts.append(block(rel, rel))
    for rel in ["research/false_alarms/measure.py", "research/false_alarms/measure_fa2.py",
                "research/false_alarms/measure_sa1_fa3.py",
                "research/normal_flight/train_eval_v2.py", "research/archive_search/eval_archive_search.py"]:
        if os.path.exists(os.path.join(ROOT, rel)):
            src = read(rel)
            m = re.match(r'\s*"""(.*?)"""', src, flags=re.S)
            parts.append(block(f"Declaration in {rel}", rel, m.group(1).strip() if m else src[:3000], "text"))

    parts.append("\n## Appendix D. Paper figures\n\n" + figures())
    parts.append("\n## Appendix E. Code map and tests\n\n" + code_map() + "\n\n#### Test files\n\n" + tests_count())
    parts.append("\n## Appendix F. The paper (LaTeX, author block removed)\n")
    parts.append(block("main.tex", "docs/paper/latex/main.tex", strip_authors(read("docs/paper/latex/main.tex")), "latex"))
    parts.append("\n## Appendix G. The supplement (LaTeX)\n")
    parts.append(block("supplement.tex", "docs/paper/latex/supplement.tex",
                       strip_authors(read("docs/paper/latex/supplement.tex")), "latex"))
    parts.append("\n## Appendix H. Project documents\n")
    for rel in ["README.md", "docs/PROJECT_GUIDE.md", "docs/VIVA.md", "docs/DEMO.md", "docs/VR_PURPOSE.md",
                "docs/FC_COMPLIANCE.md", "docs/CRITICAL_REVIEW_2026-11-27.md"]:
        body = read(rel)
        if rel == "docs/CRITICAL_REVIEW_2026-11-27.md":
            body = (
                "> *Historical snapshot (27 November 2026, pre-remediation): preserved verbatim to show every finding "
                "prior to the C1/C2 fixes (`fc73ec6`), H1-H5/M1-M5/L2 remediation (`8129e83`), 37-airport update, and "
                "the \"Ready\" -> \"No rule fired\" UI rename.*\n\n" + body
            )
        parts.append(block(rel, rel, body))

    text = redact("\n".join(parts))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"{OUT}: {len(text):,} characters, about {len(text) // 4:,} tokens")


if __name__ == "__main__":
    main()
