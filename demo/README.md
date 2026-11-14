# The cross-check demo

One paper claim, one dataset, one question:

> **Does the paper's claim match the dataset's outliers?**

This is the interaction InsightForge exists for. The paper states a claim about a
field survey; the CSV is that survey. Neither is trusted on its own, and the
answer has to quote both.

## Files

| File | What it is |
|---|---|
| `potato-blight-claim.pdf` | A two-page claim sheet, uploadable as a paper |
| `potato-blight-claim.txt` | The same text with page markers, for reading |
| `potato-blight-field.csv` | 55 plot-hours of the 2021 Kestrel survey |
| `make_demo_assets.py` | Regenerates both files identically |

The claim sheet makes three claims:

1. 12.4% of labelled images carry a wrong lesion score.
2. **71% of the contaminated images were captured between 19:00 and 05:00.**
3. No untreated plot reached 60% lesion coverage, so higher scores are errors.

## Steps

1. Sign in to the console.
2. **Overview → Add a paper**, upload `demo/potato-blight-claim.pdf`, wait for it to index.
3. **Outliers & Anomalies**, upload `demo/potato-blight-field.csv`, then run the
   screen at contamination **0.15**.
4. **Research Chat**, select the claim sheet, and ask:

   > Does the paper's claim match the dataset's outliers?

## What the data actually shows

Measured directly from the shipped CSV with the production screen
(`analytics.detect_outliers`, contamination 0.15, IsolationForest, 200 trees):

- 55 rows, **9 flagged**
- **7 of the 9 are night captures** (19:00–05:00) = **77.8%**
- the highest flagged lesion score is **91.7%**, well past the sheet's 60% ceiling

So the answer is *almost*: the claim's direction holds — contamination really is a
night-time problem in this survey — but the measured share is 77.8%, not 71%,
and the flagged rows include lesion scores the sheet itself calls impossible. A
good answer says that, cites the page the claim came from, and cites the computed
counts rather than inventing a verdict.

The two daytime rows that are also flagged (an impossible 142 t/ha yield and a
3% humidity reading) exist to keep the demo honest: the screen is not simply
re-discovering the capture hour.

## Regenerating

```bash
python demo/make_demo_assets.py
```

The CSV is seeded, so the same rows come back every run.
