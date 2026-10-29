#!/usr/bin/env python3
"""Phase 2: Act2/3 density, fall endings+epilogues, Liriel mid/late desire, 第七声 theming.

Idempotent. Mutates nodes (+ optionally meta). Safe with SKIP_PARSE=1.
Also callable from wzc_patches.apply after revision_pass.
"""
from __future__ import annotations
import json, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"

def P(t): return {"t": "p", "text": t}
def SAY(w, t, **kw):
    o = {"t": "say", "who": w, "text": t}; o.update(kw); return o
def NOTE(t, **kw):
    o = {"t": "note", "text": t}; o.update(kw); return o
def FOLD(label, *parts, **kw):
    blocks = [P(p) if isinstance(p, str) else p for p in parts]
    out = {"t": "fold", "label": label or "情欲描写", "blocks": blocks}
    if kw.get("cond") is not None: out["cond"] = kw["cond"]
    if kw.get("id"): out["id"] = kw["id"]
    return out
def add(k, v=1): return {"op": "add", "k": k, "v": v}
def setf(k, v=True): return {"op": "set", "k": k, "v": v}
def flag(k): return {"flag": k}
def cmp(k, op, v): return {"cmp": [k, op, v]}
def NOT(c): return {"not": c}
def ANY(*c): return {"any": list(c)}
def ALL(*c): return {"all": list(c)}
def C(cid, label, next=None, result=None, effects=None, **kw):
    c = {"id": cid, "label": label,
         "result": [P(r) if isinstance(r, str) else r for r in (result or [])],
         "effects": effects or [], "next": next}
    c.update(kw)
    return c

def find_choice(choices, cid):
    for c in choices or []:
        if c.get("id") == cid: return c
        r = find_choice(c.get("sub"), cid)
        if r: return r
    return None

def walk_choices(n):
    stack = list(n.get("choices") or [])
    while stack:
        c = stack.pop()
        yield c
        stack.extend(c.get("sub") or [])

def ensure_effect(target, effect):
    effects = target.setdefault("effects", [])
    if not any(e.get("op")==effect.get("op") and e.get("k")==effect.get("k") and e.get("v")==effect.get("v") for e in effects):
        effects.append(effect)

def has_fold_id(blocks, fid):
    for b in blocks or []:
        if b.get("t")=="fold" and b.get("id")==fid: return True
        if has_fold_id(b.get("blocks"), fid): return True
    return False

def has_fold_label(blocks, label):
    for b in blocks or []:
        if b.get("t")=="fold" and b.get("label")==label: return True
        if has_fold_label(b.get("blocks"), label): return True
    return False

def append_unique_block(n, block, key="id"):
    blocks = n.setdefault("blocks", [])
    kid = block.get(key)
    if kid and any(b.get(key)==kid for b in blocks):
        return False
    # also skip identical fold id
    if block.get("t")=="fold" and block.get("id") and has_fold_id(blocks, block["id"]):
        return False
    blocks.append(block)
    return True

def insert_after_first_p(n, block):
    if block.get("id") and has_fold_id(n.get("blocks"), block["id"]):
        return
    if block.get("t")=="fold" and any(b.get("t")=="fold" and b.get("id")==block.get("id") for b in n.get("blocks") or []):
        return
    blocks = n.setdefault("blocks", [])
    # avoid duplicate by id
    if block.get("id") and any(b.get("id")==block.get("id") for b in blocks):
        return
    idx = 0
    for i, b in enumerate(blocks):
        if b.get("t") == "p":
            idx = i + 1
            break
    blocks.insert(idx, block)

