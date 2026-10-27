#!/usr/bin/env python3
"""Parse 《雾钟城：第七声》 markdown scripts into public/data/nodes.json + meta.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script"
OUT = ROOT / "public" / "data"

# Files that contain playable nodes (order = source priority for duplicates)
STORY_FILES = [
    "01_序章_艾德里克.md",
    "02_序章_莉瑞尔.md",
    "03_序章_索林.md",
    "04_第一幕_灰桥镇.md",
    "05A_第二幕_雾钟城自由探索.md",
    "05B_雾钟城支线故事.md",
    "05C_雾钟城地点交互与世界文本.md",
    "05_第二幕_黑砧矿区.md",
    "06_第三幕_初鸣庭.md",
    "07_NPC完整对话与关系场景.md",
    "08_随机事件_钟骨侵扰与路人.md",
    "09_战斗_伤势_物品与资源文本.md",
    "10_结局_失败结局与后日谈.md",
    "13_城市NPC与疗法对白.md",
]

# Node ID pattern: E-PRO-01, A1-TOWN-08, A3-SHRINE-07-LATE, END-CURE-01, CITY-01, SQ-CITY-01, D-NPC-VALEN, R-MEM-01, C-04, LOC-*, etc.
NODE_HEADER = re.compile(
    r"^##\s+([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\s+(.+?)\s*$",
    re.MULTILINE,
)

# Skip non-node ## headers in 00 / README / 11 / 12
SKIP_IDS = set()

EFFECT_RE = re.compile(r"〔效果〕\s*(.*)")
CHECK_RE = re.compile(r"〔检定[：:]\s*([^〕]+)〕")
COND_INLINE = re.compile(r"〔仅\s*([^〕]+)〕")
COND_NEED = re.compile(r"〔(?:需要|条件)[：:]?\s*([^〕]+)〕")
ARROW_RE = re.compile(
    r"→\s*`?("
    r"[A-Z][A-Z0-9]*-(?:[A-Z0-9]+-)*[A-Z0-9]+"  # must contain hyphen
    r"|__\w+__"
    r")`?"
)
ARROW_RETURN = re.compile(r"→\s*返回")
BACKTICK_ASSIGN = re.compile(
    r"`([a-zA-Z_][\w.]*)\s*((?:\+=|-=|=))\s*([^`;]+)`"
)
PLAIN_ASSIGN = re.compile(
    r"(?<![`\w])([a-zA-Z_][\w.]*)\s*((?:\+=|-=|=))\s*(true|false|-?\d+|\[[^\]]*\])"
)
STAT_NAMES = {"STR", "DEX", "CON", "CHA", "INS", "WIL"}


def parse_effects(text: str) -> list[dict]:
    """Extract atomic effect ops from a Chinese/backtick mixed effect string."""
    effects: list[dict] = []
    if not text:
        return effects
    # Prefer backtick segments
    for m in BACKTICK_ASSIGN.finditer(text):
        key, op, val = m.group(1), m.group(2), m.group(3).strip()
        effects.append({"op": op, "key": key, "value": coerce(val)})
    if effects:
        # Also catch "获得 `item`" patterns
        for m in re.finditer(r"获得\s*`([^`]+)`", text):
            effects.append({"op": "add_item", "key": m.group(1).strip(), "value": 1})
        for m in re.finditer(r"失去\s*(\d+)\s*HP", text):
            effects.append({"op": "-=", "key": "hp", "value": int(m.group(1))})
        return effects
    # Fallback plain assigns
    for m in PLAIN_ASSIGN.finditer(text):
        effects.append({"op": m.group(2), "key": m.group(1), "value": coerce(m.group(3))})
    for m in re.finditer(r"获得\s*`([^`]+)`|获得\s+([a-zA-Z_][\w]*)", text):
        item = (m.group(1) or m.group(2) or "").strip()
        if item:
            effects.append({"op": "add_item", "key": item, "value": 1})
    for m in re.finditer(r"失去\s*(\d+)\s*HP", text):
        effects.append({"op": "-=", "key": "hp", "value": int(m.group(1))})
    # rel.x +1 without backtick
    for m in re.finditer(r"(rel\.\w+)\s*([+-]\d+)", text):
        effects.append({"op": "+=", "key": m.group(1), "value": int(m.group(2))})
    return effects


def coerce(val: str):
    val = val.strip().rstrip("；。.,")
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", val):
        return int(val)
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = [p.strip().strip("'\"") for p in re.split(r"[,，]", inner)]
        return parts
    return val.strip("'\"")


def parse_check(spec: str) -> dict | None:
    """Parse 'CHA，DC 13；...' or 'INS，DC 13；汤姆同行时 +1'."""
    if not spec:
        return None
    stats = []
    for s in STAT_NAMES:
        if re.search(rf"\b{s}\b", spec):
            stats.append(s)
    # also 'CHA 或 DEX'
    dc_m = re.search(r"DC\s*(\d+)", spec)
    dc = int(dc_m.group(1)) if dc_m else 13
    advantage = "优势" in spec
    disadvantage = "劣势" in spec
    # situational modifiers written as `+1` or +1
    mods = []
    for m in re.finditer(r"(?:时|若)[^；;]*?`?\+(\d+)`?", spec):
        mods.append({"when": "context", "bonus": int(m.group(1)), "raw": m.group(0)})
    # alternate DC
    alt_dc = None
    m2 = re.search(r"若\s*`?([^`；;]+)`?[^；;]*DC\s*(\d+)", spec)
    if m2:
        alt_dc = {"when": m2.group(1).strip(), "dc": int(m2.group(2))}
    return {
        "stats": stats or ["INS"],
        "dc": dc,
        "advantage": advantage,
        "disadvantage": disadvantage,
        "mods": mods,
        "alt_dc": alt_dc,
        "raw": spec.strip(),
    }


def parse_condition(raw: str) -> dict:
    """Loose condition: flag name, '汤姆同行', attribute checks, etc."""
    raw = raw.strip()
    # backtick flags
    flags = re.findall(r"`([^`]+)`", raw)
    return {"raw": raw, "flags": flags}


OPTION_START = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$")
SUBOPT = re.compile(r"^-\s+\*\*(.+?)\*\*\s*(.*)$")
BULLET = re.compile(r"^-\s+(.*)$")


NODE_HEADER_H3 = re.compile(
    r"^###\s+([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)\s+(.+?)\s*$",
    re.MULTILINE,
)

def split_nodes(text: str) -> list[tuple[str, str, str]]:
    """Return list of (id, title, body)."""
    matches = list(NODE_HEADER.finditer(text))
    # Also ###-level story nodes (R-MEM-01 etc.) that aren't already ## parents
    h3 = list(NODE_HEADER_H3.finditer(text))
    existing_pos = {(m.start()) for m in matches}
    for m in h3:
        nid = m.group(1)
        if "-" in nid and is_story_node_id(nid):
            matches.append(m)
    matches.sort(key=lambda m: m.start())
    out = []
    for i, m in enumerate(matches):
        nid, title = m.group(1), m.group(2).strip()
        # Filter out numbered section headers like "## 1. 节点命名"
        if re.match(r"^\d+\.", title) or nid in SKIP_IDS:
            # Actually ## 1. would not match our NODE_HEADER because of digit-first... 
            # our pattern requires letter start. Good.
            pass
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        out.append((nid, title, body))
    return out


def extract_body_and_choices(body: str) -> tuple[str, list[dict], str | None]:
    """Split prose from ### 选择 / #### 选择 blocks; also catch trailing → NODE."""
    # Find first choice section
    choice_headers = list(re.finditer(r"^#{2,4}\s*选择\s*$", body, re.MULTILINE))
    # Also "### 与瓦伦..." style - we keep as prose but try to parse numbered lists after them

    default_next = None
    # trailing arrow at end of node (for nodes without numbered choices)
    trail = list(ARROW_RE.finditer(body))
    if trail:
        # last arrow not inside a choice we parse might be default next
        default_next = trail[-1].group(1)

    if not choice_headers:
        # Try to find numbered options at top level even without ### 选择
        choices = parse_choice_block(body)
        prose = body
        if choices:
            # remove the numbered list from prose roughly
            first = re.search(r"^\d+\.\s+\*\*", body, re.MULTILINE)
            if first:
                prose = body[: first.start()].strip()
        # Also handle END nodes: no choices
        if not choices and default_next and default_next.startswith("END"):
            pass
        return prose, choices, default_next if not choices else None

    # Prose = before first ### 选择; but hub nodes have multiple ### sections.
    # Strategy: full body as text; extract ALL numbered **options** across the node.
    prose = body
    choices = parse_choice_block(body)
    # If choices exist, default_next only used when a choice lacks →
    return prose, choices, None


