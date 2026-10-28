"""Structural flow patches for 雾钟城：第七声 (v2).

The script describes flow in designer prose ("搜过两处后推进", "返回地点选择", "→ 对应 END-*").
The parser turns text into nodes; this module wires those nodes into a playable graph:
hubs, call/return for dialogue/combat/random events, exits for nodes that only said
"→ 返回", the city hub, the final-plan → ending mapping, epilogues and fail triggers.
"""
import json, re
from pathlib import Path
import wzc_text as T

ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------ small builders
def P(text): return {"t": "p", "text": text}
def SAY(who, text): return {"t": "say", "who": who, "text": text}
def add(k, v=1): return {"op": "add", "k": k, "v": v}
def setf(k, v=True): return {"op": "set", "k": k, "v": v}
def item(k): return {"op": "item", "k": k}
def hp(v): return {"op": "hp", "v": v}
def flag(k): return {"flag": k}
def cmp(k, op, v): return {"cmp": [k, op, v]}
def NOT(c): return {"not": c}
def ANY(*c): return {"any": list(c)}
def ALL(*c): return {"all": list(c)}

def C(cid, label, next=None, result=None, effects=None, **kw):
    c = {"id": cid, "label": label, "result": [P(r) if isinstance(r, str) else r for r in (result or [])],
         "effects": effects or [], "next": next}
    c.update(kw)
    return c

def branch(text=None, effects=None, next=None):
    return {"result": [P(t) if isinstance(t, str) else t for t in ([text] if isinstance(text, str) else (text or []))],
            "effects": effects or [], "next": next}

def node(nid, title, blocks, choices, kind="scene", **kw):
    n = {"id": nid, "title": title, "source": "patch", "kind": kind,
         "blocks": [P(b) if isinstance(b, str) else b for b in blocks], "choices": choices,
         "default_next": kw.pop("default_next", None), "routes": [], "enter_effects": []}
    n.update(kw)
    return n

def find(n, prefix, where="choices"):
    for c in n.get(where, []):
        if c["label"].startswith(prefix):
            return c
    raise KeyError(f"{n['id']}: no choice starting {prefix!r}: {[c['label'] for c in n.get(where, [])]}")

def drop(n, prefix):
    n["choices"] = [c for c in n["choices"] if not c["label"].startswith(prefix)]

def drop_block(n, needle):
    n["blocks"] = [b for b in n["blocks"] if needle not in b.get("text", "")]

def walk_choices(n):
    stack = list(n.get("choices", []))
    while stack:
        c = stack.pop()
        yield c
        stack.extend(c.get("sub") or [])

def set_result(c, *texts):
    c["result"] = [P(t) for t in texts]

def find_any(n, prefix):
    for c in walk_choices(n):
        if c.get("label", "").startswith(prefix):
            return c
    raise KeyError(f"{n['id']}: no nested choice starting {prefix!r}")

def ensure_effect(target, effect):
    effects = target.setdefault("effects", [])
    if effect not in effects:
        effects.append(effect)

def voucher_effect(target, amount):
    effects = target.setdefault("effects", [])
    effects[:] = [e for e in effects if not (e.get("op") == "add" and e.get("k") == "vouchers")]
    if amount:
        effects.append(add("vouchers", amount))

def voucher_cost(choice, amount):
    voucher_effect(choice, 0)
    choice["cost"] = {"vouchers": amount}

# ------------------------------------------------------------------ apply
def apply(N, epis):
    prologues(N)
    greybridge(N)
    dialogues(N)
    city(N)
    mine(N)
    shrine(N)
    import wzc_combat; wzc_combat.combat(N)
    reward_integrity(N)
    random_event_integrity(N)
    condition_integrity(N)
    detours(N)
    endings(N, epis)
    text_fixes(N)
    import wzc_overrides; wzc_overrides.apply_overrides(N)

# ---------------------------------------------------------------- prologues
def prologues(N):
    # ---- L-PRO-01: ruins hub, two careful searches before dark
    n = N["L-PRO-01"]
    drop_block(n, "天黑前只够仔细搜两处")
    n["blocks"].append(P("废墟里有三处值得翻找：塌掉的起居室、父亲的地窖、哨所档案房。雨越下越密，天黑前只够仔细搜两处。"))
    n["hub"] = {"counter": "lpro01_search", "limit": 2, "label": "天黑前还能仔细搜", "unit": "处",
                "advance": {"label": "天色暗了，去父亲的地窖", "next": "L-PRO-02",
                            "text": "最后一点天光也被雨吞掉了。你知道不能再拖，只剩父亲的地窖还没下去。"}}
    n["stay_choices"] = True
    c = find(n, "先搜起居室")
    c["label"] = "搜塌掉的起居室。"
    c["hub_count"] = True; c["next"] = "__SELF__"
    c["success"] = branch("你发现壁炉砖被人重新砌过。撬开那块颜色略浅的砖，后面藏着一把裹着油布的小钥匙——「家族暗格钥匙」。",
                          [item("family_cache_key")])
    c["fail"] = branch("你翻遍了碎瓦和焦木，除了那只木杯，再没有找到别的东西。")
    c = find(n, "先去父亲的地窖")
    c["label"] = "下到父亲的地窖。"
    c["next"] = "L-PRO-02"
    c["check"]["auto_text"] = "你用暗格里找到的钥匙打开了地窖侧面的小锁，没发出一点声音。"
    c["success"] = branch("你撬松了最上面两颗钉子，从木板缝里侧身挤了进去。")
    c["fail"] = branch("你还是进去了，但生锈的钉尖划开了手掌，木板倒下的声音在空荡的废墟里传得很远。",
                       [hp(-2), setf("lpro_noise")])
    c = find(n, "先搜档案房")
    c["label"] = "搜哨所档案房。"
    c["hub_count"] = True; c["next"] = "__SELF__"
    c["success"] = branch("你收起「帝国油封碎片」，又借着雨光辨出墙铭上残存的一句：“见证必须出于自愿。”",
                          [item("imperial_oil_seal"), add("truth")])
    c["fail"] = branch("湿纸一碰就碎，墙铭也只剩几道刮痕。你只带走了那块油封碎片。", [item("imperial_oil_seal")])
    c = find(n, "在废墟外等")
    c["next"] = "L-PRO-02"
    c["result"].append(P("等他钻进档案房翻找，你趁着雨声溜下了父亲的地窖。"))

    # ---- L-PRO-03: Bran
    n = N["L-PRO-03"]
    pay = find(n, "“把你知道的全说出来")
    pay["label"] = "数出 8 张票据当定金：“把你知道的全说出来，我替你儿子还债。”"
    set_result(pay, "你把八张票据压进他满是老茧的掌心。布兰盯着票据看了很久，终于开口。",
               "他交出儿子的工牌，又说出当年带队军官的名字——副尉科尔。")
    pay.pop("group_with", None)
    chk = [c for c in n["choices"] if c["id"] == "s1c1"][0]
    chk["label"] = "“把你知道的全说出来，我会替你儿子还债。”"
    chk["success"]["result"] = [P("布兰盯着你看了很久，像在你脸上找你母亲的影子。最后他交出儿子的工牌，又说出当年带队军官的名字——副尉科尔。")]
    chk["fail"] = branch("布兰摇头：“空口许诺我听过太多了。先让我看看那页账。”你没有给，他便闭紧了嘴。",
                         [add("rel.bran", -1)])
    c = find(n, "“你替他们搬了油")
    c["success"]["result"] = [P("你看出他在母亲关门这件事上还藏着话。你逼问下去，他终于承认：赛拉亲手封上了地窖门，她知道你就藏在里面。她选择救下一个女儿，而没有敲响全哨的警钟。")]
    c["fail"] = branch("布兰别过脸，不肯再多说一个字。你知道矿工那边很快会听说今晚的事。", [add("rel.miners", -1)])
    c = find(n, "袭击他")
    c["success"]["result"] = [P("你把他按倒在泥水里，夺下工牌、一枚帝国油封和一张写着仓库编号的纸条。")]
    c["fail"]["result"] = [P("布兰挣脱后朝灰桥方向狂奔示警。你只捡到他慌乱中掉下的半张编号纸。")]
    c = find(n, "放他走")
    c["effects"] = []
    set_result(c, "你侧身让开了路。布兰愣了一下，临走前低声说出了儿子的名字：奥斯温。")
    c["sub"] = [
        C("s1c5a", "叫住他：“告诉奥斯温，今晚别下最深那层。”", "L-PRO-04",
          ["布兰的脚步停了一下。他没有回头，只抬手示意自己听见了。"], [add("mercy"), setf("workers_warned")]),
        C("s1c5b", "什么也不说，看着他消失在雨里。", "L-PRO-04",
          ["你没有替任何人做决定。雨把他的脚印很快抹平了。"], [add("defiance")]),
    ]
    c["next"] = None
    # 让凯尔射击 → 炭棚营救战
    n = N["L-PRO-06"]
    c = find(n, "让凯尔射击")
    c["call"] = "C-03"; c["next"] = "L-PRO-07"
    if not c["result"]:
        set_result(c, "你朝凯尔点了点头。他搭箭上弦，等你一声令下。")

    # ---- Edric: ambush fight
    n = N["E-PRO-03"]
    n["choices"].append(C("pc1", "拔出边境剑，迎向扑来的劫匪。", "E-PRO-04",
                          ["你把汤姆推到车轮后面，自己迎着泥地冲了上去。"], call="C-01"))

    # ---- E-PRO-05 玛拉结算护送费（剧本只写了叙述，解析器未生成 vouchers 效果）
    n = N["E-PRO-05"]
    # 两段开头叙事互斥：救彼得 / 保货致彼得受伤
    for b in n["blocks"]:
        t = b.get("text") or ""
        if "客人会满意" in t or "三十二张商会券" in t or "三十二张票据" in t:
            b["cond"] = flag("peter_injured")
        if "里德是黑砧矿区" in t or (b.get("who") == "里德"):
            b["cond"] = ANY(flag("c01_prisoner"), flag("prisoner"))
    # 进入节点即按结果发券：基础 28；保货且彼得受伤路径给 32（含保匣加成）；
    # 救彼得且另保住木匣再 +4；谈妥奖金再 +2。
    n["enter_effects"] = [
        {"cond": flag("peter_injured"), "ops": [add("vouchers", 32)]},
        {"cond": ALL(flag("saved_peter"), NOT(flag("peter_injured"))), "ops": [add("vouchers", 28)]},
        {"cond": ALL(NOT(flag("saved_peter")), NOT(flag("peter_injured"))), "ops": [add("vouchers", 28)]},
        {"cond": ALL(flag("saved_peter"), flag("coffer_saved"), NOT(flag("peter_injured"))), "ops": [add("vouchers", 4)]},
        {"cond": flag("promised_bonus"), "ops": [add("vouchers", 2)]},
    ]
    # 彼得受伤时可自选留下 6 张作医药费
    if not any("医药费" in (c.get("label") or "") for c in n["choices"]):
        n["choices"].insert(0, C(
            "pay_peter", "留下六张商会券，给彼得作医药费。", "__SELF__",
            ["你数出六张商会券按进玛拉手里。她没有道谢，只是把券塞进彼得的衣襟。"],
            [add("sacrifice", 1), add("rel.mara", 1)],
            cond=flag("peter_injured"), cost={"vouchers": 6}, once=True,
        ))
    # 汤姆对白选项：补上剧本效果
    for c in n["choices"]:
        lab = c.get("label") or ""
        if "你活下来了" in lab:
            c["effects"] = [add("rel.tom", 1)]
        elif "你欠我一条命" in lab:
            c["effects"] = [add("rel.tom", -1), setf("tom_owes_favor")]
        elif "疤脸徽记写进报告" in lab:
            c["effects"] = []
            c["cond_effects"] = [{"cond": ANY(flag("toren_badge"), flag("c01_prisoner"), flag("prisoner")),
                                  "ops": [setf("harlan_evidence")]}]
        elif lab.startswith("交给帝国"):
            c["effects"] = [setf("prisoner_to_empire"), add("mercy", -1)]
            c["cond"] = ANY(flag("c01_prisoner"), flag("prisoner"))
        elif "割断绳索" in lab:
            c["effects"] = [add("mercy", 1), add("rel.toren", -1), item("toren_badge")]
            c["cond"] = ANY(flag("c01_prisoner"), flag("prisoner"))
        elif "逼问矿区暗路" in lab:
            c["cond"] = ANY(flag("c01_prisoner"), flag("prisoner"))
        elif "杀了他" in lab:
            c["effects"] = [add("cruelty", 1), item("toren_badge")]
            c["cond_effects"] = [{"cond": flag("tom_alive"), "ops": [add("rel.tom", -2)]}]
            c["cond"] = ANY(flag("c01_prisoner"), flag("prisoner"))
    if not any(c.get("id") == "settle_cont" for c in n["choices"]):
        n["choices"].append(C(
            "settle_cont", "清点完毕，继续上路。", "E-PRO-06",
            ["雨还在下。车队重新排好了队形。"], [],
        ))
    # ---- Thorin: fight in the shed
    n = N["T-PRO-02"]
    c = find(n, "砸下去")
    c["success"] = branch("锤头砸断了那人两根指骨。他惨叫着后退，其余私兵同时拔出了刀。",
                          c["success"]["effects"], "T-PRO-03")
    c["success"]["call"] = "C-02"
    c["fail"] = branch("锤子落空了。几个人一拥而上，把你按在工作台上，缴走货物，拖进了工棚的储藏间。", [], "T-PRO-04B")
    n = N["T-PRO-04B"]
    n["default_next"] = "T-PRO-04"
    for nid in ("E-PRO-08", "L-PRO-08", "T-PRO-07"):
        pass
    N["L-PRO-09"]["default_next"] = "A1-TOWN-01"
    N["T-PRO-08"]["default_next"] = "A1-TOWN-01"
    N["T-PRO-05"]["default_next"] = "T-PRO-06"