# ---------------------------------------------------------------------------
# Fall endings
# ---------------------------------------------------------------------------
FALL_ENDINGS = {
    "END-FALL-LIRIEL": {
        "title": "项圈与饲养",
        "blocks": [
            P("银链不再只是发热——它学会了替你点头。雾钟城上环某宅的无窗厅里，项圈扣上的声音轻得像合上一本账。"),
            P("那位权贵并不粗暴。他要你在许可清单上签字，要你当着仆人的面练习说“停”，然后在你说得出停的时候，仍把你按进垫褥里证明：自愿可以卖得很贵。"),
            FOLD("情欲描写",
                 "白天你穿着得体的袍，夜里他用链环短短一扯，你就会跪下去。交合时他允许你哭、允许你高潮，不允许你忘记自己是被饲养的。"
                 "你仍能拒绝某一次——拒绝会换来更温柔的惩罚：禁闭、禁吻、禁自行抚慰。银链喜欢这种规矩，它把规矩当成爱。"),
            P("同伴的信到不了这间厅。艾德里克的名字变成酒渍；索林的锤子变成传言。你有时还会想起初鸣庭缺席的那一声——真的第七声需要知情、自愿、可撤回；你把“可撤回”卖了，换一口热食与门锁。"),
            NOTE("沉沦结局：莉瑞尔 · 欲望奴隶 / 权贵宠物。后日谈已写入本页。"),
            P("【后日谈】一年后，商会册上多了一条匿名捐赠：孤儿院、矿工遗孀、以及一名曾被你魅惑过的守门兵的医药费。项圈仍在。你学会在许可的缝里藏一点点自己的名字——不够自由，却还没被磨成空白。"),
        ],
    },
    "END-FALL-EDRIC": {
        "title": "酒渍文书",
        "blocks": [
            P("旧雨骨学会了用酒把脸洗模糊。你把妹妹的离境文书压在杯垫下，杯垫湿透了，墨迹渗成一只看不清的眼睛。"),
            P("凯尔不再劝你。瓦伦把账单记在你名下。有人说雾钟城地下敲出了真的第七声，你只抬眼看了看门——门外的雨太像边境那一夜，你选择再倒一杯。"),
            FOLD("残片侵扰",
                 "死者轮流坐到你对面：父亲、哨兵、你没能救下的名字。他们不骂你，只喝酒。你跟着喝，直到记忆变成可支付的税。"),
            P("莉瑞尔的信你读了一半；索林的交货印你揉成团。私人目标没有失败——它被你主动放下，像放下一块太烫的铁。"),
            NOTE("沉沦结局：艾德里克 · 酒溃放弃。后日谈已写入本页。"),
            P("【后日谈】有人在灰桥看见一个像你的醉汉，把一枚空的铁戒指塞进募捐箱。箱子稍后被偷。没有人核对指纹。妹妹最终靠别人的文书离境——那人不是你。"),
        ],
    },
    "END-FALL-THORIN": {
        "title": "裂锤不认人",
        "blocks": [
            P("怀表停在你认定“该砸”的那一秒。矿区、城门、还是同伴的肩——裂锤骨不区分材料，只区分阻力。"),
            P("你砸开了不该砸的闸。血和矿尘糊在一起。有人喊你的名字报数，你听成了挑战。等你喘过气，身边只剩还握得住锤的手。"),
            FOLD("残片侵扰",
                 "暴怒不是热，是一条笔直的线。线上的人都变成“阻碍”。你事后能复述每一次挥击的角度，却复述不出他们临死前叫你什么。"),
            P("自治的旗被人扯下来。托伦笑你可用；帝国通缉你可用。你把自己锻成一把谁都能借的锤——直到没有人敢借。"),
            NOTE("沉沦结局：索林 · 狂怒失控。后日谈已写入本页。"),
            P("【后日谈】西炉区的学徒们改唱一首短谣：锤子认铁不认人。谣传你还活着，在更西的矿脉替人砸门。谣传停在“别报他的名字”。"),
        ],
    },
}

def patch_fall_endings(N):
    for nid, spec in FALL_ENDINGS.items():
        n = N.get(nid)
        if not n:
            N[nid] = {
                "id": nid,
                "title": spec["title"],
                "source": "phase2_fall",
                "kind": "ending",
                "blocks": list(spec["blocks"]),
                "choices": [C("title", "回到标题。", "__TITLE__", [], [])],
                "default_next": None,
                "routes": [],
                "enter_effects": [],
            }
        else:
            n["kind"] = "ending"
            n["title"] = spec["title"]
            n["blocks"] = list(spec["blocks"])
            n["choices"] = [C("title", "回到标题。", "__TITLE__", [], [])]

def patch_fall_routes(N):
    """Wire fall>=6 into CITY-HUB and A3-SHRINE-07."""
    # CITY-HUB collapse offer
    hub = N.get("CITY-HUB")
    if hub and not find_choice(hub.get("choices"), "fall6_collapse"):
        hub["choices"].insert(0, C(
            "fall6_collapse",
            "沉沦已至极限——停下，走进为你准备好的结局。",
            None,
            [P("残片把路收成一条窄缝。你可以继续装成还能选择的人，也可以承认：有些门一旦打开，就只通向同一种结束。"),
             NOTE("这将进入沉沦专属结局。")],
            [],
            once=True,
            cond=cmp("fall", ">=", 6),
            sub=[
                C("fall6_l", "（莉瑞尔）接受项圈与饲养。", "END-FALL-LIRIEL",
                  [P("你点头的时候，银链比你先笑出声。")],
                  [setf("ending", "END-FALL-LIRIEL"), setf("fall_ending", True)],
                  cond={"pc": "liriel"}),
                C("fall6_e", "（艾德里克）把文书压进酒渍里。", "END-FALL-EDRIC",
                  [P("你把杯子举到眼前，世界小成一口烈酒。")],
                  [setf("ending", "END-FALL-EDRIC"), setf("fall_ending", True)],
                  cond={"pc": "edric"}),
                C("fall6_t", "（索林）让锤子决定谁还算人。", "END-FALL-THORIN",
                  [P("怀表的滴答声停了。你听见的是骨裂。")],
                  [setf("ending", "END-FALL-THORIN"), setf("fall_ending", True)],
                  cond={"pc": "thorin"}),
                C("fall6_cancel", "还不到时候。我再撑一撑。", "__SELF__",
                  [P("你把极限按回去。手指在抖。顶栏上的沉沦数字没有退——它只是同意再等你一次。")],
                  [setf("fall6_deferred", True)],
                ),
            ],
        ))

    # A3-SHRINE-07 fall plan
    n7 = N.get("A3-SHRINE-07")
    if n7 and not find_choice(n7.get("choices"), "p_fall"):
        n7["choices"].append(C(
            "p_fall",
            "沉沦终局：让残片替你结束这一切。",
            None,
            [P("誓环上的光照见你眼里已经不是方案，是屈服的形状。真的第七声需要知情自愿可撤回——你现在缺的，正是“可撤回”。")],
            [],
            cond=cmp("fall", ">=", 6),
            sub=[
                C("p_fall_l", "把饥月骨连同自己交进权贵的饲养。", "END-FALL-LIRIEL",
                  [P("你退出内环。外环有人早已在等——项圈在烛光里亮了一下。")],
                  [setf("ending", "END-FALL-LIRIEL"), setf("fall_ending", True)],
                  cond={"pc": "liriel"}),
                C("p_fall_e", "转身去喝酒，不再听任何人的第七声。", "END-FALL-EDRIC",
                  [P("你把容器扔在环边。脚步声比钟声先走远。")],
                  [setf("ending", "END-FALL-EDRIC"), setf("fall_ending", True)],
                  cond={"pc": "edric"}),
                C("p_fall_t", "砸碎还能动的一切，包括劝你的人。", "END-FALL-THORIN",
                  [P("裂锤骨同意了。誓环的铜齿应声而断。")],
                  [setf("ending", "END-FALL-THORIN"), setf("fall_ending", True)],
                  cond={"pc": "thorin"}),
            ],
        ))

    # Foreshadow on A2-MINE-02 when fall>=5
    mine2 = N.get("A2-MINE-02")
    if mine2:
        append_unique_block(mine2, {
            "id": "fall5_mine_note",
            "t": "note",
            "cond": cmp("fall", ">=", 5),
            "text": "沉沦将满：矿尘里的每一次心跳都像倒计时。若你继续顺从残片，初鸣庭之前就会有人为你准备好“不用再选”的结局。",
        })

