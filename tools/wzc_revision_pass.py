#!/usr/bin/env python3
"""2026-10-29 design revision pass — mutates nodes.json + meta.json in place.

Safe with SKIP_PARSE=1: does not re-parse scripts. Also importable from wzc_patches.apply.
"""
from __future__ import annotations
import json, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"

# reuse builders if available
try:
    from wzc_patches import P, SAY, FOLD, C, add, setf, item, hp, flag, cmp, NOT, ANY, ALL, branch
except Exception:
    def P(t): return {"t": "p", "text": t}
    def SAY(w, t): return {"t": "say", "who": w, "text": t}
    def FOLD(label, *parts, **kw):
        blocks = [P(p) if isinstance(p, str) else p for p in parts]
        out = {"t": "fold", "label": label or "情欲描写", "blocks": blocks}
        if kw.get("cond") is not None: out["cond"] = kw["cond"]
        return out
    def C(cid, label, next=None, result=None, effects=None, **kw):
        c = {"id": cid, "label": label, "result": [P(r) if isinstance(r, str) else r for r in (result or [])],
             "effects": effects or [], "next": next}; c.update(kw); return c
    def add(k, v=1): return {"op": "add", "k": k, "v": v}
    def setf(k, v=True): return {"op": "set", "k": k, "v": v}
    def item(k, v=True): return {"op": "item", "k": k, "v": v}
    def hp(v): return {"op": "hp", "v": v}
    def flag(k): return {"flag": k}
    def cmp(k, op, v): return {"cmp": [k, op, v]}
    def NOT(c): return {"not": c}
    def ANY(*c): return {"any": list(c)}
    def ALL(*c): return {"all": list(c)}
    def branch(text=None, effects=None, next=None):
        return {"result": [P(t) if isinstance(t, str) else t for t in ([text] if isinstance(text, str) else (text or []))],
                "effects": effects or [], "next": next}


def ensure_effect(c, fx):
    if c is None: return
    eff = c.setdefault("effects", [])
    key = (fx.get("op"), fx.get("k"), fx.get("v"))
    for e in eff:
        if (e.get("op"), e.get("k"), e.get("v")) == key:
            return
    eff.append(fx)


def has_fold(blocks, label=None):
    for b in blocks or []:
        if b.get("t") == "fold" and (label is None or b.get("label") == label):
            return True
    return False


def insert_fold_after_first_p(node, fold):
    blocks = node.setdefault("blocks", [])
    if any(b.get("t") == "fold" and b.get("label") == fold.get("label") for b in blocks):
        # replace existing same-label fold text if empty-ish
        return
    # avoid dup by checking fold label+first text
    key = (fold.get("label"), (fold.get("blocks") or [{}])[0].get("text", "")[:40])
    for b in blocks:
        if b.get("t") == "fold" and b.get("label") == fold.get("label"):
            if (fold.get("blocks") or [{}])[0].get("text", "")[:40] in str(b):
                return
    idx = next((i + 1 for i, b in enumerate(blocks) if b.get("t") in ("p", "say", "inner")), len(blocks))
    blocks.insert(idx, fold)


# ---------- meta ----------
GEAR = {
    "border_sword": {"slot": "weapon", "power": 2, "name": "边防长剑"},
    "hand_crossbow": {"slot": "weapon", "power": 2, "name": "手弩"},
    "elf_rapier": {"slot": "weapon", "power": 2, "name": "精灵细剑"},
    "old_hammer": {"slot": "weapon", "power": 3, "name": "旧锤"},
    "rune_pick": {"slot": "weapon", "power": 2, "name": "符文镐"},
    "reinforced_leather": {"slot": "armor", "power": 1, "dr": 2, "name": "强化皮甲"},
    "travel_clothes": {"slot": "armor", "power": 0, "dr": 0, "name": "旅行布袍"},
    "smith_apron": {"slot": "armor", "power": 1, "dr": 1, "name": "铁匠围裙"},
    "shadow_leather": {"slot": "armor", "power": 1, "dr": 2, "name": "暗影皮甲"},
    "desire_chain": {"slot": "magic", "power": 1, "name": "银链（饥月骨）"},
    "memory_ring": {"slot": "magic", "power": 1, "name": "铁戒指（旧雨骨）"},
    "anger_watch": {"slot": "magic", "power": 1, "name": "怀表（裂锤骨）"},
    "chalk": {"slot": "magic", "power": 0, "name": "粉笔"},
}

