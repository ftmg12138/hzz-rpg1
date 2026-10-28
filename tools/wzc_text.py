"""Text helpers for the v2 parser: effect/condition/check extraction and display sanitizing."""
from __future__ import annotations
import re

STATS = ["STR", "DEX", "CON", "CHA", "INS", "WIL"]
STAT_CN = {"STR": "力量", "DEX": "敏捷", "CON": "体魄", "CHA": "魅力", "INS": "洞察", "WIL": "意志"}
STAT_RX = r"(?:STR|DEX|CON|CHA|INS|WIL)"
NODE_ID_RX = r"(?:[A-Z][A-Z0-9]*-(?:[A-Z0-9]+-)*[A-Z0-9]+(?:/[A-Z])*)"
PCS = {"艾德里克": "edric", "莉瑞尔": "liriel", "索林": "thorin"}

# ---------------------------------------------------------------- effects
IDENT = r"[A-Za-z_][\w.]*"

def coerce(v: str):
    v = v.strip().strip("；;，,。")
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    if re.fullmatch(r"[+-]?\d+", v):
        return int(v)
    return v

class Ctx:
    """Per-parse context collecting unknowns and item keys."""
    def __init__(self):
        self.items: set[str] = set()
        self.flags: set[str] = set()
        self.unknown_conds: list[str] = []
        self.fallbacks = 0

CTX = Ctx()

ITEM_VERBS = r"(?:获得|取得|得到|拿到|得|拿走|带走|找到|捡到|收下|获取)"

def parse_backtick_expr(expr: str, item_hint: bool) -> list[dict]:
    ops = []
    # split top-level on ; ； and also commas not inside brackets/parens
    parts, depth, cur = [], 0, ""
    for ch in expr:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch in ";；" or (ch in ",，" and depth == 0):
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.fullmatch(rf"({IDENT})\s*=\s*max\(\s*{IDENT}\s*,\s*(-?\d+)\s*\)", p)
        if m:
            ops.append({"op": "max", "k": m.group(1), "v": int(m.group(2))}); continue
        m = re.fullmatch(rf"({IDENT})\s*=\s*min\(\s*{IDENT}\s*,\s*(-?\d+)\s*\)", p)
        if m:
            ops.append({"op": "min", "k": m.group(1), "v": int(m.group(2))}); continue
        m = re.fullmatch(rf"({IDENT})\s*\+=\s*\[([^\]]*)\]", p)
        if m:
            for v in m.group(2).split(","):
                if v.strip():
                    ops.append({"op": "push", "k": m.group(1), "v": v.strip()})
            continue
        m = re.fullmatch(rf"({IDENT})\s*(\+=|-=)\s*(-?\d+)", p)
        if m:
            n = int(m.group(3)) * (1 if m.group(2) == "+=" else -1)
            ops.append({"op": "add", "k": m.group(1), "v": n}); continue
        m = re.fullmatch(rf"({IDENT})\s*([+-]\s*\d+)", p)
        if m:
            ops.append({"op": "add", "k": m.group(1), "v": int(m.group(2).replace(" ", ""))}); continue
        m = re.fullmatch(rf"({IDENT})\s*=\s*(.+)", p)
        if m:
            ops.append({"op": "set", "k": m.group(1), "v": coerce(m.group(2))}); continue
        m = re.fullmatch(rf"({IDENT})\s+(-?\d+)", p)
        if m:  # `alarm_town 3`
            ops.append({"op": "set", "k": m.group(1), "v": int(m.group(2))}); continue
        m = re.fullmatch(rf"({IDENT})", p)
        if m:
            k = m.group(1)
            if re.fullmatch(NODE_ID_RX, k) or k.upper() == k and "-" in k:
                continue
            if item_hint:
                ops.append({"op": "item", "k": k}); CTX.items.add(k)
            else:
                ops.append({"op": "set", "k": k, "v": True}); CTX.flags.add(k)
            continue
        # conditions/formulas in backticks (e.g. `time >= 3`, `d20 + ...`) are not effects
    return ops

CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}