# ---------------------------------------------------------------------------
# 第七声 theming
# ---------------------------------------------------------------------------
def patch_seventh_voice(N):
    # CITY-08 deepen
    n = N.get("CITY-08")
    if n:
        if not any(b.get("id") == "seventh_city08" for b in n.get("blocks") or []):
            n["blocks"].append(P(
                "钟工压低声音：“六座钟不是坏了，是在给一个空拍让路。有人管那空拍叫第七声。"
                "假的第七声，是塞维兰在誓环背面铸过的服从——听起来齐，其实没人能说不。"
                "真的那种，得是知情、自愿、还能反悔的承诺叠出来的和声。地下若传来一声，你先分清它要你点头，还是问你答不答应。”"
            ))
            n["blocks"][-1]["id"] = "seventh_city08"
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "空拍贴着你的容器骨缝走了一圈。旧雨骨想起未说完的誓；饥月骨把空拍听成喘息；裂锤骨想用一击把六钟砸齐。"
            "你按住它——这一次，按住本身就是在练习“可撤回”。",
            id="fold_city08_frag",
        ))

    # A3-SHRINE-04 reinforce
    n = N.get("A3-SHRINE-04")
    if n and not any(b.get("id") == "seventh_shrine04" for b in n.get("blocks") or []):
        n["blocks"].append({
            "id": "seventh_shrine04",
            "t": "p",
            "text": (
                "记忆最清楚的一帧：第二道誓环背面那行只有塞维兰认得的铭文——用预先录下的赞同伪造第七声。"
                "真的第七声本该是使者当面说出记得什么、想要什么、在何处拒绝；假的那种，是让人根本形不成“不同意”这个念头。"
                "照心骨把两帧叠在一起，像把真假两枚印章按在同一张纸上。"
            ),
        })

    # A3-SHRINE-07 intro reinforce
    n7 = N.get("A3-SHRINE-07")
    if n7 and not any(b.get("id") == "seventh_shrine07" for b in n7.get("blocks") or []):
        n7["blocks"].insert(0, {
            "id": "seventh_shrine07",
            "t": "p",
            "text": (
                "黎明在环上爬行。你听见的不是六座钟，而是那一下一直缺席的拍子——第七声。"
                "你可以试着叠出知情自愿可撤回的和声；也可以接受帝国或残片递来的假齐声；也可以让沉沦替你把选择关死。"
            ),
        })

    # A2-MINE-08
    n = N.get("A2-MINE-08")
    if n and not any(b.get("id") == "seventh_mine08" for b in n.get("blocks") or []):
        append_unique_block(n, {
            "id": "seventh_mine08",
            "t": "p",
            "text": (
                "照心室的回声里有一拍空着。灰袍人说：“山腹记得第七声。它不是多一口钟，是人与人把真话叠齐时多出来的那一下。"
                "你们若只想拿走力量，拿走的会是假的那种。”"
            ),
        })

