#!/usr/bin/env python3
"""Add LOC hubs from 05C, FAIL endings, and any ### R-* not already parsed."""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
nodes = json.loads((ROOT / "public/data/nodes.json").read_text(encoding="utf-8"))
meta = json.loads((ROOT / "public/data/meta.json").read_text(encoding="utf-8"))
added = 0

def choice(label, nxt, num=1, effects=None):
    return {
        "id": f"opt-{num}", "num": num, "label": label, "condition": None, "check": None,
        "effects": effects or [], "success_text": "", "fail_text": "",
        "success_effects": [], "fail_effects": [], "cost_effects": [],
        "next": nxt, "subchoices": None, "flavor": [], "raw_block": "",
    }

text = (ROOT / "script/05C_雾钟城地点交互与世界文本.md").read_text(encoding="utf-8")
parts = re.split(r"^##\s+", text, flags=re.M)[1:]
loc_map = {
    "锚门广场": "LOC-ANCHOR", "白塔区": "LOC-WHITETOWER", "书吏区": "LOC-SCRIBE",
    "河渠区": "LOC-CANAL", "上环区": "LOC-UPPER", "西炉区": "LOC-WESTFORGE",
}
for part in parts:
    lines = part.splitlines()
    title = lines[0].strip().split()[0]
    if title not in loc_map:
        continue
    nid = loc_map[title]
    if nid in nodes:
        continue
    body = "\n".join(lines[1:]).strip()
    interactions = list(re.finditer(r"^###\s+(.+)$", body, re.M))
    choices = []
    for i, m in enumerate(interactions):
        start = m.end()
        end = interactions[i + 1].start() if i + 1 < len(interactions) else len(body)
        chunk = body[start:end].strip()
        sub_id = f"{nid}-{i+1}"
        nodes[sub_id] = {
            "id": sub_id, "title": m.group(1).strip()[:40],
            "source": "05C_雾钟城地点交互与世界文本.md", "kind": "scene", "enter": None,
            "text": chunk, "choices": [choice("离开", nid)], "default_next": nid,
        }
        choices.append(choice(m.group(1).strip()[:40], sub_id, i + 1))
        added += 1
    prose = body[: interactions[0].start()].strip() if interactions else body
    choices.append(choice("返回雾钟城街区", "CITY-01", len(choices) + 1))
    nodes[nid] = {
        "id": nid, "title": title, "source": "05C_雾钟城地点交互与世界文本.md",
        "kind": "hub", "enter": None, "text": prose or f"【旁白】你来到{title}。",
        "choices": choices, "default_next": None,
    }
    added += 1

if "CITY-01" in nodes:
    for label, nid in [
        ("漫步锚门广场", "LOC-ANCHOR"), ("进入白塔区", "LOC-WHITETOWER"),
        ("进入书吏区", "LOC-SCRIBE"), ("进入河渠区", "LOC-CANAL"),
        ("走上环区", "LOC-UPPER"), ("前往西炉区", "LOC-WESTFORGE"),
    ]:
        if nid in nodes and not any(c["label"] == label for c in nodes["CITY-01"]["choices"]):
            nodes["CITY-01"]["choices"].append(choice(label, nid, len(nodes["CITY-01"]["choices"]) + 1))

text10 = (ROOT / "script/10_结局_失败结局与后日谈.md").read_text(encoding="utf-8")
for m in re.finditer(r"^###?\s+(FAIL-[\w-]+)\s+(.+)$", text10, re.M):
    nid, title = m.group(1), m.group(2).strip()
    if nid in nodes:
        continue
    start = m.end()
    nxt = re.search(r"^##\s+", text10[start:], re.M)
    body = text10[start : start + (nxt.start() if nxt else len(text10))].strip()
    nodes[nid] = {
        "id": nid, "title": title, "source": "10_结局_失败结局与后日谈.md",
        "kind": "ending", "enter": None, "text": body,
        "choices": [choice("合上这一页（返回标题）", "__TITLE__", 1, [{"op": "ending", "key": nid, "value": True}])],
        "default_next": None,
    }
    added += 1

text08 = (ROOT / "script/08_随机事件_钟骨侵扰与路人.md").read_text(encoding="utf-8")
for m in re.finditer(r"^###\s+(R-[\w-]+)\s+(.+)$", text08, re.M):
    nid, title = m.group(1), m.group(2).strip()
    if nid in nodes:
        continue
    start = m.end()
    nxt = re.search(r"^###?\s+", text08[start:], re.M)
    body = text08[start : start + (nxt.start() if nxt else 800)].strip()
    choices = []
    for om in re.finditer(r"^(\d+)\.\s+\*\*(.+?)\*\*", body, re.M):
        choices.append(choice(om.group(2).strip(), "__RETURN__", int(om.group(1))))
    if not choices:
        choices = [choice("继续赶路", "__RETURN__")]
    nodes[nid] = {
        "id": nid, "title": title, "source": "08_随机事件_钟骨侵扰与路人.md",
        "kind": "random", "enter": None, "text": body, "choices": choices, "default_next": "__RETURN__",
    }
    added += 1

meta["node_count"] = len(nodes)
(ROOT / "public/data/nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "public/data/meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"synthesize-extra: {len(nodes)} nodes (added {added})")
