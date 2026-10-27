# Claim extraction guide

A good claim set is small, specific and comparable. Aim for 2–6 claims per paper — the findings the abstract and conclusion lead with, plus any result that speaks directly to the user's research question.

## Where to read

1. Abstract — main findings, but often without context or numbers.
2. Results tables and figures — the numbers, the comparison group, the metric.
3. Methods — dataset, population, design, sample size, conditions.
4. Discussion / limitations — conditions under which the finding does not hold.

Record `source_text: "full-text"` only if you actually read beyond the abstract.

## What counts as one claim

One subject, one relation, one object, one direction, under one set of conditions.

| Paper says | Claims |
|---|---|
| "Model X beats Y on accuracy and F1 on both datasets" | One claim per metric if the user cares about both; otherwise the headline metric. Datasets go in `dataset` (one claim per dataset if results differ). |
| "Exercise reduced depression scores in adolescents but not adults" | Two claims: adolescents → `negative`; adults → `null`. Not one `mixed` claim. |
| "We found a trend toward improvement (p = 0.08)" | `direction: "null"` with the note in `conditions: ["trend p=0.08"]`. Non-significant is null. |
| "Prior work has shown A causes B" | Not this paper's claim. Skip it (or attribute it to the cited paper if that paper is in the set). |

## Direction cheat sheet

| Wording | relation | direction |
|---|---|---|
| A increases / improves / raises B | increases | positive |
| A reduces / lowers / impairs B | decreases | negative |
| A is associated with higher B | is associated with | positive |
| A has no significant effect on B | affects | null |
| A outperforms / beats B | outperforms | positive |
| A performs worse than B | underperforms | negative (auto-aligned) |
| A and B perform comparably | is comparable to | null |
| Effect of A on B depends on C | affects | mixed — prefer splitting by C |

For a decrease that is *good* (lower error, less pain), still use `decreases` + `negative`; the direction describes the number, not whether it is desirable. Say which way is better in `metric` if it is not obvious, e.g. `"RMSE (lower is better)"`.

## Context fields — be consistent

The analysis decides whether a conflict is "explained" by comparing context fields as text. Use the same spelling for the same thing across papers:

- `dataset`: the benchmark or cohort name, e.g. `"MIMIC-IV"`, `"ImageNet-1k"`, `"UK Biobank"`.
- `population`: who or what was studied, e.g. `"adults with obesity"`, `"low-resource languages"`.
- `method`: study design or model family, e.g. `"RCT"`, `"cohort"`, `"meta-analysis"`, `"fine-tuned transformer"`.
- `conditions`: short tags, e.g. `["12 weeks", "no pretraining", "scaffold split"]`.

Leave a field empty rather than guessing.

## Confidence

- `high` — clear statement with numbers, from full text, adequately powered.
- `medium` — clear statement from abstract only, or no numbers.
- `low` — hedged language ("may", "suggests"), small or pilot sample, secondary outcome, or preprint.

## Quotes

Copy exactly, ≤ 25 words, no ellipsis inside. The quote is how a student finds the passage, so prefer the sentence with the number.

## Worked example (illustrative text, not a real paper)

> Abstract sentence: "In this 12-month randomized trial of 96 adults with obesity, alternate-day fasting did not produce greater weight loss than daily calorie restriction (−6.0 vs −5.3 kg; p = 0.41)."

```json
{
  "id": "C014",
  "paper": "example2020alternate",
  "statement": "Alternate-day fasting did not lose more weight than daily calorie restriction over 12 months.",
  "subject": "alternate-day fasting",
  "relation": "is comparable to",
  "object": "daily calorie restriction",
  "direction": "null",
  "metric": "weight change (kg)",
  "value": -6.0,
  "comparison_value": -5.3,
  "unit": "kg",
  "dataset": "",
  "population": "adults with obesity",
  "method": "RCT",
  "conditions": ["12 months"],
  "sample_size": 96,
  "evidence": "abstract",
  "quote": "did not produce greater weight loss than daily calorie restriction",
  "source_text": "abstract",
  "confidence": "medium"
}
```

Note the choices: "did not produce greater" with p = 0.41 is `null`, not `negative`; the numbers are kept even though the result is null; confidence is `medium` because only the abstract was read.