def parse_choice_block(text: str) -> list[dict]:
    choices = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = OPTION_START.match(lines[i].strip())
        if not m:
            i += 1
            continue
        num = int(m.group(1))
        label = m.group(2).strip()
        rest = m.group(3).strip()
        block_lines = [rest] if rest else []
        i += 1
        # Collect continuation bullets / indented lines until next option or ## header
        while i < len(lines):
            s = lines[i]
            st = s.strip()
            if OPTION_START.match(st):
                break
            if re.match(r"^##\s+", st):
                break
            # stop at next ### that's not 选择-related subcontent? keep going for hub
            # Actually for hubs, each #### 选择 resets numbering - that's fine, we collect all
            if re.match(r"^#{3,4}\s+", st) and "选择" not in st and not st.startswith("####"):
                # new subsection - stop this option
                if re.match(r"^###\s+", st):
                    break
            block_lines.append(s)
            i += 1
            # limit runaway
            if len(block_lines) > 40:
                break

        block = "\n".join(block_lines).strip()
        choice = build_choice(num, label, block)
        choices.append(choice)
    return choices


def build_choice(num: int, label: str, block: str) -> dict:
    cond_raw = None
    cm = COND_INLINE.search(label) or COND_INLINE.search(block[:200])
    if cm:
        cond_raw = cm.group(1)
        label = COND_INLINE.sub("", label).strip()
    cm2 = COND_NEED.search(label) or COND_NEED.search(block[:200])
    if cm2 and not cond_raw:
        cond_raw = cm2.group(1)

    check = None
    cm3 = CHECK_RE.search(block)
    if cm3:
        check = parse_check(cm3.group(1))
    # also 〔CHA，DC 13〕 without 检定
    if not check:
        m = re.search(r"〔((?:STR|DEX|CON|CHA|INS|WIL)[^〕]*DC\s*\d+[^〕]*)〕", block)
        if m:
            check = parse_check(m.group(1))

    effects_text = ""
    em = EFFECT_RE.search(block)
    if em:
        effects_text = em.group(1)

    success_text = ""
    fail_text = ""
    success_effects: list[dict] = []
    fail_effects: list[dict] = []
    cost_effects: list[dict] = []

    # Parse 成功/失败 lines
    for line in block.splitlines():
        t = line.strip().lstrip("- ").strip()
        if t.startswith("成功"):
            success_text = re.sub(r"^成功[：:：]?\s*", "", t)
            success_effects = parse_effects(t)
        elif t.startswith("失败"):
            fail_text = re.sub(r"^失败[：:：]?\s*", "", t)
            fail_effects = parse_effects(t)
        elif t.startswith("代价"):
            cost_effects = parse_effects(t)

    effects = parse_effects(effects_text) if effects_text else []
    # Also parse effects from whole block if no 〔效果〕
    if not effects and not check:
        effects = parse_effects(block)

    next_id = None
    arrows = list(ARROW_RE.finditer(block))
    if arrows:
        next_id = arrows[-1].group(1)
    elif ARROW_RETURN.search(block):
        next_id = "__RETURN__"

    # Nested sub-options (like 会 / 别等我)
    subchoices = []
    for sm in SUBOPT.finditer(block):
        sub_label = sm.group(1).strip()
        sub_rest = sm.group(2).strip()
        sub_next = None
        am = ARROW_RE.search(sub_rest)
        if am:
            # might be effect not node - check if looks like NODE
            cand = am.group(1)
            if re.match(r"^(E|L|T|A\d|CITY|SQ|END|D-|R-|C-|LOC|FAIL)", cand):
                sub_next = cand
        subchoices.append(
            {
                "label": sub_label,
                "text": sub_rest,
                "effects": parse_effects(sub_rest),
                "next": sub_next,
            }
        )

    # Narrative bullets (non-effect flavor)
    flavor_lines = []
    for line in block.splitlines():
        st = line.strip()
        if not st.startswith("-"):
            continue
        if any(
            x in st
            for x in (
                "〔效果〕",
                "〔检定",
                "成功",
                "失败",
                "代价",
                "→",
            )
        ):
            continue
        if st.startswith("- **"):
            continue
        flavor_lines.append(st.lstrip("- ").strip())

    return {
        "id": f"opt-{num}",
        "num": num,
        "label": label,
        "condition": parse_condition(cond_raw) if cond_raw else None,
        "check": check,
        "effects": effects,
        "success_text": success_text,
        "fail_text": fail_text,
        "success_effects": success_effects,
        "fail_effects": fail_effects,
        "cost_effects": cost_effects,
        "next": next_id,
        "subchoices": subchoices or None,
        "flavor": flavor_lines,
        "raw_block": block[:500],
    }


