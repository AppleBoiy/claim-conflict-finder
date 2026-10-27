#!/usr/bin/env python3
"""claim-conflict-finder: compare structured claims across papers and explain disagreements.

Standard library only. No network access.

Subcommands:
  check     validate claims.json against papers.json and the schema
  analyze   group claims into topics, compare every pair, write conflicts.json + conflicts.md
  map       write conflict_map.html (self-contained visual report)
  ttl       write claims.ttl (RDF/Turtle knowledge graph of papers and claims)
  all       analyze + map + ttl

Data format: see references/schema.md.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0.0"
DIRECTIONS = {"positive", "negative", "null", "mixed"}
CONTEXT = ["dataset", "population", "method", "conditions", "metric"]
SYMMETRIC = {"is associated with", "correlates with", "is correlated with", "co-occurs with",
             "is comparable to", "differs from", "interacts with"}
# negative comparative forms are rewritten to their positive form with the direction flipped,
# so "B underperforms A" and "A outperforms B" land in the same row pointing the same way
POSFORM = {"underperforms": "outperforms", "is worse than": "is better than", "is lower than": "exceeds",
           "is inferior to": "is superior to", "is slower than": "is faster than"}
COMPARATIVE = set(POSFORM.values()) | {"is more effective than", "is more accurate than"}
FLIP = {"positive": "negative", "negative": "positive"}


def log(m: str) -> None:
    print(m, file=sys.stderr)


def load(p: Path) -> dict:
    if not p.exists():
        sys.exit(f"missing {p}")
    return json.loads(p.read_text("utf-8"))


def canon(s, aliases: dict) -> str:
    if s is None:
        return ""
    t = re.sub(r"\s+", " ", str(s).strip().lower())
    t = re.sub(r"[\"'`]", "", t)
    if t in aliases:
        return aliases[t]
    if t.endswith("s") and t[:-1] in aliases:
        return aliases[t[:-1]]
    return t


def plural_fold(t: str) -> str:
    """Fold simple English plurals word by word ("networks" -> "network"), leaving -ss/-us/-is/-ous alone."""
    def one(w: str) -> str:
        if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is", "ics", "sis")):
            return w[:-3] + "y" if w.endswith("ies") else w[:-1]
        return w
    return " ".join(one(w) for w in t.split(" "))


# ----------------------------------------------------------------------------- check

def cmd_check(a) -> int:
    root = Path(a.out)
    papers = {p["key"]: p for p in load(root / "papers.json")["papers"]}
    cl = load(root / "claims.json")
    problems, warnings = [], []
    ids = Counter(c.get("id") for c in cl.get("claims", []))
    for c in cl.get("claims", []):
        cid = c.get("id") or "?"
        if ids[cid] > 1:
            problems.append(f"{cid}: duplicate id")
        if c.get("paper") not in papers:
            problems.append(f"{cid}: paper '{c.get('paper')}' is not in papers.json")
        for f in ("statement", "subject", "relation", "object", "direction"):
            if not c.get(f):
                problems.append(f"{cid}: missing {f}")
        if c.get("direction") and c["direction"] not in DIRECTIONS:
            problems.append(f"{cid}: direction must be one of {sorted(DIRECTIONS)}")
        q = c.get("quote") or ""
        if len(q.split()) > 25:
            problems.append(f"{cid}: quote is {len(q.split())} words (max 25)")
        if not q:
            warnings.append(f"{cid}: no quote — readers cannot locate the evidence")
        if c.get("source_text", "abstract") == "abstract" and c.get("confidence") == "high":
            warnings.append(f"{cid}: high confidence from an abstract only — lowered to medium in analysis")
        for f in ("value", "comparison_value", "sample_size"):
            v = c.get(f)
            if v is not None and not isinstance(v, (int, float)):
                problems.append(f"{cid}: {f} must be a number or null")
    used = {c.get("paper") for c in cl.get("claims", [])}
    inc = [k for k, p in papers.items() if p.get("status") == "included"]
    no_claims = [k for k in inc if k not in used]
    if no_claims:
        warnings.append(f"{len(no_claims)} included papers have no claims: {', '.join(no_claims[:12])}"
                        + (" …" if len(no_claims) > 12 else ""))
    for w in warnings:
        print("warn ", w)
    for p in problems:
        print("ERROR", p)
    print(f"{len(cl.get('claims', []))} claims, {len(problems)} errors, {len(warnings)} warnings")
    return 1 if problems else 0


# ----------------------------------------------------------------------------- analyze

def normalise(c: dict, aliases: dict) -> dict:
    n = dict(c)
    n["_s"] = plural_fold(canon(c.get("subject"), aliases))
    n["_o"] = plural_fold(canon(c.get("object"), aliases))
    n["_r"] = canon(c.get("relation"), {})
    n["_m"] = canon(c.get("metric"), aliases)
    n["_d"] = c.get("direction")
    n["_v"], n["_cv"] = c.get("value"), c.get("comparison_value")
    n["_flip"] = False
    if n["_r"] in POSFORM:
        n["_r"] = POSFORM[n["_r"]]
        n["_d"] = FLIP.get(n["_d"], n["_d"])
        n["_flip"] = True
    if (n["_r"] in SYMMETRIC or n["_r"] in COMPARATIVE) and n["_s"] > n["_o"]:
        n["_s"], n["_o"] = n["_o"], n["_s"]
        if n["_r"] not in SYMMETRIC:
            n["_d"] = FLIP.get(n["_d"], n["_d"])
            n["_v"], n["_cv"] = n["_cv"], n["_v"]
            n["_flip"] = not n["_flip"]
    conf = c.get("confidence") or "medium"
    if c.get("source_text", "abstract") == "abstract" and conf == "high":
        conf = "medium"
    n["_conf"] = conf
    n["_cond"] = sorted({canon(x, aliases) for x in (c.get("conditions") or []) if x})
    return n


def topic_label(n: dict) -> str:
    if n["_r"] in COMPARATIVE or n["_r"] in SYMMETRIC:
        return f"{n['_s']} {n['_r']} {n['_o']}"
    return f"effect of {n['_s']} on {n['_o']}"


def topic_key(n: dict) -> str:
    return f"{n['_s']} | {n['_o']}"


def effect(n: dict):
    v, cv = n.get("_v"), n.get("_cv")
    if isinstance(v, (int, float)) and isinstance(cv, (int, float)):
        return v - cv
    if isinstance(v, (int, float)) and cv is None and n.get("relation", "").lower() in ("increases", "decreases", "reduces", "changes"):
        return v
    return None


def differences(a: dict, b: dict, pa: dict, pb: dict) -> list[str]:
    out = []
    for f in ("dataset", "population", "method"):
        x, y = canon(a.get(f), {}), canon(b.get(f), {})
        if x and y and x != y:
            out.append(f)
        elif bool(x) != bool(y):
            out.append(f + "?")
    if a["_cond"] != b["_cond"] and (a["_cond"] or b["_cond"]):
        out.append("conditions")
    if a["_m"] and b["_m"] and a["_m"] != b["_m"]:
        out.append("metric")
    ya, yb = pa.get("year"), pb.get("year")
    if ya and yb and abs(ya - yb) >= 8:
        out.append("era")
    na, nb = a.get("sample_size"), b.get("sample_size")
    if isinstance(na, (int, float)) and isinstance(nb, (int, float)) and min(na, nb) > 0 and max(na, nb) / min(na, nb) >= 10:
        out.append("sample size")
    if bool(pa.get("is_preprint")) != bool(pb.get("is_preprint")):
        out.append("peer review")
    return out


LABEL = {"dataset": "different datasets", "population": "different populations / settings",
         "method": "different methods or study designs", "conditions": "different experimental conditions",
         "metric": "different outcome metrics", "era": "published ≥8 years apart",
         "sample size": "sample sizes differ ≥10×", "peer review": "one is a preprint",
         "dataset?": "only one reports its dataset", "population?": "only one reports its population",
         "method?": "only one reports its method"}

HARD = {"dataset", "population", "method", "conditions", "metric"}


def compare(a: dict, b: dict, pa: dict, pb: dict, tol: float) -> dict:
    da, db = a["_d"], b["_d"]
    diffs = differences(a, b, pa, pb)
    if "mixed" in (da, db):
        kind = "conditional"
    elif {da, db} == {"positive", "negative"}:
        kind = "contradiction"
    elif "null" in (da, db) and da != db:
        kind = "null-vs-effect"
    else:
        kind = "agreement"
        ea, eb = effect(a), effect(b)
        if ea is not None and eb is not None and max(abs(ea), abs(eb)) > 0:
            rel = abs(ea - eb) / max(abs(ea), abs(eb))
            if rel > tol:
                kind = "magnitude"
    hard = [d for d in diffs if d in HARD]
    genuine = kind not in ("agreement", "conditional") and not hard
    weak = "low" in (a["_conf"], b["_conf"])
    sev = {"contradiction": 3, "null-vs-effect": 2, "conditional": 1, "magnitude": 1, "agreement": 0}[kind]
    if genuine and kind != "agreement":
        sev += 1
    if weak:
        sev -= 1
    severity = ["none", "low", "medium", "high", "high"][max(0, min(4, sev))]
    if kind == "agreement":
        severity = "none"
    return {"a": a["id"], "b": b["id"], "kind": kind, "severity": severity, "genuine": genuine,
            "differences": diffs, "explanation": explain(kind, a, b, pa, pb, diffs, genuine)}


def cite(p: dict) -> str:
    au = (p.get("authors") or ["Anon"])[0].split()[-1] if p.get("authors") else "Anon"
    etal = " et al." if len(p.get("authors") or []) > 1 else ""
    return f"{au}{etal} ({p.get('year') or 'n.d.'})"


def explain(kind, a, b, pa, pb, diffs, genuine) -> str:
    A, B = cite(pa), cite(pb)
    eff, none = (A, B) if b["_d"] == "null" else (B, A)
    cond = A if a["_d"] == "mixed" else B
    head = {
        "contradiction": f"{A} and {B} reach opposite conclusions.",
        "null-vs-effect": f"{eff} finds an effect; {none} finds no significant effect.",
        "magnitude": f"Both point the same way, but the size of the effect differs ({fmt_eff(a)} vs {fmt_eff(b)}).",
        "conditional": f"{cond} reports that the effect depends on conditions, so a single direction does not capture it.",
        "agreement": f"{A} and {B} agree.",
    }[kind]
    if kind == "agreement":
        if diffs and any(d in HARD for d in diffs):
            return head + " The agreement holds across " + ", ".join(LABEL[d] for d in diffs if d in HARD) + ", which strengthens it."
        return head
    if genuine:
        tail = (" No context difference was recorded, so this looks like a genuine disagreement worth reading both papers for"
                + (" (" + ", ".join(LABEL[d] for d in diffs) + ")" if diffs else "") + ".")
    else:
        tail = " Likely explained by " + ", ".join(LABEL[d] for d in diffs if d in LABEL) + "."
    return head + tail


def fmt_eff(n):
    e = effect(n)
    if e is None:
        return "n/a"
    u = f" {n.get('unit')}" if n.get("unit") else ""
    m = f" {n.get('metric')}" if n.get("metric") else ""
    return f"{e:+.3g}{u}{m}"


def analyze(root: Path, tol: float) -> dict:
    pdoc = load(root / "papers.json")
    papers = {p["key"]: p for p in pdoc["papers"]}
    cl = load(root / "claims.json")
    aliases = {canon(k, {}): canon(v, {}) for k, v in (cl.get("aliases") or {}).items()}
    claims = [normalise(c, aliases) for c in cl.get("claims", []) if c.get("paper") in papers]
    groups = defaultdict(list)
    for n in claims:
        groups[topic_key(n)].append(n)
    topics, pairs = [], []
    for key, members in groups.items():
        members.sort(key=lambda n: (papers[n["paper"]].get("year") or 0, n["id"]))
        tp = []
        for x, y in itertools.combinations(members, 2):
            if x["paper"] == y["paper"]:
                continue
            r = compare(x, y, papers[x["paper"]], papers[y["paper"]], tol)
            r["topic"] = key
            tp.append(r)
        kinds = Counter(r["kind"] for r in tp)
        dirs = Counter(n["_d"] for n in members)
        if len({n["paper"] for n in members}) < 2:
            verdict = "single-source"
        elif kinds.get("contradiction") and any(r["genuine"] for r in tp if r["kind"] == "contradiction"):
            verdict = "contested"
        elif kinds.get("contradiction") or kinds.get("null-vs-effect"):
            verdict = "context-dependent"
        elif kinds.get("magnitude") or kinds.get("conditional"):
            verdict = "agree on direction, not size"
        else:
            verdict = "consensus"
        first = members[0]
        topics.append({
            "topic": key, "subject": first["_s"], "object": first["_o"], "relation": first["_r"],
            "label": topic_label(first),
            "claims": [n["id"] for n in members], "papers": sorted({n["paper"] for n in members}),
            "directions": dict(dirs), "verdict": verdict,
            "conflicts": sum(1 for r in tp if r["kind"] != "agreement"),
            "genuine": sum(1 for r in tp if r["genuine"]),
        })
        pairs.extend(tp)
    order = {"contested": 0, "context-dependent": 1, "agree on direction, not size": 2, "consensus": 3, "single-source": 4}
    topics.sort(key=lambda t: (order[t["verdict"]], -len(t["papers"]), t["topic"]))
    sev = {"high": 0, "medium": 1, "low": 2, "none": 3}
    pairs.sort(key=lambda r: (sev[r["severity"]], not r["genuine"], r["topic"]))
    out = {"schema": "research-suite/conflicts@1", "created": _dt.date.today().isoformat(),
           "query": pdoc.get("query", ""), "tolerance": tol, "topics": topics, "pairs": pairs,
           "_claims": {n["id"]: {k: v for k, v in n.items() if not k.startswith("_")} | {
               "direction_canonical": n["_d"], "flipped": n["_flip"], "confidence_used": n["_conf"]} for n in claims}}
    return out


def cmd_analyze(a) -> None:
    root = Path(a.out)
    res = analyze(root, a.tolerance)
    (root / "conflicts.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    write_md(root, res)
    t = res["topics"]
    c = Counter(x["verdict"] for x in t)
    log(f"{len(res['_claims'])} claims → {len(t)} topics: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    real = [p for p in res["pairs"] if p["kind"] != "agreement"]
    log(f"{len(real)} disagreeing pairs, {sum(p['genuine'] for p in real)} genuine; wrote conflicts.json, conflicts.md")
    singles = [x for x in t if x["verdict"] == "single-source"]
    if len(singles) > 0.6 * max(1, len(t)):
        log("hint: most topics have only one paper. Normalise subject/object names with 'aliases' in claims.json "
            "so the same concept is spelled the same way across papers, then re-run.")


def write_md(root: Path, res: dict) -> None:
    papers = {p["key"]: p for p in load(root / "papers.json")["papers"]}
    C = res["_claims"]
    L = [f"# Conflict report", "", f"_Question:_ {res.get('query') or '—'}  ", f"_Generated:_ {res['created']}", ""]
    c = Counter(x["verdict"] for x in res["topics"])
    L += ["| Verdict | Topics |", "|---|---|"] + [f"| {k} | {v} |" for k, v in c.items()] + [""]
    L += ["## Disagreements, most important first", ""]
    for r in [p for p in res["pairs"] if p["kind"] != "agreement"]:
        a, b = C[r["a"]], C[r["b"]]
        L += [f"### {r['topic']} — {r['kind']} ({r['severity']}{', genuine' if r['genuine'] else ''})", "",
              f"- **{r['a']}** {cite(papers[a['paper']])} [@{a['paper']}]: {a['statement']}",
              f"- **{r['b']}** {cite(papers[b['paper']])} [@{b['paper']}]: {b['statement']}",
              f"- **Why they may differ:** {r['explanation']}", ""]
    L += ["## Topics", "", "| Topic | Verdict | Papers | ▲ | ▼ | ● |", "|---|---|---|---|---|---|"]
    for t in res["topics"]:
        d = t["directions"]
        L.append(f"| {t['label']} | {t['verdict']} | {len(t['papers'])} | {d.get('positive', 0)} | {d.get('negative', 0)} | {d.get('null', 0)} |")
    (root / "conflicts.md").write_text("\n".join(L) + "\n", "utf-8")


# ----------------------------------------------------------------------------- map

def cmd_map(a) -> None:
    root = Path(a.out)
    if not (root / "conflicts.json").exists():
        cmd_analyze(a)
    res = load(root / "conflicts.json")
    pdoc = load(root / "papers.json")
    used = {c["paper"] for c in res["_claims"].values()}
    papers = [{"key": p["key"], "title": p.get("title", ""), "year": p.get("year"),
               "authors": (p.get("authors") or [])[:3], "n_authors": len(p.get("authors") or []),
               "venue": p.get("venue", ""), "doi": p.get("doi", ""), "url": p.get("url", ""),
               "preprint": bool(p.get("is_preprint")), "cite": cite(p),
               "short": f"{((p.get('authors') or ['Anon'])[0].split() or ['Anon'])[-1]} {p.get('year') or ''}".strip()}
              for p in pdoc["papers"] if p["key"] in used]
    papers.sort(key=lambda p: (p["year"] or 0, p["key"]))
    payload = {"title": a.title or pdoc.get("query") or "Where the literature disagrees", "generated": res["created"],
               "query": pdoc.get("query", ""), "papers": papers, "topics": res["topics"], "pairs": res["pairs"],
               "claims": res["_claims"]}
    tpl = load_template("conflict_map.html")
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    (root / "conflict_map.html").write_text(
        tpl.replace("/*__DATA__*/null", data).replace("__TITLE__", html.escape(payload["title"])), "utf-8")
    log(f"wrote conflict_map.html ({len(res['topics'])} topics × {len(papers)} papers)")


# ----------------------------------------------------------------------------- ttl

def ttl_str(s) -> str:
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{s}"'


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "x"


def cmd_ttl(a) -> None:
    root = Path(a.out)
    pdoc = load(root / "papers.json")
    cl = load(root / "claims.json")
    aliases = {canon(k, {}): canon(v, {}) for k, v in (cl.get("aliases") or {}).items()}
    L = ["@prefix rs: <https://w3id.org/research-suite/vocab#> .",
         "@prefix ex: <https://w3id.org/research-suite/data/> .",
         "@prefix dct: <http://purl.org/dc/terms/> .",
         "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", "",
         "rs:Paper a <http://www.w3.org/2002/07/owl#Class> .",
         "rs:Claim a <http://www.w3.org/2002/07/owl#Class> .",
         "rs:Concept a <http://www.w3.org/2002/07/owl#Class> .", ""]
    concepts = set()
    keys = set()
    for p in pdoc["papers"]:
        if p.get("status") == "excluded":
            continue
        keys.add(p["key"])
        L.append(f"ex:paper_{slug(p['key'])} a rs:Paper ;")
        L.append(f"  dct:title {ttl_str(p.get('title', ''))} ;")
        if p.get("year"):
            L.append(f'  dct:date "{p["year"]}"^^xsd:gYear ;')
        if p.get("doi"):
            L.append(f"  rs:doi {ttl_str(p['doi'])} ;")
        for r in p.get("references", []):
            L.append(f"  rs:cites ex:paper_{slug(r)} ;")
        L.append(f"  rs:citationKey {ttl_str(p['key'])} .")
        L.append("")
    for c in cl.get("claims", []):
        if c.get("paper") not in keys:
            continue
        s, o = canon(c.get("subject"), aliases), canon(c.get("object"), aliases)
        concepts |= {s, o}
        L.append(f"ex:claim_{slug(c['id'])} a rs:Claim ;")
        L.append(f"  rs:statedIn ex:paper_{slug(c['paper'])} ;")
        L.append(f"  rs:subject ex:concept_{slug(s)} ;")
        L.append(f"  rs:predicate {ttl_str(c.get('relation', ''))} ;")
        L.append(f"  rs:object ex:concept_{slug(o)} ;")
        L.append(f"  rs:direction rs:{c.get('direction', 'mixed')} ;")
        for f in ("metric", "dataset", "population", "method", "unit"):
            if c.get(f):
                L.append(f"  rs:{f} {ttl_str(c[f])} ;")
        for f in ("value", "comparison_value", "sample_size"):
            if isinstance(c.get(f), (int, float)):
                L.append(f'  rs:{f} "{c[f]}"^^xsd:decimal ;')
        for cond in c.get("conditions") or []:
            L.append(f"  rs:condition {ttl_str(cond)} ;")
        L.append(f"  rs:statement {ttl_str(c.get('statement', ''))} .")
        L.append("")
    for s in sorted(concepts):
        L.append(f"ex:concept_{slug(s)} a rs:Concept ; dct:title {ttl_str(s)} .")
    if (root / "conflicts.json").exists():
        L.append("")
        for i, r in enumerate(load(root / "conflicts.json")["pairs"]):
            if r["kind"] == "agreement":
                L.append(f"ex:claim_{slug(r['a'])} rs:agreesWith ex:claim_{slug(r['b'])} .")
            else:
                L.append(f"ex:claim_{slug(r['a'])} rs:conflictsWith ex:claim_{slug(r['b'])} .")
    (root / "claims.ttl").write_text("\n".join(L) + "\n", "utf-8")
    log(f"wrote claims.ttl ({len(cl.get('claims', []))} claims, {len(concepts)} concepts)")


def cmd_all(a) -> None:
    if cmd_check(a):
        sys.exit("fix the errors above, then run again")
    cmd_analyze(a)
    cmd_map(a)
    cmd_ttl(a)


def load_template(name: str) -> str:
    emb = globals().get("EMBEDDED_TEMPLATES", {})
    if name in emb:
        return emb[name]
    return (Path(__file__).resolve().parent.parent / "assets" / name).read_text("utf-8")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="conflicts.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in [("check", cmd_check, "validate claims.json"),
                            ("analyze", cmd_analyze, "compare claims, write conflicts.json/md"),
                            ("map", cmd_map, "write conflict_map.html"),
                            ("ttl", cmd_ttl, "write claims.ttl"),
                            ("all", cmd_all, "check + analyze + map + ttl")]:
        s = sub.add_parser(name, help=help_)
        s.add_argument("--out", default="research", help="project folder with papers.json and claims.json")
        s.add_argument("--tolerance", type=float, default=0.5,
                       help="relative effect-size difference that counts as a magnitude disagreement")
        s.add_argument("--title")
        s.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    r = a.fn(a)
    if isinstance(r, int):
        sys.exit(r)


if __name__ == "__main__":
    main()
