"""Regenerate the demo's uploadable assets.

    python demo/make_demo_assets.py

Writes `potato-blight-claim.pdf` (the claim sheet, one page per `=== PAGE n ===`
marker) and `potato-blight-field.csv` (a seeded field survey whose outliers are
the ones the claim sheet talks about). Re-running produces identical files.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
CLAIM_TEXT = HERE / "potato-blight-claim.txt"
CLAIM_PDF = HERE / "potato-blight-claim.pdf"
FIELD_CSV = HERE / "potato-blight-field.csv"

PLOTS = ["K1-North", "K1-South", "K2-East", "K2-West"]
HEADER = [
    "row_id",
    "plot_id",
    "capture_hour",
    "lesion_score_pct",
    "leaf_temp_c",
    "humidity_pct",
    "ndvi",
    "yield_t_ha"
]


def build_pdf() -> None:
    raw = CLAIM_TEXT.read_text(encoding="utf-8")
    pages = [part.strip() for part in raw.split("=== PAGE")[1:]]
    document = fitz.open()
    for part in pages:
        page = document.new_page()
        body = part.split("===", 1)[1].strip() if "===" in part else part
        page.insert_textbox(
            fitz.Rect(56, 56, 540, 786),
            body,
            fontsize=10.5,
            fontname="helv",
            lineheight=1.35
        )
    document.save(CLAIM_PDF)
    document.close()
    print(f"wrote {CLAIM_PDF.name} ({len(pages)} pages)")


def build_csv() -> None:
    random.seed(20261114)
    rows: list[list] = []
    row_id = 1

    # 46 ordinary plot-hours: daytime capture, plausible agronomy.
    for index in range(46):
        hour = random.choice([8, 9, 10, 11, 12, 13, 14, 15, 16, 17])
        lesion = round(random.uniform(2.0, 18.0), 1)
        temp = round(random.uniform(18.0, 27.0), 1)
        humidity = round(random.uniform(58.0, 84.0), 1)
        ndvi = round(random.uniform(0.55, 0.82), 3)
        yield_t = round(random.uniform(38.0, 52.0), 1)
        rows.append(
            [row_id, PLOTS[index % 4], hour, lesion, temp, humidity, ndvi, yield_t]
        )
        row_id += 1

    # Seven night captures with implausible lesion scores: the pattern the claim
    # sheet points at.
    for index in range(7):
        hour = random.choice([21, 22, 23, 0, 1, 2, 3])
        lesion = round(random.uniform(62.0, 96.0), 1)
        humidity = round(random.uniform(93.0, 99.0), 1)
        rows.append(
            [
                row_id,
                PLOTS[index % 4],
                hour,
                lesion,
                round(random.uniform(12.0, 16.0), 1),
                humidity,
                round(random.uniform(0.30, 0.45), 3),
                round(random.uniform(30.0, 38.0), 1)
            ]
        )
        row_id += 1

    # Two daytime rows that are wrong for a different reason, so the night-time
    # claim is tested rather than assumed: one impossible yield, one dry sensor.
    rows.append([row_id, "K2-East", 11, 12.5, 22.0, 61.0, 0.71, 142.0])
    row_id += 1
    rows.append([row_id, "K1-South", 14, 9.0, 24.5, 3.0, 0.66, 47.0])

    lines = [",".join(HEADER)]
    lines += [",".join(str(value) for value in row) for row in rows]
    FIELD_CSV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {FIELD_CSV.name} ({len(rows)} rows)")


if __name__ == "__main__":
    build_pdf()
    build_csv()