def parse_effects(s: str, cond_context: bool = False) -> list[dict]:
    """Extract effect ops from a raw script line (backticks + common Chinese phrasings)."""
    ops: list[dict] = []
    if not s:
        return ops
    for m in re.finditer(r"`([^`]+)`", s):
        expr = m.group(1).strip()
        if re.fullmatch(NODE_ID_RX, expr) or re.search(r"[<>]|>=|<=|==|d20|非 ", expr):
            continue
        before = s[max(0, m.start() - 6): m.start()]
        item_hint = bool(re.search(ITEM_VERBS + r"\s*$", before)) or bool(re.search(r"(获得|取得|得到)[^，。；`]{0,4}$", before))
        if cond_context and not re.search(r"[=+\-]", expr):
            continue
        ops.extend(parse_backtick_expr(expr, item_hint))
    t = re.sub(r"`[^`]*`", "", s)
    for m in re.finditer(r"失去\s*(\d+)\s*(?:HP|点体力|点生命)", t):
        ops.append({"op": "hp", "v": -int(m.group(1))})
    for m in re.finditer(r"(?:受|承受|受到)\s*(\d+)\s*点[^，。；]{0,4}?伤", t):
        ops.append({"op": "hp", "v": -int(m.group(1))})
    for m in re.finditer(r"(?:恢复|回复)\s*(\d+)\s*(?:HP|点体力)", t):
        ops.append({"op": "hp", "v": int(m.group(1))})
    for m in re.finditer(r"(?<![花付需要交])(?:得到|获得|得|拿到|换得)\s*(\d+)\s*张?票据", t):
        ops.append({"op": "add", "k": "vouchers", "v": int(m.group(1))})
    for m in re.finditer(r"(?:花|付|支付|交出|花费)\s*(\d+)\s*张?票据", t):
        ops.append({"op": "add", "k": "vouchers", "v": -int(m.group(1))})
    for m in re.finditer(r"诅咒阶段\s*([+-]\s*\d+)", t):
        ops.append({"op": "add", "k": "curse_stage", "v": int(m.group(1).replace(" ", ""))})
    for m in re.finditer(r"城市声望\s*([+-]\s*\d+)", t):
        ops.append({"op": "add", "k": "city_rep", "v": int(m.group(1).replace(" ", ""))})
    for m in re.finditer(r"(?:残片压力|压力)\s*([+-]\s*\d+)", t):
        ops.append({"op": "add", "k": "fragment_pressure", "v": int(m.group(1).replace(" ", ""))})
    for m in re.finditer(r"使用残片\s*([+-]\s*\d+)", t):
        ops.append({"op": "add", "k": "fragment_used", "v": int(m.group(1).replace(" ", ""))})
    for m in re.finditer(r"共鸣\s*([+-]\s*\d+)", t):
        ops.append({"op": "add", "k": "resonance", "v": int(m.group(1).replace(" ", ""))})
    if re.search(r"(失去|耗|耗掉|花|耗时)(一|1)格时间", t):
        ops.append({"op": "add", "k": "time", "v": 1})
    for m in re.finditer(r"下一次\s*(?:对[^，；。]{0,6})?\s*(" + STAT_RX + r")?\s*检定(?:有)?(优势|劣势)", t):
        ops.append({"op": "adv" if m.group(2) == "优势" else "dis", "k": m.group(1) or "*"})
    # dedupe hp ops coming from both regexes on the same number
    seen, out = set(), []
    for o in ops:
        key = repr(sorted(o.items()))
        if key in seen and o["op"] in ("hp",):
            continue
        seen.add(key); out.append(o)
    return out

# ---------------------------------------------------------------- checks
DC_RX = re.compile(
    r"(?:〔\s*(?:检定[：:]\s*)?)?"
    r"(?P<stats>(?:(?:战斗|短战斗|攻击)\s*或\s*)?" + STAT_RX + r"(?:\s*(?:/|或|、|／)\s*" + STAT_RX + r")*)"
    r"\s*(?:攻击|检定)?\s*[，,]?\s*DC\s*(?P<dc>\d+)"
    r"(?P<mods>[^〕\n]*?〕|)"
)

