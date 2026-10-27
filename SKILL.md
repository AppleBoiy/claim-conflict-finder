---
name: claim-conflict-finder
description: Reads a set of research papers, extracts each finding as a structured claim (subject, relation, object, direction, metric, dataset, population, method, conditions, quote), then compares claims across papers to find contradictions, null-versus-effect results and effect-size disagreements, explains why the papers likely differ, and produces an interactive evidence-matrix page, a Markdown conflict report and an RDF/Turtle knowledge graph. Use when a student or researcher asks where papers disagree, whether the evidence is consistent, what the debate in a field is, or to check claims across a reading list.
---

# Claim Conflict Finder

Find where the literature disagrees — and, more usefully, **why**. Most "conflicting" papers are not wrong; they studied different populations, datasets, methods or conditions. This skill separates those from the **genuine** conflicts a student should read closely.

Part of the Research Suite. Input is `papers.json` from `paper-scout` (or any list of papers the user supplies); output feeds `research-dossier`. Schema: `references/schema.md`.

## Non-negotiable rules

1. **Extract, don't infer.** A claim must be something the paper states. If a paper only implies it, leave it out.
2. Every claim carries a **verbatim quote of ≤ 25 words** and where it came from (`abstract`, `Table 2`, `Results §4.1`). If you cannot quote it, you cannot claim it.
3. Claims read only from an abstract are capped at `medium` confidence; say so to the user.
4. Never resolve a conflict by guessing which paper is right. Report the difference and what would settle it.

## 1. Get the papers

- If `research/<slug>/papers.json` exists (from `paper-scout`), use papers with `"status": "included"`.
- If the user gives PDFs, DOIs or titles instead, build `papers.json` from them (key, title, authors, year, venue, doi, `"sources": ["user"]`, `"status": "included"`).
- Prefer full text. For each paper, try the `oa_url` (open-access PDF) or the PDFs the user attached. Fall back to the abstract and record `"source_text": "abstract"`.
- With more than ~25 papers, ask whether to cover all of them or the top 15–20; extraction is the slow part.

## 2. Extract claims (the core of the skill)

Read `references/extraction-guide.md` before your first extraction in a session. In short:

For each paper, record its **main findings** — usually 2–6 claims — as entries in `claims.json`:

| Field | What to write |
|---|---|
| `subject` / `object` | The two things being related, in the field's standard terms. *"intermittent fasting"*, *"weight loss"*; *"GNN"*, *"random forest"*. |
| `relation` | Short verb phrase: `increases`, `decreases`, `is associated with`, `outperforms`, `is comparable to`, `predicts`. |
| `direction` | `positive` (increases / improves / outperforms / associated with more), `negative`, `null` (no significant effect or difference), `mixed` (depends on condition **within** the paper — split it into two conditional claims when you can). |
| `metric`, `value`, `comparison_value`, `unit` | The outcome measure and the numbers if reported. Keep numbers as numbers. |
| `dataset`, `population`, `method`, `conditions`, `sample_size` | The context that could change the result. Be specific and consistent across papers: same dataset → same spelling. |
| `statement` | One plain-English sentence a student would understand. |
| `quote`, `evidence`, `source_text`, `confidence` | Proof and provenance. |

Then **normalise names**. Put synonyms in the `aliases` map at the top of `claims.json` (`"IF": "intermittent fasting"`, `"TRE": "time-restricted eating"` only if the user's question treats them as the same thing). The script compares claims by subject + object, so a concept spelled two ways will never be compared. Comparative claims are aligned automatically ("B underperforms A" ≡ "A outperforms B").

## 3. Run the analysis

Standard-library Python, no network. Run it exactly as shipped:

```bash
python3 scripts/conflicts.py check --out research/<slug>   # fix every ERROR it prints
python3 scripts/conflicts.py all   --out research/<slug>   # analyze + map + ttl
```

Outputs in the project folder:

- `conflicts.json` — every topic and every compared pair with `kind`, `severity`, `genuine`, `differences`, `explanation`
- `conflicts.md` — a readable report, most important disagreements first
- `conflict_map.html` — interactive evidence matrix + side-by-side conflict cards (self-contained; opens offline)
- `claims.ttl` — RDF/Turtle graph of papers, claims and concepts with `rs:conflictsWith` / `rs:agreesWith` links, loadable into any triple store or SPARQL tool

If the script prints *"most topics have only one paper"*, your subject/object names are not aligned. Add aliases and re-run — this is normal on the first pass.

How the script judges a pair (so you can explain it):

- **contradiction** — opposite directions. **null-vs-effect** — one finds an effect, one finds none. **magnitude** — same direction, effect sizes differ by more than `--tolerance` (default 50 %). **conditional** — a `mixed` claim. **agreement** — same direction.
- **genuine** — no difference in dataset, population, method, conditions or metric was recorded. These are the ones to read.
- **severity** — contradiction > null-vs-effect > magnitude/conditional; +1 when genuine; −1 when either claim is low confidence.

## 4. Interpret — add the judgement the script cannot

Read `conflicts.md`. For each **genuine** or **high-severity** pair, go back to both papers and look for the real reason. Common ones:

- Different **comparison baseline** or control group
- Different **follow-up length** or **dose**
- **Statistical power** — a small study reporting "no effect" is weak evidence of no effect
- Different **metric definitions** with the same name
- **Publication date** — methods, data or the phenomenon changed
- **Funding / conflict of interest**, retraction, or a later correction
- Preprint vs peer-reviewed

If you find the reason, add it to the relevant claims' `conditions` and re-run so the pair is reclassified, and keep a note for the user.

## 5. Deliver

1. **Bottom line** (3–4 sentences): where the literature agrees, where it is contested, and the single most important open disagreement.
2. **Consensus** — relationships every paper agrees on, with the papers.
3. **Debates** — for each contested relationship: what each side found (Author et al., Year), the likely reason they differ, and what study would settle it.
4. **Genuine conflicts to read** — the 3–5 pairs to read side by side, in priority order.
5. **Files**: `conflict_map.html` (open in a browser — the matrix shows who found what; the cards show why), `conflicts.md`, `claims.json`, `claims.ttl`.
6. **Caveats**: how many claims came from abstracts only, papers you could not access, and that the user should verify each quote before citing.
7. **Next step**: offer `research-dossier` to turn papers + claims + conflicts into a written, visual literature review.

## No terminal

If you cannot run Python, do steps 1–2 the same way, then compare claims by hand using the rules in section 3 and present the matrix as a Markdown table (rows = relationships, columns = papers, cells ▲ ▼ ● ◆). Say that the interactive map and Turtle file need the script.