# ---------------------------------------------------------------------------
# Act2 companion / fragment density
# ---------------------------------------------------------------------------
def patch_act2_mine(N):
    # A2-MINE-02 companion reactions
    n = N.get("A2-MINE-02")
    if n:
        append_unique_block(n, {
            "id": "comp_mine02_edric",
            "t": "say",
            "who": "艾德里克",
            "cond": ALL(NOT({"pc": "edric"}), NOT(flag("alt_edric_dead")), ANY(flag("companion"), cmp("rel.alt_a", ">=", 0))),
            "text": "“先数还能走的人。箱子和铭文都排后面——我见过把人当耗材的账本。”",
        })
        append_unique_block(n, {
            "id": "comp_mine02_liriel",
            "t": "say",
            "who": "莉瑞尔",
            "cond": ALL(NOT({"pc": "liriel"}), NOT(flag("alt_liriel_dead"))),
            "text": "“护卫盯的不是矿工，是井口。谁先眨眼，谁先变成托伦的借口。”银链在她腕间轻轻一跳，她把它按进袖里。",
        })
        append_unique_block(n, {
            "id": "comp_mine02_thorin",
            "t": "say",
            "who": "索林",
            "cond": ALL(NOT({"pc": "thorin"}), NOT(flag("alt_thorin_dead"))),
            "text": "“主轴裂纹我认得。再拖半个时辰，绞盘会吃人。别让我用锤子跟护卫讲理——讲理用扳手。”",
        })
        append_unique_block(n, {
            "id": "absent_mine02",
            "t": "note",
            "cond": ANY(flag("alt_edric_dead"), flag("alt_liriel_dead"), flag("alt_thorin_dead")),
            "text": "你下意识侧过身想对某人说话——空位置风很大。缺席的人不会在矿区突然回来。",
        })
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "矿尘一浓，容器就兴奋。旧雨骨叠上边境死者的工装；饥月骨把护卫的脉搏听成邀请；裂锤骨已在数哪根肋骨先断。"
            "你用舌尖顶住上颚，把幻觉按短——按住也扣体力。",
            id="fold_mine02_frag",
        ))
        # choice: show fragment deepen
        c = find_choice(n.get("choices"), "s2c5") or next((c for c in n.get("choices") or [] if "展示残片" in c.get("label","")), None)
        if c and not any(b.get("t")=="fold" for b in c.get("result") or []):
            c.setdefault("result", []).append(FOLD(
                "残片侵扰",
                "容器离鞘的一瞬，营地里所有人都听见了自己最耻的念头一闪。你把盖子合上，像把第七声的草稿揉掉。",
            ))
            ensure_effect(c, add("truth", 1))

    # A2-MINE-05 who stays — companion aware
    n = N.get("A2-MINE-05")
    if n:
        append_unique_block(n, {
            "id": "seventh_mine05",
            "t": "p",
            "text": "下降前，有人低声问：若下面真有“多出来的一声”，那是救人的和声，还是让人无法拒绝的假齐声？没有人答得完整。",
        })
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "绞盘咯吱时，残片跟着节拍敲你的齿关。你想像把同伴留在上面当耗材——这念头不是你的，可它很完整。你报出同伴的名字压住它。",
            id="fold_mine05_frag",
        ))

    # A2-MINE-07 reunion
    n = N.get("A2-MINE-07")
    if n:
        append_unique_block(n, {
            "id": "comp_mine07_party",
            "t": "p",
            "text": (
                "三面石门合拢前，在场的持有者彼此对视。齐全时，低鸣会短暂齐成接近第七声的轮廓——随即裂开，因为还缺“可撤回”的那一拍。"
                "若有人已死或未至，空位会像缺齿，假齐声更危险。"
            ),
        })
        append_unique_block(n, {
            "id": "absent_mine07",
            "t": "note",
            "cond": ANY(flag("alt_edric_dead"), flag("alt_liriel_dead"), flag("alt_thorin_dead")),
            "text": "石门旁的空位没人填。你们用三声——或两声——往下走，都知道余波会落到缺席者相关的人身上。",
        })
        # Ensure edric/thorin fragment folds too
        if not has_fold_id(n.get("blocks"), "fold_mine07_edric"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "旧雨骨把另两人的脸叠成你没能带出边境的队伍。你抓住门框，直到木头刺进掌心，才把同伴认回来。",
                cond={"pc": "edric"}, id="fold_mine07_edric",
            ))
        if not has_fold_id(n.get("blocks"), "fold_mine07_thorin"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "裂锤骨想一锤砸开三面门“省得磨蹭”。你改去拧自己的拇指关节，疼意盖过砸意。",
                cond={"pc": "thorin"}, id="fold_mine07_thorin",
            ))

    # A2-MINE-09 witness — deepen for all PCs + companion
    n = N.get("A2-MINE-09")
    if n:
        append_unique_block(n, {
            "id": "witness_peer",
            "t": "p",
            "text": "见证不只播你的私欲。若同伴在场，你也会看见他们不肯承认的愿望——以及你曾怎样把代价推到他们身上。",
        })
        if not has_fold_id(n.get("blocks"), "fold_mine09_edric"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "画面里你把文书举得比垂死者的手更高。雨洗不掉这帧。你想关掉，旧雨骨偏把亮度调高。",
                cond={"pc": "edric"}, id="fold_mine09_edric",
            ))
        if not has_fold_id(n.get("blocks"), "fold_mine09_thorin"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "你看见自己砸错的那一闸：水涌出来时，有人喊的是你的名字不是敌号。裂锤骨为之满足。",
                cond={"pc": "thorin"}, id="fold_mine09_thorin",
            ))
        # Liriel desire choice triad on witness
        if not find_choice(n.get("choices"), "mine09_desire_submit"):
            n["choices"].append(C(
                "mine09_desire_submit",
                "（莉瑞尔）让见证把欲望播完——顺从它。",
                "__SELF__",
                [P("你没有挡住那帧。银链烫进皮肤。你承认自己想要被看见、被进入、被证明不是弃物。"),
                 FOLD("情欲描写",
                      "光幕上的交合不再遮掩：汗、齿印、射在小腹上的白浊、说停之后对方真的停住的那一秒。"
                      "你当着山腹哭出来——哭完，沉沦又深一寸。"),
                 NOTE("沉沦 +1。残片压迫上升。")],
                [add("fall", 1), add("fragment_pressure", 1), setf("liriel_witness_submit")],
                once=True,
                cond=ALL({"pc": "liriel"}, cmp("fall", ">=", 0)),
            ))
            n["choices"].append(C(
                "mine09_desire_use",
                "（莉瑞尔）把播出的欲望转化成对在场者的筹码。",
                "__SELF__",
                [P("你擦干眼角，声音发哑：“都看见了。谁敢拿这个要挟我，我就先把你们最耻的愿望当众复述。”"),
                 FOLD("情欲描写",
                      "威胁本身让银链兴奋。你感到腿间一阵湿热——把羞耻锻成武器的快感，几乎比被进入更危险。"),
                 NOTE("沉沦 +1。腐化微升。")],
                [add("fall", 1), add("corruption", 1), setf("liriel_witness_leverage")],
                once=True,
                cond={"pc": "liriel"},
            ))
            n["choices"].append(C(
                "mine09_desire_resist",
                "（莉瑞尔）关掉欲望帧——付出血的代价。",
                "__SELF__",
                [P("你咬破舌尖，用血味盖过热意。光幕暗了一角。鼻子先流出的是血，不是泪。"),
                 FOLD("情欲描写",
                      "未完成的交合幻象抽离时，小腹抽痛，像被从高潮里硬拽出来。你站稳了——仍醒着，也更虚弱。"),
                 NOTE("体力 -2。残片压迫仍在。")],
                [{"op": "hp", "v": -2}, add("fragment_pressure", 1), setf("liriel_witness_resist")],
                once=True,
                cond={"pc": "liriel"},
            ))

    # A2-MINE-10 / 11 companion stakes
    for nid, text in [
        ("A2-MINE-10", "山腹裂开时，谁先被推上救生绳，谁被留作支撑——同伴会记住你的手。缺席者的名字会被活着的人骂出来。"),
        ("A2-MINE-11", "古水道岔口回声很长。有人说这水道连着初鸣庭的排流，连着那一下真假难辨的第七声。"),
    ]:
        n = N.get(nid)
        if n and not any(b.get("id") == f"p2_{nid}" for b in n.get("blocks") or []):
            append_unique_block(n, {"id": f"p2_{nid}", "t": "p", "text": text})