# ---------------------------------------------------------------- Greybridge
TOWN_LOCS = [
    ("A1-TOWN-02", "去白鸦旅店打听消息。"),
    ("A1-TOWN-03", "去灰烛礼拜堂看看伤员。"),
    ("A1-TOWN-04", "去红牡丹找米拉。"),
    ("A1-TOWN-05", "去钟楼后的格罗姆铺子。"),
    ("A1-TOWN-07", "去帝国军务所见哈兰上尉。"),
]

def greybridge(N):
    n = N["A1-TOWN-01"]
    n["kind"] = "hub"
    n["stay_choices"] = True
    n["blocks"].append(P("今晚你只来得及把两处地方查个透彻。东仓那边迟早会出事。"))
    n["hub"] = {"counter": "town_deep", "limit": 2, "label": "入夜前还能深入查访", "unit": "处",
                "advance": {"label": "东仓方向传来一声闷响", "next": "A1-TOWN-08",
                            "text": "钟楼敲过第二遍时，东边的天空先红了一下，又变成一种不自然的蓝。"},
                "extra": {"label": "顾不上了，再查一处", "effects": [add("resonance"), setf("workers_warned", False)],
                          "text": "你决定再挤出一点时间。可等你出来时，东仓的夜袭恐怕已经开始了。"}}
    n["choices"] = []
    for i, (nid, label) in enumerate(TOWN_LOCS):
        n["choices"].append(C(f"go{i}", label, nid, [], [], once=True, travel=True, hub_visit=True))
    n["choices"].insert(4, C("go_goal", "去办自己的事。", "A1-TOWN-06", [], [], once=True, travel=True, hub_visit=True))
    leave = lambda nid: C("leave", "离开这里，回到街口。", "A1-TOWN-01", ["你把听到的消息在心里过了一遍，回到雨里的街口。"],
                          [add("town_deep"), add("time")])
    for nid, _ in TOWN_LOCS:
        if nid in ("A1-TOWN-07",):
            continue
        t = N[nid]
        t["stay_choices"] = True
        t["choices"].append(leave(nid))
    # private goal & Harlan: one decision, then back to the street
    for nid in ("A1-TOWN-06", "A1-TOWN-07"):
        t = N[nid]
        for c in t["choices"]:
            if c.get("next") in (None, "__SELF__"):
                c["next"] = "A1-TOWN-01"
            for b in ("success", "fail"):
                if c.get(b) and c[b].get("next") in (None, "__SELF__"):
                    c[b]["next"] = None
            c["effects"] = c.get("effects", []) + [add("town_deep"), add("time")]
            for s in c.get("sub") or []:
                s["next"] = "A1-TOWN-01"
        t["default_next"] = "A1-TOWN-01"
    t = N["A1-TOWN-06"]
    drop_block(t, "该节点不单独耗时")
    t["blocks"].insert(0, P("你一直把自己的事压在心底。现在，总得先把它办了。"))
    c = find(t, "抄录并把原件留给后来者")
    c["success"]["result"] = [P("你一页页抄完，把原件放回原处。没有人发现你来过。")]
    c["fail"]["result"] = [P("抄到一半，天色已经暗了下来。你只得匆匆收笔。")]
    # 09 → 09~2 → 10
    N["A1-TOWN-09~2"]["default_next"] = "A1-TOWN-10"
    n = N["A1-TOWN-08"]
    c = find(n, "直接冲过去")
    c["call"] = "C-04"
    # A1-TOWN-10: choices to next act
    n = N["A1-TOWN-10"]
    n["blocks"] = [b for b in n["blocks"] if b.get("text") != "众人提供彼此矛盾却都可信的办法"]
    for b in n["blocks"]:
        if b.get("text", "").startswith("艾琳听说"):
            n["blocks"].insert(n["blocks"].index(b), P("天亮前，众人给出了彼此矛盾、却都听上去可信的办法："))
            break

# ---------------------------------------------------------------- dialogues (call / return)
DIALOGUE_AT = {
    "D-NPC-VALEN": ("A1-TOWN-02", "单独和瓦伦多聊几句。"),
    "D-NPC-YSOLDE": ("A1-TOWN-02", "单独和伊索尔多聊几句。"),
    "D-NPC-KAEL": ("A1-TOWN-02", "去找凯尔说话。"),
    "D-ALT": ("A1-TOWN-02", "和另一位残片持有者坐下来谈谈。"),
    "D-NPC-EILYN": ("A1-TOWN-03", "等艾琳忙完，和她说说话。"),
    "D-NPC-TOM": ("A1-TOWN-03", "和小汤姆聊聊。"),
    "D-NPC-MIRA": ("A1-TOWN-04", "和米拉私下谈谈。"),
    "D-NPC-SKYE": ("A1-TOWN-04", "找楼梯阴影里的斯凯。"),
    "D-NPC-GROMM": ("A1-TOWN-05", "陪格罗姆坐一会儿。"),
    "D-NPC-HARLAN": ("A1-TOWN-07", "先听听哈兰本人怎么想。"),
    "D-NPC-TOREN": ("A2-MINE-01B", "先摸清托伦这个人。"),
    "D-NPC-HELGA": ("A2-MINE-02", "找赫尔嘉问问矿上的情况。"),
    "D-NPC-SHADOW": ("A3-SHRINE-04", "让塞维兰把话说完。"),
    "CITY-NPC-MAUREL": ("CITY-03", "求见圣务长莫雷尔。"),
    "CITY-NPC-ANSER": ("CITY-03", "和见习生安瑟聊聊。"),
    "CITY-NPC-SAREI": ("CITY-05", "和换命术士萨芮谈谈条件。"),
    "CITY-NPC-ROEN": ("CITY-05", "去见候选人罗恩。"),
    "CITY-NPC-HESS": ("CITY-09", "和静默署的赫斯医官谈谈。"),
    "CITY-NPC-FEIN": ("CITY-09", "去看看患者费恩。"),
    "CITY-NPC-LEONA": ("SQ-CITY-05", "单独和莱欧娜谈谈。"),
    "CITY-NPC-RADEK": ("SQ-CITY-05", "去见商会理事拉德克。"),
    "CITY-NPC-VARICK": ("SQ-CITY-02", "和议员瓦瑞克说几句话。"),
    "CITY-NPC-ALAINA": ("SQ-CITY-02", "私下找阿莱娜。"),
    "CITY-NPC-SERA": ("SQ-CITY-01", "和塞拉、奥多坐下来谈。"),
    "CITY-NPC-IRI": ("SQ-CITY-04", "和伊芮、贝尔蒙谈谈。"),
    "CITY-NPC-NIMA": ("SQ-CITY-03", "和妮玛、达莫斯谈谈。"),
}

