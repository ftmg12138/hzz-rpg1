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

def FOLD(label, *parts, **kw):
    """Collapsed explicit prose. UI renders as ▸ label; click expands nested blocks.
    Markup in nodes.json: {"t":"fold","label":"情欲描写","blocks":[...]}
    Optional cond on the fold itself (same as other blocks).
    """
    blocks = []
    for part in parts:
        if isinstance(part, str):
            blocks.append(P(part))
        elif isinstance(part, dict):
            blocks.append(part)
        else:
            blocks.extend(part)
    out = {"t": "fold", "label": label or "情欲描写", "blocks": blocks}
    if "cond" in kw and kw["cond"] is not None:
        out["cond"] = kw["cond"]
    return out

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
    liriel_desire(N)
    companion_liriel_intimacy(N)
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
    # After combat/endings/overrides: intimacy folds must win last.
    companion_liriel_intimacy(N)
    late_liriel_intimacy(N)

    # 2026-10-29 design revision (equip/fall/folds/dossiers); idempotent
    try:
        import wzc_revision_pass
        wzc_revision_pass.apply_to_nodes(N)
    except Exception as e:
        print('wzc_revision_pass skipped:', e)

    try:
        import wzc_phase1_systems as _p1
        _p1.patch_tavern_shallow(N)
        _p1.patch_stash_actions(N)
    except Exception as e:
        print('wzc_phase1_systems skipped:', e)

    try:
        import wzc_phase2_pass as _p2
        _p2.apply_to_nodes(N)
    except Exception as e:
        print('wzc_phase2_pass skipped:', e)

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
    # Companion hub: never offer the PC as their own companion.
    if "D-ALT" in N:
        pc_of = {"t1": "edric", "t2": "liriel", "t3": "thorin"}
        for c in N["D-ALT"]["choices"]:
            if c.get("id") in pc_of:
                c["cond"] = NOT({"pc": pc_of[c["id"]]})
        N["D-ALT"]["blocks"] = [P("另一位残片持有者注意到了你，停下了手里的事。")]