def find_check(s: str):
    m = DC_RX.search(s)
    if m:
        stats = re.findall(STAT_RX, m.group("stats"))
        ck = {"stats": stats, "dc": int(m.group("dc"))}
        if re.search(r"战斗", m.group("stats")):
            ck["combat"] = True
        mods = m.group("mods") or ""
        tail = s[m.end(): m.end() + 40]
        modtxt = mods + " " + tail.split("。")[0]
        am = re.search(r"`(\w+)`\s*(?:时|则)?(?:有)?优势", s)
        if am:
            ck["adv_if"] = {"flag": am.group(1)}
        if "莉瑞尔使用银链可自动成功" in mods:
            ck["auto_if"] = {"all": [{"pc": "liriel"}]}
        lm = re.search(r"降至\s*(\d+)", modtxt)
        if lm:
            ck["dc_alt"] = int(lm.group(1))
        return ck, m.start(), m.end()
    # bare stat attack "DEX 攻击"
    m = re.search(r"(" + STAT_RX + r")\s*攻击", s)
    if m:
        return {"stats": [m.group(1)], "dc": 13, "combat": True}, m.start(), m.end()
    m = re.search(r"(" + STAT_RX + r"(?:\s*/\s*" + STAT_RX + r")*)\s*(?:检定|判定)", s)
    if m and "下一次" not in s[max(0, m.start() - 8): m.start()]:
        return {"stats": re.findall(STAT_RX, m.group(1)), "dc": 13}, m.start(), m.end()
    return None, -1, -1

# ---------------------------------------------------------------- conditions
COND_WORDS = [
    # phrase, condition
    ("汤姆同行", {"flag": "tom_with"}),
    ("汤姆在场", {"flag": "tom_with"}),
    ("救下彼得", {"flag": "peter_saved"}),
    ("彼得获救", {"flag": "peter_saved"}),
    ("救下汤姆", {"flag": "tom_saved"}),
    ("汤姆获救", {"flag": "tom_saved"}),
    ("已使用残片", {"cmp": ["fragment_used", ">=", 1]}),
    ("使用过残片", {"cmp": ["fragment_used", ">=", 1]}),
    ("有钥匙", {"flag": "family_cache_key"}),
    ("同伴在场", {"flag": "companion"}),
    ("关系 <=0", {"cmp": ["@rel", "<=", 0]}),
    ("关系 >=1", {"cmp": ["@rel", ">=", 1]}),
    ("关系 >=2", {"cmp": ["@rel", ">=", 2]}),
    ("关系至少 +1", {"cmp": ["@rel", ">=", 1]}),
    ("关系至少 0", {"cmp": ["@rel", ">=", 0]}),
    ("哈兰在场", {"flag": "harlan_present"}),
    ("有帝国文书", {"any": [{"flag": "harlan_writ"}, {"flag": "imperial_pass"}]}),
    ("托伦存活", {"not": {"flag": "toren_dead"}}),
    ("携带炸药", {"any": [{"flag": "explosives"}, {"flag": "imperial_fuse"}]}),
    ("有炸药", {"any": [{"flag": "explosives"}, {"flag": "imperial_fuse"}]}),
    ("照心骨缺席", {"not": {"flag": "four_bones_present"}}),
    ("若玩家接受转移", {"flag": "curse_transferred"}),
    ("若玩家中止仪式", {"flag": "ritual_stopped"}),
    ("城市声望非负", {"cmp": ["city_rep", ">=", 0]}),
    ("curse_stage >=4", {"cmp": ["curse_stage", ">=", 4]}),
]
for name, pc in PCS.items():
    COND_WORDS.append((name + "路线", {"pc": pc}))
    COND_WORDS.append(("仅" + name, {"pc": pc}))
    COND_WORDS.append(("若玩家是" + name, {"pc": pc}))
    COND_WORDS.append(("若玩家不是" + name, {"not": {"pc": pc}}))
    COND_WORDS.append((name + "专属", {"pc": pc}))