# ---------------------------------------------------------------------------
# Act3 shrine density + absence
# ---------------------------------------------------------------------------
def patch_act3_shrine(N):
    n = N.get("A3-SHRINE-01")
    if n:
        append_unique_block(n, {
            "id": "comp_shrine01_ask",
            "t": "p",
            "text": "问同伴看见什么时，答案按人而异：艾德里克看见雨；莉瑞尔看见未说出口的欲；索林看见该砸与不该砸的界线。若某人已死，幻象会用他的嗓音说话——那是陷阱。",
        })
        # deepen ask companions choice
        c = next((c for c in n.get("choices") or [] if "同伴看见" in c.get("label","")), None)
        if c:
            c["result"] = [
                P("你挨个看向还在场的人。"),
                SAY("艾德里克", "“我看见我没能带走的人。别让幻象用他们的嘴下令。”", cond=ALL(NOT({"pc":"edric"}), NOT(flag("alt_edric_dead")))),
                SAY("莉瑞尔", "“我看见我想要的。我想要的不一定该立刻得到。”银链亮了一下又暗下去。", cond=ALL(NOT({"pc":"liriel"}), NOT(flag("alt_liriel_dead")))),
                SAY("索林", "“我看见该砸的门。也看见不该砸的头。报我的名字，别报敌号。”", cond=ALL(NOT({"pc":"thorin"}), NOT(flag("alt_thorin_dead")))),
                NOTE("若有同伴缺席，对面的幻象会冒充其声——你已被告知那是陷阱。"),
            ]
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "桥下白光每转一圈，残片就试着改写你的下一句台词。按住它像按住即将出口的伪证。",
            id="fold_shrine01_frag",
        ))
        # Liriel private temptation choice
        if not find_choice(n.get("choices"), "shrine01_desire"):
            n["choices"].append(C(
                "shrine01_desire",
                "（莉瑞尔）听幻象把“被需要”说完。",
                "__SELF__",
                [P("塞维兰的幻象换了嗓音，用你最熟的那种低声：“留下来，我让所有人需要你。”"),
                 FOLD("情欲描写",
                      "幻象的手并不存在，却精确按在你腰窝与腿根。你在桥中央湿了——众目之下。你可以顺着喘息点头，也可以把银链攥到掌心出血。"),
                 NOTE("选择后果由你下一步决定；此处先记下诱惑。")],
                [add("fragment_pressure", 1), setf("shrine_desire_tempt_seen")],
                once=True,
                cond={"pc": "liriel"},
                sub=[
                    C("s01_sub", "顺从诱惑，借欲压过恐惧（沉沦）。", "__SELF__",
                      [P("你点了头。热意散开时，桥好像变宽了——代价记在沉沦上。"),
                       FOLD("情欲描写", "幻象满足地退开前，让你感到被进入的错觉高潮。腿软。你仍站着。")],
                      [add("fall", 1)], once=True),
                    C("s01_use", "把诱惑反过来，逼幻象露出破绽。", "__SELF__",
                      [P("你笑了一下：“需要我？先让我看见你的假第七声怎么铸的。”幻象滞了一帧。"),
                       FOLD("情欲描写", "你用尚未褪去的湿意当武器——羞耻变成探针。")],
                      [add("truth", 1), add("fall", 1)], once=True),
                    C("s01_res", "咬破舌尖拒绝。", "__SELF__",
                      [P("血味盖过情欲。幻象皱眉，像被撤回了一记签名。"),
                       NOTE("体力 -1。")],
                      [{"op":"hp","v":-1}], once=True),
                ],
            ))

    # A3-SHRINE-03 oath ring
    n = N.get("A3-SHRINE-03") or N.get("A3-SHRINE-03~2")
    # patch both if exist
    for nid in ("A3-SHRINE-03", "A3-SHRINE-03~2"):
        n = N.get(nid)
        if not n: continue
        if not any(b.get("id") == "seventh_oath" for b in n.get("blocks") or []):
            append_unique_block(n, {
                "id": "seventh_oath",
                "t": "p",
                "text": (
                    "誓环的每一道齿都在问同一件事：你记得什么、想要什么、在何处拒绝。"
                    "答全的人，才有资格参与真的第七声；用魅力或怒火替别人答，都会把和声锻成服从。"
                ),
            })
        # Prefer ~2 interactive oath node; else base node if no ~2
        if nid == "A3-SHRINE-03~2" or (nid == "A3-SHRINE-03" and "A3-SHRINE-03~2" not in N):
            if not find_choice(n.get("choices"), "oath_liriel_hunger"):
                n["choices"].append(C(
                    "oath_liriel_hunger",
                    "（莉瑞尔）在饥月位诚实说出欲望与停词。",
                    "__SELF__",
                    [P("你站在饥月槽前，把想要的事说得很难听，也很清楚；并把停词钉死在铜齿上。"),
                     FOLD("情欲描写",
                          "你说想要被按进石环进入到哭出来——也说若对方不停，你就视为伪造的第七声，有权反击。"
                          "银链既兴奋又害怕：它第一次听见欲望与撤回写在同一句里。"),
                     NOTE("真相 +1。若沉沦已高，诚实本身也会再推你一把。")],
                    [add("truth", 1), setf("liriel_oath_hunger_spoken")],
                    once=True,
                    cond={"pc": "liriel"},
                ))
                # high fall variant consequence
                n["choices"].append(C(
                    "oath_liriel_fall_trade",
                    "（莉瑞尔·沉沦深）请求环外权贵“代管”你的欲望。",
                    "__SELF__",
                    [P("你听见自己说：有人比我更懂怎么锁住发热。银链跳得像在鼓掌。"),
                     FOLD("情欲描写",
                          "你想象项圈、开门权、定期检查——交合被安排进日程。你还没签字，沉沦却先签了。"),
                     NOTE("沉沦 +1。饲养线已接通终局。")],
                    [add("fall", 1), setf("liriel_patron_offer_seen"), setf("liriel_oath_patron_ask")],
                    once=True,
                    cond=ALL({"pc": "liriel"}, cmp("fall", ">=", 4)),
                ))

    # A3-SHRINE-06 seating
    n = N.get("A3-SHRINE-06")
    if n:
        append_unique_block(n, {
            "id": "seventh_seat",
            "t": "p",
            "text": (
                "四枚钟骨入槽时，环心空出一拍。那一拍不是等待塞维兰，是等待你们是否愿意把知情自愿可撤回的承诺叠上去——"
                "叠上去，才是第七声；用命令填满，就是假的那一声。"
            ),
        })
        if not has_fold_id(n.get("blocks"), "fold_shrine06_edric"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "旧雨骨想用死者的赞同填满空拍。你拒绝代替死人点头。",
                cond={"pc": "edric"}, id="fold_shrine06_edric",
            ))
        if not has_fold_id(n.get("blocks"), "fold_shrine06_thorin"):
            n["blocks"].append(FOLD(
                "残片侵扰",
                "裂锤骨想用一击逼所有人齐声。你把锤放下，空拍仍空着——这是你此刻能做的最硬的拒绝。",
                cond={"pc": "thorin"}, id="fold_shrine06_thorin",
            ))

    # A3-SHRINE-08 last words — absence aware already partially; add fall note
    n = N.get("A3-SHRINE-08")
    if n:
        append_unique_block(n, {
            "id": "fall_last_word_note",
            "t": "note",
            "cond": cmp("fall", ">=", 5),
            "text": "沉沦很深的人说话时，残片会抢最后一句。若你听见自己的嗓音比想法更快，那就是假第七声的预习。",
        })