# ---------------------------------------------------------------- liriel desire / intimacy (consensual adult)
# ---------------------------------------------------------------- liriel desire / intimacy (consensual adult)
def liriel_desire(N):
    """Necklace-driven desire / charm scenes: tame surface + foldout explicit prose.

    Foldouts use block type `fold` (see FOLD()). Surface lines stay readable;
    ▸ 情欲描写 expands the direct sex/desire beats. Charm that hollows consent
    keeps the moral cost visible; mid-scene forced non-con still cuts short.
    """
    # ---- L-PRO-02 first touch
    n = N["L-PRO-02"]
    for b in n["blocks"]:
        if "地窖外有脚步" in b.get("text", "") or "银链在你掌中震动" in b.get("text", ""):
            b["text"] = (
                "地窖外有脚步。一个陌生男人低声咒骂，正用铁钩拨开门边的石块。"
                "银链在你掌中震动，热意沉进小腹——你忽然非常清楚自己可以怎样让他放下戒心。"
            )
    c = find(n, "把银链戴上")
    c["result"] = [
        P("你把银链绕上颈窝。热意立刻沉下来。你靠近门边，声音放软：“我被困住了。请帮帮我。”男人丢下铁钩来搬石头，甚至没有先问你是谁。"),
        FOLD(
            "情欲描写",
            "银链一贴皮肤，乳尖与腿根就发烫发软。你把呼吸调得恰好像受惊，让领口松一点，让他的目光黏上来。"
            "他搬石头时裤裆已经顶起形状；银链满意地轻颤——它要的不是求救，是你把自己当成诱饵的那一刻。",
        ),
    ]
    c = find(n, "咬住舌尖")
    if c.get("success"):
        c["success"]["result"] = [P("你咬破舌尖。痛压过那一阵发软。你守住了自己，没有把亲近冲动送出去。")]
    if c.get("fail"):
        c["fail"]["result"] = [P("亲近的冲动没压干净，你仍未使用魅惑——只是心神发颤，下一句好话会更难说稳。")]

    # ---- L-PRO-06 charm lure
    n = N["L-PRO-06"]
    c = find(n, "用银链引开")
    c["result"] = [
        P("你让银链发热，对靠外的男人轻声说：“跟我来。我想单独跟你说。”他丢下同伴跟你走进雨里。巷角交手之后女孩得救了；被你引开又丢下的男人，会在镇里执着寻找你。"),
        FOLD(
            "情欲描写",
            "他的瞳孔放大，裤裆顶起形状。你在巷角把他按在湿墙上，舌尖刚触到他喉结——随即一肘砸上侧腹，夺刀回身偷袭另一个。"
            "他记得的不是刀，是你贴上来时的体温与未兑现的交合。",
        ),
    ]
    ensure_effect(c, setf("enchanted_follower_pending"))

    # ---- L-PRO-07 first full desire intrusion
    n = N["L-PRO-07"]
    n["blocks"] = [
        P("雨停了。凯尔或妮芙若在，会走在前方；若只剩你一人，路旁旅舍窗里透出暖光。"),
        P("银链骤然收紧。热意从腕间沉进小腹，呼吸乱了——欲望先是身体里的热，随后变成更难承认的东西：如果别人真正渴望你，你就暂时不用判断自己值不值得活。"),
        FOLD(
            "情欲描写",
            "乳头发硬，腿根发软。你想被手掌按住腰，想被嘴唇堵住未说完的话，想用交合确认自己不是地窖里那个屏住呼吸的影子。"
            "银链把“被进入、被弄到发抖”熨进每一口呼吸里。",
        ),
    ]
    c = find(n, "向愿意的人提出亲近")
    c["label"] = "向愿意的人提出亲近，并允许对方真实回答。"
    c["result"] = [
        P("你没有催动银链。你把话说清楚：你现在想被抱、想亲近——但对方可以说不。"),
        {
            "t": "p",
            "text": "凯尔听完，喉结滚动一下：“现在不行。但你可以走近一点。”他让你的肩贴上他的，掌心扣住你的指节。没有更进一步，可那体温足够让银链松一寸。",
            "cond": {"cmp": ["rel.kael", ">=", 1]},
        },
        FOLD(
            "情欲描写",
            "他的体温贴着你的侧乳与腰线。你几乎想抬腿跨上去，把湿热带进他掌心；他却只把下巴搁在你发顶，呼吸发沉。"
            "“再往下，就不是安慰了，”他哑声说，“等你不是被链子推着的时候——再问我一次。”你夹紧双腿忍住，银链恨得发颤。",
            cond={"cmp": ["rel.kael", ">=", 1]},
        ),
        {
            "t": "p",
            "text": "妮芙握住你的手：“我可以陪你走。不是你欠我的，也不是今晚就得脱衣服。”她把你拉到屋檐下，额头抵着你的。银链不满地轻颤，却找不到可趁的缝。",
            "cond": {"all": [{"flag": "saved_neve"}, {"not": {"cmp": ["rel.kael", ">=", 1]}}]},
        },
        FOLD(
            "情欲描写",
            "她的鼻尖蹭过你的。你想吻深一点、想把她的手按上自己胸口以下；她轻轻摇头，却没有退开。"
            "“我想要你，”她承认，“但不是今晚被银链点着的那种要。先活过灰桥。”腿根发软，你还是只回握了她的手指。",
            cond={"all": [{"flag": "saved_neve"}, {"not": {"cmp": ["rel.kael", ">=", 1]}}]},
        ),
        {
            "t": "p",
            "text": "旅舍里有个愿意的陌生人。你们关上门；他先问了一句“你确定？”事后你按旅舍规矩付清房钱。银链安静了一阵，像被喂饱。",
            "cond": {"all": [{"not": {"cmp": ["rel.kael", ">=", 1]}}, {"not": {"flag": "saved_neve"}}]},
        },
        FOLD(
            "情欲描写",
            "你把银链藏进袖口，自己去解他的扣子。他的手顺着你的腰滑进裙摆，手指探进湿热处时你咬住了他的肩；随后他把你抵在床沿进入，每一次顶撞都让银链轻轻发颤，却无法替任何人开口。"
            "你高潮时叫出了声，他也射在里面——都是自愿，没有魅惑。",
            cond={"all": [{"not": {"cmp": ["rel.kael", ">=", 1]}}, {"not": {"flag": "saved_neve"}}]},
        ),
    ]
    c["effects"] = [add("fragment_pressure", -1)]
    c["cond_effects"] = [
        {"cond": {"cmp": ["rel.kael", ">=", 1]}, "ops": [add("rel.kael")]},
        {"cond": {"all": [{"flag": "saved_neve"}, {"not": {"cmp": ["rel.kael", ">=", 1]}}]}, "ops": [add("rel.mira")]},
        {"cond": {"all": [{"not": {"cmp": ["rel.kael", ">=", 1]}}, {"not": {"flag": "saved_neve"}}]},
         "ops": [add("time"), add("vouchers", -3)]},
    ]

    c = find(n, "利用银链确保对方不会拒绝")
    c["result"] = [
        P("银链一热，对方的眼神就空了。你得到短暂安抚，随即恶心：那不是自愿。画面在这里切断。"),
        FOLD("情欲描写", "身体还在迎合，可回应里没有本人——只有被银链点着的机械动作。你没有把这一场写完整。"),
    ]

    c = find(n, "把冲动转成坦白")
    c["result"] = [
        P("你告诉同行者：“我现在很想亲近，证明我不是多余的。这不是请求，只是事实。”银链不满地收紧，却找不到可替你开口的缝。"),
        FOLD("情欲描写", "你说得更直白：想让人按住你、进入你。对方听完，只按自己的意愿回应；银链找不到命令可下。"),
    ]

    c = find(n, "独自压下去")
    c["success"]["result"] = [P("你靠在湿树上，直到那一阵颤意退去。银链还在跳，可你没有把它指向任何人。")]
    c["fail"]["result"] = [P("欲望没压住，你仍独自熬过了这一阵。没有伤害别人，只是腿软得几乎站不稳。")]

    c = find(n, "用刀尖在银片上刻一道痕")
    c["result"] = [P("刀尖划过银片，血珠滚进刻痕。痛意压过情欲半拍。你提醒它：这具身体是谁的。")]

    # ---- L-PRO-08 charm the gate guard
    n = N["L-PRO-08"]
    c = find(n, "魅惑守门兵")
    c["label"] = "魅惑守门兵"
    c["result"] = [
        P("你把银链按在锁骨下，声音放软：“放我进城。夜里……来找我。”守门兵放行，并报了巷口旅舍的后门。"),
        P("换岗后他果然擅离岗位摸进来。天亮后军务处通报：灰桥东门守兵擅离职守，记大过并调离。城镇公告栏多了一条含糊的「纪律处罚」新闻。残片的低语贴得更近。"),
        FOLD(
            "情欲描写",
            "门一闩上，他的手就急着扯开你的衣带、揉你的乳尖，裤裆硬挺着顶在你小腹上——那不是谈妥边界的邀请，是银链替他点着的火。"
            "你把他按到墙板反客为主，自己坐下去吃进他的阴茎；木板随着顶撞轻响，你高潮时咬着他的肩叫出声，他也射在里面，还喘着求再来一次。"
            "残片的低语像满意地舔过耳廓。",
        ),
    ]
    ensure_effect(c, setf("enchanted_follower_pending"))
    ensure_effect(c, setf("charm_guard_news"))

    # ---- A1-TOWN-04 Mira
    mira = N["A1-TOWN-04"]
    for b in mira["blocks"]:
        if b.get("text", "").startswith("米拉一眼看出") or "银链带来的躁动" in b.get("text", ""):
            b["text"] = "米拉一眼看出银链带来的躁动：你的瞳孔偏大，坐下时双腿不自觉地并紧。"
        if "欲望不是罪" in b.get("text", ""):
            b["text"] = "“欲望不是罪。想被抱紧、想亲近，都不是。把别人的回答拿走，才是。”"

    mira["choices"] = [c for c in mira["choices"] if c.get("id") != "t_desire"]

    topic = next((c for c in mira["choices"] if "亲近而非沉沦" in c.get("label", "") or c.get("id") == "t_desire"), None)
    if topic is None:
        leave_i = next((i for i, c in enumerate(mira["choices"]) if c.get("id") == "leave"), len(mira["choices"]))
        topic = C("t_desire", "向米拉坦白银链带来的情欲躁动。", None, [], [], topic=True, once=True, cond={"pc": "liriel"}, sub=[])
        mira["choices"].insert(leave_i, topic)
    topic["id"] = "t_desire"
    topic["label"] = "向米拉坦白银链带来的情欲躁动。"
    topic["cond"] = {"pc": "liriel"}
    topic["topic"] = True
    topic["once"] = True
    topic["next"] = None
    topic["result"] = [
        SAY("米拉", "“银链放大的是欲望，不只是想上床。想被爱、想让人别走、想让一句拒绝消失，都是。别恨自己的渴望。盯着你打算让谁替它付账。”"),
        P("她把一串钥匙转了半圈，等你自己选。"),
        FOLD("情欲描写", "她说得更直白：想被进入、想叫出声，也可以——只要对方还能说停。"),
    ]
    topic["effects"] = []
    topic["sub"] = [
        C(
            "intimate",
            "请她安排一场双方都自愿的亲近。",
            "__SELF__",
            [
                P("米拉带你见了一位同样自愿、且听过边界说明的客人。门关上之后，没有魅惑，没有“不会拒绝”的把戏。淡出前，米拉在门外敲了一下，提醒时辰。"),
                FOLD(
                    "情欲描写",
                    "对方先问你哪里可以碰。你把银链摘下放在枕边，自己跨坐上去，引导对方的手指、再引导进入。"
                    "肉体撞在一处时银链在枕边轻颤，却插不进你们的对话——你们都能说停。汗、喘息、小腹痉挛的高潮都是你们自己选的。",
                ),
            ],
            [add("time"), add("fragment_pressure", -1), {"op": "item", "k": "shaken", "v": False}, setf("mira_intimate_done"), setf("visited_mira")],
            once=True,
        ),
        C(
            "kitchen",
            "去后厨帮忙，靠劳动压下冲动。",
            "__SELF__",
            [P("你在后厨剁菜、搬汤桶，直到手臂发酸、情欲退成背景噪音。米拉递来一碗浓汤：“欲望可以留着。先把肚子填上。”")],
            [add("fragment_pressure", -1), setf("visited_mira")],
            once=True,
        ),
        C(
            "nonrefuse",
            "要求找一个不会拒绝的人。",
            "__SELF__",
            [
                SAY("米拉", "“门在那边。别再进我的店。”"),
                P("她当场结束谈话。红牡丹的门在你身后合上。"),
            ],
            [add("rel.mira", -2), setf("visited_mira")],
            once=True,
        ),
    ]

    # ---- Desire intrusion pool
    des2 = N["R-DES-02"]
    c = find(des2, "停下欣赏")
    c["result"] = [P("你在橱窗前多站了一会儿。镜中那张“更好看”的脸朝你微笑——耳形更尖，目光更冷。你没有触碰银链，幻象自己散了。")]

    des1 = N["R-DES-01"]
    des1["blocks"] = [
        P("同伴说要去执行后援。银链却把“留下”熨进舌尖：留下来，别让这具身体空着。话到嘴边，几乎要变成命令。"),
        FOLD("情欲描写", "它要的不只是陪伴——是留下来抱你，摸到你发抖，用交合把后援时辰一起吞掉。"),
    ]
    c = find(des1, "请求而不强迫")
    c["result"] = [
        P("你只说：“我想你留下。你可以拒绝。”对方按自己的意愿答了。被拒绝也让压力松了一点——因为边界还在。"),
        FOLD("情欲描写", "你把话说全：想被抱紧，被摸到发抖。对方听完，只给了自己愿意给的那一部分。"),
    ]
    c = find(des1, "魅惑留下")
    c["result"] = [
        P("银链一紧，同伴的脚步顿住。他把你抵在墙角，直到后援时辰错过。效果解除后关系崩了一角；后援失败。"),
        FOLD(
            "情欲描写",
            "你把他的手按上自己的腰、再往下滑进衣摆；他眼神发空，却仍硬着身子亲吻、抚摸。"
            "事后他想起那晚的空白与你身上的味道，像吞下一根刺。",
        ),
    ]

    des3 = N["R-DES-03"]
    des3["blocks"] = [
        P("旅店侍者被银链牵着，声音发紧：“今晚的房费……算我的。”他的目光停在你唇上、锁骨上。那不是清醒的邀请。"),
        FOLD("情欲描写", "裤裆顶起形状，像已经在想象把你按在门板上操。银链替他说完了那句不该说的话。"),
    ]
    c = find(des3, "接受但明确只要房间")
    c["result"] = [P("你收下免单，却把门从里面闩上，只睡不碰。门外他喘了一会儿才离开。即便如此，你仍在用银链扭曲过的同意换舒适——腐化悄然加深。")]
    c = find(des3, "付全价并拉开距离")
    c["result"] = [
        P("你把三张商会券拍在柜上，后退一步：“我要的是床。”他眨眼，欲望像潮水退去，剩下尴尬的红晕。"),
        FOLD("情欲描写", "你说得更硬：“我要的是床，不是你的鸡巴。”"),
    ]
    c = find(des3, "问对方原本想说什么")
    c["result"] = [P("他眨眼后抹了把脸：“其实客满。刚才那句……我不该那么说。”你可离开。")]
    c = find(des3, "加深影响索取情报")
    c["result"] = [
        P("你让银链再热一分。他把仓库暗门的位置说完；你按住他的手，只要情报，不给下面那一场。"),
        FOLD("情欲描写", "他的手指急着去解你的衣带、想把你按在柜台上。你只要地图上的缝，不要他的阴茎。"),
    ]

    des4 = N["R-DES-04"]
    des4["blocks"] = [
        P("银链贴着皮肤发烫，低语清晰：只要提起凯尔当年的迟疑，他就不会拒绝任何请求。"),
        FOLD("情欲描写", "包括跟你上床，包括替你去死——银链把愧疚和情欲拧成同一根绳子。"),
    ]
    c = find(des4, "使用愧疚让他冒险")
    c["result"] = [P("你提起那晚他晚到半个时辰。他脸色发白，却仍照你的话冒险。任务成了；他看你的眼神多了一层屈辱。腐化加深。")]
    c = find(des4, "直接提出请求")
    c["result"] = [P("你不提旧事，只把请求说清楚。他按你们现在的关系回答——没有银链替你撬开的缝。")]
    c = find(des4, "告诉他银链给了这个念头")
    c["result"] = [
        P("你坦白：“银链让我觉得，只要提起那晚，你就会答应我任何事。”凯尔沉默片刻：“谢谢你没把诚实也当武器。”"),
        FOLD("情欲描写", "你把后半句也说了：包括抱我。他听完，只点了点头，没有退开，也没有扑上来。"),
    ]
    c = find(des4, "不请求")
    c["result"] = [P("你什么也没有要求。欲念在舌尖转了一圈又咽回去。凯尔的愧疚留在了他自己心里。")]

    des5 = N["R-DES-05"]
    des5["blocks"] = [
        P("礼拜堂伤员握住你的手说“别走”。他不是爱你，只是痛和害怕；可被需要的感觉仍像火。"),
        FOLD("情欲描写", "银链甚至想把这点火扭成“留下，让他靠着你的身体入睡”——把护理扭成床笫。"),
    ]
    c = find(des5, "陪到药生效")
    c["result"] = [P("你留下来握着他的手，直到药力压住呻吟。没有更越界的触碰。艾琳向你点了点头。")]
    c = find(des5, "让银链延长依赖")
    c["result"] = [P("你让银链轻颤。伤员抓紧你的指节，把脸埋进你掌心。腐化加深；下次你离开时，他会恐慌发作。")]
    c = find(des5, "温和抽手叫修女来")
    c["result"] = [P("你轻轻抽手，把修女唤来。“他需要的是药，不是我的身体。”边界清楚，银链不满地凉下去。")]

    des6 = N["R-DES-06"]
    des6["blocks"] = [
        P("先前被你魅惑过的男人堵住巷口。雨淋湿他的衣领，他却硬着嗓子说你们“命中注定”。既可怜，又危险。"),
        FOLD(
            "情欲描写",
            "他记得的是你的味道、你腿间的热，以及被丢下后整夜未能发泄的欲火——裤裆可耻地支着，却把那当成爱。",
        ),
    ]
    c = find(des6, "解除并坦白影响")
    c["success"]["result"] = [
        P("你握住银链反向一拧，把话说死：“是我骗了你。那晚不是爱。”他崩溃跪地，随后踉跄离开。"),
        FOLD("情欲描写", "你说得更狠：骗的是他的身体。离开时他裤裆还可耻地支着。"),
    ]
    c["fail"]["result"] = [P("他不听。欲念转成怒火，他扑上来撕你的衣领，短兵相接。")]
    c = find(des6, "再次命令忘掉")
    c["result"] = [
        P("银链再热一分。他眼里的执念熄成空白，连同那晚的记忆一起被抹掉。他茫然走开。腐化加深。"),
        FOLD("情欲描写", "被抹掉的还包括你骑在他身上的画面——只剩潮湿的空白。"),
    ]
    c = find(des6, "交给米拉安置")
    c["result"] = [
        P("你把他交给米拉。她会锁好房间、等他重新想起自己是谁。"),
        FOLD("情欲描写", "他还硬着、说不出完整句子——记得的不是名字，是你腿间的热。"),
    ]
    c = find(des6, "杀死以绝后患")
    c["result"] = [P("短兵相接。你在他扑上来时刺穿他的喉。残酷加深；巷口的雨洗不掉那点未散的腥气。")]

    # ---- Companion hub: ask Liriel to charm a guard
    if "D-ALT" in N:
        for c in N["D-ALT"]["choices"]:
            if c.get("id") != "t2":
                continue
            for s in c.get("sub") or []:
                if "魅惑守卫" in s.get("label", ""):
                    s["result"] = [
                        P("你要莉瑞尔用银链迷倒守卫。她盯着你看了很久，拇指摩过银片。"),
                        P("若守卫危险且另有退路，她会摇头拒绝；你尊重这句拒绝时，她眼里会多一点真的信任。若她照做：守卫跟着进暗巷，她用银链换过路，出来时银链发烫，她不看你。"),
                        FOLD(
                            "情欲描写",
                            "拒绝时她会说：“我可以自己挨刀。别让我再替别人决定他想不想硬着鸡巴跟上来。”"
                            "照做时：声音放软，守卫瞳孔一散；门后是急促的解带声与压抑呻吟。出来时她只丢下一句：“下次你自己骑上去。”",
                        ),
                    ]

    if "D-NPC-MIRA" in N:
        mira_d = N["D-NPC-MIRA"]
        for b in mira_d["blocks"]:
            if "银链放大的是欲望" in b.get("text", ""):
                b["text"] = "“银链放大的是欲望，不只是身体上的亲近。想被爱、想让人别走、想让一句拒绝消失，都是。别恨自己的渴望。盯着你打算让谁替它付账。”"
            if b.get("text", "").startswith("允许一次将强制魅惑") or b.get("text", "").startswith("这句话可当作"):
                b["text"] = "这句话可当作高压侵扰时的锚：把强制魅惑改成坦白，而不是再把别人的渴望点旺。"
        if not any(b.get("t") == "fold" for b in mira_d.get("blocks") or []):
            # Keep surface advisory; fold carries the blunt bedroom framing from the script.
            insert_at = next((i + 1 for i, b in enumerate(mira_d["blocks"]) if "银链放大的是欲望" in b.get("text", "")), len(mira_d["blocks"]))
            mira_d["blocks"].insert(
                insert_at,
                FOLD(
                    "情欲描写",
                    "她说得更直白：想被进入、想叫出声、想把人按在床沿弄到发抖，都可以——"
                    "只要对方还能说停，而你也听得进去。银链最爱的，是把这句话偷走。",
                ),
            )


