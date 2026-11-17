"""Check this repo against the nine SAAF quality standards.

Standard library only. Exit code 1 when a standard is missing or, without
--allow-placeholders, when template placeholders are still in the files.
Source of the standards: SAAF-Project docs/conventions/quality-standards.md
"""
import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("standards")
ROOT = Path(__file__).parents[1]
README_MIN_BYTES = 500
# What a README has to cover, and the words a heading may use for it. The template uses the first of each.
README_SECTIONS = {
    "what it does": ("what it does", "what this", "overview", "purpose", "about"),
    "input and output": ("input", "output"),
    "install and run": ("install", "run", "usage", "getting started", "quick start", "quickstart", "demo"),
    "limitations": ("limitation", "limits", "coverage gaps", "known issues"),
}
PLACEHOLDER = re.compile(
    r"\[[^\]\n]*(placeholder|agent name|repo-name|your-github-handle|contact address|one sentence|two or three sentences|"
    r"name or team|for example|list the variable|what the agent|which model|link to the plan|who owns this|yyyy-mm-dd|"
    r"csv, columns|using the findings)[^\]\n]*\]|\[(?:name|url)\]", re.I)
# The criteria template marks what is still to be written with an ellipsis.
ELLIPSIS_FILES = {"AUDIT-CRITERIA.md"}
MANIFESTS = {"requirements.txt", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile.lock", "package.json",
             "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.mod", "Cargo.toml"}
SKIP_DIRS = {".git", ".venv", "node_modules", "vendor", "__pycache__"}
# LLM checks: every criterion in AUDIT-CRITERIA.md has a number and a tag; llm_checks.yaml holds one check per [llm] one.
LLM_CHECK_FILES = ("llm_checks.yaml", "evals/llm_checks.yaml")
CRITERION_ID = re.compile(r"(?<![\w-])([A-Z]{1,4}-\d+(?:\.\d+)?)(?![\w-])")
CRITERION_TAG = re.compile(r"\[(llm|code)\]", re.I)
CHECK_ID = re.compile(r"^\s*-\s*id:\s*[\"']?([A-Za-z]{1,4}-\d+(?:\.\d+)?)[\"']?\s*(?:#.*)?$", re.M)


def files() -> List[Path]:
    return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]


def anywhere(name: str) -> bool:
    return any((ROOT / folder / name).is_file() for folder in ("", ".github", "docs"))


