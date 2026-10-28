#!/usr/bin/env python3
"""Lint public/data/nodes.json for leaked markup and structural problems.

Works on both the v1 schema (text/success_text/...) and the v2 schema (blocks/result/...).
Exit code 1 if any hard failures.  Usage: lint-nodes.py [nodes.json] [--json out.json] [-v]
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
args = [a for a in sys.argv[1:] if not a.startswith("-")]
path = Path(args[0]) if args else ROOT / "public/data/nodes.json"
VERBOSE = "-v" in sys.argv
nodes = json.loads(path.read_text(encoding="utf-8"))
STARTS = ["E-PRO-01", "L-PRO-01", "T-PRO-01"]
SPECIAL = {"__SELF__", "__RETURN__", "__TITLE__", "__ENDING__", None, ""}

LEAKS = {
    "bold **": re.compile(r"\*\*"),
    "heading #": re.compile(r"(^|\n)\s*#+"),
    "〔〕 annotation": re.compile(r"[〔〕]"),
    "arrow →": re.compile(r"→"),
    "backtick": re.compile(r"`"),
    "= true/false": re.compile(r"=\s*(true|false)"),
    "rel.": re.compile(r"rel\."),
    "DC n": re.compile(r"DC\s*\d"),
    "stat abbrev": re.compile(r"(?<![A-Za-z])(STR|DEX|CON|CHA|INS|WIL)(?![A-Za-z])"),
    "node id": re.compile(r"[A-Z][A-Z0-9]*-[A-Z0-9-]*\d"),
    "ascii identifier": re.compile(r"[A-Za-z_]{2,}"),
    "bullet dash": re.compile(r"(^|\n)\s*-\s"),
    "list numbering": re.compile(r"(^|\n)\s*\d+\.\s"),
    # prose-quality heuristics: dangling clauses / designer voice left by stripping
    "dangling clause": re.compile(r"(否则|则|仅|使|与|且|或|并|但|取得|获得|得到|并获得|可|将)[。，；]?$|(取得|获得|得到)\s*[与和、，。；]|，[，。]|^[，。；、]"),
    "designer voice": re.compile(r"玩家|解锁|检定|判定|节点|标记为|写入|记为|关系值|优势|劣势|修正|属性|结算|触发|状态栏|系统|后日谈|自动成功|占\s*\d+\s*格|一格|界面|变量|开发键"),
    "dc number": re.compile(r"[降升]至\s*\d+"),
    "outcome prefix": re.compile(r"^(成功|失败|大成功|关键失败)"),
}

stats = Counter()
examples = defaultdict(list)

def leak(where, s):
    if not isinstance(s, str) or not s:
        return
    for name, rx in LEAKS.items():
        n = len(rx.findall(s))
        if n:
            stats[name] += n
            if len(examples[name]) < 6:
                examples[name].append(f"{where}: {s[:90]!r}")

def is_v2(n):
    return "blocks" in n

# ---- display strings ----
def v1_strings(nid, n):
    yield f"{nid}.title", n.get("title")
    yield f"{nid}.text", n.get("text")
    for i, c in enumerate(n.get("choices") or []):
        # v1 UI rendered "num." + label + raw check hint
        ck = c.get("check")
        hint = ""
        if ck:
            hint = f" {ck.get('stat') or '/'.join(ck.get('stats') or [])} DC {ck.get('dc')}"
        yield f"{nid}.c{i}.label", f"{c.get('num')}. {c.get('label')}{hint}"
        for k in ("success_text", "fail_text"):
            yield f"{nid}.c{i}.{k}", c.get(k)
        for f in c.get("flavor") or []:
            yield f"{nid}.c{i}.flavor", f
        for j, s in enumerate(c.get("subchoices") or []):
            yield f"{nid}.c{i}.s{j}.label", s.get("label")

def blocks_strings(where, blocks):
    for b in blocks or []:
        yield where, b.get("text")
        if b.get("who"):
            yield where + ".who", b.get("who")

def v2_choice_strings(where, c):
    yield where + ".label", c.get("label")
    yield where + ".group", c.get("group")
    if c.get("mark"):
        yield where + ".mark", c["mark"].get("suffix")
    if c.get("tag"):
        yield where + ".tag", c.get("tag")
    yield from blocks_strings(where + ".result", c.get("result"))
    for k in ("success", "fail"):
        if c.get(k):
            yield from blocks_strings(f"{where}.{k}", c[k].get("result"))
    for j, s in enumerate(c.get("sub") or []):
        yield from v2_choice_strings(f"{where}.s{j}", s)

def v2_strings(nid, n):
    yield f"{nid}.title", n.get("title")
    yield from blocks_strings(f"{nid}.blocks", n.get("blocks"))
    for i, c in enumerate(n.get("choices") or []):
        yield from v2_choice_strings(f"{nid}.c{i}", c)
    if n.get("hub") and n["hub"].get("advance"):
        yield f"{nid}.hub", n["hub"]["advance"].get("label")

# ---- structure ----
struct = Counter()
sexamples = defaultdict(list)
def sfail(kind, msg):
    struct[kind] += 1
    if len(sexamples[kind]) < 8:
        sexamples[kind].append(msg)

def has_text(blocks):
    return any((b.get("text") or "").strip() for b in blocks or [])

def targets_of(n):
    out = set()
    def walk(c):
        for k in ("next", "call"):
            out.add(c.get(k))
        for e in c.get("effects") or []:
            if e.get("k") == "ending":
                out.add(e.get("v"))
        for k in ("success", "fail"):
            if c.get(k):
                out.add(c[k].get("next")); out.add(c[k].get("call"))
                for e in c[k].get("effects") or []:
                    if e.get("k") == "ending":
                        out.add(e.get("v"))
        for s in c.get("sub") or c.get("subchoices") or []:
            walk(s)
    for c in n.get("choices") or []:
        walk(c)
    out.add(n.get("default_next"))
    if n.get("hub") and n["hub"].get("advance"):
        out.add(n["hub"]["advance"].get("next"))
    for t in n.get("calls") or []:
        out.add(t)
    for r in n.get("routes") or []:
        out.add(r.get("next"))
    for t in n.get("ambients") or []:
        out.add(t)
    if any(c.get("travel") for c in n.get("choices") or []):
        out.update(k for k, v in nodes.items() if k.startswith("R-"))
    return {t for t in out if t not in SPECIAL}

for nid, n in nodes.items():
    strings = v2_strings(nid, n) if is_v2(n) else v1_strings(nid, n)
    for where, s in strings:
        leak(where, s)
    ending = n.get("kind") == "ending"
    chs = n.get("choices") or []
    if not ending and not chs and not n.get("default_next"):
        sfail("dead-end node (no choices)", nid)
    if is_v2(n):
        if not has_text(n.get("blocks")):
            sfail("node without narration", nid)
        for i, c in enumerate(chs):
            lab = c.get("label") or ""
            if not lab.strip():
                sfail("empty label", f"{nid}.c{i}")
            if re.search(r"\d+\.\s*\S.*\d+\.", lab) or re.match(r"^\s*\d+\.", lab):
                sfail("numbering artifact in label", f"{nid}.c{i}: {lab}")
            stays = c.get("next") in (None, "__SELF__")
            if c.get("check"):
                for k in ("success", "fail"):
                    if not has_text((c.get(k) or {}).get("result")) and not has_text(c.get("result")):
                        sfail(f"check without {k} text", f"{nid}.c{i}: {lab}")
            elif stays and not has_text(c.get("result")) and not c.get("sub") and not c.get("call"):
                sfail("empty result text", f"{nid}.c{i}: {lab}")
        for u in n.get("unparsed") or []:
            sfail("unparsed line", f"{nid}: {u[:80]}")
    else:
        for i, c in enumerate(chs):
            if c.get("next") in (None, "") and not (c.get("success_text") or c.get("fail_text")):
                sfail("empty result text", f"{nid}.c{i}: {c.get('label')}")
            if re.search(r"\d+\.\s*\S.*\d+\.", c.get("label") or ""):
                sfail("numbering artifact in label", f"{nid}.c{i}")
        # v1 dumped blank effect bullets into text
        for m in re.finditer(r"(^|\n)\s*-\s*(\n|$)", n.get("text") or ""):
            sfail("empty bullet (lost content)", nid)
    for t in targets_of(n):
        if t not in nodes:
            sfail("dangling target", f"{nid} → {t}")

# reachability
seen, stack = set(), [s for s in STARTS if s in nodes]
try:
    _meta = json.load(open(Path(path).with_name("meta.json"), encoding="utf-8"))
    FAIL_SEEDS = [r["node"] for r in _meta.get("fail_rules", [])] + [_meta[k]["node"] for k in ("curse_fail", "wound_fail") if k in _meta]
except Exception:
    FAIL_SEEDS = []
stack += [f for f in FAIL_SEEDS if f in nodes]
pools = {}
for nid, n in nodes.items():
    for p in n.get("pools") or []:
        pools.setdefault(p, []).append(nid)
while stack:
    x = stack.pop()
    if x in seen:
        continue
    seen.add(x)
    n = nodes[x]
    nxt = set(targets_of(n))
    for p in n.get("random_pools") or []:
        nxt |= set(pools.get(p, []))
    stack.extend(t for t in nxt if t in nodes and t not in seen)
unreach = sorted(set(nodes) - seen)
for u in unreach:
    sfail("unreachable node", u)

# Critical story settlements that must grant currency (regression guards)
def _effects_grant_vouchers(effs):
    for e in effs or []:
        if e.get("op") == "add" and e.get("k") == "vouchers" and int(e.get("v") or 0) > 0:
            return True
        if _effects_grant_vouchers(e.get("ops") or e.get("effects")):
            return True
    return False

SETTLEMENT_VOUCHERS = {
    "E-PRO-05": "玛拉护送费结算必须发放商会券",
}
for nid, why in SETTLEMENT_VOUCHERS.items():
    n = nodes.get(nid)
    if not n:
        sfail("missing settlement node", f"{nid}: {why}")
        continue
    ok = _effects_grant_vouchers(n.get("enter_effects"))
    if not ok:
        for c in n.get("choices") or []:
            if _effects_grant_vouchers(c.get("effects")):
                ok = True; break
            for ce in c.get("cond_effects") or []:
                if _effects_grant_vouchers(ce.get("ops") or ce.get("effects")):
                    ok = True; break
    if not ok:
        sfail("settlement missing vouchers grant", f"{nid}: {why}")

endings_reach = sorted(x for x in seen if nodes[x].get("kind") == "ending")
total_leaks = sum(stats.values())
print(f"lint {path.name}: {len(nodes)} nodes, schema={'v2' if any(is_v2(n) for n in nodes.values()) else 'v1'}")
print(f"  RAW-MARKUP LEAKS: {total_leaks}")
for k, v in stats.most_common():
    print(f"    {k:22s} {v}")
    if VERBOSE:
        for e in examples[k]:
            print("        ", e)
print(f"  STRUCTURAL: {sum(struct.values())}")
for k, v in struct.most_common():
    print(f"    {k:30s} {v}")
    if VERBOSE:
        for e in sexamples[k]:
            print("        ", e)
print(f"  reachable endings: {len(endings_reach)}")
if "--json" in sys.argv:
    out = sys.argv[sys.argv.index("--json") + 1]
    Path(out).write_text(json.dumps({"leaks": dict(stats), "total_leaks": total_leaks,
        "structural": dict(struct), "examples": examples, "sexamples": sexamples}, ensure_ascii=False, indent=1))
sys.exit(1 if total_leaks or struct else 0)