def dialogues(N):
    npc_ids = [k for k in N if k.startswith(("D-NPC-", "CITY-NPC-")) or k == "D-ALT"]
    city_targets = [k for k in N if k.startswith(("CITY-0", "CITY-1", "SQ-CITY-")) and "~" not in k]
    for did in npc_ids:
        d = N[did]
        name = re.sub(r"^.*[”」]", "", d["title"]).strip()
        short = re.split(r"[·・]", name)[0]
        short = short[-3:] if len(short) > 3 else short
        if not d["blocks"]:
            d["blocks"] = [P(f"{name}注意到了你，停下了手里的事。")]
        d["kind"] = "dialogue"
        d["stay_choices"] = True
        d["choices"].append(C("bye", "结束交谈。", "__RETURN__", ["你道了别。"], []))
        for c in d["choices"]:
            if c.get("topic"):
                c["once"] = True
        if did in DIALOGUE_AT:
            at, label = DIALOGUE_AT[did]
        else:
            at = next((t for t in city_targets if short in json.dumps(N[t], ensure_ascii=False)), None)
            label = f"和{short}单独谈谈。"
            if not at:
                continue
        host = N[at]
        host.setdefault("choices", []).insert(0 if at.startswith("A3") else len(host["choices"]),
                                              C(f"talk_{did}", label, "__SELF__", [], [], call=did, once=True, talk=True))
        d["return_hint"] = at

# ---------------------------------------------------------------- city
CITY_SPOTS = [
    ("CITY-03", "去白塔，问拔除术的代价。"),
    ("CITY-04", "去学院旧馆，找伊索尔的稳定药。"),
    ("CITY-05", "去河渠黑市，见那位换命术士。"),
    ("CITY-06", "去西炉区，请矮人拆开容器。"),
    ("CITY-07", "去书吏区档案馆，翻查旧水利图。"),
    ("CITY-08", "去钟楼，听六座钟为何错拍。"),
    ("CITY-09", "去书吏区地下旧馆，查静默署。"),
    ("SQ-CITY-01", "去锚门广场东侧的贫民巷，那栋倾斜的房子。"),
    ("SQ-CITY-02", "去上环区，赴议员瓦瑞克的无窗宅晚宴。"),
    ("SQ-CITY-03", "去锚门药铺，看看那桩药瓶失窃的事。"),
    ("SQ-CITY-04", "去书吏区的城市藏珍馆。"),
    ("SQ-CITY-05", "去书吏区抄写街，找那位低阶书吏。"),
]
LOCS = [("LOC-ANCHOR", "锚门广场"), ("LOC-WHITETOWER", "白塔区"), ("LOC-SCRIBE", "书吏区"),
        ("LOC-CANAL", "河渠区"), ("LOC-UPPER", "上环区"), ("LOC-WESTFORGE", "西炉区")]

def city(N):
    N["CITY-01"]["default_next"] = "CITY-02"
    n = N["CITY-01"]
    for b in n["blocks"]:
        if "系统把它们" in b.get("text", "") or b.get("text", "").startswith("进入后"):
            b["text"] = "进城后，广场公告栏上贴着五条“治疗传闻”：白塔拔除、学院稳定药、河渠换命契、矮人拆表，还有一句“离开矿尘范围自然痊愈”。没有一条写明真假。"
    n = N["CITY-02"]
    n["default_next"] = "CITY-HUB"
    keep = []
    for b in n["blocks"]:
        t = b.get("text", "")
        if t.startswith(("无论方式", "若卖给古物商", "说明危险并买回", "强抢", "任由商人承受", "完成本节点")):
            continue
        keep.append(b)
    n["blocks"] = keep
    walk = ["你走到第三十一步时，症状准时找上门来。容器并没有凭空回到你身上——它就在原地，等你自己回去拿。"]
    for c in n["choices"]:
        if not c.get("sub"):
            c["result"] = [P(walk[0])]
            c["sub"] = [
                C("back", "转身回去，把它拿回来。", "CITY-HUB", ["你折返回去，把容器重新带在身上。症状像退潮一样慢慢散了。"], [setf("cure_leads_open")]),
                C("never", "坚持走下去，绝不回头。", "FAIL-05",
                  ["你数到了第一百步。然后你忘了自己为什么要数。"], [setf("abandoned_container")]),
                C("push", "咬着牙继续走，走到第五十步。", "CITY-HUB",
                  ["你的体力骤然被抽空一半，脑子里有一小段记忆像被剪掉了。你终于明白：丢掉它的代价，远比带着它更重。最后你还是回去把它拿了回来。"],
                  [hp(-4), add("curse_stage"), setf("cure_leads_open")]),
            ]
            c["next"] = None
    c = find(n, "卖给古物商")
    c["result"] = [P("古物商爽快地付了钱。可你还没走出广场，就看见他已经把它戴在了身上。")]
    c["sub"] = [
        C("buyback", "向他说明危险，把它买回来。", "CITY-HUB", ["你退还了钱，又额外赔了两张票据。商人吓得脸色发白，但总算保住了命。"],
          [add("vouchers", -2), setf("cure_leads_open")]),
        C("grab", "直接抢回来。", "CITY-HUB", ["你一把将它夺回。围观的人记住了你的脸。"], [add("city_rep", -1), setf("cure_leads_open")]),
        C("leave", "任由商人承受，自己撑着离开。", "CITY-HUB",
          ["半个钟头后，你的症状减轻了；而那个商人开始呈现和你一模一样的病状。原来真的有人能替你背这个。"],
          [add("cruelty"), setf("curse_transferred_seen"), setf("cure_leads_open")]),
    ]
    c["next"] = None
    # --- the hub
    hub = node("CITY-HUB", "雾钟城", [
        "六座钟楼各自报着各自的时辰。你手里有四种听上去可信的治疗，也有一些越来越清晰的、关于城市地下的传闻。",
        "每深入一处，回声病都会往前走一步。别把时间都花在犹豫上。"], [], kind="hub", stay_choices=True)
    hub["hub"] = {"counter": "city_actions", "label": "已深入调查", "unit": "处", "count_up": True,
                  "curse_checks": [2, 4, 6]}
    for nid, label in CITY_SPOTS:
        hub["choices"].append(C("go_" + nid, label, nid, [], [add("city_actions")], once=True, travel=True, hub_visit=True))
    for lid, name in LOCS:
        hub["choices"].append(C("loc_" + lid, f"在{name}随便走走。", lid, [], [], once=True, travel=True, group="闲逛"))
    hub["choices"].append(C("go_mine", "去西边山腹的黑砧矿区。", "A2-MINE-00", ["你决定先去找这病的源头。"], [], once=True,
                            cond=NOT(flag("mine_done"))))
    hub["choices"].append(C("go_entry", "你已经知道入口在哪儿了。", "CITY-10", ["该去城市底下看看了。"], [],
                            cond=ANY(cmp("sanctuary_clues", ">=", 2), cmp("city_actions", ">=", 5))))
    N["CITY-HUB"] = hub
    for nid, _ in CITY_SPOTS:
        last = nid
        while last + "~2" in N or (re.sub(r"~\d+$", "", last) + "~" + str(int(last.split("~")[1]) + 1 if "~" in last else 2)) in N:
            base = re.sub(r"~\d+$", "", last)
            k = int(last.split("~")[1]) + 1 if "~" in last else 2
            last = f"{base}~{k}"
        if not N[last].get("default_next"):
            N[last]["default_next"] = "CITY-HUB"
        for c in N[last]["choices"]:
            if c.get("next") == "__SELF__" and not c.get("talk"):
                c["next"] = None
    n = N["CITY-07"]
    if not n["choices"]:
        n["choices"] = [
            C("read", "把三份文档摊在一起对照。", "CITY-HUB",
              ["建城图上没有第零蓄水池，维修账却年年给它付钱，地契里还多出一块“共同见证地”。三样东西拼在一起，指向旧城底下同一个位置。"],
              [add("sanctuary_clues")], check={"stats": ["INS"], "dc": 13},
              success=branch("你在档案馆书架后找到一道测绘井的旧记号。那是一条不必动刀就能下去的路。", [add("sanctuary_clues"), setf("archive_shaft")]),
              fail=branch("你只能确定大致的方位，入口还得再找。"))]
    n = N["CITY-08"]
    n["blocks"].insert(0, P("六座钟楼各响各的，从来没有在整点同时敲过。钟工说那不是坏了，是故意的。"))
    c = find(n, "有钟律线索或格罗姆结构图")
    c["label"] = "照钟律线索，按正确的次序拉绳。"
    c["cond"] = ANY(flag("bell_resonance_clue"), flag("tuning_tools"), flag("bone_names_known"))
    c["result"] = [P("六根钟绳在你手里依次落下。第七拍并不存在于任何一座钟里，却在你脚下的石板深处响了起来。")]
    c["effects"] = [add("sanctuary_clues")]
    c = find(n, "靠")
    c["label"] = "仔细听，自己找出那一拍。"
    c["effects"] = []
    c["check"] = {"stats": ["INS"], "dc": 16}
    c["result"] = []
    c["success"] = branch("你在第六下与第一下之间听见了一段空白——那段空白在往地下沉。", [add("sanctuary_clues")])
    c["fail"] = branch("你拉错了一根绳。一声错误的低频在城里回荡，静默署的人很快就会来查。", [add("curse_stage")])
    c = find(n, "让怀表/戒指/银链带路")
    c["label"] = "让身上的残片带路。"
    c["effects"] = [add("fragment_used"), add("sanctuary_clues")]
    c = find(n, "贿赂六名钟工")
    c["cost"] = {"vouchers": 12}
    c["effects"] = [e for e in c["effects"] if e.get("k") != "vouchers"] + [add("sanctuary_clues")]
    c["result"] = [P("六名钟工同时敲响了各自的钟。全城都听见了那一声不该存在的回音。")]
    for c in n["choices"]:
        c["next"] = "CITY-HUB"
    # LOC hubs with ambient scenes
    for lid, name in LOCS:
        L = N[lid]
        L["stay_choices"] = True
        for i, aid in enumerate(L.get("ambients", [])):
            A = N[aid]
            L["choices"].append(C(f"amb{i}", A["title"] + "。", "__SELF__", [], [], call=aid, once=True))
            A["default_next"] = "__RETURN__"
            for c in walk_choices(A):
                if c.get("next") == "__SELF__":
                    c["next"] = None
        L["choices"].append(C("back", "回到城中心。", "CITY-HUB", [], []))
    # CITY-10 → A3-SHRINE-00 → A3-SHRINE-01
    n = N["CITY-10"]
    n["blocks"] = [P("线索终于拼到了一起：雾钟城底下还藏着一座不在任何地图上的蓄水池。通往那里的路不止一条。")]
    n["default_next"] = "A3-SHRINE-00"
    n["choices"] = []
    n = N["A3-SHRINE-00"]
    n["default_next"] = "A3-SHRINE-01"
    for c in n["choices"]:
        c["next"] = None
    find(n, "黑砧古水道")["cond"] = flag("mine_done")
    find(n, "无窗宅地窖")["cond"] = {"seen": "SQ-CITY-02"}
    find(n, "档案馆测绘井")["cond"] = ANY(flag("archive_shaft"), {"seen": "CITY-07"})
    find(n, "白塔无声井")["cond"] = {"seen": "CITY-08"}
    find(n, "河渠旧浴场")["cond"] = ANY({"seen": "CITY-05"}, {"seen": "LOC-CANAL"})
    c = find(n, "残片强引")
    c["effects"] = c.get("effects", []) + [hp(-4), add("fragment_used")]