def readme_ok() -> bool:
    path = ROOT / "README.md"
    if not path.is_file() or path.stat().st_size < README_MIN_BYTES:
        return False
    headings = [line.lstrip("#").strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
    missing = [name for name, words in README_SECTIONS.items() if not any(word in heading for heading in headings for word in words)]
    for name in missing:
        LOG.info("     README.md has no heading for '%s' (a heading with one of: %s)", name, ", ".join(README_SECTIONS[name]))
    return not missing


def has_tests() -> bool:
    return any(re.search(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]+\.py$|\.(test|spec)\.[jt]sx?$", str(p.relative_to(ROOT))) for p in files())


def has_ci() -> bool:
    folder = ROOT / ".github" / "workflows"
    return folder.is_dir() and any(p.suffix in {".yml", ".yaml"} for p in folder.iterdir())


CHECKS: List[Tuple[str, Callable[[], bool]]] = [
    ("README.md explains the agent", readme_ok),
    ("agent.yaml", lambda: (ROOT / "agent.yaml").is_file() or (ROOT / "agent.yml").is_file()),
    ("AUDIT-CRITERIA.md", lambda: (ROOT / "AUDIT-CRITERIA.md").is_file()),
    # The SAAF-Project organisation policy (SAAF-Project/.github) covers every repo; a file of its own is optional.
    ("SECURITY.md (organisation policy)", lambda: True),
    ("LICENSE", lambda: any((ROOT / n).is_file() for n in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"))),
    ("Tests", has_tests),
    ("Dependencies", lambda: any(p.name in MANIFESTS for p in files())),
    ("CI", has_ci),
    ("CODEOWNERS", lambda: anywhere("CODEOWNERS")),
]


def tagged_criteria(text: str) -> Dict[str, str]:
    """The numbered criteria of AUDIT-CRITERIA.md: number to tag ("llm" or "code").

    A criterion is a line, or a table cell with the cell before it, that holds a number (CO-1.2, M-3, N-1) and a tag.
    The order does not matter: "- [llm] CO-1.2 Given ...", "- CO-1.2 [llm] Given ..." and "| M-1 | ✓ [code] ... |" all count.
    """
    found: Dict[str, str] = {}
    for line in text.splitlines():
        if not CRITERION_TAG.search(line):
            continue
        cells = [c for c in line.split("|")] if line.lstrip().startswith("|") else [line]
        number: Optional[str] = None
        for cell in cells:
            ids = CRITERION_ID.findall(cell)
            tag = CRITERION_TAG.search(cell)
            if ids:
                number = ids[0].upper()
            if tag and number:
                found.setdefault(number, tag.group(1).lower())
                number = None
    return found


def check_ids(text: str) -> List[str]:
    """The ids of the checks in llm_checks.yaml, in the order they appear."""
    return [m.group(1).upper() for m in CHECK_ID.finditer(text)]


def unwritten_checks(text: str) -> List[str]:
    """The ids of the checks that still hold a template placeholder."""
    marks = [(m.start(), m.group(1).upper()) for m in CHECK_ID.finditer(text)]
    ends = [start for start, _ in marks[1:]] + [len(text)]
    return [number for (start, number), end in zip(marks, ends, strict=False) if PLACEHOLDER.search(text[start:end])]


def llm_checks_report(criteria_text: Optional[str], checks_text: Optional[str], where: str = "llm_checks.yaml") -> List[str]:
    """What does not line up between the [llm] criteria and the checks. A report: it never fails the run."""
    if criteria_text is None:
        return []
    wanted = sorted(number for number, tag in tagged_criteria(criteria_text).items() if tag == "llm")
    if checks_text is None:
        return [f"LLM checks: no llm_checks.yaml yet, {len(wanted)} criteria are tagged [llm]"] if wanted else []
    ids = check_ids(checks_text)
    unwritten = unwritten_checks(checks_text)
    written = set(ids) - set(unwritten)
    lines = [f"LLM checks: {len(written & set(wanted))} of {len(wanted)} criteria tagged [llm] have a check in {where}"]
    lines += [f"     check {number} is still a placeholder" for number in dict.fromkeys(unwritten)]
    lines += [f"     no check for {number}" for number in wanted if number not in ids]
    lines += [f"     check {number} has no criterion tagged [llm] with that number" for number in dict.fromkeys(ids) if number not in wanted]
    lines += [f"     check {number} appears more than once" for number in dict.fromkeys(ids) if ids.count(number) > 1]
    return lines


def read(path: Path) -> Optional[str]:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def placeholders() -> List[str]:
    hits: List[str] = []
    for name in ("README.md", "agent.yaml", "CODEOWNERS", "AUDIT-CRITERIA.md", "llm_checks.yaml"):
        path = ROOT / name
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PLACEHOLDER.search(line) or (name in ELLIPSIS_FILES and "…" in line):
                hits.append(f"{name}:{number}: {line.strip()[:80]}")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-placeholders", action="store_true", help="do not fail on template placeholders")
    args = parser.parse_args()
    failed = 0
    for number, (label, check) in enumerate(CHECKS, start=1):
        ok = check()
        failed += 0 if ok else 1
        LOG.info("%s  %02d  %s", "ok " if ok else "NO ", number, label)
    checks_file = next((name for name in LLM_CHECK_FILES if (ROOT / name).is_file()), None)
    for line in llm_checks_report(read(ROOT / "AUDIT-CRITERIA.md"), read(ROOT / checks_file) if checks_file else None, checks_file or "llm_checks.yaml"):
        LOG.info("%s", line)
    left = placeholders()
    for hit in left:
        LOG.info("     placeholder left: %s", hit)
    LOG.info("%d of %d standards in place, %d placeholders left", len(CHECKS) - failed, len(CHECKS), len(left))
    if failed or (left and not args.allow_placeholders):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
