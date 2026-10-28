#!/usr/bin/env python3
"""v2 parser for 《雾钟城：第七声》.

Turns the markdown scripts into structured nodes:
  node = {id, title, kind, blocks:[{t, who?, text, cond?}], choices:[choice], default_next, routes, hub?, ...}
  choice = {id, label, group?, cond?, mark?, once, check?, cost?, result:[blocks], effects:[ops],
            next, success:{result,effects,next}, fail:{...}, sub:[choice]}
Nothing shown to the player keeps markdown, dev variables, node ids or 〔〕 annotations.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wzc_text as T
from wzc_text import sanitize, label_clean, parse_effects, find_check, parse_cond, CTX, NODE_ID_RX, narrate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script"
OUT = ROOT / "public" / "data"
sys.path.insert(0, str(ROOT / "tools"))
from wzc_names import ITEM_NAMES, NPC_NAMES  # noqa: E402
T.ITEM_NAMES.update(ITEM_NAMES)

FILES = [
    "01_序章_艾德里克.md", "02_序章_莉瑞尔.md", "03_序章_索林.md", "04_第一幕_灰桥镇.md",
    "05A_第二幕_雾钟城自由探索.md", "05B_雾钟城支线故事.md", "05_第二幕_黑砧矿区.md",
    "06_第三幕_初鸣庭.md", "07_NPC完整对话与关系场景.md", "09_战斗_伤势_物品与资源文本.md",
    "10_结局_失败结局与后日谈.md", "13_城市NPC与疗法对白.md",
]
H2 = re.compile(r"^##\s+(" + NODE_ID_RX + r")\s*(.*)$")
DEV_HEADINGS = ("当前线索的自然提示", "行动规则", "规则测试", "此时玩家知道什么", "抽取规则", "战斗表现原则",
                "通用动作文本", "结算顺序", "支线收束原则", "城市 NPC 反应规则", "设计", "说明", "备注")
TOPIC_PREFIXES = ("D-NPC", "D-ALT", "CITY-NPC", "LOC-")
TOPIC_NODES = {"A3-SHRINE-07", "A1-TOWN-02", "A1-TOWN-03", "A1-TOWN-04", "A1-TOWN-05", "A1-TOWN-07"}
SEQ_NODES = {"A1-TOWN-09", "CITY-03", "SQ-CITY-01", "SQ-CITY-02", "A2-MINE-04", "A2-MINE-05", "A3-SHRINE-03"}
DEV_LINE = re.compile(r"(后推进|推进。?$|进入下一节点|跳转|^本节点|^此节点|^注[：:]|^设计[：:])")

unparsed_global: list[str] = []

# ------------------------------------------------------------------ reading

def split_h2(text, fname):
    out, cur = [], None
    for line in text.splitlines():
        m = H2.match(line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "lines": [], "source": fname}
            out.append(cur); continue
        if line.startswith("## "):
            cur = None; continue
        if line.startswith("# "):
            continue
        if cur is not None:
            cur["lines"].append(line)
    return out

def read_all():
    raw = []
    for f in FILES:
        raw += split_h2((SCRIPT / f).read_text(encoding="utf-8"), f)
    # 08 random events: ### R-* under pool sections
    text = (SCRIPT / "08_随机事件_钟骨侵扰与路人.md").read_text(encoding="utf-8")
    pool, cur = None, None
    pools_by_h2 = {"通用旅行事件": "travel", "艾德里克：记忆侵扰池": "edric", "莉瑞尔：欲望侵扰池": "liriel",
                   "索林：愤怒侵扰池": "thorin", "路人新闻池": "news"}
    for line in text.splitlines():
        if line.startswith("## "):
            pool = pools_by_h2.get(line[3:].strip()); cur = None; continue
        m = re.match(r"^###\s+(R-[A-Z]+-\d+)\s*(.*)$", line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "lines": [], "source": "08", "pool": pool}
            raw.append(cur); continue
        if line.startswith("### "):
            cur = None; continue
        if cur is not None:
            cur["lines"].append(line)
    # news pool lines (bullets) become one node each if no ### ids exist there
    # 05C: districts → LOC hubs; ambient ### → own nodes
    text = (SCRIPT / "05C_雾钟城地点交互与世界文本.md").read_text(encoding="utf-8")
    loc_ids = {"锚门广场": "LOC-ANCHOR", "白塔区": "LOC-WHITETOWER", "书吏区": "LOC-SCRIBE",
               "河渠区": "LOC-CANAL", "上环区": "LOC-UPPER", "西炉区": "LOC-WESTFORGE"}
    district, cur = None, None
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            district = None; cur = None
            if name in loc_ids:
                district = {"id": loc_ids[name], "title": name, "lines": [], "source": "05C", "ambients": []}
                raw.append(district); cur = district
            continue
        m = re.match(r"^###\s+(CITY-AMBIENT-\d+)\s*(.*)$", line)
        if m and district:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "lines": [], "source": "05C", "district": district["id"]}
            district["ambients"].append(cur["id"]); raw.append(cur); continue
        if line.startswith("### ") and district:
            cur = district; continue  # 区域正文 heading: prose belongs to district
        if cur is not None:
            cur["lines"].append(line)
    # 10: FAIL-* and epilogues
    text = (SCRIPT / "10_结局_失败结局与后日谈.md").read_text(encoding="utf-8")
    cur = None
    for line in text.splitlines():
        m = re.match(r"^###\s+(FAIL-\d+)\s*(.*)$", line)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "lines": [], "source": "10", "fail": True}
            raw.append(cur); continue
        if line.startswith("#"):
            cur = None; continue
        if cur is not None:
            cur["lines"].append(line)
    return raw

def epilogues():
    text = (SCRIPT / "10_结局_失败结局与后日谈.md").read_text(encoding="utf-8")
    sec = text.split("## 主角私人尾声", 1)[1].split("\n## ", 1)[0]
    out = {}
    for part in re.split(r"^###\s+", sec, flags=re.M)[1:]:
        name, body = part.split("\n", 1)
        pc = T.PCS.get(name.strip())
        out[pc] = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    return out

# ------------------------------------------------------------------ blocks

def speech_block(text):
    m = re.match(r"^【([^】]+)】\s*(.*)$", text)
    if not m:
        return None
    who, rest = m.group(1), m.group(2)
    body = sanitize(rest)
    if not body:
        return None
    if who in ("旁白",):
        return {"t": "p", "text": body}
    if who in ("内心",):
        return {"t": "inner", "text": body}
    if "系统" in who or "提示" in who or "设计" in who:
        return {"t": "dev"}
    return {"t": "say", "who": sanitize(who) or who, "text": body}

def prose_block(line, cond=None):
    s = line.strip()
    if not s:
        return None
    if s.startswith("|") or s.startswith("```") or re.fullmatch(r"-{3,}", s):
        return None
    if s.startswith(">"):
        b = sanitize(s.lstrip("> "))
        return {"t": "quote", "text": b} if b else None
    s2 = re.sub(r"^\s*[-*]\s+", "", s)
    sp = speech_block(s2)
    if sp:
        if sp.get("t") == "dev":
            return None
        if cond: sp["cond"] = cond
        return sp
    b = sanitize(s2)
    if not b:
        return None
    blk = {"t": "p", "text": b}
    if cond: blk["cond"] = cond
    return blk

# ------------------------------------------------------------------ choices

OPT_NUM = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
OPT_BUL = re.compile(r"^(\s*)[-*]\s+(.*)$")
BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")

def indent_of(line):
    return len(line) - len(line.lstrip(" "))

def gather_items(lines, numbered: bool):
    """Split section lines into option items: (head_text, [child lines]) with child indentation kept."""
    items, pre, cur = [], [], None
    base = None
    for ln in lines:
        if not ln.strip():
            continue
        if numbered:
            m = OPT_NUM.match(ln)
            if m and (base is None or indent_of(ln) <= base):
                base = indent_of(ln)
                cur = [m.group(3), []]; items.append(cur); continue
        else:
            m = OPT_BUL.match(ln)
            if m and (base is None or indent_of(ln) <= base):
                base = indent_of(ln)
                cur = [m.group(2), []]; items.append(cur); continue
        if cur is None:
            pre.append(ln)
        elif indent_of(ln) > (base or 0) or ln.lstrip().startswith(("-", "*", "成功", "失败")):
            cur[1].append(ln)
        else:
            # unindented line after the list ends the list
            cur = None; pre.append(ln)
    return pre, items

def split_label(head: str):
    """Return (label, rest_of_line)."""
    m = BOLD_LEAD.match(head.strip())
    if m:
        lab, rest = m.group(1), m.group(2)
        lab = lab.rstrip("：:")
        if rest.startswith("：") or rest.startswith(":"):
            rest = rest[1:]
        return lab, rest
    # "label：rest" plain bullet
    m = re.match(r"^([^：:。，“【〔`]{2,18})[：:]\s*(.*)$", head.strip())
    if m:
        return m.group(1), m.group(2)
    # "label，rest" — take first clause
    m = re.match(r"^([^，。；“【〔]{2,16})[，；]\s*(.*)$", head.strip())
    if m:
        return m.group(1), m.group(2)
    return head.strip(), ""

OUTCOME = re.compile(r"(关键失败|大成功|成功|失败)(?:时)?[：:，]?")

def outcome_segments(s: str):
    """Split 'xxx成功A；失败B' into [(kind|None, text)]."""
    segs, pos, kind = [], 0, None
    for m in OUTCOME.finditer(s):
        # only treat as marker at clause starts
        before = s[:m.start()]
        if m.start() != 0 and not re.search(r"[；。;，,\s〕]\s*$", before) and not re.search(r"(检定|DC\s*\d+)\s*$", before):
            continue
        if "也" in s[m.end():m.end() + 1] and m.group(1) == "失败":
            pass
        segs.append((kind, s[pos:m.start()]))
        kind = {"大成功": "success", "成功": "success", "关键失败": "fail", "失败": "fail"}[m.group(1)]
        pos = m.end()
    segs.append((kind, s[pos:]))
    return [(k, t) for k, t in segs if t.strip()]

def arrows(s: str):
    nxt = None
    for m in re.finditer(r"→\s*`?(" + NODE_ID_RX + r")`?", s):
        nxt = m.group(1)
    if nxt is None:
        for m in re.finditer(r"(?:进入|前往|转入|跳到|可走)[^`，。；]{0,12}`(" + NODE_ID_RX + r")`", s):
            nxt = m.group(1)
    if nxt is None and re.search(r"→\s*返回", s):
        nxt = "__SELF__"
    if nxt and "/" in nxt:
        nxt = nxt.split("/")[0]
    return nxt

def _first_is_rest(txt, rest):
    return bool(rest) and txt.strip() == re.sub(r"〔(?!检定|效果|战斗)(?![^〕]*DC)[^〕]*〕", "", rest).strip()

def fallback_text(kind, check, label):
    CTX.fallbacks += 1
    stat = (check or {}).get("stats", ["INS"])[0] if check else None
    if kind == "fail":
        return {
            "STR": "力气差了一点，事情没能按你想的发展。", "DEX": "你的动作慢了半拍，没能成功。",
            "CON": "你的身体撑不住，只得作罢。", "CHA": "对方并不买账。", "INS": "你没能看出更多端倪。",
            "WIL": "那股冲动压过了你，这一次你没能守住。",
        }.get(stat, "事情没有按你想的发展。")
    if kind == "success":
        return {
            "STR": "你咬牙发力，成了。", "DEX": "你动作干净利落。", "CON": "你硬撑了下来。",
            "CHA": "对方被你说动了。", "INS": "你看出了关键。", "WIL": "你守住了自己。",
        }.get(stat, "你做到了。")
    lab = re.sub(r"[。！？]$", "", label).strip("“”\"")
    if lab.startswith(("“", "\"")) or "“" in label:
        return "你把话说出口，对方沉默片刻，记下了。"
    return f"你决定：{lab}。"

def build_choice(head: str, children: list[str], cid: str, ctx_npc=None):
    lab_raw, rest = split_label(head)
    ch = {"id": cid, "label": "", "result": [], "effects": [], "next": None}
    # inline annotations on the label line
    raw_ann = re.findall(r"〔([^〕]*)〕", lab_raw + " " + rest)
    for a in raw_ann:
        if a.startswith("检定") or re.search(r"DC\s*\d", a) or a.startswith("战斗"):
            continue
        if a.startswith("始终可见"):
            mm = re.search(r"若(.+?)则标注[“\"](.+?)[”\"]", a)
            if mm:
                ch["mark"] = {"cond": parse_cond(mm.group(1)), "suffix": mm.group(2)}
            continue
        if a.startswith(("效果",)):
            continue
        c = parse_cond(a)
        if c:
            ch["cond"] = c if "cond" not in ch else {"all": [ch["cond"], c]}
        else:
            ch.setdefault("cond_note", []).append(a)
    lab_noann = re.sub(r"〔[^〕]*〕", "", lab_raw)
    ch["label"] = label_clean(lab_noann)
    rest_noann = re.sub(r"〔(?!检定|效果|战斗)(?![^〕]*DC)[^〕]*〕", "", rest)
    lines = []
    if rest_noann.strip():
        lines.append((0, rest_noann.strip()))
    child_base = min((indent_of(l) for l in children), default=0)
    sub_items = []
    i = 0
    while i < len(children):
        ln = children[i]
        ind = indent_of(ln) - child_base
        txt = re.sub(r"^\s*[-*]\s+", "", ln).strip()
        bm = BOLD_LEAD.match(txt)
        if bm and (txt.startswith("**“") or txt.startswith("**\"") or "→" in txt or ind == 0 and len(bm.group(1)) <= 24 and not bm.group(1).endswith(("：", ":"))):
            # nested option → sub-choice (collect its deeper children)
            kids = []
            j = i + 1
            while j < len(children) and indent_of(children[j]) - child_base > ind:
                kids.append(children[j]); j += 1
            sub_items.append((txt, kids))
            i = j; continue
        lines.append((ind, txt)); i += 1

    check, _, _ = find_check(lab_raw)
    if check is None:
        _c, _s, _e = find_check(rest)
        if _c and not re.search(r"(成功|失败)", rest[_e:]):
            check = _c
    branch = {"success": {"result": [], "effects": [], "next": None}, "fail": {"result": [], "effects": [], "next": None}}
    after_check = check is not None
    pay_alt = None
    for ind, txt in lines:
        if re.fullmatch(r"→\s*`?[^`]*`?。?", txt) or txt.startswith("→"):
            n = arrows(txt)
            if n: ch["next"] = n
            continue
        nx = arrows(txt)
        # payment-or-check alternative
        pm = re.search(r"需要\s*(\d+)\s*张?票据", txt)
        ck, cs, ce = find_check(txt)
        if pm and ck:
            pay_alt = int(pm.group(1))
        elif pm and not ck:
            ch["cost"] = {"vouchers": int(pm.group(1))}
        if txt.startswith("〔效果〕") or txt.startswith("效果："):
            ops = parse_effects(txt)
            ch["effects"] += ops
            tail = sanitize(re.sub(r"^〔效果〕|^效果：", "", txt))
            if tail: ch["result"].append({"t": "p", "text": tail})
            if nx: ch["next"] = nx
            continue
        if ck and check is not None and cs <= 2 and not after_check:
            pass
        if ck and (check is None or (txt is not None and lines and lines[0][1] == txt and _first_is_rest(txt, rest))):
            if check is not None and lines[0][1] == txt:
                ck = check
            check = ck
            after_check = True
            before, after = txt[:cs], txt[ce:]
            if re.search(r"自动成功", txt[:cs]) or "有钥匙" in before:
                pass
            am = re.search(r"若([^，,；]{1,12})[，,]\s*(?:可|则)?([^；;]*?)[；;，,]\s*否则\s*$", before)
            if am:
                ac = parse_cond(am.group(1))
                if ac:
                    check["auto_if"] = ac
                    check["auto_text"] = narrate(sanitize(am.group(2)))
                before = before[:am.start()]
            if pm:
                before = ""
            if before.strip():
                b = prose_block(before)
                if b and not re.search(r"需要\s*\d+\s*张?票据", before):
                    ch["result"].append(b)
            segs = outcome_segments(after)
            first = True
            for kind, seg in segs:
                k = kind or "success"
                tgt = branch[k]
                tgt["effects"] += parse_effects(seg)
                n2 = arrows(seg)
                if n2: tgt["next"] = n2
                if "失败也可进入" in txt or ("也可进入" in seg and k == "fail"):
                    tgt["also"] = True
                seg_clean = re.sub(r"^(?:也可进入|仍可进入)[，,]?\s*(?:但)?", "", seg.strip())
                if pm and k == "success" and not kind:
                    continue
                b = narrate(sanitize(seg_clean)) if sanitize(seg_clean) else ""
                if seg_clean.strip().startswith(("也可进入", "仍可进入")):
                    b = narrate(sanitize(seg.strip()))
                if b and len(b) > 3:
                    tgt["result"].append({"t": "p", "text": b})
                first = False
            continue
        om = re.match(r"^(关键失败|大成功|成功|失败)[：:]\s*(.*)$", txt)
        if om and (check or pay_alt):
            k = "success" if om.group(1) in ("成功", "大成功") else "fail"
            seg = om.group(2)
            branch[k]["effects"] += parse_effects(seg)
            if nx: branch[k]["next"] = nx
            b = prose_block(seg)
            if b:
                if b["t"] == "p": b["text"] = narrate(b["text"])
                branch[k]["result"].append(b)
            continue
        if om and not check:
            # outcome text without a parsable check → treat as plain result
            txt = om.group(2)
        # inline outcomes in a plain line after check: "成功X；失败Y"
        if check and re.search(r"(^|[；。，])\s*(成功|失败)", txt) and not txt.startswith("【"):
            for kind, seg in outcome_segments(txt):
                k = kind or "success"
                branch[k]["effects"] += parse_effects(seg)
                b = sanitize(seg)
                if b and len(b) > 3: branch[k]["result"].append({"t": "p", "text": narrate(b)})
            continue
        if DEV_LINE.search(txt):
            continue
        ops = parse_effects(txt)
        if nx and not ch["next"]:
            ch["next"] = nx
        if txt.startswith(("代价：", "后果：")):
            b = sanitize(txt)
            ch["effects"] += ops
            if b: ch["result"].append({"t": "note", "text": b})
            continue
        cond = None
        cm = re.match(r"^若([^，,：:]{1,30})[，,：:]", txt)
        if cm:
            cond = parse_cond(cm.group(1))
        b = prose_block(txt)
        if cond is not None and ops:
            ch.setdefault("cond_effects", []).append({"cond": cond, "ops": ops})
            ops = []
        if after_check and b and b["t"] == "p" and not cond:
            branch["success"]["result"].append(b)
            branch["success"]["effects"] += ops
        else:
            if b:
                if cond: b["cond"] = cond
                ch["result"].append(b)
            ch["effects"] += ops
    if check:
        ch["check"] = check
        for k in ("success", "fail"):
            br = branch[k]
            if not br["result"]:
                br["result"].append({"t": "p", "text": fallback_text(k, check, ch["label"])})
                br["fallback"] = True
            if br.get("also") and not br["next"]:
                br["next"] = branch["success"]["next"] or ch["next"]
            br.pop("also", None)
            if not br["next"]:
                br["next"] = None
            if not br["effects"]:
                br.pop("effects")
            ch[k] = br
    else:
        for b in ch["result"]:
            if b.get("text"):
                b["text"] = re.sub(r"^(?:成功|大成功)(?:时)?[，：:]?", "", b["text"]) or b["text"]
        # outcome bits without check (e.g. pay alternative) fold into result
        for k in ("success",):
            ch["result"] += branch[k]["result"]; ch["effects"] += branch[k]["effects"]
            if branch[k]["next"] and not ch["next"]:
                ch["next"] = branch[k]["next"]
    # sub-choices
    subs = []
    for j, (shead, skids) in enumerate(sub_items):
        sc = build_choice(shead, skids, f"{cid}.{j+1}", ctx_npc)
        subs.append(sc)
    if subs:
        ch["sub"] = subs
    if not ch["label"]:
        ch["label"] = "继续"
    if pay_alt:
        ch["pay_alt"] = pay_alt
    if not ch.get("check") and not ch["result"] and not subs:
        ch["result"].append({"t": "p", "text": fallback_text(None, None, ch["label"])})
        ch["fallback"] = True
    if ctx_npc:
        for e in [*ch["effects"], *(ch.get("success", {}).get("effects") or []), *(ch.get("fail", {}).get("effects") or [])]:
            pass
    return ch

def expand_pay_alt(ch):
    """'需要 8 张票据；或 CHA DC 13' → two choices: pay (auto success) and talk (check)."""
    n = ch.pop("pay_alt", None)
    if not n:
        return [ch]
    pay = json.loads(json.dumps(ch))
    pay["id"] = ch["id"] + "p"
    pay["label"] = ch["label"]
    pay["cost"] = {"vouchers": n}
    pay.pop("check", None)
    succ = pay.pop("success", {})
    pay.pop("fail", None)
    pay["result"] = ch["result"] + [b for b in succ.get("result", []) if not succ.get("fallback")]
    pay["effects"] = ch["effects"] + succ.get("effects", [])
    pay["next"] = succ.get("next") or ch["next"]
    pay["group_with"] = ch["id"]
    return [pay, ch]

# ------------------------------------------------------------------ sections / nodes

def split_sections(lines):
    secs, cur = [], {"h": None, "level": 2, "lines": []}
    secs.append(cur)
    for ln in lines:
        m = re.match(r"^(#{3,4})\s+(.*)$", ln)
        if m:
            cur = {"h": m.group(2).strip(), "level": len(m.group(1)), "lines": []}
            secs.append(cur); continue
        cur["lines"].append(ln)
    return secs

def section_kind(sec, node_id):
    h = sec["h"] or ""
    body = [l for l in sec["lines"] if l.strip()]
    if any(k in h for k in DEV_HEADINGS):
        return "dev"
    numbered = sum(1 for l in body if OPT_NUM.match(l) and indent_of(l) == 0)
    bullets = [l for l in body if OPT_BUL.match(l) and indent_of(l) == 0]
    bold_b = sum(1 for l in bullets if BOLD_LEAD.match(re.sub(r"^\s*[-*]\s+", "", l)))
    if "选择" in h or numbered >= 2:
        return "choices_num" if numbered else ("choices_bul" if bullets else "prose")
    if bullets and (bold_b >= 2 or (node_id.startswith(("R-", "CITY-AMBIENT", "C-")) and len(bullets) >= 2)):
        return "choices_bul"
    if bullets and node_id.startswith(("C-",)):
        return "choices_bul"
    if h in ("调查仪式", "办法", "起势", "处理", "解决", "行动", "可用方式", "开门方式", "调查目标", "检查尸体",
             "唤醒矿工", "制动危机", "倒塌", "下降", "追逐", "撤离分配", "公开处理", "谁留下") and bullets:
        return "choices_bul"
    if h.startswith(("第一轮", "第二轮", "第三轮", "方案")) and bullets:
        return "choices_bul"
    return "prose"

def heading_cond(h):
    if not h:
        return None
    for name, pc in T.PCS.items():
        if h.startswith(name + "：") or h.startswith(name + ":"):
            return {"pc": pc}
    if h.startswith("若") or "路线" in h or "专属" in h:
        return parse_cond(h)
    return None

def parse_prose_lines(lines, cond=None, nid=""):
    blocks, enter_effects, routes, default_next, notes = [], [], [], None, []
    para = []
    def flush():
        if para:
            txt = "".join(p.strip() for p in para)
            b = prose_block(txt, cond)
            if b: blocks.append(b)
            para.clear()
    for ln in lines:
        s = ln.strip()
        if not s:
            flush(); continue
        if s.startswith("```") or DEV_LINE.search(s):
            flush(); continue
        if s.startswith("|"):
            flush(); continue
        m = re.match(r"^〔(进入|触发|来源|条件|可见|始终可见[^〕]*)〕\s*(.*)$", s)
        if m:
            flush()
            notes.append(m.group(1) + "：" + m.group(2))
            if m.group(1) == "可见" or m.group(1) == "条件":
                c = parse_cond(m.group(2))
                if c: cond = c
            continue
        m = re.match(r"^〔([^〕]*)〕\s*$", s)
        if m and not m.group(1).startswith("效果"):
            flush()
            c = parse_cond(m.group(1))
            cond = c
            notes.append("cond:" + m.group(1))
            continue
        if s.startswith("〔效果〕"):
            flush(); enter_effects += parse_effects(s); continue
        if s.startswith("→") or re.fullmatch(r".{0,20}→\s*`?" + NODE_ID_RX + r"`?.{0,30}", s):
            flush()
            n = arrows(s)
            if n:
                rc = parse_cond(s.split("→")[0]) if "若" in s.split("→")[0] else None
                if rc:
                    routes.append({"cond": rc, "next": n})
                else:
                    default_next = n
            continue
        if re.match(r"^\s*[-*]\s+", ln) or s.startswith("【") or s.startswith(">"):
            flush()
            sm = re.match(r"^\s*[-*]\s+([^：:]{2,10})路线[：:]\s*(.*)$", ln)
            if sm and sm.group(1) in T.PCS:
                b = prose_block(sm.group(2), {"pc": T.PCS[sm.group(1)]})
            else:
                b = prose_block(s, cond)
            if b: blocks.append(b)
            continue
        para.append(s)
    flush()
    return blocks, enter_effects, routes, default_next, notes

def build_node(r):
    nid = r["id"]
    node = {"id": nid, "title": label_clean(r["title"]) or nid, "source": r["source"], "kind": "scene",
            "blocks": [], "choices": [], "default_next": None, "routes": [], "enter_effects": []}
    if r.get("pool"): node["pools"] = [r["pool"]]; node["kind"] = "random"
    if nid.startswith("END"): node["kind"] = "ending"
    if r.get("fail"): node["kind"] = "ending"; node["fail"] = True
    if nid.startswith(("D-", "CITY-NPC")): node["kind"] = "dialogue"
    if nid.startswith("C-"): node["kind"] = "combat"
    if nid.startswith("LOC-"): node["kind"] = "hub"
    topic_mode = nid.startswith(TOPIC_PREFIXES) or nid in TOPIC_NODES
    secs = split_sections(r["lines"])
    seq = nid in SEQ_NODES or (nid.startswith("C-") and any("转折" in (x["h"] or "") for x in secs))
    parent_h, parent_cond, last_topic, round_idx = None, None, None, 0
    for si, sec in enumerate(secs):
        h = sec["h"] or ""
        hcond = heading_cond(h) if si > 0 else None
        if sec["level"] == 3 or si == 0:
            parent_h, parent_cond, last_topic = (h or None), hcond, None
        eff_cond = hcond if sec["level"] == 3 else (hcond or parent_cond)
        kind = section_kind(sec, nid)
        if kind == "dev":
            continue
        if kind == "prose":
            blocks, ee, routes, dn, notes = parse_prose_lines(sec["lines"], eff_cond, nid)
            if topic_mode and h and si > 0 and blocks and not eff_cond:
                for bb in blocks: bb.pop("cond", None)
                tc = {"id": f"t{si}", "label": label_clean(h), "result": blocks, "effects": ee, "next": None, "topic": True}
                node["choices"].append(tc); last_topic = tc
                ee = []
            elif topic_mode and h and si > 0 and blocks and last_topic is not None and sec["level"] == 4:
                last_topic["result"] += blocks
            else:
                if h and si > 0 and blocks and not eff_cond and not h.startswith(("区域正文", "选择")):
                    hb = {"t": "h", "text": label_clean(h)}
                    if seq: hb["round"] = round_idx
                    node["blocks"].append(hb)
                if seq:
                    for bb in blocks: bb["round"] = round_idx
                node["blocks"] += blocks
            node["enter_effects"] += ee
            node["routes"] += routes
            if dn: node["default_next"] = dn
            continue
        numbered = kind == "choices_num"
        pre, items = gather_items(sec["lines"], numbered)
        sec_cond = None
        pre_lines = []
        for p in pre:
            m = re.match(r"^\s*〔([^〕]*)〕\s*(.*)$", p.strip())
            if m and not m.group(1).startswith(("效果", "检定")):
                c = parse_cond(m.group(1)); sec_cond = c or sec_cond
                rest = m.group(2)
                if rest.strip():
                    c2 = parse_cond(rest)
                    if c2: sec_cond = {"all": [x for x in (sec_cond, c2) if x]}
                continue
            pre_lines.append(p)
        allc = [x for x in (sec_cond, eff_cond) if x]
        sec_cond = None if not allc else (allc[0] if len(allc) == 1 else {"all": allc})
        pblocks, ee, routes, dn, _ = parse_prose_lines(pre_lines, None, nid)
        node["enter_effects"] += ee
        node["routes"] += routes
        if dn: node["default_next"] = dn
        group = None
        if h and h != "选择" and not hcond:
            group = label_clean(h)
        elif h == "选择" and sec["level"] == 4 and parent_h and not parent_cond:
            group = label_clean(parent_h)
        built = []
        for k, (head, kids) in enumerate(items):
            c = build_choice(head, kids, f"s{si}c{k+1}")
            built += expand_pay_alt(c)
        if topic_mode:
            if sec["level"] == 4 and last_topic is not None:
                if pblocks: last_topic["result"] += pblocks
                last_topic.setdefault("sub", []).extend(built)
                continue
            if h and h != "选择" and si > 0:
                tc = {"id": f"t{si}", "label": group or label_clean(h) or "交谈",
                      "result": pblocks or [{"t": "p", "text": fallback_text(None, None, group or "交谈")}],
                      "effects": [], "next": None, "topic": True, "sub": built}
                if sec_cond: tc["cond"] = sec_cond
                node["choices"].append(tc); last_topic = tc
                continue
        if pblocks:
            if group and not topic_mode and len(built) and (seq or sec["level"] == 3):
                pblocks.insert(0, {"t": "h", "text": group})
            for bb in pblocks:
                if sec_cond and "cond" not in bb: bb["cond"] = sec_cond
                if seq: bb["round"] = round_idx
            node["blocks"] += pblocks
        for c in built:
            if group and not seq: c["group"] = group
            if sec_cond: c["cond"] = {"all": [c["cond"], sec_cond]} if c.get("cond") else sec_cond
            c["round"] = round_idx if seq else 0
            node["choices"].append(c)
        if seq and built:
            round_idx += 1
    node["rounds"] = max(1, round_idx) if seq else 1
    if r.get("ambients"):
        node["ambients"] = r["ambients"]
    return node

def split_rounds(nodes):
    """A node with several sequential choice sections becomes NID, NID~2, ... chained."""
    out = {}
    for nid, n in nodes.items():
        R = n.pop("rounds", 1)
        if R <= 1 or n["kind"] in ("dialogue", "hub"):
            for c in n["choices"]: c.pop("round", None)
            for b in n["blocks"]: b.pop("round", None)
            out[nid] = n; continue
        final_next = n["default_next"]
        parts = []
        for r_i in range(R):
            pid = nid if r_i == 0 else f"{nid}~{r_i+1}"
            p = dict(n) if r_i == 0 else {"id": pid, "title": n["title"], "source": n["source"], "kind": n["kind"],
                                          "blocks": [], "choices": [], "default_next": None, "routes": [], "enter_effects": []}
            p["blocks"] = [b for b in n["blocks"] if b.get("round", 0) == r_i] if r_i else [b for b in n["blocks"] if not b.get("round")]
            p["choices"] = [c for c in n["choices"] if c.get("round", 0) == r_i]
            for c in p["choices"]: c.pop("round", None)
            for b in p["blocks"]: b.pop("round", None)
            parts.append(p)
        for i, p in enumerate(parts):
            nxt = parts[i + 1]["id"] if i + 1 < len(parts) else final_next
            p["default_next"] = nxt
            if i + 1 < len(parts):
                p["routes"] = []
                p["pick_one"] = True
            if not p["blocks"]:
                p["blocks"] = [{"t": "p", "text": "局面还没有结束。"}]
            out[p["id"]] = p
    return out

def main():
    raw = read_all()
    nodes = {}
    for r in raw:
        if r["id"] in nodes:
            continue
        nodes[r["id"]] = build_node(r)
    nodes = split_rounds(nodes)
    import wzc_patches
    wzc_patches.apply(nodes, epilogues())
    finalize(nodes)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    meta = wzc_patches.meta(nodes)
    unresolved = set()
    for node in nodes.values():
        stack = list(node.get("choices") or [])
        while stack:
            choice = stack.pop()
            unresolved.update(choice.get("cond_note") or [])
            stack.extend(choice.get("sub") or [])
    meta["unknown_conditions"] = sorted(unresolved)
    meta["fallback_texts"] = CTX.fallbacks
    meta["item_keys_without_name"] = sorted(k for k in CTX.items if k not in ITEM_NAMES)
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"v2 parse: {len(nodes)} nodes; unresolved conds {len(unresolved)}; fallback texts {CTX.fallbacks}; "
          f"unnamed items {len(meta['item_keys_without_name'])}")

def finalize(nodes):
    """Resolve choice next defaults & once flags."""
    for nid, n in nodes.items():
        dn = n.get("default_next")
        def fix(c, top=True):
            for k in ("success", "fail"):
                if c.get(k) and c[k].get("next") == "__SELF__":
                    c[k]["next"] = "__SELF__"
            if c.get("next") is None and not c.get("success", {}).get("next") and not c.get("sub"):
                if top and dn and not n.get("stay_choices") and not c.get("topic"):
                    c["next"] = dn
                else:
                    c["next"] = "__SELF__"
            if c.get("next") in (None, "__SELF__") or (c.get("success") and c["success"].get("next") in (None, "__SELF__")):
                c.setdefault("once", True)
            for s in c.get("sub") or []:
                fix(s, False)
        for c in n["choices"]:
            fix(c)
        if not n["routes"]:
            n.pop("routes")
        if not n["enter_effects"]:
            n.pop("enter_effects")

if __name__ == "__main__":
    main()
