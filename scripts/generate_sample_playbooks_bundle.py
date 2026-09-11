"""Zip the sample playbook Markdown files for download from Settings.

The source .md files live in data/sample_templates/playbooks/ and are tuned
to the planted scenario in data/sample_templates/opsmind_sample_data.zip
(SAMPLE-1001 stockout, ValueLine Shipping carrier delay, SAMPLE-1002 returns
spike, SAMPLE-1004 flash sale) — upload the CSV bundle first, then these SOPs,
to get grounded playbook citations alongside the SQL evidence.

Run:
    python -m scripts.generate_sample_playbooks_bundle
"""

from __future__ import annotations

import zipfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_templates" / "playbooks"
OUT_ZIP = Path(__file__).resolve().parents[1] / "data" / "sample_templates" / "opsmind_sample_playbooks.zip"


def main() -> None:
    md_files = sorted(SRC_DIR.glob("*.md"))
    if not md_files:
        raise SystemExit(f"No .md files found in {SRC_DIR}")

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in md_files:
            zf.write(f, arcname=f.name)

    print(f"[generate_sample_playbooks_bundle] wrote {OUT_ZIP} ({len(md_files)} playbooks)")
    for f in md_files:
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