def is_story_node_id(nid: str) -> bool:
    prefixes = (
        "E-PRO", "L-PRO", "T-PRO",
        "A1-", "A2-", "A3-",
        "CITY-", "SQ-", "END-",
        "D-NPC", "D-ALT",
        "R-", "C-", "LOC-", "FAIL-", "IX-", "EVT-", "BATTLE-", "ITEM-",
        "NPC-",
    )
    return nid.startswith(prefixes) or bool(re.match(r"^(E|L|T)-", nid))


def main():
    nodes: dict[str, dict] = {}
    warnings: list[str] = []
    sources_used = []

    for fname in STORY_FILES:
        path = SCRIPT / fname
        if not path.exists():
            warnings.append(f"missing file: {fname}")
            continue
        text = path.read_text(encoding="utf-8")
        sources_used.append(fname)
        for nid, title, body in split_nodes(text):
            if not is_story_node_id(nid):
                # e.g. accidental matches - skip
                if re.match(r"^\d", nid):
                    continue
                # Allow END and others already covered
                if nid not in ("结算顺序",) and len(nid) < 3:
                    continue
                # Skip Chinese-only weirdness
                if not re.match(r"^[A-Z]", nid):
                    continue
            prose, choices, default_next = extract_body_and_choices(body)

            # Classify
            kind = "scene"
            if nid.startswith("END"):
                kind = "ending"
            elif nid.startswith("D-"):
                kind = "dialogue"
            elif nid.startswith("R-") or nid.startswith("EVT"):
                kind = "random"
            elif nid.startswith("C-") or nid.startswith("BATTLE"):
                kind = "combat"
            elif "HUB" in nid or nid in (
                "A1-TOWN-01",
                "CITY-01",
                "CITY-10",
            ):
                kind = "hub"

            # Clean prose for display: keep speaker tags
            display = prose.strip()
            # Strip leading 〔进入〕 lines into enter_condition
            enter = None
            em = re.match(r"〔进入〕([^\n]+)\n*", display)
            if em:
                enter = em.group(1).strip()
                display = display[em.end() :].lstrip()

            node = {
                "id": nid,
                "title": title,
                "source": fname,
                "kind": kind,
                "enter": enter,
                "text": display,
                "choices": choices,
                "default_next": default_next,
            }

            if nid in nodes:
                warnings.append(f"duplicate node {nid} in {fname} (keeping first from {nodes[nid]['source']})")
                continue
            nodes[nid] = node

    # Patch critical transitions if missing
    patches = apply_patches(nodes, warnings)

    # Link integrity
    missing_links = []
    for nid, node in nodes.items():
        targets = []
        if node.get("default_next") and node["default_next"] not in ("__RETURN__",):
            targets.append(node["default_next"])
        for c in node.get("choices") or []:
            if c.get("next") and c["next"] not in ("__RETURN__",):
                targets.append(c["next"])
            for sc in c.get("subchoices") or []:
                if sc.get("next"):
                    targets.append(sc["next"])
        for t in targets:
            if t not in nodes:
                missing_links.append(f"{nid} → {t}")

    # Meta
    meta = {
        "title": "雾钟城：第七声",
        "version": "1.0.0",
        "node_count": len(nodes),
        "sources": sources_used,
        "characters": {
            "edric": {
                "id": "edric",
                "name": "艾德里克",
                "title": "人类斥候",
                "blurb": "善于察觉与潜行。为了妹妹的离境文书，他走在北路的雨里。",
                "traits": ["善于察觉", "身手敏捷", "寡言"],
                "stats": {"STR": 12, "DEX": 15, "CON": 13, "CHA": 10, "INS": 15, "WIL": 12},
                "hp": 16,
                "max_hp": 16,
                "carried": ["border_sword", "hand_crossbow", "6_bolts", "lily_comb", "8_vouchers"],
                "storage": ["bedroll", "winter_cloak", "28_vouchers"],
                "fragment": "memory_ring",
                "fragment_name": "旧雨骨（铁戒指）",
                "private_goal": "secure_exit_writ",
                "start": "E-PRO-01",
            },
            "liriel": {
                "id": "liriel",
                "name": "莉瑞尔",
                "title": "半精灵流亡者",
                "blurb": "口才与魅力出众。十年前的哨所旧案仍缠着她的银链。",
                "traits": ["能言善辩", "身手敏捷", "心事重"],
                "stats": {"STR": 9, "DEX": 15, "CON": 11, "CHA": 16, "INS": 14, "WIL": 13},
                "hp": 12,
                "max_hp": 12,
                "carried": ["elf_rapier", "burnt_ledger", "chalk", "11_vouchers"],
                "storage": ["lute", "spare_dress", "9_vouchers"],
                "fragment": "desire_chain",
                "fragment_name": "饥月骨（银链）",
                "private_goal": "learn_outpost_truth",
                "start": "L-PRO-01",
            },
            "thorin": {
                "id": "thorin",
                "name": "索林",
                "title": "矮人工匠",
                "blurb": "体格结实，拒不认输。怀表里的裂锤骨会放大他的愤怒。",
                "traits": ["体格结实", "力大", "工匠之手"],
                "stats": {"STR": 16, "DEX": 9, "CON": 16, "CHA": 10, "INS": 12, "WIL": 14},
                "hp": 24,
                "max_hp": 24,
                "carried": ["old_hammer", "rune_pick", "delivery_receipt", "5_vouchers"],
                "storage": ["tool_chest", "spare_parts", "24_vouchers"],
                "fragment": "anger_watch",
                "fragment_name": "裂锤骨（怀表）",
                "private_goal": "obtain_delivery_seal",
                "start": "T-PRO-01",
            },
        },
        "time_labels": ["黄昏", "入夜", "深夜", "午夜", "三更", "四更", "黎明"],
        "item_names": ITEM_NAMES,
        "warnings": warnings[:200],
        "missing_links": missing_links[:200],
        "patches_applied": patches,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nodes.json").write_text(
        json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Stats
    with_choices = sum(1 for n in nodes.values() if n["choices"])
    endings = sum(1 for n in nodes.values() if n["kind"] == "ending")
    print(f"Parsed {len(nodes)} nodes ({with_choices} with choices, {endings} endings)")
    print(f"Warnings: {len(warnings)}, missing links: {len(missing_links)}")
    if missing_links[:15]:
        print("Sample missing:", *missing_links[:15], sep="\n  ")
    return 0


ITEM_NAMES = {
    "border_sword": "边防长剑",
    "hand_crossbow": "手弩",
    "6_bolts": "弩矢×6",
    "lily_comb": "莉莉的木梳",
    "8_vouchers": "商会券×8",
    "28_vouchers": "商会券×28",
    "bedroll": "铺盖卷",
    "winter_cloak": "冬氅",
    "elf_rapier": "精灵细剑",
    "burnt_ledger": "烧焦账册",
    "chalk": "粉笔",
    "11_vouchers": "商会券×11",
    "lute": "鲁特琴",
    "spare_dress": "备用衣裙",
    "9_vouchers": "商会券×9",
    "old_hammer": "旧锤",
    "rune_pick": "符文镐",
    "delivery_receipt": "交货回执",
    "5_vouchers": "商会券×5",
    "tool_chest": "工具箱",
    "spare_parts": "备用零件",
    "24_vouchers": "商会券×24",
    "memory_ring": "铁戒指（旧雨骨）",
    "desire_chain": "银链（饥月骨）",
    "anger_watch": "怀表（裂锤骨）",
    "half_mine_map": "半张矿道图",
    "ysolde_note": "伊索尔的纸条",
    "medicine_pack": "止血粉",
    "toren_badge": "疤脸铜扣",
    "mine_drain_route": "矿区排水渠路线",
}


def apply_patches(nodes: dict, warnings: list) -> list[str]:
    """Hand-coded critical transitions for hub / incomplete parses."""
    applied = []

    def ensure_choice(nid, label, next_id, effects=None, condition=None):
        if nid not in nodes:
            return
        node = nodes[nid]
        # avoid dup labels
        for c in node["choices"]:
            if c["label"] == label:
                if not c.get("next"):
                    c["next"] = next_id
                    applied.append(f"fill next {nid}: {label} → {next_id}")
                return
        node["choices"].append(
            {
                "id": f"patch-{len(node['choices'])+1}",
                "num": len(node["choices"]) + 1,
                "label": label,
                "condition": condition,
                "check": None,
                "effects": effects or [],
                "success_text": "",
                "fail_text": "",
                "success_effects": [],
                "fail_effects": [],
                "cost_effects": [],
                "next": next_id,
                "subchoices": None,
                "flavor": [],
                "raw_block": "(patch)",
            }
        )
        applied.append(f"add choice {nid}: {label} → {next_id}")

    # Prologue ends → Greybridge hub
    for pid, nxt in (
        ("E-PRO-08", "A1-TOWN-01"),
        ("L-PRO-08", "A1-TOWN-01"),
        ("T-PRO-08", "A1-TOWN-01"),
    ):
        if pid in nodes:
            n = nodes[pid]
            if not n["choices"]:
                ensure_choice(pid, "进入灰桥镇", nxt, [{"op": "=", "key": "time", "value": 1}])
            else:
                for c in n["choices"]:
                    if not c.get("next"):
                        c["next"] = nxt
                        applied.append(f"prologue link {pid} → {nxt}")

    # Greybridge hub navigation
    if "A1-TOWN-01" in nodes:
        hub_opts = [
            ("前往白鸦旅店", "A1-TOWN-02"),
            ("前往灰烛礼拜堂", "A1-TOWN-03"),
            ("前往红牡丹", "A1-TOWN-04"),
            ("前往格罗姆的铺子", "A1-TOWN-05"),
            ("处理私人目标", "A1-TOWN-06"),
            ("前往军务所（哈兰）", "A1-TOWN-07"),
        ]
        for label, nxt in hub_opts:
            if nxt in nodes:
                ensure_choice("A1-TOWN-01", label, nxt)

    # Return to hub from locations if no next
    for loc in (
        "A1-TOWN-02",
        "A1-TOWN-03",
        "A1-TOWN-04",
        "A1-TOWN-05",
        "A1-TOWN-06",
        "A1-TOWN-07",
    ):
        if loc in nodes:
            n = nodes[loc]
            has_return = any(
                (c.get("next") in ("A1-TOWN-01", "A1-TOWN-08", "A1-TOWN-09"))
                for c in n["choices"]
            )
            if not n["choices"] or not has_return:
                ensure_choice(
                    loc,
                    "离开此地，回到镇口",
                    "A1-TOWN-01",
                    [{"op": "+=", "key": "town_visits", "value": 1}],
                )

    # After enough visits / time, push toward clock / warehouse
    if "A1-TOWN-08" in nodes and "A1-TOWN-09" in nodes:
        for c in nodes["A1-TOWN-08"].get("choices") or []:
            if not c.get("next"):
                c["next"] = "A1-TOWN-09"
        if not nodes["A1-TOWN-08"]["choices"]:
            ensure_choice("A1-TOWN-08", "仓促赶往东仓", "A1-TOWN-09")

    if "A1-TOWN-10" in nodes:
        # Fire aftermath → city
        if "CITY-01" in nodes:
            ensure_choice("A1-TOWN-10", "连夜赶往雾钟城", "CITY-01")
            if "A2-MINE-01A" in nodes:
                ensure_choice("A1-TOWN-10", "改道黑砧矿区", "A2-MINE-01A")

    # City hub
    if "CITY-01" in nodes:
        for label, nxt in [
            ("前往锚门广场", "CITY-02"),
            ("打听白塔拔除术", "CITY-03"),
            ("打听学院稳定术", "CITY-04"),
            ("打听河渠换命契", "CITY-05"),
            ("打听西炉拆解术", "CITY-06"),
            ("查阅第零蓄水池档案", "CITY-07"),
            ("倾听六钟错拍", "CITY-08"),
            ("前往静默署", "CITY-09"),
        ]:
            if nxt in nodes:
                ensure_choice("CITY-01", label, nxt)

    for loc in [f"CITY-0{i}" for i in range(2, 10)] + ["CITY-10"]:
        if loc in nodes:
            ensure_choice(loc, "返回雾钟城街区", "CITY-01")

    if "CITY-10" in nodes and "A3-SHRINE-00" in nodes:
        ensure_choice("CITY-10", "潜入第零蓄水池", "A3-SHRINE-00")
    if "A3-SHRINE-00" in nodes and "A3-SHRINE-01" in nodes:
        ensure_choice("A3-SHRINE-00", "沿裂隙桥下行", "A3-SHRINE-01")

    # Chain shrine if missing nexts
    shrine_chain = [
        "A3-SHRINE-01",
        "A3-SHRINE-02",
        "A3-SHRINE-03",
        "A3-SHRINE-04",
        "A3-SHRINE-05",
        "A3-SHRINE-06",
        "A3-SHRINE-07",
        "A3-SHRINE-08",
    ]
    for a, b in zip(shrine_chain, shrine_chain[1:]):
        if a in nodes and b in nodes:
            n = nodes[a]
            if not any(c.get("next") for c in n["choices"]):
                ensure_choice(a, "继续深入", b)

    # Ending choices from final plan node
    if "A3-SHRINE-07" in nodes:
        for label, end in [
            ("记录后沉睡，留下事实", "END-01"),
            ("切断服从铭文，承受反噬", "END-02"),
            ("尝试建立雾钟地方新约", "END-03"),
            ("带着诅咒离开（若已安排退路）", "END-08"),
        ]:
            if end in nodes:
                ensure_choice("A3-SHRINE-07", label, end)

    # Personal cure endings from city therapy nodes
    cure_map = [
        ("CITY-03", "接受白塔代祷并离城", "END-CURE-01"),
        ("CITY-04", "接受学院长期稳定术", "END-CURE-02"),
        ("CITY-05", "签下河渠换命契", "END-CURE-03"),
        ("CITY-06", "接受西炉内化拆解", "END-CURE-04"),
    ]
    for loc, label, end in cure_map:
        if loc in nodes and end in nodes:
            ensure_choice(loc, label, end)

    # Ensure ending nodes are terminal
    for nid, n in nodes.items():
        if n["kind"] == "ending" and not n["choices"]:
            n["choices"] = [
                {
                    "id": "to-title",
                    "num": 1,
                    "label": "合上这一页（返回标题）",
                    "condition": None,
                    "check": None,
                    "effects": [{"op": "ending", "key": nid, "value": True}],
                    "success_text": "",
                    "fail_text": "",
                    "success_effects": [],
                    "fail_effects": [],
                    "cost_effects": [],
                    "next": "__TITLE__",
                    "subchoices": None,
                    "flavor": [],
                    "raw_block": "(ending)",
                }
            ]
            applied.append(f"ending terminal {nid}")

    # Nodes with no choices and no default_next: add stub continue if we can guess
    for nid, n in list(nodes.items()):
        if n["kind"] == "ending":
            continue
        if n["choices"]:
            # fill empty nexts with default if present in text
            continue
        if n.get("default_next") and n["default_next"] in nodes:
            ensure_choice(nid, "继续", n["default_next"])
        elif n.get("default_next") and n["default_next"] not in nodes:
            warnings.append(f"default_next missing: {nid} → {n['default_next']}")
            ensure_choice(
                nid,
                "继续（此分支目标未收录）",
                "__STUB__",
            )

    # Stub node
    if "__STUB__" not in nodes:
        nodes["__STUB__"] = {
            "id": "__STUB__",
            "title": "未完全解析的岔路",
            "source": "patch",
            "kind": "scene",
            "enter": None,
            "text": "【旁白】雾比刚才更浓。这段岔路的数据尚未完全从剧本转录进来，但你的旅程不必停在这里。\n\n你可以回到最近的安全地点，或直接进入已知的下一幕。",
            "choices": [],
            "default_next": None,
        }
        ensure_choice("__STUB__", "返回灰桥镇口", "A1-TOWN-01")
        if "CITY-01" in nodes:
            ensure_choice("__STUB__", "前往雾钟城", "CITY-01")
        if "A3-SHRINE-01" in nodes:
            ensure_choice("__STUB__", "前往初鸣庭（若已发现）", "A3-SHRINE-01")
        applied.append("created __STUB__")

    return applied


if __name__ == "__main__":
    sys.exit(main())