# ---------------------------------------------------------------- reward and consequence integrity
def reward_integrity(N):
    """Keep player-facing promises synchronized with persistent game state."""
    # Prologues and Greybridge: several rewards were present only in prose.
    voucher_cost(find(N["E-PRO-08"], "交 4 张"), 4)
    c = find(N["T-PRO-01"], "接受减价")
    ensure_effect(c["success"], item("mine_access_token"))
    ensure_effect(c["fail"], item("mine_access_token"))
    voucher_effect(find(N["T-PRO-02"], "将怀表攥进掌心"), 5)
    voucher_effect(find(N["T-PRO-03"], "把科德留给私兵"), 18)

    c = find_any(N["A1-TOWN-02"], "拿假线索")
    ensure_effect(c["success"], add("vouchers", 4))
    voucher_effect(find_any(N["A1-TOWN-02"], "要求她买下残片"), 20)
    voucher_effect(find_any(N["A1-TOWN-04"], "卖掉这个真相"), 10)
    c = find(N["A1-TOWN-06"], "只给钱")
    voucher_cost(c, 20)
    ensure_effect(c, setf("harlan_writ"))
    ensure_effect(c, setf("family_writ_paid"))

    # City side quest 1: every advertised non-cash reward now exists in inventory.
    n = N["SQ-CITY-01~2"]
    c = find(n, "公开两份账")
    ensure_effect(c, setf("tenant_union_started"))
    c = find(n, "烧官方账")
    ensure_effect(c, item("free_storage_token"))
    c = find(n, "用账勒索奥多")
    ensure_effect(c, setf("oddo_blackmailed"))
    c = find(n, "把账交给塞拉")
    ensure_effect(c, item("sewn_pack_strap"))
    c = find(n, "替奥多向人群辩护")
    ensure_effect(c, setf("oddo_restitution"))

    # City side quest 2: let the player investigate before committing to a plan.
    n = N["SQ-CITY-02"]
    n["stay_choices"] = True
    investigations = [
        ("瓦瑞克确实", "varick_profit_known"),
        ("他匿名资助", "varick_hospital_known"),
        ("他计划在明日", "varick_vote_known"),
    ]
    for prefix, key in investigations:
        c = find(n, prefix)
        c["next"] = "__SELF__"
        c["once"] = True
        ensure_effect(c, setf(key))
        ensure_effect(c, add("varick_investigations"))
    if not any(c.get("id") == "to_action" for c in n["choices"]):
        n["choices"].append(C(
            "to_action", "结束调查，决定今晚怎么做。", "SQ-CITY-02~2",
            ["你离开人群，重新衡量阿莱娜的委托与瓦瑞克造成的伤害。"], [],
        ))

    n = N["SQ-CITY-02~2"]
    c = find(n, "按约下毒")
    ensure_effect(c["success"], add("vouchers", 20))
    ensure_effect(c["success"], setf("varick_dead"))
    ensure_effect(c["success"], item("upper_house_key"))
    ensure_effect(c["fail"], setf("alaina_exposed"))
    c = find(n, "当面刺杀")
    ensure_effect(c, add("vouchers", 20))
    ensure_effect(c, setf("varick_dead"))
    ensure_effect(c, item("upper_house_key"))
    c = find(n, "偷账本")
    ensure_effect(c["success"], item("varick_ledger"))
    ensure_effect(c["success"], setf("varick_removed"))
    c = find(n, "以账本勒索")
    c["cond"] = flag("varick_profit_known")
    ensure_effect(c["success"], setf("silent_office_bill_withdrawn"))
    ensure_effect(c["success"], add("city_rep"))
    c = find(n, "向瓦瑞克出卖")
    ensure_effect(c, setf("alaina_betrayed"))
    ensure_effect(c, item("upper_house_key"))
    c = find(n, "把双方叫到同一桌")
    c["cond"] = ALL(
        cmp("varick_investigations", ">=", 3),
        NOT(flag("alaina_exposed")),
        NOT(flag("alaina_betrayed")),
    )
    ensure_effect(c, setf("varick_hearing"))
    ensure_effect(c, item("upper_house_key"))

    # City side quest 3: payment options cannot drive currency below zero.
    n = N["SQ-CITY-03"]
    c = find(n, "替妮玛付差价")
    voucher_cost(c, 4)
    ensure_effect(c, item("archive_cabinet_key"))
    ensure_effect(c, setf("nima_brother_saved"))
    c = find(n, "让达莫斯赊账")
    ensure_effect(c["success"], item("archive_cabinet_key"))
    ensure_effect(c["success"], setf("nima_brother_saved"))
    c = find(n, "让妮玛带走药")
    ensure_effect(c, item("archive_cabinet_key"))
    ensure_effect(c, setf("nima_brother_saved"))
    ensure_effect(c, setf("paid_patient_harmed"))
    c = find(n, "抓住妮玛")
    ensure_effect(c, setf("nima_detained"))
    c = find(n, "调配替代药")
    ensure_effect(c["success"], item("archive_cabinet_key"))
    ensure_effect(c["success"], item("stable_medicine"))
    ensure_effect(c["success"], setf("all_patients_helped"))
    ensure_effect(c["fail"], setf("medicine_spoiled"))
    c = find(n, "买下整家药铺")
    voucher_cost(c, 18)
    ensure_effect(c, item("pharmacy_credit"))
    ensure_effect(c, item("stable_medicine"))

    # City side quest 4: payment, route, map access and the amulet are real rewards.
    n = N["SQ-CITY-04"]
    c = find(n, "把真品还给伊芮")
    voucher_effect(c, 8)
    ensure_effect(c, item("smugglers_canal_route"))
    ensure_effect(c, setf("silver_finger_returned"))
    c = find(n, "说服伊芮暂借")
    ensure_effect(c, setf("revocable_museum_loan"))
    c = find(n, "制作替代件")
    voucher_cost(c, 6)
    ensure_effect(c, item("silver_shard_amulet"))
    ensure_effect(c, item("smugglers_canal_route"))
    ensure_effect(c, setf("flood_bell_repaired"))
    c = find(n, "把真品卖给第三方")
    voucher_effect(c, 20)
    ensure_effect(c, setf("silver_finger_sold"))
    c = find(n, "拒绝归还")
    ensure_effect(c, item("city_old_map_access"))
    c = find(n, "砸毁银指")
    ensure_effect(c, add("rel.iri", -2))
    ensure_effect(c, add("rel.belmont", -2))
    ensure_effect(c, setf("silver_finger_destroyed"))

    # City side quest 5: outcomes alter evidence, people and money independently.
    n = N["SQ-CITY-05"]
    c = find(n, "按委托暗杀")
    ensure_effect(c, item("merchant_storage_token"))
    ensure_effect(c, setf("leona_dead"))
    c = find(n, "威胁她离城")
    ensure_effect(c["success"], setf("leona_exiled"))
    ensure_effect(c["success"], setf("pollution_records_hidden"))
    c = find(n, "收买她")
    c["cond"] = ALL(
        ANY(flag("stable_medicine"), flag("benzoin_medicine"), flag("medicine_pack")),
        ANY(flag("mira_safehouse_hint"), flag("mine_drain_route"), flag("smugglers_canal_route")),
    )
    voucher_effect(c, 12)
    ensure_effect(c, setf("leona_names_withheld"))
    c = find(n, "保护她完成交接")
    c["check"] = {"stats": ["DEX", "CHA"], "dc": 13}
    c["result"] = []
    c["effects"] = []
    c["success"] = branch(
        "你挡住刀手，让莱欧娜把记录交给三名互不隶属的见证人。拉德克被立案调查，商会票据也跟着贬值了一阵。",
        [add("city_rep", 2), item("leona_testimony"), setf("radek_investigated")],
    )
    c["fail"] = branch(
        "刀手伤了你，但莱欧娜仍把一份记录扔进了人群。证据保住了，她本人只能连夜转移。",
        [hp(-2), add("city_rep"), item("pollution_records"), setf("leona_exiled")],
    )
    c = find(n, "把她挪用赈济款一并公开")
    ensure_effect(c, item("leona_testimony"))
    ensure_effect(c, add("truth"))
    ensure_effect(c, setf("leona_prosecuted"))
    ensure_effect(c, setf("radek_investigated"))
    c = find(n, "双重勒索")
    c["check"] = {"stats": ["INS", "CHA"], "dc": 16}
    c["result"] = []
    c["effects"] = []
    c["success"] = branch(
        "你把两个彼此冲突的谎言都维持到了交钱那一刻，一共拿到三十二张票据。",
        [add("corruption", 2), add("vouchers", 32), setf("double_blackmail")],
    )
    c["fail"] = branch(
        "莱欧娜和拉德克核对了你的说法。两边都公开了你索钱的字据，你一张也没拿到。",
        [add("city_rep", -3), setf("blackmail_exposed")],
    )
    c = find(n, "杀拉德克")
    ensure_effect(c, add("cruelty"))
    ensure_effect(c, setf("radek_dead"))

    # Random and ambient scenes: convert prose-only spending to guarded costs.
    voucher_cost(find(N["R-TRAVEL-07"], "付钱请她别唱"), 1)
    voucher_cost(find(N["R-TRAVEL-11"], "不赌，直接付费"), 4)
    ensure_effect(find(N["R-TRAVEL-11"], "不赌，直接付费"), setf("skye_reliable_answer"))
    ensure_effect(find(N["R-DES-02"], "砸镜")["success"], add("vouchers", -2))
    voucher_cost(find(N["R-ANG-01"], "付钱"), 4)
    c = find(N["R-ANG-01"], "据理还价")
    ensure_effect(c["success"], add("vouchers", -2))
    c = find(N["R-ANG-01"], "砸柜台")
    ensure_effect(c, add("corruption"))
    ensure_effect(c, add("alarm_town"))
    ensure_effect(find(N["R-ANG-01"], "修好他坏掉的秤"), item("rope"))
    voucher_cost(find(N["R-ANG-02"], "买下两份药"), 5)
    c = find(N["R-ANG-05"], "买下马")
    voucher_cost(c, 8)
    ensure_effect(c, item("pack_animal"))

    ambient_costs = {
        "CITY-AMBIENT-04": ("你替她付", 3),
        "CITY-AMBIENT-07": ("贿赂 2", 2),
        "CITY-AMBIENT-08": ("花 3", 3),
        "CITY-AMBIENT-10": ("支付 3", 3),
        "CITY-AMBIENT-16": ("代垫 12", 12),
    }
    for nid, (prefix, amount) in ambient_costs.items():
        voucher_cost(find(N[nid], prefix), amount)
    ensure_effect(find(N["CITY-AMBIENT-03"], "只记下签发人"), setf("radek_named"))
    ensure_effect(find(N["CITY-AMBIENT-05"], "建议两人共同检查"), item("copper_tuning_fork"))
    ensure_effect(find(N["CITY-AMBIENT-08"], "花 3"), item("banned_bell_history"))
    ensure_effect(find(N["CITY-AMBIENT-08"], "举报摊主"), item("academy_access_note"))
    ensure_effect(find(N["CITY-AMBIENT-13"], "以一枚糖"), item("childs_sound_map"))
    voucher_effect(find(N["CITY-AMBIENT-17"], "强行修复"), 3)

    c = find(N["CITY-AMBIENT-09"], "购买一次签名服务")
    voucher_cost(c, 5)
    ensure_effect(c, item("forged_signature_pen"))
    c = find(N["CITY-AMBIENT-09"], "砸笔")
    c["result"] = [P("笔断成两截。抄写员指着价目牌，要你赔十二张票据；巷口已经有人在叫巡吏。")]
    c["effects"] = []
    c["next"] = None
    c["sub"] = [
        C("pay", "赔十二张票据。", "__RETURN__", ["抄写员收起断笔，仍不认同你替她砸东西。"], [], cost={"vouchers": 12}),
        C("run", "趁巡吏赶来前逃走。", "__RETURN__", [], [], check={"stats": ["DEX"], "dc": 13},
          success=branch("你钻进两座档案楼之间的窄缝，甩开了巡吏。", [add("city_rep", -1)]),
          fail=branch("巡吏追上了你。你赔了钱，名字也被记进损毁公物的册子。", [add("vouchers", -12), add("city_rep", -1)])),
    ]

    # A base negative voucher effect is always an up-front price. Expressing it
    # as cost lets the UI show the amount and disables choices the player cannot pay.
    for n in N.values():
        for c in walk_choices(n):
            debit = -sum(
                int(e.get("v") or 0)
                for e in c.get("effects", [])
                if e.get("op") == "add" and e.get("k") == "vouchers" and int(e.get("v") or 0) < 0
            )
            if debit and not c.get("cost"):
                voucher_cost(c, debit)