def parse_cond(raw: str):
    """Parse a natural-language/backtick condition. Returns AST or None if not understood."""
    s = raw.strip().strip("〔〕").strip()
    s = re.sub(r"^(仅|可见|需要|条件|触发)[：:]?\s*", "", s)
    if not s:
        return None
    parts = []
    # backtick comparisons / flags
    for m in re.finditer(r"(非\s*)?`([^`]+)`", s):
        e = m.group(2).strip()
        neg = bool(m.group(1))
        cm = re.fullmatch(rf"({IDENT})\s*(>=|<=|==|=|>|<)\s*(-?\d+|true|false)", e)
        if cm:
            v = coerce(cm.group(3))
            op = "==" if cm.group(2) == "=" else cm.group(2)
            c = {"cmp": [cm.group(1), op, v]}
        elif re.fullmatch(IDENT, e) and not re.fullmatch(NODE_ID_RX, e):
            c = {"flag": e}
        else:
            continue
        parts.append({"not": c} if neg else c)
    for m in re.finditer(rf"(?<![`\w])({IDENT})\s*(>=|<=|>|<)\s*(-?\d+)", re.sub(r"`[^`]*`", "", s)):
        parts.append({"cmp": [m.group(1), m.group(2), int(m.group(3))]})
    for m in re.finditer(r"(" + STAT_RX + r")\s*修正至少\s*\+?(\d+)", s):
        parts.append({"cmp": ["mod." + m.group(1), ">=", int(m.group(2))]})
    for phrase, c in COND_WORDS:
        if phrase in s:
            parts.append(c)
    if not parts:
        CTX.unknown_conds.append(raw.strip())
        return None
    if len(parts) == 1:
        return parts[0]
    if "或" in s and "且" not in s:
        return {"any": parts}
    return {"all": parts}

# ---------------------------------------------------------------- display sanitizing
ITEM_NAMES: dict[str, str] = {}

def _item_sub(m):
    k = m.group(2)
    name = ITEM_NAMES.get(k)
    return m.group(1) + (f"「{name}」" if name else "")

PUNCT_FIX = [
    (r"[ \t]+", " "),
    (r"\s*([，。；：！？、）」』”])", r"\1"),
    (r"([（「『“])\s*", r"\1"),
    (r"（\s*[，；、]*\s*）", ""),
    (r"「」", ""),
    (r"[，；、]+([。！？])", r"\1"),
    (r"([。！？])[，；、]+", r"\1"),
    (r"[，；、]{2,}", "，"),
    (r"；，|，；", "；"),
    (r"。{2,}", "。"),
    (r"^[，；、。：\s]+", ""),
    (r"[，；、：\s]+$", ""),
    (r"(与|和|及|或|并|且)([，；。]|$)", r"\2"),
    (r"(取得|获得|得到|使|并|且|但)\s*([。；])", r"\2"),
]

M = "\x00"

def drop_marked(t: str) -> str:
    """Drop every clause that still contains a stripped-mechanics marker."""
    if M not in t:
        return t
    parts = re.split(r"([，；。！？：])", t)
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        d = parts[i + 1] if i + 1 < len(parts) else ""
        if M in seg:
            if d in ("。", "！", "？") and out:
                out[-1] = out[-1].rstrip("，；：") + d
            continue
        out.append(seg + d)
    return "".join(out)

DESIGNER_CLAUSE = re.compile(r"玩家|解锁|检定|判定|优势|劣势|系统|节点|结算|修正|属性|状态栏|后日谈|结局|自动|占\s*\d+\s*格|一格|界面|变量|开发键|内部|指标|士气\s*\d|^\s*腐化\s*$|^\s*腐化|使用次数|主线|关系|先制|[降升]至\s*\d+|[降升]至\s*$|禁用|隐藏惩罚|^\s*环境\s*$|可作为|可用于|视为|声望|倾向|锚点|终幕|路线(?!图)|必然成功|最完整|一轮|(?:引发|需|各|并|取决于|的生死|无[^，。；“”]{1,3})\s*$|^\s*(?:成功|失败|大成功|关键失败)(?:时|则|且|后)?[：:]?|按[^，。；]{0,6}(?:状态|关系)")

IF_NOTE = re.compile(r"^若[^“”]*$")
IF_NOTE_WORDS = re.compile(r"否则|没有则|若没有|终幕|结局|获得|得到|声望|关系|变量|界面|惩罚|记入|视为|可成为|可恢复|恢复|更可能|更完整|安全|存活|死亡|被困|有效|成功|失败|同样|可|会")

def drop_if_notes(t: str) -> str:
    sents = re.findall(r"[^。！？]+[。！？]?", t)
    out = []
    for x in sents:
        core = x.strip()
        if IF_NOTE.match(core) and (IF_NOTE_WORDS.search(core) or not re.search(r"[，；：]", core)):
            continue
        out.append(x)
    return "".join(out)

