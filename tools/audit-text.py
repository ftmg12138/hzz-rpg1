"""Second-pass text audit: designer-voice and broken-sentence heuristics."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N = json.loads((ROOT / "public/data/nodes.json").read_text(encoding="utf-8"))
PATS = {
    "unbalanced": None,
    "no terminal punct": re.compile(r"[^。！？…”」』）\)—～~!?\.》]$"),
    "designer words": re.compile(r"你可[在选]|可选择|玩家|角色(?!们)|这一点很重要|体力上限|永久|随机|一项|点体力|检定|判定|优势|劣势|回合|敌人：|防御\s*\d|倒计时|触发|解锁|选项|分支|节点|属性|DC|HP|DR|\d+\s*点|获得\s*\d|失去\s*\d|阶段|上限|奖励|惩罚|计数|进度"),
    "dangling": re.compile(r"[，、：；（“「]$|^[，。、；：）”」]"),
    "suspect": re.compile(r"奖励|线索。$|^代价：|按主角|可见|标志|候选|若[^，。]{0,12}[，：]|进入候选|提供.{0,6}(便利|线索)|不描写|此选择|本身不|可迫使|即。|必开|全员|同伴受|所有人受|受\s*\d|行动。|额外获得|消耗|耗时|一格|半格|时间格|指数|共鸣值|真相值|声望|关系[+-]|城市行动|自由选择|不恶化|存活增加"),
    "fallback 你决定": re.compile(r"^你决定："),
}
PAIRS = [("（", "）"), ("“", "”"), ("「", "」"), ("(", ")")]
def texts(n):
    for i, b in enumerate(n.get("blocks", [])):
        if b.get("t") != "h": yield f"b{i}", b.get("text", "")
    st = [(c, c["id"]) for c in n.get("choices", [])]
    while st:
        c, p = st.pop()
        yield p + ".label", c.get("label", "")
        for nm, src in (("r", c), ("ok", c.get("success") or {}), ("ko", c.get("fail") or {})):
            for j, b in enumerate(src.get("result") or []):
                yield f"{p}.{nm}{j}", b.get("text", "")
        st += [(s, p + "/" + s["id"]) for s in c.get("sub") or []]
hits = {k: [] for k in PATS}
for nid, n in N.items():
    for path, t in texts(n):
        t = t.strip()
        if not t: continue
        if any(t.count(a) != t.count(b) for a, b in PAIRS): hits["unbalanced"].append((nid, path, t))
        for k, rx in PATS.items():
            if rx is None: continue
            if k == "no terminal punct" and path.endswith(".label"): continue
            if rx.search(t): hits[k].append((nid, path, t))
for k, v in hits.items():
    print(f"{k:20s} {len(v)}")
if "-v" in sys.argv:
    want = sys.argv[sys.argv.index("-v") + 1] if len(sys.argv) > sys.argv.index("-v") + 1 else None
    for k, v in hits.items():
        if want and k != want: continue
        for nid, p, t in v: print(f"[{k}] {nid} {p} | {t[:160]}")