def condition_integrity(N):
    """Resolve source annotations that would otherwise leave gated choices always visible."""
    rules = [
        ("E-PRO-06", "请汤姆先入城", ANY(flag("tom_alive"), flag("tom_with"), flag("tom_saved"))),
        ("L-PRO-05", "把完整账页", flag("burnt_ledger")),
        ("L-PRO-05", "“你若想审判", cmp("mod.INS", ">=", 2)),
        ("L-PRO-06", "让凯尔射击", cmp("rel.kael", ">=", -1)),
        ("T-PRO-05", "把怒气对准", flag("c02_ward_alone")),
        ("A1-TOWN-02", "给他看真实物证", ANY(
            flag("saved_neve"), flag("c01_prisoner"), flag("shadow_named_hint"),
            flag("harlan_evidence"), flag("imperial_oil_seal"),
        )),
        ("A1-TOWN-02", "询问灰袍人", ANY(
            flag("shadow_offer"), flag("shadow_named_hint"), flag("shadow_pattern"),
        )),
        ("A1-TOWN-02", "质问她为何早知", flag("ysolde_note")),
        ("A1-TOWN-04", "把瓦伦说成危险人物", flag("valen_betrayed")),
        ("A1-TOWN-07", "指控他执行非法灭口", ANY(
            flag("family_truth"), flag("father_letter_kept"), flag("burnt_ledger"), flag("eilyn_record"),
        )),
        ("A2-MINE-01A", "煽动士兵拒绝炸矿", ANY(
            flag("eilyn_record"), flag("family_truth"), flag("father_letter_kept"), cmp("mod.CHA", ">=", 3),
        )),
        ("A3-SHRINE-01", "指出幻象中的错误", ANY(
            flag("memory_anchor_honest"), flag("family_truth"), flag("kael_confession"),
            flag("gromm_approach_honest"), flag("honest_witness"),
        )),
        ("D-NPC-TOREN", "“你怕第四层", flag("toren_dream")),
    ]
    for node_id, prefix, cond in rules:
        choice = find_any(N[node_id], prefix)
        choice["cond"] = cond
        choice.pop("cond_note", None)