DOSSIERS = {
    "valen": {
        "name": "“银舌”瓦伦",
        "appear": "四十出头，笑脸常挂，袖口却总留着墨渍。三只空杯像替没来的人占座。",
        "personality": "把情报当货卖；真疼的只有失踪的女儿艾拉。",
        "history0": "灰桥消息贩子。你只知道他什么都肯谈——只要你付得起。",
        "history1": "他要的不是钱，是米拉十年前送走的女孩下落。",
        "history2": "艾拉改名阿莱娅，曾从帝国押运车逃出；瓦伦仍不敢相信自己配相认。",
    },
    "ysolde": {
        "name": "伊索尔",
        "appear": "五十岁上下，发丝被墨水染黑几绺，书墙把火炉隔成她的领地。",
        "personality": "把一切当成可记录的样本；拒绝时她反而更尊重你。",
        "history0": "自称中立学者，对你的残片容器兴趣大于对你本人。",
        "history1": "她承认长誓钟七骨只是禁书假说之一，却已开始为你描摹铭文。",
        "history2": "灰衣信使的死与她安排的偷窃有关；她称之为“低估风险”。",
    },
    "mira": {
        "name": "米拉",
        "appear": "四十二岁，妆只画一半，钥匙串从不离手。",
        "personality": "欲望不是罪，拿走别人的回答才是。庇护矿工家属比接客优先。",
        "history0": "红牡丹的主人，先问你是求庇护、卖消息还是找麻烦。",
        "history1": "她组织排水渠撤人，也藏着艾拉的去向。",
        "history2": "她一眼能看出银链的热，也拒绝为你找“不会说不的人”。",
    },
    "eilyn": {
        "name": "艾琳修女",
        "appear": "灰烛礼拜堂，烟熏黑镜前缝伤口的女人，眼睛比烛火更冷。",
        "personality": "先救人再问立场；教会的“净化”让她私藏灰瓶。",
        "history0": "今夜镜前躺着商队与矿工的伤员。",
        "history1": "她用灰试过你的容器，并说出塞维兰残缺的名字。",
        "history2": "她把三年前的秘密记录托你带给受害者家属。",
    },
    "edric": {
        "name": "艾德里克",
        "appear": "边境斥候的瘦高个子，斗篷边总沾着泥，木梳一类的小物件藏得很紧。",
        "personality": "话少，观察多；保护妹妹的离境比任何大义都硬。",
        "history0": "未选他时，他会作为持有旧雨骨的同伴出现。",
        "history1": "戒指逼他看见父亲的雨夜；他既怕忘记，也怕再经历一次。",
        "history2": "若沉沦加深，他会借酒把责任推开，连家人的名字都懒得再提。",
    },
    "liriel": {
        "name": "莉瑞尔",
        "appear": "半精灵流亡者，银链贴腕，领口下锁骨常有浅痕。",
        "personality": "锋利自嘲，身体比嘴诚实；最恨别人替她决定“该不该想要”。",
        "history0": "未选她时，她带着饥月骨与苔冠旧案的阴影进场。",
        "history1": "银链放大欲望，也放大“被需要就证明自己还配活”的执念。",
        "history2": "沉沦高时，她可能把同意偷换成命令，或把自己交进权贵的饲养。",
    },
    "thorin": {
        "name": "索林",
        "appear": "矮人工匠，虎口满茧，怀表链常绕在腰带上。",
        "personality": "重承诺、厌空话；怒气来时像炉火失控。",
        "history0": "未选他时，他为交货印与古剑修理被卷进共鸣。",
        "history1": "裂锤骨让他有权说“不”，也诱他砸错对象。",
        "history2": "沉沦高时暴怒成性，同伴会先护住自己的头，再听他说话。",
    },
    "kael": {
        "name": "凯尔",
        "appear": "宽肩、油渍围裙，柜台后永远擦着同一只杯子。",
        "personality": "嘴硬心软；认得每一个常客的沉默。",
        "history0": "灰桥旅人酒馆的老板。你刚踏进门他就用下巴点了点空位。",
        "history1": "他默许瓦伦在角落做情报买卖，自己抽成极少。",
        "history2": "他见过太多残片持有者——多数没有活着走出这座城。",
    },
    "mara": {
        "name": "玛拉",
        "appear": "皮手套、铜扣、笑里藏刀的短发女人。",
        "personality": "一切皆可议价；翻脸比翻账本更快。",
        "history0": "东仓区的商会面孔。她递来的不是善意，是合同。",
        "history1": "她要你去抄仓库，名义是“清理异常回声”。",
        "history2": "商会要的是残片容器的流向，不是你的命——除非你挡路。",
    },
    "garrick": {
        "name": "加里克",
        "appear": "铁盔压眉，嗓子像砂纸。",
        "personality": "规章高于人情；偶尔会为“省事”放一马。",
        "history0": "城门与仓区巡逻的伍长。",
        "history1": "他收过商会的“加班费”，对异常钟鸣装聋。",
        "history2": "若警报拉响，他会第一个封锁街口。",
    },
    "gromm": {
        "name": "格罗姆",
        "appear": "冷炉前的老矮人，门上写着“只修工具，不修英雄”。",
        "personality": "固执、耻于英雄叙事；弟弟死于服从铭文。",
        "history0": "灰桥钟楼后的铺子。",
        "history1": "他参与过誓环复制件，如今只肯把工具交给承诺封存的人。",
        "history2": "他能拓出旧雨、饥月、裂锤、照心的古称。",
    },
}


def patch_meta(meta):
    meta["gear"] = GEAR
    meta["dossiers"] = DOSSIERS
    meta["resonance_help"] = (
        "共鸣：雾钟城水道与钟楼对你体内钟骨的同频压力。"
        "升高会让残片侵扰更频、逼近不可逆的连接；等待不会降低它。"
        "治疗与沉沦都不能免费清零倒计时。"
    )
    meta["fall_help"] = (
        "沉沦：残片按你的性格把你往深处拖。"
        "莉瑞尔偏欲望奴隶化；艾德里克偏消极借酒；索林偏暴怒滥伤。"
        "与“腐化”（借残片支配他人）分开计算。"
    )
    # default armor names already in carried; map starting armor into characters
    for pc, armor in (("edric", "reinforced_leather"), ("liriel", "travel_clothes"), ("thorin", "smith_apron")):
        ch = meta["characters"][pc]
        ch["armor"] = armor
        if armor not in meta.get("item_names", {}):
            meta.setdefault("item_names", {})[armor] = GEAR[armor]["name"]
        # ensure storage list preserved
    meta["item_names"] = meta.get("item_names") or {}
    for k, g in GEAR.items():
        meta["item_names"].setdefault(k, g["name"])
    meta["version"] = "2.1.0-revision"
    return meta


