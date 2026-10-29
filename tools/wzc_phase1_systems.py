#!/usr/bin/env python3
"""Phase 1 systems pass: deepen shallow Act1 companion beats + fall threshold content.
Mutates public/data/nodes.json + meta.json. Idempotent. Safe with SKIP_PARSE=1.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"

def P(t): return {"t": "p", "text": t}
def SAY(w, t): return {"t": "say", "who": w, "text": t}
def NOTE(t): return {"t": "note", "text": t}
def FOLD(label, *parts, **kw):
    blocks = [P(p) if isinstance(p, str) else p for p in parts]
    out = {"t": "fold", "label": label or "情欲描写", "blocks": blocks}
    if kw.get("cond") is not None: out["cond"] = kw["cond"]
    return out
def add(k, v=1): return {"op": "add", "k": k, "v": v}
def setf(k, v=True): return {"op": "set", "k": k, "v": v}

def find_choice(choices, cid):
    for c in choices or []:
        if c.get("id") == cid: return c
        r = find_choice(c.get("sub"), cid)
        if r: return r
    return None

def replace_or_set_result(c, blocks):
    c["result"] = blocks

SHOW = {
    "t4_ed_show": {
        "who": "莉瑞尔", "fold": "情欲描写",
        "fold_text": (
            "低鸣贴着耻骨走完一圈时，银链烫得她咬住下唇。她没有躲你的视线，只把容器推近半寸："
            "“你听见了。那就别装听不见。我想要什么，它比我嘴诚实——但今晚我还自己说了算。”"
        ),
        "follow": (
            "莉瑞尔把容器收回袖中，声音压得很低：“共享一次低鸣，不等于把命交给你。"
            "东仓或矿区之前，你若再敢把我当货盘点，我就先割你的包。”"
            "她却仍坐着没走——这是一种更危险的信任。"
        ),
    },
    "t4_li_show": {
        "who": "艾德里克", "fold": "残片侵扰",
        "fold_text": (
            "旧雨骨把两人的心跳叠进同一场雨里：泥、血、父亲的背影一闪而过。"
            "艾德里克的指节发白，却没有合上盒盖——他让你看见他最怕被看见的那一秒。"
        ),
        "follow": (
            "艾德里克把铁戒指按回指根：“现在你知道了。别拿同情换情报。"
            "我要妹妹离境的文书。你要什么，一会儿再说。”"
            "他抬眼看你，第一次把你当成能并肩走夜路的人，而不是又一个会卖他的陌生人。"
        ),
    },
    "t4_th_show": {
        "who": "艾德里克", "fold": "残片侵扰",
        "fold_text": (
            "裂锤骨与旧雨骨短促相撞：你想砸开桌沿，他想把雨夜钉死在记忆里。"
            "两人同时吸气，像刚从同一口井里爬出来。"
        ),
        "follow": (
            "艾德里克点了一下头：“矮人的账我听得懂。交货印、古剑、还有不把同伴当耗材——"
            "这些够我们走到矿区。再往后，各凭本事。”"
            "他没有收回容器太快，等于默认你们已经交换过不可外传的秘密。"
        ),
    },
}

ALLY = {
    "t4_ed_ally": [
        P("莉瑞尔考虑片刻，把酒盏转了半圈：“到矿区为止。私人的账，我们各算各的。”"),
        P("她伸出手指在桌面上划了一条线：“线这边是合作。线那边——别假装你懂我的欲望或我的罪。”"),
        FOLD("情欲描写", "划线时她的指尖擦过你手背，银链热了一下。那不是邀请上床，是确认你敢不敢被拒绝。"),
        NOTE("你与莉瑞尔约定同行到矿区。稍后可以再与她深谈。"),
    ],
    "t4_li_ally": [
        P("艾德里克考虑片刻：“到矿区为止。私人的账，我们各算各的。”"),
        P("他补了一句：“我断后，你别为箱子把命留下。妹妹的文书比任何铭文都硬。”"),
        FOLD("残片侵扰", "他说“断后”时，旧雨骨塞给你一张陌生哨兵的脸——你眨掉它，才把同伴认回来。"),
        NOTE("你与艾德里克约定同行到矿区。稍后可以再与他深谈。"),
    ],
    "t4_th_ally": [
        P("艾德里克考虑片刻：“到矿区为止。私人的账，我们各算各的。”"),
        P("他看着你满是茧的手：“你砸门，我掩护。别让怀表替你选人。”"),
        FOLD("残片侵扰", "裂锤骨想把“同盟”理解成“可以砸的名单”。你把拇指按进掌心，直到疼意压过它。"),
        NOTE("你与艾德里克约定同行到矿区。稍后可以再与他深谈。"),
    ],
}

TAKE = {
    "t4_ed_take": [
        P("莉瑞尔的脸色沉下去。她没有拔剑，只把银链绕紧一圈：“你刚才说的是‘交出’，不是‘借用’。”"),
        P("瓦伦咳嗽一声，用空杯敲桌，打断了即将升温的冲突：“两位，外头有耳朵。想杀人，去河沟。”"),
        FOLD("情欲描写", "冲突里银链反而兴奋——她厌恶这种兴奋，厌恶里又有一瞬被看穿的颤栗。她把战栗按回去，眼神更冷。"),
        NOTE("关系恶化。她仍坐在这儿，但信任已经裂开。"),
    ],
    "t4_li_take": [
        P("艾德里克的脸色沉下去。他没有掏弩，只把椅子往后拖了半寸：“再说一次试试。”"),
        P("瓦伦咳嗽一声，打断了即将升温的冲突：“灰桥不欢迎当众抢货。想死自己去东仓。”"),
        FOLD("残片侵扰", "旧雨骨喜欢冲突：它把艾德里克的脸叠成你父亲斥责的侧影。你必须承认——刚才那句“交出”，有一半不是你自己想说的。"),
        NOTE("关系恶化。短期合作变得更贵。"),
    ],
    "t4_th_take": [
        P("艾德里克的脸色沉下去。瓦伦咳嗽一声，打断了即将升温的冲突。"),
        P("索林——不，是你自己——指节已经握白。艾德里克盯着那只手：“把锤子放桌上。我们还没到要互砸的份上。”"),
        FOLD("残片侵扰", "裂锤骨差点替你完成抢夺。你把它按回去时，牙齿打颤。"),
        NOTE("关系恶化。他记住了你想抢容器的那一刻。"),
    ],
}

def patch_show(c, key):
    spec = SHOW[key]
    replace_or_set_result(c, [
        P(f"你把容器放在桌上。{spec['who']}愣了一下，也掏出了自己的。低鸣贴着骨头走了一圈。"),
        FOLD(spec["fold"], spec["fold_text"]),
        P(spec["follow"]),
        NOTE("你们交换了不可外传的秘密（共享残片真相）。此后可选择深谈，而不是停留在这一句。"),
    ])
    eff = c.setdefault("effects", [])
    for fx in [add("rel.alt_a", 1), setf("shared_fragment_truth"), setf("showed_containers"), add("truth", 1)]:
        if not any(e.get("op")==fx["op"] and e.get("k")==fx["k"] and e.get("v")==fx.get("v") for e in eff):
            # truth add might duplicate — allow once
            if fx["k"] == "truth" and any(e.get("k")=="truth" and e.get("op")=="add" for e in eff):
                continue
            eff.append(fx)

def patch_tavern_shallow(N):
    n = N.get("A1-TOWN-02")
    if not n: return
    for key in SHOW:
        c = find_choice(n.get("choices"), key)
        if c: patch_show(c, key)
    for key, blocks in ALLY.items():
        c = find_choice(n.get("choices"), key)
        if c:
            replace_or_set_result(c, blocks)
            if "ed" in key: 
                for fx in [setf("companion_offer_liriel"), setf("shared_fragment_truth")]:
                    if not any(e.get("k")==fx["k"] for e in c.get("effects") or []):
                        c.setdefault("effects", []).append(fx)
            else:
                for fx in [setf("companion_offer_edric"), setf("shared_fragment_truth")]:
                    if not any(e.get("k")==fx["k"] for e in c.get("effects") or []):
                        c.setdefault("effects", []).append(fx)
    for key, blocks in TAKE.items():
        c = find_choice(n.get("choices"), key)
        if c: replace_or_set_result(c, blocks)

    # dossier_here: remove bracket leak, clearer CTA
    c = find_choice(n.get("choices"), "dossier_here")
    if c:
        replace_or_set_result(c, [
            P("你把目光逐一投向在场的人：外貌、脾气、以及目前听来的私情，在脑中短暂排好——像斥候做的那种无声点名。"),
            NOTE("点上方「人物」可展开已结识者的简介。尚未深谈的人，档案只会留下浅浅一笔。"),
        ])

    # Fall >=4 visible consequence on tavern (PC)
    blocks = n.setdefault("blocks", [])
    if not any(b.get("id") == "fall4_tavern" for b in blocks):
        blocks.append({
            "id": "fall4_tavern",
            "t": "note",
            "cond": {"cmp": ["fall", ">=", 4]},
            "text": "沉沦已深：残片开始替你改写酒馆里的每一次对视。压抑它会疼；顺从它会换来更短的路与更贵的自己。",
        })
        blocks.append({
            "id": "fall4_liriel",
            "t": "p",
            "cond": {"all": [{"pc": "liriel"}, {"cmp": ["fall", ">=", 4]}]},
            "text": "角落里有人朝你举杯——不是客人，是托人传话的中间商。他只说：“有位大人愿养‘会发热的人’，吃住与门禁都包。”银链跳了一下。你还没答应。",
        })
        blocks.append({
            "id": "fall4_edric",
            "t": "p",
            "cond": {"all": [{"pc": "edric"}, {"cmp": ["fall", ">=", 4]}]},
            "text": "凯尔把烈酒推到你手边，没问你要不要。旧雨骨喜欢这种预支的放弃：少记一点，明天还能走路——也更可能走丢妹妹的名字。",
        })
        blocks.append({
            "id": "fall4_thorin",
            "t": "p",
            "cond": {"all": [{"pc": "thorin"}, {"cmp": ["fall", ">=", 4]}]},
            "text": "邻桌有人笑得太尖。怀表发烫，你已经在数他的牙齿该从哪一颗开始。瓦伦咳了一声，把你的视线扯回来——再晚半秒，锤子就会离桌。",
        })

    # Optional fall4 choice for liriel PC
    if not find_choice(n.get("choices"), "fall4_patron_hint"):
        n["choices"].append({
            "id": "fall4_patron_hint",
            "label": "听中间商把“饲养”说完（沉沦）。",
            "once": True,
            "cond": {"all": [{"pc": "liriel"}, {"cmp": ["fall", ">=", 4]}]},
            "result": [
                P("中间商把条件讲得很清楚：项圈、开门权、定期“检查发热”。报酬是屋子、药，以及有人在你失控时把门从外面锁上。"),
                FOLD("情欲描写",
                     "他说“检查”时目光落在你锁骨。银链兴奋得发疼。你仍能拒绝——目前如此。拒绝本身让你恶心，也让你确认自己还醒着。"),
                NOTE("邀约已记下。更深的沉沦结局尚未开启（后续章节）。"),
            ],
            "effects": [setf("liriel_patron_offer_seen"), add("fall", 1)],
            "next": "__SELF__",
        })

def patch_stash_actions(N):
    """Make A1-STASH-01 actually offer item moves, not only a bag tip."""
    n = N.get("A1-STASH-01")
    if not n: return
    n["blocks"] = [
        P("储物柜闻起来有湿羊毛和旧油。你最多再塞两件非残片物品——残片容器贴着你，像拒绝被关起来。"),
        P("每存一件，你就轻一分，东仓的敌人也占上风一分。打开「行囊」可精细存取；也可直接用下面的快捷操作。"),
    ]
    # Keep existing done/cancel; prepend quick stash if missing
    choices = n.setdefault("choices", [])
    if not find_choice(choices, "stash_quick_weapon"):
        choices.insert(0, {
            "id": "stash_quick_weapon",
            "label": "试着把一件武器存进柜子。",
            "result": [P("你检查武器格。柜门能否合上，以行囊与存放提示为准。")],
            "effects": [{"op": "stash_slot", "v": "weapon"}],
            "next": "__SELF__",
            "once": True,
        })
        choices.insert(1, {
            "id": "stash_quick_misc",
            "label": "再塞一件护甲或杂物进柜（若有）。",
            "result": [P("你检查杂物格。若没有能存的东西，钥匙仍留在手里。")],
            "effects": [{"op": "stash_slot", "v": "misc"}],
            "next": "__SELF__",
            "once": True,
        })
    for cid, slot in (("stash_quick_weapon", "weapon"), ("stash_quick_misc", "misc")):
        c = find_choice(choices, cid)
        c["effects"] = [{"op": "stash_slot", "v": slot}]
        c["cond"] = {"cmp": ["warehouse_stashed", "<", 2]}
        c["result"] = [P("你检查柜格。是否真的存下物品，以刚才的存放提示为准。")]

def patch_meta(meta):
    meta["stats_help"] = {
        "hp": "体力：归零会进入伤势失败。战斗、压抑残片、强行赶路都会扣它。",
        "vouchers": "商会券：雾钟城流通的记账票据。买通、雇佣、部分情报与疗伤需要它。",
        "resonance": meta.get("resonance_help") or "共鸣：城与钟骨同频的压力。只升不降，升高则侵扰更频。",
        "fall": meta.get("fall_help") or "沉沦：按性格被残片拖深。与“腐化”（支配他人）分开。",
        "power": "战力：武器+护甲+魔具/残片的战力加值，再加上力量或敏捷修正的较高者。战力≥4 时战斗检定占优。",
        "fragment_pressure": "残片压迫：身体层面的催促（耳鸣、发热、误认）。可用意志硬抗，但通常付出血或时间。",
        "truth": "真相：你离长誓钟与服从铭文的实情更近了几步。影响可解锁的终局路径。",
    }
    meta["power_help"] = meta["stats_help"]["power"]
    meta["vouchers_help"] = meta["stats_help"]["vouchers"]
    meta["hp_help"] = meta["stats_help"]["hp"]
    # version stamp for cache bust awareness
    meta["ui_revision"] = "phase1-systems-2026-10-29"
    return meta

def main():
    nodes = json.loads((DATA / "nodes.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    patch_tavern_shallow(nodes)
    patch_stash_actions(nodes)
    patch_meta(meta)
    (DATA / "nodes.json").write_text(json.dumps(nodes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # quick verify
    c = find_choice(nodes["A1-TOWN-02"]["choices"], "t4_li_show")
    assert c and len(c["result"]) >= 3, "show beat not expanded"
    assert "stats_help" in meta
    print("phase1 systems patch ok; t4_li_show blocks=", len(c["result"]))

if __name__ == "__main__":
    main()