def companion_liriel_intimacy(N):
    """Edric / Thorin paths: first meeting Liriel, and companion hangouts — foldout desire where chemistry fits."""
    # ---- A1-TOWN-02 first recognition (Edric meets Liriel at the dark table)
    tavern = N.get("A1-TOWN-02")
    if tavern:
        # Flavor when Edric sees her: attraction / silver-chain tension, not forced sex
        for b in tavern["blocks"]:
            if b.get("cond") == {"pc": "edric"} or (isinstance(b.get("cond"), dict) and b.get("cond").get("pc") == "edric"):
                if "莉瑞尔坐在最暗的桌边" in b.get("text", ""):
                    b["text"] = (
                        "莉瑞尔坐在最暗的桌边，与凯尔低声争论是否公开一份旧名单。"
                        "她腕间的银链偶尔反光；你移开视线时，仍觉得那一点凉意像贴上了自己的脉搏。"
                    )
        # Insert fold after edric-specific block if not already present
        has_fold = any(b.get("t") == "fold" and b.get("cond", {}).get("pc") == "edric" for b in tavern["blocks"])
        if not has_fold:
            insert_at = next((i + 1 for i, b in enumerate(tavern["blocks"]) if b.get("cond", {}).get("pc") == "edric"), None)
            if insert_at is not None:
                tavern["blocks"].insert(
                    insert_at,
                    FOLD(
                        "情欲描写",
                        "近看时你才发现她领口下的锁骨被银链磨出浅痕，呼吸略急——像刚压下一阵不该在公共场合发作的热。"
                        "她抬眼掠过你时，那一瞥里有评估，也有一闪而过的、几乎像邀请的湿意。你握紧杯柄，告诉自己那只是烛火。",
                        cond={"pc": "edric"},
                    ),
                )

        t4 = next((c for c in tavern["choices"] if c.get("id") == "t4" or "第一次相认" in c.get("label", "")), None)
        if t4:
            # Keep generic surface; add PC-conditional foldouts for meeting Liriel (edric) or later chemistry notes
            base = [
                P("两个残片容器靠近时，你与对方同时听见低鸣。"),
                P("杯中麦酒泛起四圈波纹。你身上的容器发热；对方也立刻按住了某处衣物。你们对视时，都知道对方看见了同一条不存在的线，正从脚下伸向南方矿区。"),
                {
                    "t": "p",
                    "text": "暗桌边的莉瑞尔抬起眼。银链在她腕间轻轻一跳，像认出了你怀里的旧雨骨。",
                    "cond": {"pc": "edric"},
                },
                FOLD(
                    "情欲描写",
                    "她把手指按在银片上，指节发白——不是怕你，是怕银链把“靠近他”说成命令。"
                    "你闻到雨、麦酒，和她身上一丝被强行压下的甜热。桌下她的膝几乎碰到你的；谁也没有再挪开。"
                    "若你愿意，这一晚本可以只剩呼吸与未说完的邀请；她等你先开口，也等自己还能说不。",
                    cond={"pc": "edric"},
                ),
                {
                    "t": "p",
                    "text": "若暗桌边是莉瑞尔，她看你的眼神会先停在你满是茧的手上，再抬到眼睛：像在估量这双手会不会在该停的时候停。",
                    "cond": {"pc": "thorin"},
                },
                FOLD(
                    "情欲描写",
                    "银链发热时她的呼吸乱了一拍。她低声说：“矮人的规矩我懂——先量，再敲。别让它替我量你。”"
                    "膝在桌下轻轻碰上你的腿甲；她没有躲开。那不是魅惑，是她自己把缝留给你：要或不要，都得你用嘴问。",
                    cond={"pc": "thorin"},
                ),
            ]
            # Don't wipe sub results; only replace parent result
            t4["result"] = base

            # Sub: show container — edric×liriel spark
            for s in t4.get("sub") or []:
                if s.get("id") == "s4c1" or "展示自己的容器" in s.get("label", ""):
                    s["result"] = [
                        P("你把自己的残片放在桌上。对方愣了一下，随即也掏出了自己的。"),
                        {
                            "t": "p",
                            "text": "莉瑞尔的银链与你的容器隔空共鸣，两人都微微抬头，像被同一根弦弹了一下。",
                            "cond": {"pc": "edric"},
                        },
                        FOLD(
                            "情欲描写",
                            "共鸣不只在骨头里。她的瞳孔微微放大，唇线发干；你察觉自己也硬了半分，随即被她一声轻咳打断。"
                            "“别误会，”她低声说，却没有收回手，“它喜欢靠近会发热的东西。我不一定喜欢。”——话里留了缝，也留了退路。",
                            cond={"pc": "edric"},
                        ),
                        FOLD(
                            "情欲描写",
                            "共鸣震得她指尖发麻。她看着你虎口的旧茧，喉咙发紧：“你的锤子认得金属。也认得……人该不该再往下敲。”"
                            "她的另一只手在裙下掐进自己的大腿，压住银链掀起的湿意，直到你把容器收回。",
                            cond={"pc": "thorin"},
                        ),
                    ]
                if s.get("id") == "s4c3" or "提出合作" in s.get("label", ""):
                    s["result"] = [
                        P("“到矿区为止，我们一起走。”对方想了想，点了点头。"),
                        {
                            "t": "p",
                            "text": "莉瑞尔把银链藏进袖口：“一起走可以。别命令我喜欢你。”",
                            "cond": {"pc": "edric"},
                        },
                        FOLD(
                            "情欲描写",
                            "她靠得更近时，袖口里的银链仍在发烫。你听得见她压低的呼吸：“路上若它又发作……你问我，别替我答。”"
                            "那句话把可能发生的交合与绝对不允许的魅惑划开了。",
                            cond={"pc": "edric"},
                        ),
                        FOLD(
                            "情欲描写",
                            "“一起走，”她说，拇指摩过你袖口的铁屑，“夜里若我想要你——我会自己说。你只准用耳朵听，不准用链子听。”"
                            "话音未落，银链还是烫了一下；她骂了一句精灵粗话，把欲念按回齿关。",
                            cond={"pc": "thorin"},
                        ),
                    ]

    # ---- D-ALT Liriel-as-companion: deepen hangouts for Edric & Thorin
    dalt = N.get("D-ALT")
    if not dalt:
        return
    for c in dalt["choices"]:
        if c.get("id") != "t2":
            continue
        # Soften intro when talking to her as companion
        if not any(b.get("t") == "fold" for b in dalt.get("blocks") or []):
            # keep global blocks tame; per-sub handles intimacy
            pass
        for s in c.get("sub") or []:
            lab = s.get("label", "")
            sid = s.get("id", "")
            if "银链在说什么" in lab or sid in ("s2c1", "s2_chain"):
                s["result"] = [
                    P("“它不说。它让我的话听起来像我本来就想说，然后等我责怪它。”莉瑞尔把拇指按在银片上，停了一停。"),
                    FOLD(
                        "情欲描写",
                        "她看着你（无论你是艾德里克还是索林），喉结轻滚：“有时它让我想被按在墙上亲到腿软——然后看我恨不恨自己把愿望说成你的错。”"
                        "银链发热，她却把话说完，没有伸手拉你。边界还在：你可以走，也可以问下一步。",
                    ),
                ]
            elif "坦白苔冠" in lab or "苔冠" in lab or sid in ("s2c2", "s2_truth"):
                s["result"] = [
                    P("你问她愿不愿意亲口说说苔冠的事。她沉默了很久：“等我准备好。”"),
                    FOLD(
                        "情欲描写",
                        "她的指尖在你手腕内侧停了一秒，像试探温度，又像索取一点非银链的安慰。"
                        "“别用身体换我的秘密，”她说，“若哪天我想要你，我会自己说——不是它替我说。”",
                    ),
                ]
            elif "安静地待一会儿" in lab or "刻一个点" in lab or sid in ("s2c4", "s2_quiet"):
                s["result"] = [
                    P("她让你用小刀在银片背面刻一个点。“若它把我的愿望说成命令，你提醒我这是我自己刻的。”"),
                    FOLD(
                        "情欲描写",
                        "刻完时你们的指节相碰。她没有退开，呼吸扫过你的耳际：“今晚到此为止。若你还想……明天再问，问的是我，不是链子。”"
                        "银链不满地凉下去。你记下了那一点未兑现的热——自愿，且可撤回。",
                    ),
                ]
            # charm guard already handled in liriel_desire

        # Add optional once-topic: share a room / acknowledge desire (player-chosen)
        existing_ids = {s.get("id") for s in (c.get("sub") or [])}
        if "s2_desire" not in existing_ids:
            leave_or_end = len(c.get("sub") or [])
            desire = C(
                "s2_desire",
                "承认你们之间的吸引，问她是否愿意更进一步。",
                "__SELF__",
                [
                    P("你把话说清楚：你被她吸引，也看见银链在搅局——你要的是她本人的回答。"),
                    P("莉瑞尔沉默片刻，拇指摩过银片：“今晚可以。摘下它。任何一刻说停，都算数。”"),
                    FOLD(
                        "情欲描写",
                        "门闩落下。她把银链放在杯托上，自己跨坐到你腿上，先吻你的下唇，再引导你的手掌贴上她的腰、乳尖、湿热处。"
                        "进入时她咬住你的肩压住叫声；每一次顶撞都让杯托上的银链轻颤，却插不进你们的呼吸——你们都能说停。"
                        "高潮时她额头顶着你的，汗湿的发黏在颊边。事后她重新戴上银链，声音恢复平静：“这是我选的。记住区别。”",
                    ),
                ],
                [add("rel.liriel", 1), add("time"), setf("liriel_shared_night")],
                once=True,
            )
            c.setdefault("sub", []).insert(max(0, leave_or_end - 0), desire)