# ---------- fragment folds for all three ----------
MEM_FOLDS = {
    "R-MEM-01": ("残片侵扰",
        "雨披一晃，你听见当年军靴踏泥的节奏。戒指在胸口烫得像第二颗心脏："
        "追上他，问他为什么不回头；追上他，就能改写那封从未寄到的家书。"
        "理智知道那是错认，旧雨骨却把“差一点就能听见”按进你的牙关。"),
    "R-MEM-02": ("残片侵扰",
        "木梳缺齿的断面在指腹反复放大。戒指坚持：那是父亲离家夜你哭断的；"
        "你清楚它去年才断。两套记忆叠在一起，像有人把你的童年重新排版，还要求你签字画押。"),
    "R-MEM-03": ("残片侵扰",
        "街角的笑声忽然变成妹妹的咳嗽。你眨一下眼，人还是陌生人，嗓子却已经发紧。"
        "旧雨骨不给你整段故事，只塞给你最痛的那一帧，逼你用行动把它续完。"),
    "R-MEM-04": ("残片侵扰",
        "你闻到家里炉灰的味道——这座城里根本没有那只炉。戒指让过去的房间叠在现在的石板上，"
        "每走一步都像踩进已经塌掉的地板。"),
    "R-MEM-05": ("残片侵扰",
        "死者的名字在舌尖排队。你没有见过他们全部，旧雨骨却记得。压制它像按住一口即将喷发的井。"),
    "R-MEM-06": ("残片侵扰",
        "你短暂相信自己已经死在北路那一夜，此刻只是记忆的回放。醒来时指甲陷进掌心，血是热的，证明你还活着——也证明残片还能再骗你一次。"),
}

ANG_FOLDS = {
    "R-ANG-01": ("残片侵扰",
        "怀表每响一下，你就听见柜台被砸裂的声响预演。不是比喻——手臂里的热铁在找落点。"
        "裂锤骨低语：价格不公就该改形状；改形状最快的方法，是锤子。"),
    "R-ANG-02": ("残片侵扰",
        "军官的后脑成为最清晰的靶心。怀表滴答变成擂鼓：拖出去、按下去、让队伍恢复“正确”。"
        "你知道那会变成暴行，怒意却把“正确”两个字焊在喉头。"),
    "R-ANG-03": ("残片侵扰",
        "拖延的每一秒都像有人用钝锉磨你的牙。裂锤骨把等待翻译成羞辱，再催你向人动手。"),
    "R-ANG-04": ("残片侵扰",
        "谎言的气味比炉烟更冲。你想像验铁一样验这张嘴——敲碎，看里面是不是空的。"),
    "R-ANG-05": ("残片侵扰",
        "马匹受惊、人声嘈杂。怀表要你一锤定音：谁挡路谁就该让开，骨头也一样。"),
    "R-ANG-06": ("残片侵扰",
        "怒意退潮后留下耳鸣。你看见自己刚才举锤的角度——再偏一寸就是人命。裂锤骨对此毫不在乎。"),
}

DES_FALL = {
    # choice id substrings that should add fall for liriel
}


def patch_fragment_events(N):
    for nid, (label, text) in MEM_FOLDS.items():
        if nid not in N: continue
        insert_fold_after_first_p(N[nid], FOLD(label, text))
        # fall on surrender-ish choices
        for c in N[nid].get("choices") or []:
            lab = c.get("label", "")
            if any(x in lab for x in ("追上去", "相信戒指", "借戒指", "沉进", "任由")):
                ensure_effect(c, add("fall", 1))
            if any(x in lab for x in ("不追", "坚持真实", "说出", "按住", "抗拒")):
                ensure_effect(c, add("fragment_resisted", 1))
            # ensure some result text
            if not c.get("result"):
                c["result"] = [P("你处理完这次闪回。旧雨骨仍在发热，只是暂时安静了半寸。")]

    for nid, (label, text) in ANG_FOLDS.items():
        if nid not in N: continue
        insert_fold_after_first_p(N[nid], FOLD(label, text))
        for c in N[nid].get("choices") or []:
            lab = c.get("label", "")
            if any(x in lab for x in ("砸", "拖出", "怒势", "动手", "吼", "打")):
                ensure_effect(c, add("fall", 1))
            if not c.get("result"):
                c["result"] = [P("怒意退了一寸。怀表的滴答仍在，像提醒你下一次还会再来。")]

    # R-DES already has some folds; ensure fall on submit/corrupt paths + fill R-DES-02
    for nid in [f"R-DES-0{i}" for i in range(1, 7)]:
        if nid not in N: continue
        n = N[nid]
        if nid == "R-DES-02" and not has_fold(n.get("blocks")):
            insert_fold_after_first_p(n, FOLD(
                "情欲描写",
                "镜中的脸更湿、更软，唇色像刚被人吻过。银链要你相信：只要成为那张脸，就会有人硬着进来、求你别停。"
                "热意贴着腿根往上爬；你得决定是伸手进衣襟顺从它，还是把镜子拧开。",
            ))
        for c in n.get("choices") or []:
            lab = c.get("label", "")
            if any(x in lab for x in ("顺从", "留下", "亲近", "接受", "跟", "利用银链", "确保", "不会拒绝", "沉沦")):
                ensure_effect(c, add("fall", 1))
            if "利用" in lab or "不会拒绝" in lab or "确保对方" in lab:
                ensure_effect(c, add("fall", 1))  # extra
            if not c.get("result"):
                c["result"] = [P("银链的热退了些。你知道它只是改用更慢的方式等你下一次松手。")]