# ---------------------------------------------------------------------------
# City desire + companion density (Liriel mid)
# ---------------------------------------------------------------------------
def patch_city_desire(N):
    # CITY-03 white tower
    n = N.get("CITY-03")
    if n and not find_choice(n.get("choices"), "city03_desire"):
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "白塔的药味里，残片像被冷水激了一下又反扑。按住它时手指发白。",
            id="fold_city03_frag",
        ))
        n["choices"].append(C(
            "city03_desire",
            "（莉瑞尔）在拔除术前，让银链选一个“自愿安抚”的对象。",
            "__SELF__",
            [P("塔侍的目光在你锁骨停住。你知道这是银链在问路。"),
             FOLD("情欲描写",
                  "若你点头，他会在净室帘后用手指与唇安抚到你腿软——自愿、可停、且会被写进沉沦。"
                  "若你拒绝，银链会疼，塔侍会退，故事继续。"),
             NOTE("三选一见子选项。")],
            [],
            once=True,
            cond={"pc": "liriel"},
            sub=[
                C("c03_sub", "接受安抚（沉沦）。", "__SELF__",
                  [P("帘落下。你把停词说清楚，然后任热意把术前的恐惧蒸掉一层。"),
                   FOLD("情欲描写",
                        "他的手指进得很慢，唇按在你小腹。你高潮时咬住自己的腕，不让声音爬上塔阶。事后他洗手，你重新系好银链——链比刚才更服帖，也更沉。")],
                  [add("fall", 1), {"op":"hp","v":1}], once=True),
                C("c03_use", "把安抚变成情报交换。", "__SELF__",
                  [P("你抓住他的领口：“先告诉我拔除术会挖走什么记忆。”他照做了。银链满足于这种交易。"),
                   FOLD("情欲描写", "情报换来的亲吻更冷，也更有效。你让他停在刚好不够释放的地方——控制本身是快感。")],
                  [add("fall", 1), add("truth", 1)], once=True),
                C("c03_res", "拒绝，忍受银链灼痛。", "__SELF__",
                  [P("你说不。塔侍退开。银链烫出一圈红痕。"),
                   NOTE("残片压迫 +1。")],
                  [add("fragment_pressure", 1)], once=True),
            ],
        ))

    # CITY-05 canal
    n = N.get("CITY-05")
    if n and not find_choice(n.get("choices"), "city05_desire"):
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "河渠的湿冷本该压欲，饥月骨却把雾气听成别人的喘息。你盯着契约看，直到字不再扭动。",
            id="fold_city05_frag",
        ))
        n["choices"].append(C(
            "city05_desire",
            "（莉瑞尔）问萨芮：换命是否也能“换欲”。",
            "__SELF__",
            [P("萨芮眯眼：“能。但那不是治疗，是把饥渴写入别人的骨头。我按自愿计价。”"),
             FOLD("情欲描写",
                  "她说计价时尾音发黏。你感到银链跃跃欲试：把欲火塞进罗恩或某个仇人，自己一身轻——"
                  "轻的代价是沉沦与某具身体的终身发热。"),
             NOTE("可用子选项。")],
            [setf("sarei_desire_transfer_known")],
            once=True,
            cond={"pc": "liriel"},
            sub=[
                C("c05_sub", "请她示范一次短暂共欲（沉沦）。", "__SELF__",
                  [P("铜碗相碰。你们共享十息的热。十息后断开，你跪在湿砖上喘。"),
                   FOLD("情欲描写",
                        "那十息里你们几乎在众目下交合——没有插入，却有同步的痉挛与闷哼。断开时两人都湿透。萨芮洗手：“示范结束。要买另算。”")],
                  [add("fall", 1)], once=True),
                C("c05_use", "记下手法，留作对敌人的威胁。", "__SELF__",
                  [P("你付了一张券只买口头说明。知识本身让银链安静片刻。"),
                   NOTE("腐化倾向微升。")],
                  [add("corruption", 1), add("fall", 1)], once=True),
                C("c05_res", "拒绝，回到换命正题。", "__SELF__",
                  [P("你摇头。萨芮居然像松了口气。")],
                  [], once=True),
            ],
        ))

    # CITY-08 already has seventh; add liriel desire listen
    n = N.get("CITY-08")
    if n and not find_choice(n.get("choices"), "city08_desire"):
        n["choices"].append(C(
            "city08_desire",
            "（莉瑞尔）让空拍的第七声从身体里走过一遍。",
            "__SELF__",
            [P("你把银链贴上栏杆。空拍灌进腰眼。"),
             FOLD("情欲描写",
                  "那不是钟声，是一下深顶的错觉。你扶着栏杆高潮前硬生生刹车——停词是你自己喊的。"
                  "真的第七声预演了一半：自愿、可撤回。假的那种不会让你喊停。"),
             NOTE("真相 +1；若继续顺从则沉沦。")],
            [add("truth", 1)],
            once=True,
            cond={"pc": "liriel"},
            sub=[
                C("c08_sub", "不刹车，让空拍做完（沉沦）。", "__SELF__",
                  [P("你没喊停。膝软。钟工假装没看见。"),
                   FOLD("情欲描写", "空拍在你体内收束成一次无伴侣的高潮。你咬住手套，不让声音落入第六声里。")],
                  [add("fall", 1)], once=True),
                C("c08_ok", "记下差别，离开。", "__SELF__",
                  [P("你分清了真假。腿仍在抖，心却更定。")],
                  [], once=True),
            ],
        ))

    # SQ-CITY-02 Varick dinner — patron path
    n = N.get("SQ-CITY-02")
    if n and not find_choice(n.get("choices"), "sq02_patron"):
        insert_after_first_p(n, FOLD(
            "残片侵扰",
            "无窗宅的香料太满。残片把每一种气味都翻译成“留下/拿走/服从”。你数自己的呼吸压过它。",
            id="fold_sq02_frag",
        ))
        n["choices"].append(C(
            "sq02_patron",
            "（莉瑞尔）听瓦瑞克旁敲侧击的“饲养”条件。",
            "__SELF__",
            [P("议员把酒盏一转：“城需要会发热的人被妥善安置。吃住、药、门锁——都可以谈。”"),
             FOLD("情欲描写",
                  "他不说性交，但日程表上的“定期检查”写得很白。你的银链跳了。你可以把它当成终局预告，也可以现在就探路。"),
             NOTE("沉沦线关键。")],
            [setf("liriel_patron_offer_seen")],
            once=True,
            cond=ALL({"pc": "liriel"}, cmp("fall", ">=", 3)),
            sub=[
                C("sq02_accept_talk", "继续听完，不签字（沉沦微升）。", "__SELF__",
                  [P("你听完。没有签字。出门时膝弯仍软。"),
                   FOLD("情欲描写", "他替你披外衣时手指擦过乳侧，像已经在练习所有权。你没躲——也没允。")],
                  [add("fall", 1), setf("liriel_patron_terms_heard")], once=True),
                C("sq02_reject", "当众拒绝。", "__SELF__",
                  [P("你说：我不是畜产。厅里静了一拍。瓦瑞克笑着举杯。"),
                   NOTE("关系变化；银链因拒绝而疼。")],
                  [add("fragment_pressure", 1)], once=True),
                C("sq02_lean", "暗示初鸣庭后再谈——把自己标价。", "__SELF__",
                  [P("你把价码推高：先活过黎明，再谈项圈。他竟认真点头。"),
                   FOLD("情欲描写", "把自身当期货交易让你恶心，也让你兴奋。两种感觉都写进沉沦。")],
                  [add("fall", 1), add("corruption", 1)], once=True),
            ],
        ))

    # SQ-CITY-02~2 action beat
    n2 = N.get("SQ-CITY-02~2")
    if n2 and not find_choice(n2.get("choices"), "sq02b_fall6"):
        n2["choices"].append(C(
            "sq02b_fall6",
            "（沉沦极限）今夜就留下，接受饲养结局。",
            "END-FALL-LIRIEL",
            [P("你把外衣递给仆人。门锁从外面合上的声音，比任何钟都齐。")],
            [setf("ending", "END-FALL-LIRIEL"), setf("fall_ending", True), add("fall", 1)],
            once=True,
            cond=ALL({"pc": "liriel"}, cmp("fall", ">=", 6)),
        ))

    # CITY-HUB companion peer short event
    hub = N.get("CITY-HUB")
    if hub and not find_choice(hub.get("choices"), "peer_city_event"):
        hub["choices"].append(C(
            "peer_city_event",
            "与仍在世的另一位持有者短谈——互为主角，不是差事。",
            "__SELF__",
            [P("街角风很大。你们不谈任务编号，只谈各自残片今晚想让你们变成谁。"),
             FOLD("情欲描写",
                  "若对方是莉瑞尔，银链会在话音间发热；边界与停词仍要当面确认。",
                  cond=ALL(NOT({"pc":"liriel"}), NOT(flag("alt_liriel_dead")))),
             FOLD("残片侵扰",
                  "若对方是艾德里克，雨会无故倾下来一分钟；你们一起等它停。",
                  cond=ALL(NOT({"pc":"edric"}), NOT(flag("alt_edric_dead")))),
             FOLD("残片侵扰",
                  "若对方是索林，他会把锤子横在膝上，要你先报数再说话。",
                  cond=ALL(NOT({"pc":"thorin"}), NOT(flag("alt_thorin_dead")))),
             NOTE(" mutual 关系微调。")],
            [add("rel.alt_a", 1), setf("peer_city_talk")],
            once=True,
        ))