# ---------------------------------------------------------------- late-game liriel intimacy folds
def late_liriel_intimacy(N):
    """Mid/late beats where desire or Liriel chemistry is implied but was still summary-only.

    Scripts for A2/A3/END rarely stage full sex scenes; hunger-bone and witness
    moments still need foldouts so later chapters are not left coy beside the
    prologue/desire-pool pass.
    """
    # ---- C-03 charcoal shed: silver-chain lure (combat charm, not mid-sex)
    if "C-03" in N:
        for c in N["C-03"].get("choices") or []:
            lab = c.get("label", "")
            if c.get("id") == "c" or "银链引开" in lab or "用银链" in lab:
                # Always rewrite — combat rebuild may have wiped a prior fold.
                c["result"] = [
                    P("你摸到银链，低声唤住其中一人。他像被线牵着一样转过身，朝你走来，眼神空空的。另一人慌了神，丢下妮芙去拉他。"),
                    FOLD(
                        "情欲描写",
                        "银链把“跟我走”送进他胯骨。他硬着、步子发飘，目光黏在你唇上与领口——不是听懂了命令，是欲火替他做了决定。"
                        "你没有在巷里兑现；刀光起来时，他记得的仍是那一口未吻上的热。",
                    ),
                ]

    # ---- A2-MINE-09: Liriel's unspoken wish — deepen only for her PC
    if "A2-MINE-09" in N:
        n = N["A2-MINE-09"]
        if not any(b.get("t") == "fold" for b in n.get("blocks") or []):
            insert_at = next(
                (i + 1 for i, b in enumerate(n["blocks"]) if "莉瑞尔：希望有人爱她" in b.get("text", "")),
                None,
            )
            if insert_at is not None:
                n["blocks"].insert(
                    insert_at,
                    FOLD(
                        "情欲描写",
                        "画面不只停在“被爱”。你看见自己被按进潮湿被褥，被人进到最深，哭着求对方别停——然后求对方证明：那晚的沉默不是遗弃。"
                        "银链在见证光里发烫，像要把这场交合写成赦免书。你知道那不是爱，是饥渴披着爱的皮。",
                        cond={"pc": "liriel"},
                    ),
                )

    # ---- A2-MINE-07 reunion: three holders; Liriel's chain flares
    if "A2-MINE-07" in N:
        n = N["A2-MINE-07"]
        if not any(b.get("t") == "fold" for b in n.get("blocks") or []):
            n["blocks"].append(
                FOLD(
                    "情欲描写",
                    "三人聚齐时，银链在莉瑞尔腕间猛跳。她咬住下唇压住一声几乎要出口的喘——小腹发紧，腿间一瞬间湿透，像有人在暗处握住了她。"
                    "她看向在场的人，眼里有一瞬恳求：别趁现在问她要不要。问，她怕自己会点头。",
                )
            )

    # ---- A3-SHRINE-06: hunger bone seats — shared desire surge
    if "A3-SHRINE-06" in N:
        n = N["A3-SHRINE-06"]
        if not any(b.get("t") == "fold" for b in n.get("blocks") or []):
            # Insert after the four-bones seating paragraph
            insert_at = next(
                (i + 1 for i, b in enumerate(n["blocks"]) if "银链进入第二槽" in b.get("text", "")),
                None,
            )
            fold = FOLD(
                "情欲描写",
                "饥月骨入槽的一瞬，所有人都尝到彼此最耻的渴望：有人想被按在石环上进入，有人想把唇压上仇敌的喉结，有人只想被抱紧到发抖。"
                "若你是莉瑞尔，银链几乎要替你喊出名字；乳尖与腿根同时发烫，交合的幻象叠在誓环铜光上，又在下一息被裂锤骨的拒绝撕开。"
                "没人在内环真的脱衣——可每个人都知道自己刚才想做什么，也知道别人看见了。",
            )
            if insert_at is not None:
                # Preserve the seating block's cond on the fold
                seat = n["blocks"][insert_at - 1]
                if seat.get("cond"):
                    fold["cond"] = seat["cond"]
                n["blocks"].insert(insert_at, fold)
            else:
                n["blocks"].append(fold)

    # ---- A3-SHRINE-03~2 Liriel oath: abandoning charm — residual body memory
    n = N.get("A3-SHRINE-03~2")
    if n:
        for c in n.get("choices") or []:
            if "放弃银链" in c.get("label", "") or "银链的魅力" in c.get("label", "") or "莉瑞尔" in c.get("label", ""):
                results = [b for b in (c.get("result") or []) if b.get("t") != "fold"]
                if not results:
                    results = [P("你把真相一字不落地说了出来。银链失去了光泽，你也不再替任何人决定该不该原谅。")]
                c["result"] = results + [
                    FOLD(
                        "情欲描写",
                        "放弃魅力不等于欲望消失。你仍记得被进入时的颤、记得有人在你身体里射精时的热；只是银链再也无法把这些记忆锻成命令。"
                        "下一次若还有交合，必须是你自己开口——声音发哑也没关系。",
                    )
                ]

    # ---- END-01 cooling containers: residual intimacy memory for liriel
    if "END-01" in N:
        n = N["END-01"]
        n["blocks"] = [b for b in (n.get("blocks") or []) if b.get("t") != "fold"]
        n["blocks"].append(
            FOLD(
                "情欲描写",
                "银链冷却时，最后散去的不是命令，是体温记忆：谁的手曾按在你腰上，谁在你里面射过，谁在说停之后真的停了。"
                "那些画面留下，却再也推不动别人的腿。你第一次为“只能自己要”松了一口气。",
                cond={"pc": "liriel"},
            )
        )

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
                if b.get("t") == "fold":
                    nested = fix_blocks(b.get("blocks") or [])
                    if not nested and b.get("text"):
                        # legacy single-text fold
                        tb = {"t": "p", "text": b["text"]}
                        nested = fix_blocks([tb])
                    if nested:
                        nb = dict(b)
                        nb["blocks"] = nested
                        nb.pop("text", None)
                        out.append(nb)
                    continue
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
    m = {
        "title": "雾钟城：第七声", "version": "2.2.0-phase2", "node_count": len(N),
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
    try:
        import wzc_revision_pass as _rp
        _rp.patch_meta(m)
    except Exception as e:
        print("revision meta skipped:", e)
    try:
        import wzc_phase1_systems as _p1
        _p1.patch_meta(m)
    except Exception as e:
        print("phase1 meta skipped:", e)
    try:
        import wzc_phase2_pass as _p2
        _p2.patch_meta(m, N)
    except Exception as e:
        print("phase2 meta skipped:", e)
    return m