def patch_prologue_folds(N):
    # Edric first fragment moments
    if "E-PRO-03" in N:
        insert_fold_after_first_p(N["E-PRO-03"], FOLD(
            "残片侵扰",
            "戒指第一次真正咬住你时，北路的雨忽然变成多年前的雨。"
            "父亲的背影在货车一侧闪过，靴印与今天重叠。你尝到铁锈与钟油——明明战场上没有钟。"
            "旧雨骨不问你愿不愿意记得，它只把记忆灌进血管，再看你会不会跟着跑。",
            cond={"pc": "edric"},
        ))
    if "E-PRO-07" in N:
        insert_fold_after_first_p(N["E-PRO-07"], FOLD(
            "残片侵扰",
            "进城前的最后一阵晕眩里，你看见妹妹在炉边削木勺，又看见她变成伤员名单上的一行字。"
            "你扶着桥栏吐出一口带血的唾沫：残片在教你用最坏的结局预演活着。",
        ))
    # Thorin
    if "T-PRO-05" in N:
        insert_fold_after_first_p(N["T-PRO-05"], FOLD(
            "残片侵扰",
            "怀表盖弹开的瞬间，世界缩成可敲打的表面：坏轮、假印、赫尔嘉的嘴。"
            "力量热得发疼，像锻炉从肋骨里点燃。裂锤骨说：打断它，形状就会听话。"
            "你的手指已经在找锤柄——还没决定砸谁，肌肉先同意了。",
        ))
        for c in N["T-PRO-05"].get("choices") or []:
            if any(x in c.get("label", "") for x in ("砸烂", "吼出", "对准")):
                ensure_effect(c, add("fall", 1))
    if "T-PRO-03" in N:
        insert_fold_after_first_p(N["T-PRO-03"], FOLD(
            "残片侵扰",
            "工棚里的每一次拖延都让齿轮声变尖。你看见自己把私兵的头盔砸进炉门——画面清晰得可耻。",
        ))
    # Liriel L-PRO-07 fall
    if "L-PRO-07" in N:
        for c in N["L-PRO-07"].get("choices") or []:
            lab = c.get("label", "")
            if "亲近" in lab or "利用银链" in lab:
                ensure_effect(c, add("fall", 1))
            if "利用银链" in lab:
                ensure_effect(c, add("fall", 1))


# ---------- tavern ----------
ALT_LABEL = {
    "edric": ("liriel", "莉瑞尔", "与莉瑞尔：第一次相认"),
    "liriel": ("edric", "艾德里克", "与艾德里克：第一次相认"),
    "thorin": ("edric", "艾德里克", "与艾德里克：第一次相认"),
}