def random_event_integrity(N):
    """Restore state changes that terse random-event bullets lost during parsing."""
    def ch(node_id, choice_id):
        return next(c for c in N[node_id]["choices"] if c["id"] == choice_id)

    # Shared travel events.
    ensure_effect(ch("R-TRAVEL-01", "s0c1")["success"], {"op": "adv", "k": "*"})
    ensure_effect(ch("R-TRAVEL-01", "s0c2"), item("single_military_boot"))
    c = ch("R-TRAVEL-02", "s0c1"); voucher_cost(c, 10); ensure_effect(c, item("silver_coins"))
    ensure_effect(ch("R-TRAVEL-02", "s0c2")["success"], setf("toren_bank_run_known"))
    ensure_effect(ch("R-TRAVEL-02", "s0c3")["success"], item("silver_coins"))
    ensure_effect(ch("R-TRAVEL-02", "s0c3")["fail"], add("alarm_town"))
    ensure_effect(ch("R-TRAVEL-02", "s0c4"), setf("street_exchange_closed"))

    c = ch("R-TRAVEL-03", "s0c1"); ensure_effect(c, setf("clean_water_spent")); ensure_effect(c, setf("well_child_saved"))
    c = ch("R-TRAVEL-03", "s0c2"); ensure_effect(c, setf("white_well_sealed")); ensure_effect(c, setf("chapel_water_shortage"))
    ensure_effect(ch("R-TRAVEL-03", "s0c3"), setf("well_child_sick"))
    c = ch("R-TRAVEL-03", "s0c4")
    ensure_effect(c["success"], add("time")); ensure_effect(c["success"], setf("city_resonance_casualties_reduced"))

    c = ch("R-TRAVEL-04", "s0c1")
    for branch_data in (c["success"], c["fail"]):
        ensure_effect(branch_data, setf("buried_worker_saved")); ensure_effect(branch_data, add("time"))
    ensure_effect(c["fail"], setf("drain_route_blocked"))
    ensure_effect(ch("R-TRAVEL-04", "s0c2"), setf("buried_worker_waiting"))

    ensure_effect(ch("R-TRAVEL-05", "s0c1"), item("conflicting_imperial_orders"))
    ensure_effect(ch("R-TRAVEL-05", "s0c3")["success"], setf("forged_blast_order_known"))
    ensure_effect(ch("R-TRAVEL-05", "s0c4"), setf("conflicting_orders_burned"))
    ensure_effect(ch("R-TRAVEL-06", "s0c1")["success"], setf("deserter_disarmed"))
    ensure_effect(ch("R-TRAVEL-06", "s0c1")["fail"], setf("baker_wounded"))
    ensure_effect(ch("R-TRAVEL-06", "s0c2")["success"], setf("deserter_captured"))
    ensure_effect(ch("R-TRAVEL-06", "s0c2")["fail"], add("alarm_town"))
    ensure_effect(ch("R-TRAVEL-06", "s0c3"), setf("checkpoint_password"))
    ensure_effect(ch("R-TRAVEL-06", "s0c4"), setf("deserter_to_empire"))

    ensure_effect(ch("R-TRAVEL-07", "s0c1"), setf("alaina_convoy_clue"))
    c = ch("R-TRAVEL-07", "s0c2"); ensure_effect(c, add("fragment_pressure", -1)); ensure_effect(c, setf("liriel_identity_public"))
    c = ch("R-TRAVEL-08", "s0c1"); ensure_effect(c, item("spare_rivet"))
    c = ch("R-TRAVEL-08", "s0c2"); ensure_effect(c, item("stolen_tool_kit")); ensure_effect(c, setf("helga_tools_stolen"))
    ensure_effect(ch("R-TRAVEL-08", "s0c3"), item("borrowed_file"))
    ensure_effect(ch("R-TRAVEL-09", "s0c1"), setf("hero_rumor_corrected"))
    ensure_effect(ch("R-TRAVEL-09", "s0c3"), setf("warehouse_helpers"))
    c = ch("R-TRAVEL-09", "s0c4"); ensure_effect(c, add("corruption")); ensure_effect(c, add("fragment_pressure", -1))
    c = ch("R-TRAVEL-10", "s0c1"); ensure_effect(c, add("time")); ensure_effect(c, add("rel.miners"))
    ensure_effect(ch("R-TRAVEL-10", "s0c2"), setf("winter_clothes_stored"))
    ensure_effect(ch("R-TRAVEL-10", "s0c4"), item("winter_cloak"))
    ensure_effect(ch("R-TRAVEL-11", "s0c3"), add("rel.skye", -1))
    ensure_effect(ch("R-TRAVEL-11", "s0c3"), setf("skye_alaina_clue"))
    ensure_effect(ch("R-TRAVEL-12", "s0c1"), setf("quake_child_saved"))
    ensure_effect(ch("R-TRAVEL-12", "s0c2"), setf("quake_evidence_saved"))
    ensure_effect(ch("R-TRAVEL-12", "s0c3"), add("rel.companion"))
    ensure_effect(ch("R-TRAVEL-12", "s0c4"), setf("quake_all_saved"))

    # Edric's memory intrusions.
    c = ch("R-MEM-01", "s0c1"); ensure_effect(c, add("time")); ensure_effect(c, setf("father_boot_detail"))
    ensure_effect(ch("R-MEM-01", "s0c2")["success"], add("fragment_pressure", -1))
    c = ch("R-MEM-01", "s0c4"); ensure_effect(c, add("fragment_used")); ensure_effect(c, setf("father_bone_memory"))
    ensure_effect(ch("R-MEM-02", "s0c3"), setf("lily_memory_anchor"))
    ensure_effect(ch("R-MEM-02", "s0c4"), {"op": "item", "k": "lily_comb", "v": False})
    ensure_effect(ch("R-MEM-03", "s0c1"), setf("guilt_pressure_immunity"))
    ensure_effect(ch("R-MEM-03", "s0c2"), setf("honest_witness"))
    ensure_effect(ch("R-MEM-03", "s0c4"), setf("victim_name_remembered"))
    ensure_effect(ch("R-MEM-04", "s0c2"), add("rel.companion"))
    c = ch("R-MEM-04", "s0c4")
    c["effects"] = [setf("protect_companion_ready")]
    c = ch("R-MEM-05", "s0c1"); voucher_cost(c, 3); ensure_effect(c, item("old_wooden_bowl"))
    ensure_effect(ch("R-MEM-05", "s0c3")["success"], item("old_wooden_bowl"))
    ensure_effect(ch("R-MEM-05", "s0c3")["success"], add("corruption"))
    ensure_effect(ch("R-MEM-06", "s0c1"), setf("escape_plan_open"))
    ensure_effect(ch("R-MEM-06", "s0c2"), add("fragment_pressure", -1))
    c = ch("R-MEM-06", "s0c3"); ensure_effect(c, add("time")); ensure_effect(c, setf("lily_real_message"))
    c = ch("R-MEM-06", "s0c4"); ensure_effect(c, add("fragment_used")); ensure_effect(c, add("corruption"))

    # Liriel's desire intrusions.
    ensure_effect(ch("R-DES-01", "s0c1"), add("fragment_pressure", -1))
    c = ch("R-DES-01", "s0c2"); ensure_effect(c, add("rel.companion", -2)); ensure_effect(c, add("corruption")); ensure_effect(c, setf("support_mission_failed"))
    ensure_effect(ch("R-DES-01", "s0c4"), setf("loneliness_anchor"))
    c = ch("R-DES-02", "s0c2"); ensure_effect(c, {"op": "adv", "k": "CHA"}); ensure_effect(c, add("fragment_used"))
    c = ch("R-DES-03", "s0c1"); ensure_effect(c, hp(2)); ensure_effect(c, add("corruption"))
    c = ch("R-DES-03", "s0c2"); voucher_cost(c, 3); ensure_effect(c, add("fragment_pressure", -1))
    c = ch("R-DES-03", "s0c4"); ensure_effect(c, setf("warehouse_access_hint")); ensure_effect(c, add("corruption")); ensure_effect(c, setf("enchanted_follower_pending"))
    c = ch("R-DES-04", "s0c1"); ensure_effect(c, add("rel.kael", -1)); ensure_effect(c, add("corruption")); ensure_effect(c, setf("kael_forced_risk"))
    ensure_effect(ch("R-DES-04", "s0c3"), add("rel.kael"))
    c = ch("R-DES-05", "s0c1"); ensure_effect(c, add("time")); ensure_effect(c, add("rel.eilyn"))
    ensure_effect(ch("R-DES-05", "s0c2"), setf("chapel_return_promised"))
    c = ch("R-DES-05", "s0c3"); ensure_effect(c, add("corruption")); ensure_effect(c, setf("patient_dependency_extended"))
    ensure_effect(ch("R-DES-06", "s0c1")["success"], setf("enchanted_follower_released"))
    ensure_effect(ch("R-DES-06", "s0c1")["fail"], hp(-2))
    c = ch("R-DES-06", "s0c2"); ensure_effect(c, add("corruption")); ensure_effect(c, setf("follower_memory_erased"))
    c = ch("R-DES-06", "s0c3"); c["cond"] = cmp("rel.mira", ">=", 0); ensure_effect(c, setf("follower_with_mira"))
    c = ch("R-DES-06", "s0c4"); ensure_effect(c, add("cruelty")); ensure_effect(c, setf("enchanted_follower_dead"))

    # Thorin's anger intrusions.
    ensure_effect(ch("R-ANG-02", "s0c1")["success"], setf("officer_yielded"))
    ensure_effect(ch("R-ANG-02", "s0c1")["fail"], add("alarm_town"))
    c = ch("R-ANG-02", "s0c2"); ensure_effect(c["success"], add("city_rep")); ensure_effect(c["success"], add("alarm_town"))
    c = ch("R-ANG-02", "s0c3"); ensure_effect(c, add("corruption")); ensure_effect(c, add("fragment_used"))
    ensure_effect(ch("R-ANG-02", "s0c4"), item("medicine_pack"))
    ensure_effect(ch("R-ANG-03", "s0c1"), add("time"))
    ensure_effect(ch("R-ANG-03", "s0c2"), {"op": "dis", "k": "INS"})
    ensure_effect(ch("R-ANG-03", "s0c3"), item("improved_tools"))
    ensure_effect(ch("R-ANG-03", "s0c4"), setf("toren_material_theft_known"))
    c = ch("R-ANG-04", "s0c1"); ensure_effect(c, add("rel.companion")); ensure_effect(c, add("fragment_pressure", -1))
    ensure_effect(ch("R-ANG-04", "s0c2"), add("rel.companion", -1))
    c = ch("R-ANG-04", "s0c3"); ensure_effect(c, add("rel.companion", -2)); ensure_effect(c, add("corruption"))
    ensure_effect(ch("R-ANG-04", "s0c4")["success"], setf("anger_anchor"))
    ensure_effect(ch("R-ANG-05", "s0c1")["success"], add("time"))
    ensure_effect(ch("R-ANG-05", "s0c2"), add("cruelty"))
    ensure_effect(ch("R-ANG-06", "s0c2"), add("defiance"))
    ensure_effect(ch("R-ANG-06", "s0c3"), setf("damaged_item_repaired"))

    # Non-random scenes caught by the same audit.
    c = find_any(N["A1-TOWN-05"], "指责他制造了武器")
    ensure_effect(c, add("rel.gromm", -2)); ensure_effect(c, item("tuning_tools"))
    ensure_effect(find_any(N["A1-TOWN-05"], "以索林师父")["success"], item("tuning_tools"))
    ensure_effect(find_any(N["A1-TOWN-05"], "保证誓环只用于封存"), item("tuning_tools"))
    ensure_effect(find(N["CITY-03~2"], "借仪式反向读取")["success"], add("sanctuary_clues"))
    ensure_effect(find(N["A2-MINE-01A"], "出示哈兰文书")["success"], setf("mine_explosives_known"))
    c = find(N["A2-MINE-02"], "先下井确认")
    ensure_effect(c, setf("fast_descent_access")); ensure_effect(c, add("rel.miners", -1))

    # Ambient follow-through.
    c = find(N["CITY-AMBIENT-07"], "用城市声望担保")
    c["cond"] = cmp("city_rep", ">=", 1); ensure_effect(c, item("load_bearing_clasp"))
    ensure_effect(find(N["CITY-AMBIENT-07"], "找到二十年前")["success"], item("load_bearing_clasp"))
    ensure_effect(find(N["CITY-AMBIENT-07"], "贿赂 2"), item("load_bearing_clasp"))
    ensure_effect(find(N["CITY-AMBIENT-07"], "教布罗克"), item("load_bearing_clasp"))
    c = find(N["CITY-AMBIENT-07"], "威胁书吏"); ensure_effect(c, item("load_bearing_clasp")); ensure_effect(c, add("alarm_town"))
    ensure_effect(find(N["CITY-AMBIENT-12"], "买下两半"), item("bridge_deed"))

# ---------------------------------------------------------------- mine
def mine(N):
    N["A2-MINE-02"]["default_next"] = "A2-MINE-02X"
    for c in N["A2-MINE-02"]["choices"]:
        if c.get("next") == "__SELF__" and not c.get("talk"):
            c["next"] = None
    c = find(N["A2-MINE-02"], "煽动矿工冲破护卫")
    c["call"] = "C-06"
    N["A2-MINE-00"] = node("A2-MINE-00", "去黑砧矿区的路", [
        "黑砧矿区在雾钟城西边的山腹里。帝国封了官道，可进山的路不止一条。"], [
        C("a", "走官道，过帝国检查站。", "A2-MINE-01A", [], []),
        C("b", "走托伦的私人商道。", "A2-MINE-01B", [], []),
        C("c", "钻旧排水渠，跟着米拉留下的红布走。", "A2-MINE-01C", [], []),
        C("d", "跟凯尔走山脊上的猎道。", "A2-MINE-01D", [], [])])
    N["A2-MINE-02X"] = node("A2-MINE-02X", "工棚还是囚牢", [
        "下井前，你只来得及把一处地方彻底查清。"], [
        C("shed", "去工棚和账房。", "A2-MINE-03", [], []),
        C("jail", "去关人的囚牢。", "A2-MINE-04", [], [])])
    c = find(N["A2-MINE-01A"], "攻击检查站")
    c["call"] = "C-05"
    c = find(N["A2-MINE-04~2"], "把科尔交给")
    c["call"] = "C-07"; c["next"] = "A2-MINE-05"
    n = N["A2-MINE-05"]
    for c in n["choices"]:
        lab = c["label"]
        if lab.startswith("奥斯温自愿留下"):
            c["label"] = "让奥斯温留下守绞盘。"; c["cond"] = ANY(flag("workers_warned"), cmp("rel.miners", ">=", 1))
        elif lab.startswith("索林同伴"):
            c["label"] = "让索林留下，他保证装置不出错。"; c["cond"] = NOT({"pc": "thorin"})
        elif lab.startswith("格罗姆若同行"):
            c["label"] = "格罗姆说他留下。"; c["cond"] = cmp("rel.gromm", ">=", 1)
        elif lab.startswith("命令低关系"):
            c["label"] = "命令一个不信任你的人留下。"
        elif lab.startswith("无人留下"):
            c["label"] = "谁也不留，大家一起下去。"
    # 08 → 09 (witness) or leave
    N["A2-MINE-08"]["default_next"] = "A2-MINE-09"
    for c in N["A2-MINE-08"]["choices"]:
        if c.get("next") == "__SELF__":
            c["next"] = None
    N["A2-MINE-09"]["default_next"] = "A2-MINE-10"
    for c in N["A2-MINE-09"]["choices"]:
        if c.get("next") == "__SELF__":
            c["next"] = None
    n = N["A2-MINE-10"]
    n["default_next"] = "A2-MINE-11"
    n["enter_effects"] = n.get("enter_effects", []) + [add("sanctuary_clues"), setf("mine_done")]
    for c in n["choices"]:
        if c.get("next") == "__SELF__":
            c["next"] = None
    find(n, "使用临时核心")["cond"] = flag("temporary_core")
    n = N["A2-MINE-10-LEAVE"]
    n["enter_effects"] = n.get("enter_effects", []) + [setf("mine_done"), setf("four_bones_present", False)]
    c = find(n, "救尽可能多的人后离开")
    if c.get("next") is None:
        c["next"] = "CITY-HUB"
    c = find(n, "只保自己与私人目标")
    c["next"] = "END-08"
    n = N["A2-MINE-11"]
    targets = {"沿古水道直接入城": "CITY-10", "先回地表救人": "CITY-HUB", "把照心骨交给某方": "CITY-HUB",
               "拒绝带走照心骨": "CITY-HUB", "尝试在矿区直接治疗自己": "CITY-HUB"}
    for c in n["choices"]:
        for k, v in targets.items():
            if c["label"].startswith(k):
                c["next"] = v
    find(n, "拒绝带走照心骨")["effects"].append(setf("four_bones_present", False))
    find(n, "沿古水道直接入城")["effects"] = find(n, "沿古水道直接入城").get("effects", []) + [setf("four_bones_present")]
    find(n, "先回地表救人")["effects"] = find(n, "先回地表救人").get("effects", []) + [setf("four_bones_present")]
    N["A2-MINE-01A"]["enter_effects"] = N["A2-MINE-01A"].get("enter_effects", []) + [setf("mine_visited")]

