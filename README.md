# Claim Conflict Finder

See where research papers disagree — and whether different datasets, populations or methods explain it.

A free, open-source [agent skill](https://www.agensi.io/learn/skill-md-format) (SKILL.md) for students and researchers. Works with Claude Code, Codex CLI, Cursor, Gemini CLI and any agent that supports the SKILL.md standard.

## What it does

1. The agent reads each paper and records its main findings as **structured claims**: subject, relation, object, direction (▲ ▼ ● ◆), metric and values, dataset, population, method, conditions, a ≤25-word verbatim quote and where it came from.
2. `scripts/conflicts.py` aligns equivalent claims (synonyms via `aliases`, plurals, and "B underperforms A" ≡ "A outperforms B"), compares every pair across papers and labels it **contradiction**, **null-vs-effect**, **magnitude**, **conditional** or **agreement**.
3. Each disagreement is marked **genuine** (same setup, different answer — read both papers) or **explained** by a recorded context difference, with a plain-English explanation and a severity.

## Outputs

| File | What it is |
|---|---|
| `conflict_map.html` | Interactive evidence matrix (relationships × papers) and side-by-side conflict cards. Offline, light/dark, mobile-friendly. |
| `conflicts.md` | Readable report, most important disagreements first |
| `conflicts.json` | Every topic and compared pair, machine-readable |
| `claims.ttl` | RDF/Turtle knowledge graph of papers, claims and concepts with `rs:conflictsWith` / `rs:agreesWith` — load it into any triple store and query with SPARQL |

```bash
python3 scripts/conflicts.py check --out research/<slug>
python3 scripts/conflicts.py all   --out research/<slug>
```

See [`references/extraction-guide.md`](references/extraction-guide.md) for how claims are extracted.

## Network

None. Reads and writes only inside the `--out` folder.

## Part of the Research Suite

Three free, open-source agent skills that chain through one shared data format ([`references/schema.md`](references/schema.md)):

| Step | Skill | What it does |
|---|---|---|
| 1 | [paper-scout](https://github.com/AppleBoiy/paper-scout) | Finds real papers, ranks them, draws a citation map, writes BibTeX |
| 2 | [claim-conflict-finder](https://github.com/AppleBoiy/claim-conflict-finder) | Extracts findings as claims and shows where and why papers disagree |
| 3 | [research-dossier](https://github.com/AppleBoiy/research-dossier) | Writes a visual, citation-checked literature review |

Each skill also works on its own.

## Install

**Any agent through Agensi** — search for `claim-conflict-finder` on [agensi.io](https://www.agensi.io) and add it (free).

**Claude Code**

```bash
git clone https://github.com/AppleBoiy/claim-conflict-finder.git ~/.claude/skills/claim-conflict-finder
```

**Other SKILL.md agents** (Codex CLI, Cursor, Gemini CLI, …) — clone the repo into the agent's skills folder. The agent reads `SKILL.md`; the scripts need Python 3.9+ and nothing else.

Then just ask, e.g. *"Using my reading list, where do these papers disagree about intermittent fasting and insulin sensitivity?"*

## Development

```bash
python3 -m unittest discover -s tests -v   # offline tests, no network needed
python3 tools/package.py                    # builds dist/claim-conflict-finder.zip for Agensi (templates embedded into the script)
```

`assets/` holds the HTML template(s); `scripts/` loads them from there during development, and the packaged zip embeds them so the script runs as a single file.

## License

MIT © [Chaipat Jainan](https://www.chaipat.cc). Issues and pull requests welcome.