def patch_tavern(N):
    n = N.get("A1-TOWN-02")
    if not n: return
    # Fix recognition choice into three PC-conditional choices
    choices = n.get("choices") or []
    choices = [c for c in choices if c.get("id") not in {"t4_th_l", "dossier_here"} and not (c.get("id") == "t4" or "第一次相认" in c.get("label", "") or "另一位主角" in c.get("label", ""))]

    def recog(cid, pc, other_id, other_name, label):
        return C(
            cid, label, "__SELF__",
            result=[
                P(f"两个残片容器靠近时，你与{other_name}同时听见低鸣。"),
                P("杯中麦酒泛起四圈波纹。你身上的容器发热；对方也立刻按住了某处衣物。"
                  "你们对视时，都知道对方看见了同一条不存在的线，正从脚下伸向南方——以及更远的、缺了一声的钟。"),
                FOLD(
                    "情欲描写" if other_id == "liriel" else "残片侵扰",
                    (
                        f"近在咫尺时，{other_name}腕间银链轻跳。热意不是命令，是提问：你要不要承认自己也想靠近。"
                        "桌下膝碰膝；她等你先开口，也等自己还能说不。"
                        if other_id == "liriel" else
                        f"{other_name}按住胸口的戒指，呼吸乱了一拍。旧雨骨把你的脸叠进某段不该属于他的记忆；"
                        "他低声说：“别让它替我们互相介绍。我们自己说。”"
                        if other_id == "edric" else
                        f"{other_name}的怀表滴答骤然变重。怒意扫过又收住——他认的是容器，不是敌人。"
                    ),
                    cond={"pc": pc},
                ) if other_id in ("liriel", "edric") else P(f"{other_name}看着你，点了点头。"),
            ],
            effects=[add(f"rel.{ 'alt_a' }", 1), setf("shared_fragment_truth"), setf(f"met_{other_id}"), setf(f"talked_{other_id}"), setf("met_alt")],
            once=True, cond={"pc": pc},
            sub=[
                C(f"{cid}_show", "直接展示自己的容器。", "__SELF__",
                  [P(f"你把容器放在桌上。{other_name}愣了一下，也掏出了自己的。低鸣贴着骨头走了一圈。")],
                  [add(f"rel.alt_a", 1), setf("shared_fragment_truth")]),
                C(f"{cid}_watch", "假装无事，观察对方。", "__SELF__",
                  [P(f"你按住容器，目光却没离开{other_name}的手。对方同样在估量你。")],
                  [], check={"stats": ["INS"], "dc": 13},
                  success=branch(f"你看清了{other_name}藏容器的位置。", [setf(f"knows_{other_id}_fragment")]),
                  fail=branch(f"{other_name}察觉你在撒谎，眼神冷了一寸。", [add("rel.alt_a", -1)])),
                C(f"{cid}_ally", "提出合作到矿区为止。", "__SELF__",
                  [P(f"{other_name}考虑片刻：“到矿区为止。私人的账，我们各算各的。”")],
                  [add("rel.alt_a", 1), setf("companion_offer_" + other_id)]),
                C(f"{cid}_take", "要求对方交出容器。", "__SELF__",
                  [P(f"{other_name}的脸色沉下去。瓦伦咳嗽一声，打断了即将升温的冲突。")],
                  [add("rel.alt_a", -2), add("cruelty", 1)]),
            ],
        )

    new_recog = [
        recog("t4_ed", "edric", "liriel", "莉瑞尔", "与莉瑞尔：第一次相认"),
        recog("t4_li", "liriel", "edric", "艾德里克", "与艾德里克：第一次相认"),
        recog("t4_th", "thorin", "edric", "艾德里克", "与艾德里克：第一次相认"),
        # thorin can also meet liriel later at gromm; add optional if wanted:
        C("t4_th_l", "与莉瑞尔：在暗桌旁点头致意", "__SELF__",
          [P("莉瑞尔抬眼扫过你满是茧的手，又落到眼睛上。银链轻响。你们没有深谈，却都知道彼此不是普通人。"),
           FOLD("情欲描写", "她的呼吸乱了一拍，低声说：“矮人的规矩我懂——先量，再敲。别让它替我量你。”膝在桌下轻轻碰上你的腿甲。", cond={"pc": "thorin"})],
          [setf("met_liriel"), add("rel.alt_b", 1)], once=True, cond={"pc": "thorin"}),
    ]

    # Fix Valen / Ysolde parent feedback + met flags; fix empty sub results
    for c in choices:
        if c.get("id") == "t1" or "与瓦伦" in c.get("label", ""):
            c["label"] = "与瓦伦：一条消息的价格"
            c["once"] = True
            ensure_effect(c, setf("met_valen"))
            ensure_effect(c, setf("talked_valen"))
            if not c.get("result"):
                c["result"] = [P("你在瓦伦的空杯对面坐下。他笑着等你开价。")]
            for s in c.get("sub") or []:
                ensure_effect(s, setf("met_valen"))
                if not s.get("result"):
                    s["result"] = [P("瓦伦把情报像货物一样推过桌面。你记下了东仓、口令，以及他眼里那一点真的疼。")]
                # fall not relevant
        if c.get("id") == "t3" or "与伊索尔" in c.get("label", ""):
            c["label"] = "与伊索尔：知识不等于中立"
            c["once"] = True
            ensure_effect(c, setf("met_ysolde"))
            ensure_effect(c, setf("talked_ysolde"))
            ensure_effect(c, setf("dossier_ysolde_depth", 1))
            if not c.get("result"):
                c["result"] = [P("伊索尔放下笔：“它有没有让你想做一件本来就想做、但不肯承认的事？”")]
            for s in c.get("sub") or []:
                ensure_effect(s, setf("met_ysolde"))
                ensure_effect(s, setf("talked_ysolde"))
                if not s.get("result"):
                    s["result"] = [P("伊索尔记下你的回答。她没有安慰你，只把一张描摹纸推过来——或把盐包按进你掌心。")]

    # Gate talk_* first-greet style: only after met, and dialogue nodes should skip t1 if talked
    for c in choices:
        if c.get("id") == "talk_D-NPC-VALEN":
            c["cond"] = flag("met_valen")
            c["label"] = "再找瓦伦多聊几句。"
            if not c.get("result"):
                c["result"] = [P("你再次在瓦伦桌边坐下。他已经不等你自我介绍。")]
        if c.get("id") == "talk_D-NPC-YSOLDE":
            c["cond"] = flag("met_ysolde")
            c["label"] = "再找伊索尔核对笔记。"
            if not c.get("result"):
                c["result"] = [P("伊索尔头也不抬：“你回来了。先说症状有没有变。”——没有寒暄。")]
        if c.get("id") == "talk_D-ALT":
            c["label"] = "与另一位残片持有者深谈。"
            c["cond"] = ANY(
                ALL(NOT({"pc": "edric"}), flag("met_edric"), NOT(flag("alt_edric_dead"))),
                ALL(NOT({"pc": "liriel"}), flag("met_liriel"), NOT(flag("alt_liriel_dead"))),
                ALL(NOT({"pc": "thorin"}), flag("met_thorin"), NOT(flag("alt_thorin_dead"))),
            )
            if not c.get("result"):
                c["result"] = [P("你们找了个不太吵的角落。这一次不是相认，是算账——彼此的目标、底线，以及残片正在如何改写你们。")]
        if c.get("id") == "talk_D-NPC-KAEL":
            if not c.get("result"):
                c["result"] = [P("凯尔把弓放在膝上，等你把话说清楚。")]

    # Add dossier peek choice
    choices.append(C(
        "dossier_here", "打量在场的人（人物简介）。", "__SELF__",
        [P("你把目光逐一投向在场的人。你记得的外貌、脾气，以及目前听来的私情，在脑中短暂排好——像斥候做的那种无声点名。"),
         P("点上方「人物」可查看已结识者的简介。若尚未深谈，档案只会留下浅浅一笔。")],
        [setf("hint_dossier_ui")], once=False,
    ))

    n["choices"] = new_recog + choices

    # Gate D-NPC first greet topics
    for nid, metflag, first_ids in [
        ("D-NPC-VALEN", "met_valen", ["t1"]),
        ("D-NPC-YSOLDE", "met_ysolde", ["t1"]),
    ]:
        d = N.get(nid)
        if not d: continue
        for c in d.get("choices") or []:
            if c.get("id") == "t1":
                key = "talked_valen" if "VALEN" in nid else "talked_ysolde"
                c["cond"] = NOT(flag(key))
                # if somehow shown, rewrite
                c["label"] = "初见寒暄" if "VALEN" in nid else "初见：研究伦理之外的寒暄"