# ---------------------------------------------------------------- shrine & finale
def shrine(N):
    n = N["A3-SHRINE-04"]
    c = find(n, "“你只是失败了")
    c["call"] = "C-09"
    n = N["A3-SHRINE-05"]
    c = find(n, "支持哈兰缴械托伦")
    c["call"] = "C-08"
    c["fail"] = branch("托伦的人比你预想得多。场面乱成一团，你只能先护住自己。", [hp(-3)])
    for c in n["choices"]:
        if c.get("group") == "照心骨到场判定":
            c["auto"] = True
    # turn the "照心骨到场判定" pseudo-choices into routes on entering 06
    pseudo = [c for c in n["choices"] if c.get("group") == "照心骨到场判定"]
    n["choices"] = [c for c in n["choices"] if c.get("group") != "照心骨到场判定"]
    n["blocks"] = [b for b in n["blocks"] if b.get("text") != "照心骨到场判定"]
    for c in n["choices"]:
        if c["label"].startswith("命令双方停手"):
            c["success"]["result"] = [P("你的声音压过了所有人。两边的人都愣住了，武器一件件放低。")]
            c["fail"]["result"] = [P("没有人听你的。刀剑撞在一起，你只能退到环边。")]
        if c["label"].startswith("支持哈兰缴械托伦") and not c["success"]["result"]:
            c["success"]["result"] = [P("托伦被按倒在地。帝国的人控制了外圈。")]
    N["A3-SHRINE-06"]["default_next"] = "A3-SHRINE-07"
    N["A3-SHRINE-06"]["routes"] = [{"cond": cmp("resonance", ">=", 6), "next": "A3-SHRINE-07-LATE"}]
    b6 = N["A3-SHRINE-06"]["blocks"]
    N["A3-SHRINE-06"]["blocks"] = [b for b in b6 if "界面应显示" not in b.get("text", "")]
    for b in N["A3-SHRINE-06"]["blocks"]:
        b["text"] = b.get("text", "").replace("玩家进入最终方案选择。", "").strip()
    # bone presence becomes block conditions already parsed from 〔four_bones_present〕
    # ---- A3-SHRINE-07: hand-wired final plans
    four = flag("four_bones_present")
    E = lambda *x: list(x)
    plans = [
        C("p1", "方案一：四声解誓，毁掉服从铭文。", None,
          ["需要一个人留在内环承受四种回声，一个人逆转外环，一个人毁掉第二环上的铭文。"], [],
          cond=ANY(ALL(flag("tuning_ring_repaired"), cmp("truth", ">=", 3)), cmp("truth", ">=", 3)),
          sub=[C("p1a", "我留在内环。", "A3-SHRINE-08", ["你走进内环。四种声音同时压了下来，你把它们一一认下。"], [add("sacrifice"), setf("ending", "END-01")],
                 cond=four),
               C("p1b", "我留在内环——哪怕只剩三声。", "A3-SHRINE-08", ["中央的槽是空的。你知道这样只能扯断命令，却没人能看清余波会落到谁头上。"],
                 [add("sacrifice"), setf("ending", "END-02")], cond=NOT(four)),
               C("p1c", "请一位同伴自愿留下。", "A3-SHRINE-08", ["你没有替对方决定代价。对方自己走了进去。"], [setf("ending", "END-02")],
                 cond=ANY(cmp("rel.kael", ">=", 3), cmp("rel.gromm", ">=", 3), cmp("rel.eilyn", ">=", 3), cmp("rel.tom", ">=", 3))),
               C("p1d", "用临时核心逼某个人进去。", "A3-SHRINE-08", ["技术上它成功了。可就在你下命令的那一刻，服从铭文也刻进了你自己。"],
                 [add("corruption", 2), setf("ending", "END-05")])]),
        C("p2", "方案二：订立雾钟地方新约。", None,
          ["众人不把钟骨合成一件，而是一起说出限制：谁也不得命令另一个意识；谁都可以撤回；每次使用，代价都要让受影响的人看见。"], [],
          cond=ALL(cmp("truth", ">=", 4), four),
          sub=[C("p2a", "公开全部罪证，连同我自己的过错。", "A3-SHRINE-08", ["你把一切都说了出来。没有人打断你。"], [setf("ending", "END-03")],
                 cond=NOT(cmp("corruption", ">=", 3))),
               C("p2b", "成为各方都能监督的守约人。", "A3-SHRINE-08", ["你答应了。誓约成立，但钟骨偶尔还会失衡。"], [setf("ending", "END-04")])]),
        C("p3", "方案三：交给帝国封存。", None,
          ["哈兰承诺把钟骨送进内地黑库，并撤销炸矿的命令。你可以提条件，但最多只能确保两个。"], [],
          cond=ANY(flag("harlan_writ"), cmp("rel.harlan", ">=", 1)),
          sub=[C("p3a", "信任哈兰，交出来。", "A3-SHRINE-08", ["哈兰接过铅箱，向你行了个军礼。"], [setf("ending", "END-06")]),
               C("p3b", "表面交出，暗中留下一枚。", "A3-SHRINE-08", ["你的手在铅箱上停了半秒。没有人看见。"], [add("corruption"), setf("ending", "END-06")])]),
        C("p4", "方案四：交给托伦，换矿区自治。", None,
          ["托伦愿意用四声冠逼帝国撤军，把矿井分给工人，却不肯放弃自己的指挥权。"], [],
          cond=NOT(flag("toren_dead")),
          sub=[C("p4a", "接受他的条件。", "A3-SHRINE-08", ["托伦大笑，把钟骨举过了头顶。"], [setf("ending", "END-07")]),
               C("p4b", "在交接的一刻杀了他。", "A3-SHRINE-08", ["你得手了。可他的护卫和帝国的人同时扑向了核心。"], [add("cruelty", 2), setf("ending", "END-11")])]),
        C("p5", "方案五：分开封存，各自带走。", None,
          ["把钟骨重新放回容器，由几名自愿的守护者朝不同方向离开。共鸣会停下，风险只是被推迟。"], [],
          sub=[C("p5a", "找齐愿意守护的人，各走一条路。", "A3-SHRINE-08", ["每个人都明白自己带走的是什么。"], [setf("ending", "END-10")]),
               C("p5b", "偷偷塞一枚给不知情的人。", "A3-SHRINE-08", ["当下一切顺利。只是你知道，有个人往后会替你付账。"], [add("corruption", 2), setf("ending", "END-10")])]),
        C("p6", "方案六：带着自己的目标离开。", None,
          ["趁其他人争执，你取回自己的容器和凭证，从侧道离开。你最多能带走一个人。"], [],
          sub=[C("p6a", "走侧道，头也不回。", "END-08", [], [setf("ending", "END-08")],
                 check={"stats": ["DEX", "INS"], "dc": 16, "auto_if": ANY(flag("harlan_writ"), flag("mine_drain_route"))},
                 success=branch("你摸着湿冷的墙找到了出口。身后的光越来越亮。"),
                 fail=branch("侧道塌了一半。你挤出去时，已经浑身是伤。", [hp(-6)])),
               C("p6b", "临走前先警告全镇。", "END-08", ["你放慢了脚步，把消息传了出去。这会让你更难脱身，但会少死很多人。"],
                 [add("mercy"), setf("ending", "END-08")])]),
        C("p7", "方案七：夺取临时核心。", None,
          ["你把钟骨接进自己的容器，试图压过塞维兰。这只能形成一顶不稳定的“四声冠”。"], [],
          cond=four,
          sub=[C("p7a", "压过他。", "A3-SHRINE-08", [], [],
                 check={"stats": ["WIL", "CHA"], "dc": 16}, cond=NOT(cmp("corruption", ">=", 4)),
                 success=branch("你听见了所有人的愿望，却还认得出哪一个是自己的。", [setf("ending", "END-12")]),
                 fail=branch("你的手不再听你使唤。塞维兰借着你的身体，戴上了那顶冠。", [setf("ending", "END-05")])),
               C("p7c", "压过他——用你此刻全部的渴望。", "A3-SHRINE-08", ["冠戴上的时候，你觉得一切都终于听你的了。这种感觉好得可怕。"],
                 [setf("ending", "END-13")], cond=cmp("corruption", ">=", 4)),
               C("p7b", "邀请塞维兰共治。", "A3-SHRINE-08", ["你向那片透明的影子伸出手。他第一次露出真正意外的神情。"], [setf("ending", "END-14")])]),
        C("p8", "方案八：炸毁初鸣庭。", None,
          ["你可以在誓环顶点引爆炸药，让山体掩埋这里的一切。"], [],
          cond=ANY(flag("explosives"), flag("mine_explosives"), flag("blasting_charges")),
          sub=[C("p8a", "点燃引信，掩护所有人撤离。", "A3-SHRINE-08", ["引信嘶嘶地烧了起来。"], [setf("ending", "END-15")]),
               C("p8b", "点燃长引信，由你留下守着。", "A3-SHRINE-08", ["你让其他人先走。"], [add("sacrifice"), setf("ending", "END-16")])]),
        C("p9", "方案九：记录塞维兰，再让钟骨沉默。", None,
          ["先让照心骨记下他的一切，再一同沉默。知识留下，人格不留。"], [],
          cond=ALL(four, flag("tuning_ring_repaired")),
          sub=[C("p9a", "开始记录。", "A3-SHRINE-08", ["白光里，塞维兰把他记得的一切都说了出来，然后安静了。"], [setf("ending", "END-01")])]),
    ]
    n = N["A3-SHRINE-07"]
    n["blocks"] = [P("黎明已经到了。环上的光一圈圈亮起，所有人都在等你开口。"),
                   P("每一个方案都有代价。没有哪一个会被叫作好结局。")]
    n["choices"] = plans
    n["kind"] = "scene"
    # LATE
    n = N["A3-SHRINE-07-LATE"]
    for b in n["blocks"]:
        if b.get("text", "").startswith("只保留"):
            b["text"] = "已经没有时间商量了。"
    n["blocks"] = [b for b in n["blocks"] if "触发" not in b.get("text", "") and "倒计时" not in b.get("text", "")]
    c = find(n, "抱住照心骨"); c["cond"] = four
    c = find(n, "逆转前三槽"); c["cond"] = NOT(four)
    c = find(n, "把到场钟骨交给最强阵营")
    c["next"] = None
    c["result"] = [P("你把钟骨推向离你最近的那一方。")]
    c["sub"] = [C("h", "交给哈兰。", "END-06", [], []), C("t", "交给托伦。", "END-07", [], [])]
    c = find(n, "点燃炸药"); c["next"] = "END-15"; c["cond"] = ANY(flag("explosives"), flag("mine_explosives"), flag("blasting_charges"))
    # 08: last words, then the chosen ending
    n = N["A3-SHRINE-08"]
    n["blocks"] = [P("在一切变得无法挽回之前，还在场的人各自说了一句话。")]
    for who, line in [("艾德里克", "“别替我说我愿意。问我，然后听答案。”"), ("莉瑞尔", "“活下来不是裁决。今天之后，我自己决定这条命做什么。”"),
                      ("索林", "“能修的不是每样都该照原样修。”")]:
        n["blocks"].append({"t": "say", "who": who, "text": line, "cond": NOT({"pc": {"艾德里克": "edric", "莉瑞尔": "liriel", "索林": "thorin"}[who]})})
    n["blocks"] += [SAY("艾琳", "“救赎不是抹去记录，是记录之后仍允许人改变。”"), SAY("塞维兰", "“我也曾说过这些。区别只在你接下来做什么。”")]
    n["choices"] = [C(f"w{i}", lab, None, [res], [setf("last_word", tone)]) for i, (lab, res, tone) in enumerate([
        ("“这是我选的，我来承担。”", "你说完，没有再看任何人。", "bear"),
        ("“我没有别的办法。”", "你的声音比你以为的要轻。", "excuse"),
        ("“都别动。照我说的做。”", "所有人都安静了下来。", "command"),
        ("什么也不说。", "你只是点了点头。", "silence")])]
    n["routes_after"] = True
    n["default_next"] = "__ENDING__"