HARD_DESIGNER = re.compile(r"界面|变量|开发键|玩家|标为")

def mark_designer(t: str) -> str:
    t = drop_if_notes(t)
    parts = re.split(r"([，；。！？：])", t)
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        d = parts[i + 1] if i + 1 < len(parts) else ""
        if (DESIGNER_CLAUSE.search(seg) and "“" not in seg and "”" not in seg) or HARD_DESIGNER.search(seg):
            seg = seg + M
        out.append(seg + d)
    return "".join(out)

def sanitize(s: str, label: bool = False) -> str:
    if not s:
        return ""
    t = s
    t = t.replace("**", "")
    t = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", t)
    t = re.sub(r"^#+\s*", "", t)
    # items mentioned after a verb become 「中文名」
    t = re.sub(r"(" + ITEM_VERBS + r"\s*)`(\w+)`", _item_sub, t)
    t = re.sub(r"(进入|解锁|触发|前往|转入|走向|可走[^`，。；]{0,10}|开放|跳到)\s*`" + NODE_ID_RX + r"`(?:\s*的[^，。；]*变体)?", lambda m: m.group(1) if not m.group(1).startswith("可走") else m.group(1)[2:], t)
    t = re.sub(r"`(\w+)`", lambda m: f"「{ITEM_NAMES[m.group(1)]}」" if m.group(1) in ITEM_NAMES else m.group(0), t)
    t = re.sub(r"`[^`]*`", M, t)
    t = re.sub(r"〔[^〕]*〕", "", t)
    t = re.sub(r"→\s*(?:`?" + NODE_ID_RX + r"`?|返回[^。；\n]*)[^。；\n]*", "", t)
    t = t.replace("→", "")
    # checks and mechanics
    t = re.sub(r"(?:(?:战斗|短战斗)\s*或\s*)?" + STAT_RX + r"(?:\s*(?:/|或|、|／)\s*" + STAT_RX + r")*\s*(?:攻击|检定)?\s*[，,]?\s*DC\s*\d+", M, t)
    t = re.sub(r"DC\s*\d+", M, t)
    t = re.sub(r"难度\s*[+-]\s*\d+", "难度更高", t)
    t = re.sub(r"下一次[^，；。]*?(?:检定|攻击)[^，；。]*?(?:优势|劣势)", "", t)
    t = re.sub(r"[^，；。]*?时(?:有)?(?:优势|劣势)", "", t)
    t = re.sub(r"(?:获得|得到)?一次[^，；。]{0,8}检定(?:优势|劣势)", "", t)
    t = re.sub(r"(" + STAT_RX + r")\s*攻击", "出手", t)
    t = re.sub(r"(" + STAT_RX + r")\s*(?:检定|判定)", "检定", t)
    t = re.sub(r"失去\s*(\d+)\s*HP", "受了伤", t)
    t = re.sub(r"HP\s*上限", "体力上限", t)
    t = re.sub(r"(\d+)\s*HP", r"\1 点体力", t)
    t = re.sub(r"(?:关系|城市声望|诅咒阶段|共鸣|残片压力|压力|使用残片)\s*[+-]\s*\d+", "", t)
    t = re.sub(r"(?:关系|声望)\s*(?:至少|不低于|达到|高于|低于)\s*[+-]?\s*\d+", M, t)
    t = re.sub(r"关系不变", "", t)
    t = re.sub(r"(\w)?rel\.\w+\s*(?:[<>=]=?|[+-])?\s*\d*", M, t)
    t = re.sub(r"\(\s*\)", "", t)
    t = t.replace("玩家", "你")
    t = re.sub(r"你们?自己", lambda m: m.group(0), t)
    t = re.sub(r"(?<![A-Za-z])" + STAT_RX + r"(?![A-Za-z])", M, t)
    t = re.sub(r"[A-Za-z_][\w./-]*(?:\s*(?:[<>=]=?|[+-])\s*\d+)?", M, t)
    t = re.sub(r"(?<=[\u4e00-\u9fff）])\s*[+-]\d+", "", t)
    t = re.sub(r"\s[+-]\d+", "", t)
    if not label:
        t = t.replace("触发", "引发")
        t = mark_designer(t)
    if label:
        t = re.sub(r"[：:，]?\s*占\s*\d+\s*格", "", t)
    t = t.replace(M, "") if label else drop_marked(t)
    for a, b in PUNCT_FIX:
        t = re.sub(a, b, t)
    for a, b in PUNCT_FIX:
        t = re.sub(a, b, t)
    t = polish(t.strip())
    if re.fullmatch(r"[\s，。；：、！？“”「」（）0-9\-—…]*", t):
        return ""
    if re.fullmatch(r"(成功|失败|关键失败|大成功|无后果|仍|也|则|否则)[。，]?", t):
        return ""
    return t