def patch_warehouse(N):
    n = N.get("A1-TOWN-08")
    if not n: return
    n["blocks"] = [
        P("钟楼敲九下。第九声没有停，低沉余音沿石板路向南滚去。杯子、门锁、武器护手同时轻响。"),
        P("你的残片容器发烫。画面不是预言：东仓里，托伦的买手与灰手抄写员正把三样东西往黑篷车上扔——"
          "铅皮匣的线索、十年前的旧档、矿工名单。黎明帝国要封井；他们要在封井前抢走“西边深层与第七声同时有回应”的证据。"
          "账本被浇上炼金盐，火光发蓝——既是灭口，也是掩护。"),
        FOLD(
            "残片侵扰",
            "容器烫得像要烙穿皮肉。旧雨/饥月/裂锤各自用你听得懂的方式催促："
            "追上去、占有那份名单、砸开挡路的门。鼻血或耳鸣随之而来——第一幕的异常不再是氛围，而是身体在报警。",
        ),
        P("抵达仓库前，你只能做一件准备。"),
    ]
    n["choices"] = [
        C("prep_comp", "召集一个同伴。", None,
          [P("你在脑中点名：谁还活着、谁肯为你挡一刀、谁此刻离东仓最近。")],
          [setf("warehouse_prep", "companion")],
          sub=[
            C("comp_ed", "叫上艾德里克。", "A1-TOWN-09",
              [P("艾德里克点头，检查弩机：“我断后。别为箱子把命留下。”")],
              [setf("companion", "edric"), setf("warehouse_companion", "edric"), {"op": "adv", "k": "*"}],
              cond=ALL(NOT({"pc": "edric"}), NOT(flag("alt_edric_dead")))),
            C("comp_li", "叫上莉瑞尔。", "A1-TOWN-09",
              [P("莉瑞尔把银链按进袖中：“我开路。别要求我让守卫‘自愿’——除非你也敢听拒绝。”")],
              [setf("companion", "liriel"), setf("warehouse_companion", "liriel"), {"op": "adv", "k": "*"}],
              cond=ALL(NOT({"pc": "liriel"}), NOT(flag("alt_liriel_dead")))),
            C("comp_th", "叫上索林。", "A1-TOWN-09",
              [P("索林掂了掂锤子：“门我来。人你们捞。”")],
              [setf("companion", "thorin"), setf("warehouse_companion", "thorin"), {"op": "adv", "k": "*"}],
              cond=ALL(NOT({"pc": "thorin"}), NOT(flag("alt_thorin_dead")))),
            C("comp_none", "算了，无人可召，自己上。", "A1-TOWN-09",
              [P("你收回目光。东仓的蓝火不会等你。")], []),
          ]),
        C("prep_drain", "抄近路封排水渠。", "A1-TOWN-09",
          [P("你钻进小巷，用木板死死卡住排水口。敌人的退路窄了一截；你的手也被铁栅划开。")],
          [hp(-2), setf("warehouse_drain_sealed")],
          check={"stats": ["DEX"], "dc": 13},
          success=branch("木板卡死。河门那边会挤成一团。", [setf("warehouse_drain_sealed")]),
          fail=branch("你摔进湿泥，到手时已经在流血；排水渠只封了一半。", [hp(-2)])),
        C("prep_stash", "先把关键物品存入安全点。", "A1-STASH-01",
          [P("你冲回白鸦旅店储物柜。钥匙还在——但每多放一件，东仓的火就亮一分。敌人会占上风。")],
          [setf("warehouse_enemy_advantage", True), setf("warehouse_prep", "stash")]),
        C("prep_rush", "直接冲过去。", "A1-TOWN-09",
          [P("你没有多想。容器在怀里发烫，像在催你更快——也像在高兴。"),
           FOLD("残片侵扰", "催促变成愉悦时最危险：你分不清是自己要救人，还是残片要你靠近那三件货。")],
          [add("fragment_pressure", 1), add("fall", 1)], call="C-04"),
    ]
    # stash mini node
    N["A1-STASH-01"] = {
        "id": "A1-STASH-01", "title": "白鸦储物柜", "source": "revision", "kind": "scene",
        "blocks": [
            P("储物柜闻起来有湿羊毛和旧油。你最多再塞两件非残片物品——残片容器贴着你，像拒绝被关起来。"),
            P("〔打开「行囊」可将物品移入安全点。选下方选项确认你已放好或放弃。〕"),
        ],
        "choices": [
            C("stash_done", "锁上柜子，奔向东仓。", "A1-TOWN-09",
              [P("柜门锁上。你赶往东仓；蓝火已经压过屋脊。存过的东西留在柜中，身上装备以行囊为准。")],
              [setf("stash_used_pre_warehouse", True), setf("warehouse_enemy_advantage", True)],
              call="C-04"),
            C("stash_cancel", "结束整理，立刻赶往东仓。", "A1-TOWN-09",
              [P("你甩上柜门，朝蓝火跑去。若已放入物品，它们仍留在柜中；耽搁的时间也追不回来。")],
              [], cond_effects=[{"cond": {"cmp": ["warehouse_stashed", "==", 0]},
                                  "ops": [setf("warehouse_enemy_advantage", False)]}],
              call="C-04"),
        ],
        "default_next": "A1-TOWN-09",
    }
    # enrich C-04 / A1-TOWN-09 opening if present
    for cid in ("C-04", "A1-TOWN-09"):
        node = N.get(cid)
        if not node: continue
        if not any("第七声" in (b.get("text") or "") for b in node.get("blocks") or []):
            node["blocks"].insert(0, P(
                "东仓的蓝火映出黑篷车。他们要的不只是钱：名单、旧档与铅匣残迹拼在一起，才会指向“第七声”曾回应过的地方。"
            ))
        if not any(b.get("t") == "fold" for b in node.get("blocks") or []):
            insert_fold_after_first_p(node, FOLD(
                "残片侵扰",
                "火光一跳，残片就在血里鼓掌。你想救人、抢档、截匣——每一种冲动都被放大到像唯一正确答案。",
            ))
        # enemy advantage note as conditional block
        node["blocks"].append({
            "t": "note", "text": "你来晚了一步：敌人已占货架与河门，开场更难。",
            "cond": flag("warehouse_enemy_advantage"),
        })
        node["blocks"].append({
            "t": "note", "text": "同伴的脚步就在你侧后——这一场你们不是独自硬闯。",
            "cond": ANY(flag("warehouse_companion"), cmp("companion", "!=", None)) if False else flag("warehouse_companion"),
        })
        # simpler companion note
        node["blocks"] = [b for b in node["blocks"] if "同伴的脚步" not in b.get("text", "")]
        node["blocks"].append({"t": "note", "text": "同伴的脚步就在你侧后。", "cond": flag("warehouse_companion")})