# ---------------------------------------------------------------- random detours & combat returns
def detours(N):
    for nid, n in N.items():
        if nid.startswith("R-") or nid.startswith("C-"):
            base = re.sub(r"~\d+$", "", nid)
            k = int(nid.split("~")[1]) + 1 if "~" in nid else 2
            last = f"{base}~{k}" not in N
            if last:
                n["default_next"] = "__RETURN__"
            for c in walk_choices(n):
                if c.get("next") == "__SELF__":
                    c["next"] = None
        if nid.startswith("FAIL-"):
            n["kind"] = "ending"

FAIL_RULES = [
    {"prefix": ["E-PRO", "L-PRO", "T-PRO", "C-01", "C-02", "C-03"], "node": "FAIL-01"},
    {"prefix": ["A1-", "C-04"], "node": "FAIL-02"},
    {"prefix": ["C-05"], "node": "FAIL-03"},
    {"prefix": ["A2-", "C-06", "C-07", "C-08"], "node": "FAIL-04"},
    {"prefix": ["A3-", "C-09"], "node": "FAIL-07"},
    {"prefix": [""], "node": "FAIL-05"},
]

# ---------------------------------------------------------------- endings & epilogues
EPI_RULES = {
    "edric": [("文书有效", flag("harlan_writ")), ("以父亲记忆为代价", flag("lost_father_memory")),
              ("父亲军信公开", ALL(flag("truth_public"), flag("father_letter_kept"))), ("私人目标放弃", None)],
    "liriel": [("高腐化", cmp("corruption", ">=", 3)), ("完整证据", cmp("truth", ">=", 4)),
               ("焚毁档案", flag("private_goal_abandoned")), ("选择性证据", None)],
    "thorin": [("怀表内化", {"ending": "END-CURE-04"}), ("合法交货", ANY(flag("private_goal_secured"), flag("workshop_ledger"))),
               ("假印成功", flag("harlan_blackmail")), ("放弃订单救矿工", None)],
}

EPILOGUES = {}

def endings(N, epis):
    for nid, n in N.items():
        if n.get("kind") == "ending" or nid.startswith(("END-", "FAIL-")):
            n["kind"] = "ending"
            n["choices"] = [C("title", "回到标题。", "__TITLE__", [], [])]
            n["blocks"] = [b for b in n["blocks"] if b.get("text")]
    variants = {}
    for pc, paras in (epis or {}).items():
        out = []
        for raw in paras:
            m = re.match(r"\*\*(.+?)[：:]\*\*\s*(.*)", raw)
            if not m:
                continue
            lab, body = m.group(1), T.sanitize(m.group(2))
            cond = None
            for key, c in EPI_RULES.get(pc, []):
                if lab.startswith(key):
                    cond = c if c is not None else {"else": True}
                    break
            if cond is None:
                continue
            out.append({"label": lab, "text": body, "cond": cond})
        out.sort(key=lambda v: 1 if v["cond"].get("else") else 0)
        variants[pc] = out
    for vs in variants.values():
        for v in vs:
            t = final_clean(v["text"]) or v["text"]
            t = t.replace("也被。", "也被记录在案。")
            if t.startswith("责任也难以追究"): t = "档案化为灰烬，罪行与" + t
            v["text"] = t
    EPILOGUES.clear(); EPILOGUES.update(variants)

# ---------------------------------------------------------------- text fixes for leftovers the generic pass cannot word well
GENERIC_LABEL = {
    "常见问答": "你到底是什么", "他何时说谎": "拆穿他的话", "身份变体": "你的来历",
    "羁绊场景": "更私人的话", "背叛揭穿": "被揭穿的背叛", "终幕底线": "最后的底线",
    "终幕贡献": "最后能出的力", "可合作条件": "合作的条件", "羁绊动作。": "陪对方安静地待一会儿。",
    "初见闲谈": "初见寒暄", "交接现场": "交接那天", "他到底同不同意": "他到底愿不愿意",
}

LABEL_FIX = {
    ("D-NPC-TOM", "成长结算"): "之后的汤姆",
    ("CITY-NPC-ANSER", "同意判定"): "他到底同不同意",
    ("D-NPC-HELGA", "索林关系"): "关于索林",
    ("CITY-AMBIENT-04", "揭穿“花钱哭虚伪”，遗孀回答：“我花钱买的是有人记得说他的名字。”关系无奖励。"): "揭穿“花钱哭”的虚伪。",
}
TEXT_FIX = {
    "照心骨到场判定": None,
    "后续修誓环自动成功一次": "后续修誓环时能派上用场",
    "每人偏好。": "",
}

DESIGNER_SENT = re.compile(r"状态|关系|旁白|授予|由此前|一级|压力|若，|需已有|你决定：.*需要|决定$|是否.*决定|根据|倾向|计入|扣除|恢复一|分别|界面|高城内")

def split_sents(t):
    out, buf, depth = [], "", 0
    for ch in t:
        buf += ch
        if ch in "“「": depth += 1
        elif ch in "”」": depth = max(0, depth - 1)
        elif ch in "。！？" and depth == 0:
            out.append(buf); buf = ""
    if buf: out.append(buf)
    return out

def final_clean(t):
    keep = []
    for x in split_sents(t):
        core = x.strip()
        bare = re.sub(r"“[^”]*”", "", core)
        if DESIGNER_SENT.search(bare):
            continue
        if re.match(r"^若[^，；：]*[。！？]?$", core):
            continue
        keep.append(x)
    t = "".join(keep).strip()
    t = re.sub(r"^[，；：、]+", "", t)
    return t

def text_fixes(N):
    N["A1-TOWN-06"]["title"] = "未了的私事"
    N["A3-SHRINE-07-LATE"]["title"] = "黎明"
    for c in walk_choices(N["C-04"]):
        for b in c.get("result", []):
            if b.get("text", "").startswith("阻止敌人取得"):
                b["text"] = "你把箱子推进了河里，谁也没能拿走它。只是之后你得去河闸把它捞回来。"
    for nid, n in N.items():
        if nid.startswith("__"):
            continue
        for c in walk_choices(n):
            k = (nid, c["label"])
            if k in LABEL_FIX:
                c["label"] = LABEL_FIX[k]
            c["label"] = GENERIC_LABEL.get(c["label"], c["label"])
            c["label"] = re.sub(r"^羁绊场景：", "", c["label"])
            c["label"] = re.sub(r"——.*$", "", c["label"]).strip()
            c["label"] = re.sub(r"(.+)变体$", r"\1", c["label"])
        def fix_blocks(bl):
            out = []
            for b in bl:
                t = b.get("text", "")
                for a, r in TEXT_FIX.items():
                    if a in t:
                        t = None if r is None else t.replace(a, r)
                        if t is None:
                            break
                if t is None:
                    continue
                t = re.sub(r"[；，]?解锁[^；。]*", "", t)
                t = final_clean(t) if b.get("t") != "say" else t
                b["text"] = t
                if t:
                    out.append(b)
            return out
        n["blocks"] = fix_blocks(n.get("blocks", []))
        for c in walk_choices(n):
            c["result"] = fix_blocks(c.get("result", []))
            for br in ("success", "fail"):
                if c.get(br):
                    c[br]["result"] = fix_blocks(c[br].get("result", []))
    c = find(N["A3-SHRINE-04"], "“力量本就该")
    c["result"] = [b for b in c["result"]]

# ---------------------------------------------------------------- meta
def meta(N):
    chars = json.loads((ROOT / "tools/characters.json").read_text(encoding="utf-8"))
    epis = EPILOGUES
    return {
        "title": "雾钟城：第七声", "version": "2.0.0", "node_count": len(N),
        "characters": chars,
        "time_labels": ["黄昏", "入夜", "深夜", "午夜", "三更", "四更", "黎明"],
        "item_names": dict(T.ITEM_NAMES),
        "epilogues": epis,
        "fail_rules": FAIL_RULES,
        "curse_fail": {"stage": 5, "node": "FAIL-06"},
        "wound_fail": {"hp_max": 2, "endings": ["END-01", "END-02", "END-03", "END-04", "END-10"], "node": "FAIL-08"},
        "random": {"chance": 0.35, "guarantee": 3, "pools": {"edric": "edric", "liriel": "liriel", "thorin": "thorin"}},
        "dc_words": {"10": "较易", "13": "中等", "16": "困难", "19": "极难"},
        "stat_names": {"STR": "力量", "DEX": "敏捷", "CON": "体魄", "CHA": "魅力", "INS": "洞察", "WIL": "意志"},
    }