# ---------------------------------------------------------------------------
# Meta / epilogues / version
# ---------------------------------------------------------------------------
def patch_meta(meta, N):
    meta["version"] = "2.2.0-phase2"
    meta["ui_revision"] = "phase2-act23-fall-2026-10-29"
    meta["fall_help"] = (
        "沉沦：残片按性格把你往深处拖（莉瑞尔→欲望奴隶化；艾德里克→酒与放弃；索林→暴怒失控）。"
        "与“腐化”（支配他人）分开。阈值 4 出现可见后果；阈值 6 可进入沉沦专属结局与后日谈。"
    )
    sh = meta.setdefault("stats_help", {})
    sh["fall"] = meta["fall_help"]
    # epilogues: add fall variants at front of each PC list
    epis = meta.setdefault("epilogues", {})
    fall_epis = {
        "liriel": {"label": "沉沦·饲养", "text": "项圈仍在。你在许可的缝里藏自己的名字；真的第七声你只在梦里练习撤回。", "cond": {"flag": "fall_ending"}},
        "edric": {"label": "沉沦·酒渍", "text": "文书化开。雨还在下。你把杯子当作唯一还肯回应的誓约。", "cond": {"flag": "fall_ending"}},
        "thorin": {"label": "沉沦·裂锤", "text": "锤子认铁不认人。有人唱短谣，没有人报你的名。", "cond": {"flag": "fall_ending"}},
    }
    for pc, spec in fall_epis.items():
        lst = epis.setdefault(pc, [])
        if not any(v.get("label") == spec["label"] for v in lst):
            lst.insert(0, spec)
    meta["node_count"] = len(N)
    meta["phase2"] = {
        "fall_endings": list(FALL_ENDINGS.keys()),
        "notes": "Act2/3 density + fall endings + Liriel mid/late desire + 第七声 theming",
    }
    return meta

def apply_to_nodes(N, meta=None):
    patch_fall_endings(N)
    patch_fall_routes(N)
    patch_seventh_voice(N)
    patch_act2_mine(N)
    patch_act3_shrine(N)
    patch_city_desire(N)
    if meta is not None:
        patch_meta(meta, N)
    return N

def main():
    nodes = json.loads((DATA / "nodes.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    # Phase1 first so Phase2 can stamp version/fall_help/ui_revision last
    try:
        import wzc_phase1_systems as p1
        p1.patch_tavern_shallow(nodes)
        p1.patch_stash_actions(nodes)
        p1.patch_meta(meta)
    except Exception as e:
        print("phase1 re-apply skipped:", e)
    apply_to_nodes(nodes, meta)
    (DATA / "nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # verify
    assert "END-FALL-LIRIEL" in nodes
    assert find_choice(nodes["CITY-HUB"]["choices"], "fall6_collapse")
    assert find_choice(nodes["A3-SHRINE-07"]["choices"], "p_fall")
    assert find_choice(nodes["A2-MINE-09"]["choices"], "mine09_desire_submit")
    print("phase2 OK; fall endings + act2/3 density applied; version", meta.get("version"))

if __name__ == "__main__":
    main()