def patch_town10_seventh(N):
    n = N.get("A1-TOWN-10")
    if not n: return
    # insert seventh-sound beat
    blocks = n["blocks"]
    if not any("第七声" in (b.get("text") or "") for b in blocks):
        blocks.insert(2, P(
            "余烬里，伊索尔忽然问：“刚才仓库——你们谁对谁说过一句不带命令的实话？”"
            "若有人答了，残片会短暂同频，像六座钟楼的缝隙里多敲了一下无形的声音。"
            "格罗姆骂她神神叨叨，却仍低声补了一句：“那才叫第七声的边角。真正的第七声，得是知情、自愿、还能反悔的承诺。假的那种，是塞维兰的货色。”"
        ))
        blocks.insert(3, FOLD(
            "残片侵扰",
            "那一下和声里，你听见自己最不想承认的愿望被轻轻点名——然后又散了。"
            "旧雨要你记住它；饥月要你占有它；裂锤要你拒绝它。选择仍是你的。",
        ))
    # peer disagreement choice
    if not any(c.get("id") == "peer_argue" for c in n.get("choices") or []):
        n["choices"].insert(0, C(
            "peer_argue", "听另两位持有者争执该去哪治病。", "__SELF__",
            [
                P("火后，各人对治病的办法各有主张。你先确认还有谁愿意留在河岸说话。"),
                {"t": "say", "who": "艾德里克", "text": "“先保住还能走的人。”",
                 "cond": ANY({"pc": "edric"}, ALL(flag("met_edric"), NOT(flag("alt_edric_dead"))))},
                {"t": "say", "who": "莉瑞尔", "text": "“保人，还是保你那张离境文书？先说清楚。”",
                 "cond": ANY({"pc": "liriel"}, ALL(flag("met_liriel"), NOT(flag("alt_liriel_dead"))))},
                {"t": "say", "who": "索林", "text": "“我修得动的东西我修。修不动的，别拿大话压我。”",
                 "cond": ANY({"pc": "thorin"}, ALL(flag("met_thorin"), NOT(flag("alt_thorin_dead"))))},
                P("他们没有自动组成拯救小队。每人的私人目标仍在，残片只是把路叠在一起。"),
                FOLD("情欲描写", "争执间隙，莉瑞尔的目光在你喉结上停过一瞬又收回；银链只热了一下。她说：“别用这种时候试我。”——拒绝本身也是她还醒着的证据。",
                     cond={"pc": "edric"}),
                FOLD("残片侵扰", "旧雨骨把两人的脸叠成边境死者的脸；你必须眨眼几次，才把同伴认回来。", cond={"pc": "edric"}),
                FOLD("残片侵扰", "裂锤骨想让你砸断这无用的争论。你把锤柄按进泥里，直到手指发疼。", cond={"pc": "thorin"}),
            ],
            [setf("peer_therapy_argument")],
            once=True,
        ))


def patch_shrine_absence(N):
    n = N.get("A3-SHRINE-03~2") or N.get("A3-SHRINE-03")
    # Gate "请一位同伴" style and named PC sacrifice options
    for nid in list(N):
        if not nid.startswith("A3-SHRINE"): continue
        node = N[nid]
        for c in node.get("choices") or []:
            walk = [c] + list(c.get("sub") or [])
            # also nested
            stack = list(c.get("sub") or [])
            while stack:
                s = stack.pop(); walk.append(s); stack.extend(s.get("sub") or [])
            for s in walk:
                lab = s.get("label", "")
                for role, name in (("edric", "艾德里克"), ("liriel", "莉瑞尔"), ("thorin", "索林")):
                    if name in lab:
                        present = ANY({"pc": role}, ALL(flag(f"met_{role}"), NOT(flag(f"alt_{role}_dead"))))
                        if nid == "A3-SHRINE-03~2" and s.get("id") in {"s3c6", "s3c7", "s3c8"}:
                            s["cond"] = present
                        else:
                            s["cond"] = ALL(s["cond"], present) if s.get("cond") else present
                if "请一位同伴自愿留下" in lab:
                    s["cond"] = ANY(*[
                        ALL(NOT({"pc": role}), flag(f"met_{role}"), NOT(flag(f"alt_{role}_dead")))
                        for role in ("edric", "liriel", "thorin")
                    ])
                    # add incomplete party variant nearby — handled in parent shrine patch below

    # A3-SHRINE-07 incomplete party option text
    n7 = N.get("A3-SHRINE-07")
    if n7:
        for c in n7.get("choices") or []:
            for s in c.get("sub") or []:
                if s.get("id") == "p1b" or "只剩三声" in s.get("label", ""):
                    s["result"] = [P("中央的槽是空的——或者该站在这里的人已经不在了。你知道这样只能扯断命令，却没人能看清余波会落到谁头上。")]
                    ensure_effect(s, setf("three_voice_break", True))


def patch_act1_pressure(N):
    n = N.get("A1-TOWN-01")
    if n:
        ee = n.setdefault("enter_effects", [])
        # bump pressure / resonance baseline once
        if not any(e.get("k") == "fragment_pressure" for e in ee):
            ee.append({"op": "max", "k": "fragment_pressure", "v": 2})
        if not any(e.get("k") == "resonance" and e.get("op") == "max" for e in ee):
            ee.append({"op": "max", "k": "resonance", "v": 1})
        if not any("回声病" in (b.get("text") or "") for b in n.get("blocks") or []):
            n["blocks"].append(P(
                "你扶着桥柱停了停。耳鸣里有极细的钟声——不是镇上那座楼，是你随身的那一声。"
                "残片的异常从今晚开始变得更不客气：它要你把路走完，哪怕用眩晕和出血来赶工。"
            ))
            insert_fold_after_first_p(n, FOLD(
                "残片侵扰",
                "血丝爬进唾液。旧雨骨塞给你一张死者的脸；饥月骨让路过的体温变得过分清晰；裂锤骨则数着谁该被推开。"
                "你用意志按住它——成功时也付出了短暂的腿软。",
            ))


