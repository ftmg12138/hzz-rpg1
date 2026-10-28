#!/usr/bin/env python3
import json, sys
N = json.load(open("public/data/nodes.json"))
def cond(c): return f" [if {json.dumps(c, ensure_ascii=False)}]" if c else ""
def blocks(bs, ind):
    for b in bs:
        who = f"{b['who']}: " if b.get("who") else ""
        print(f"{ind}({b['t']}) {who}{b.get('text','')}{cond(b.get('cond'))}")
def ch(c, ind):
    extra = []
    for k in ("check","cost","mark","once","group","next","effects","cond_note","fallback"):
        if c.get(k): extra.append(f"{k}={json.dumps(c[k], ensure_ascii=False)}")
    print(f"{ind}* {c['label']}{cond(c.get('cond'))}  " + " ".join(extra))
    blocks(c.get("result", []), ind + "    ")
    for k in ("success", "fail"):
        if c.get(k):
            print(f"{ind}    <{k}> next={c[k].get('next')} eff={json.dumps(c[k].get('effects',[]), ensure_ascii=False)}")
            blocks(c[k]["result"], ind + "        ")
    for s in c.get("sub") or []: ch(s, ind + "    ")
for nid in sys.argv[1:]:
    n = N[nid]
    print(f"=== {nid} {n['title']} kind={n['kind']} default_next={n.get('default_next')} routes={n.get('routes')} enter={n.get('enter_effects')} hub={n.get('hub')}")
    blocks(n["blocks"], "  ")
    for c in n["choices"]: ch(c, "  ")