DESIGNER_DROP = [
    r"[，；]?\s*解锁(?:追问|后续|对话|选项|新选项|[^，。；]{0,8}选项)",
    r"[，；]?\s*(?:后续|之后)?一次[^，。；]{0,8}(?:检定|判定)自动成功",
    r"[，；]?\s*(?:检定|判定)(?:自动)?成功",
    r"[，；]?\s*无需(?:检定|判定)",
    r"[，；]?\s*(?:无|不需)(?:检定|判定)",
    r"[，；]?\s*获得状态",
    r"[，；]?\s*本节点[^。；]*",
    r"[，；]?\s*关系(?:恶化|改善|提升|下降|变差|变好)",
    r"[，；]?\s*写入[^，。；]*",
    r"[，；]?\s*记为[^，。；]*",
    r"[，；]?\s*标记为[^，。；]*",
]
VERB_START = ("发现", "看出", "取得", "找到", "得到", "获得", "听出", "认出", "说服", "拿到", "进入", "打开", "避开", "救下",
              "察觉", "注意到", "辨认", "撬开", "推开", "拉住", "接住", "稳住", "压住", "挡住", "躲开", "追上", "摆脱",
              "得知", "确认", "证明", "逼出", "问出", "套出", "换来", "赢得", "争取", "保住", "修好", "修复", "成功", "顺利",
              "及时", "迅速", "悄悄", "安全", "带走", "带出", "抢下", "抢回", "截下", "制住", "击倒", "击退", "逃离", "逃出",
              "识破", "读出", "译出", "想起", "记起", "看清", "听见", "看见", "闻到", "摸到", "撑住", "忍住", "守住", "压下")

def polish(t: str) -> str:
    t = re.sub(r"(^|[。！？])获得\s*(?=\S)", r"\1你得到了", t)
    t = re.sub(r"(得到了?|获得)\s*状态\s*", r"\1", t)
    for rx in DESIGNER_DROP:
        t = re.sub(rx, "", t)
    t = re.sub(r"^(?:时|则|并)[，,]?", "", t)
    # drop a dangling last clause left behind by stripped mechanics
    for _ in range(3):
        m = re.search(r"(否则|则|仅|使|并|且|但|可|将|若|让|时|自动成功|取得|获得|得到|与|和)[。，；]?$", t)
        if not m:
            break
        cut = max(t.rfind("，", 0, m.start()), t.rfind("；", 0, m.start()), t.rfind("。", 0, m.start()))
        t = (t[:cut] if cut > 0 else "").rstrip("，；") 
        if t and not t.endswith(("。", "！", "？", "”", "」")):
            t += "。"
    t = re.sub(r"，[，。]", "。", t)
    t = re.sub(r"^[，。；、]+", "", t)
    return t

def narrate(t: str) -> str:
    """Turn a designer outcome clause ('发现壁炉砖…') into second-person narration ('你发现壁炉砖…')."""
    if not t:
        return t
    if t.startswith(VERB_START):
        t = "你" + t
        t = t.replace("你成功", "你").replace("你顺利", "你顺利")
    if t.startswith("也可进入，但"):
        t = "你还是进去了，但" + t[6:]
    elif t.startswith(("也可进入", "仍可进入")):
        t = "你还是进去了。" + t[4:].lstrip("，")
    if not re.search(r"[。！？”」…]$", t):
        t += "。"
    return t

def label_clean(s: str) -> str:
    t = sanitize(s, label=True)
    t = re.sub(r"[：:]$", "", t)
    return t.strip()