def patch_d_alt_peers(N):
    d = N.get("D-ALT")
    if not d: return
    d["blocks"] = [P("你只找已经结识、仍能与你说话的持有者。每个人都带着自己的目的与界限。")]
    for c in d.get("choices") or []:
        role = {"t1": "edric", "t2": "liriel", "t3": "thorin"}.get(c.get("id"))
        if role:
            c["cond"] = ALL(NOT({"pc": role}), flag(f"met_{role}"), NOT(flag(f"alt_{role}_dead")))
    # Expand companion scenes with voice + folds + fall
    for c in d.get("choices") or []:
        if c.get("id") == "t1":  # edric companion
            # add deeper subs if missing
            subs = c.setdefault("sub", [])
            if not any(s.get("id") == "s1_fragment" for s in subs):
                subs.append(C("s1_fragment", "问旧雨骨今晚又让他看见谁。", "__SELF__",
                    [P("艾德里克沉默很久：“有时是父亲。有时是还活着的人，穿着死人的雨披。我追过一次——追到的是个吓坏的哨兵。”"),
                     FOLD("残片侵扰", "他说这话时，你自己的容器也烫了一下。两人之间短暂共享同一帧雨夜，又猛地断开。")],
                    [add("rel.alt_a", 1), setf("talked_edric_fragment")]))
            if not any(s.get("id") == "s1_drink" for s in subs):
                subs.append(C("s1_drink", "看他借酒压记忆（沉沦）。", "__SELF__",
                    [P("他要了最烈的麦酒，喝相不好看。“少记一点，明天还能走路。”这不是策略，是在提前练习放弃。"),
                     FOLD("残片侵扰", "旧雨骨满足地安静了半寸——用遗忘换来的安静。")],
                    [add("fall_edric", 1), setf("edric_drink_seen")],
                    cond=cmp("fall", ">=", 0)))
        if c.get("id") == "t2":  # liriel
            subs = c.setdefault("sub", [])
            if not any(s.get("id") == "s2_fall4" for s in subs):
                subs.append(C("s2_fall4", "她提起“有人愿意养我”的邀约。", "__SELF__",
                    [P("莉瑞尔笑了一下，笑意不到眼底：“雾钟城有位权贵，喜欢收‘会发热的人’。吃住都行，条件是项圈与开门权。”"
                      "银链在腕间兴奋地一跳。她看着你：“我还没答应。你最好在我答应之前，给我一个配活着的理由——或者一门真正的治愈。”"),
                     FOLD("情欲描写",
                          "她把项圈两个字说得很慢，像已经想象过皮革贴喉、手指从锁骨滑到乳尖、在许可与臣服之间反复练习说停。"
                          "热意明显；她仍把决定权按在自己手上——目前如此。")],
                    [setf("liriel_patron_offer_seen")],
                    cond=cmp("fall_liriel", ">=", 4)))
            # ensure desire sub adds fall
            for s in subs:
                if s.get("id") == "s2_desire" or "吸引" in s.get("label", ""):
                    s["effects"] = [e for e in s.get("effects") or [] if e.get("k") != "fall"]
                    if not any(b.get("t") == "fold" for b in s.get("result") or []):
                        s.setdefault("result", []).append(FOLD(
                            "情欲描写",
                            "承认吸引之后，空气变得很窄。她问边界，也问停词；自愿的交合可以很直白，但每一步都等你回答。",
                        ))
        if c.get("id") == "t3":
            subs = c.setdefault("sub", [])
            if not any(s.get("id") == "s3_rage" for s in subs):
                subs.append(C("s3_rage", "问他会不会砸错人。", "__SELF__",
                    [P("索林盯着自己的手：“会。怀表不管对象对不对，只管阻力大不大。所以我才要你们在我发火时喊我的名字——不是求饶，是报数。”"),
                     FOLD("残片侵扰", "他说“报数”时指节发白，像已经在想象下一锤。")],
                    [add("rel.alt_b", 1)]))


def patch_menu_resonance_node(N):
    """No separate node; UI reads meta. Ensure town leave choices have feedback."""
    for nid, label_sub in [("A1-TOWN-03", "礼拜堂"), ("A1-TOWN-04", "红牡丹"), ("A1-TOWN-05", "铺子")]:
        n = N.get(nid)
        if not n: continue
        for c in n.get("choices") or []:
            if not c.get("result") and c.get("next") and c.get("next") != "__SELF__":
                c["result"] = [P("你把这件事暂告一段落，脚步声落在身后的门板上。")]


def apply_to_nodes(N):
    patch_fragment_events(N)
    patch_prologue_folds(N)
    patch_tavern(N)
    patch_warehouse(N)
    patch_town10_seventh(N)
    patch_shrine_absence(N)
    patch_act1_pressure(N)
    patch_d_alt_peers(N)
    patch_menu_resonance_node(N)
    # L-PRO-07 ensure fall already; boost more liriel mid content lightly on CITY if present
    for nid, text in [
        ("CITY-01", "进城时银链/戒指/怀表同时一沉。城市本身在听。"),
    ]:
        if nid in N and not any(b.get("t") == "fold" and "残片" in b.get("label", "") for b in N[nid].get("blocks") or []):
            insert_fold_after_first_p(N[nid], FOLD(
                "残片侵扰",
                text + "展开时你能看清它如何改写呼吸、视线与想做的下一件事——按住它要付出血或时间。",
            ))
    return N


def main():
    nodes_path = DATA / "nodes.json"
    meta_path = DATA / "meta.json"
    N = json.loads(nodes_path.read_text())
    meta = json.loads(meta_path.read_text())
    patch_meta(meta)
    apply_to_nodes(N)
    nodes_path.write_text(json.dumps(N, ensure_ascii=False, indent=1))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("revision pass OK", "nodes", len(N), "version", meta.get("version"))


if __name__ == "__main__":
    main()
