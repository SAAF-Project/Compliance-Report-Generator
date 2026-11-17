"""Build the ISO/IEC JTC 1/SC 42 (artificial intelligence) standards catalogue.

Reads the ISO Open Data deliverables export (one JSON object per line), keeps
the deliverables owned by ISO/IEC JTC 1/SC 42 that are published or under
development, and writes ``saaf/knowledge/standards_data/ISO_IEC_SC42.json``.
Withdrawn (95.99) and deleted (xx.98) projects are left out, which matches the
committee catalogue on iso.org with "published" and "under development"
selected (issue #55).

Standard library only. Run from the repository root:

    python -I tools/standards_sources/iso_sc42.py            # download the export
    python -I tools/standards_sources/iso_sc42.py FILE.jsonl  # use a local copy

The export is about 80 MB. Regenerate the data through a pull request and
review the diff: stages change often.
"""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = REPO_ROOT / "saaf" / "knowledge" / "standards_data" / "ISO_IEC_SC42.json"
SOURCE = (
    "https://isopublicstorageprod.blob.core.windows.net/opendata/_latest/"
    "iso_deliverables_metadata/json/iso_deliverables_metadata.jsonl"
)
CATALOGUE = "https://www.iso.org/committee/6794475/x/catalogue/p/1/u/1/w/0/d/0"
COMMITTEE = "ISO/IEC JTC 1/SC 42"
USER_AGENT = "Mozilla/5.0 (compatible; SAAF-standards-catalogue-builder/1.0)"


def status(stage: int) -> str | None:
    """'published', 'under development', or None for withdrawn/deleted projects."""
    if stage == 9599 or stage % 100 == 98:
        return None
    return "published" if stage >= 6060 else "under development"


def stage_code(stage: int) -> str:
    return f"{stage // 100:02d}.{stage % 100:02d}"


def build(lines) -> list[dict]:
    rows = []
    for line in lines:
        if COMMITTEE not in line:  # cheap pre-filter on an 80 MB file
            continue
        rec = json.loads(line)
        if rec.get("ownerCommittee") != COMMITTEE:
            continue
        st = status(rec["currentStage"])
        if st is None:
            continue
        rows.append({
            "reference": rec["reference"],
            "title": rec["title"]["en"].strip(),
            "type": rec["deliverableType"],
            "stage": stage_code(rec["currentStage"]),
            "status": st,
            "publication_date": rec.get("publicationDate"),
            # 90.92: published, but a revision has been started
            "under_revision": rec["currentStage"] == 9092,
        })
    rows.sort(key=lambda r: (r["status"] != "published", r["reference"]))
    return rows


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        path = Path(argv[1])
    else:
        tmp = Path(tempfile.mkdtemp(prefix="iso_opendata_")) / "deliverables.jsonl"
        req = urllib.request.Request(SOURCE, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)
        path = tmp
    with path.open(encoding="utf-8") as fh:
        standards = build(fh)
    if not standards:
        raise SystemExit(f"no {COMMITTEE} deliverables found in {path}")
    data = {
        "committee": COMMITTEE,
        "committee_title": "Artificial intelligence",
        "catalogue": CATALOGUE,
        "source": SOURCE,
        "retrieved_on": date.today().isoformat(),
        "retrieval_method": "tools/standards_sources/iso_sc42.py",
        "standards": standards,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    published = sum(s["status"] == "published" for s in standards)
    print(f"wrote {OUT_FILE.relative_to(REPO_ROOT)}: {len(standards)} deliverables "
          f"({published} published, {len(standards) - published} under development)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
