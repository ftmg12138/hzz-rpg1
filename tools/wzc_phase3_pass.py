#!/usr/bin/env python3
"""Playable companion commitments, mine rescue consequences, and a city safe point."""
from __future__ import annotations

from wzc_phase2_pass import ALL, ANY, C, FOLD, NOTE, SAY, add, cmp, flag, setf


def P(t, **kw):
    block = {"t": "p", "text": t}
    block.update(kw)
    return block


ROLES = {
    "edric": ("艾德里克", "旧雨骨"),
    "liriel": ("莉瑞尔", "饥月骨"),
    "thorin": ("索林", "裂锤骨"),
}


def pronoun(role):
    return "她" if role == "liriel" else "他"


def eq(key, value):
    return {"eq": [key, value]}


def alive_other(role):
    return ALL({"not": {"pc": role}}, flag(f"met_{role}"), {"not": flag(f"alt_{role}_dead")})


def make_node(nid, title, blocks, choices, default_next=None):
    return {
        "id": nid, "title": title, "source": "phase3", "kind": "scene",
        "blocks": [P(b) if isinstance(b, str) else b for b in blocks],
        "choices": choices, "default_next": default_next,
    }


def patch_city(N):
    hub = N["CITY-HUB"]
    hub["choices"] = [c for c in hub["choices"] if c.get("id") != "peer_city_event"]
    hub["blocks"].append(P(
        "河渠旁有白鸦旅店的城中分号。两地共用封签账本：灰桥寄存的箱子已随商队送到，柜钥仍在你手里。"
        "城里也许有办法只稳住病、不替钟承担任何使命；你可以为此继续查。"
    ))
    hub["choices"].insert(0, C(
        "city_safe", "去白鸦旅店城中分号整理行囊。", "CITY-SAFE-01",
        ["掌柜对照封签，把箱子搬上柜台。你终于能在不赶路的时候清点武器、衣物和药瓶。"],
    ))
    N["CITY-SAFE-01"] = make_node(
        "CITY-SAFE-01", "白鸦旅店·城中分号",
        [
            "掌柜把旧钥匙放在你面前，柜门后的油布包与灰桥寄存时一样。行囊里可存放或取回非残片物品；卸下装备会立刻影响战力。",
            "靠街的窗户有六声钟的回响。第七声只存在于你骨头里：你还不能确定它是解药、陷阱，还是某个活人尚未说出的拒绝。",
            NOTE("打开「行囊」进行存取和装备。这里没有东仓倒计时。"),
        ],
        [C("safe_return", "收好钥匙，回城里。", "CITY-HUB",
           ["你锁上柜门，记下封签编号。下一次回来，东西仍会在这里。"])],
    )
    links = {
        "edric": "雨披下那张未写完的名单",
        "liriel": "袖口下发烫的银链",
        "thorin": "膝上的修井锤",
    }
    for role, (name, bone) in ROLES.items():
        hub["choices"].append(C(
            f"peer_city_{role}", f"在钟楼背面找{name}谈谈。", f"CITY-PEER-{role.upper()}",
            [f"你看见{name}独坐檐下，手边是{links[role]}。这次你先问{pronoun(role)}是否愿意说话。"],
            once=True, cond=alive_other(role),
        ))

    N["CITY-PEER-EDRIC"] = make_node(
        "CITY-PEER-EDRIC", "雨停之前",
        [
            "艾德里克没有先谈钟。他把一张皱纸摊开：边境撤离名单上，最后三人的名字都写在同一行。他记得自己当时说过『等下一辆车』。那辆车没有来。",
            P("你是莉瑞尔时，他不再把你的银链当危险物展示，只问你是否也有一个不能读完的名字。你说起父亲的旧誓，他没有替你原谅任何人。", cond={"pc": "liriel"}),
            P("你是索林时，他承认自己曾把工程损失写成战损；你把被抹掉的矿工姓名补在纸边，问他是否敢在新的报告里照抄。", cond={"pc": "thorin"}),
            SAY("艾德里克", "“旧雨骨最会许诺：再喝一杯，就不用记得那辆没来的车。我知道它在撒谎，也知道自己有时愿意信。”"),
            "远处的酒馆开门。他盯了一眼招牌，没站起来。你可以留住这片刻，也可以利用他的软处。",
        ],
        [
            C("edric_listen", "陪他把名单上的名字读完。", "CITY-HUB",
              ["你没有说『这不是你的错』。你们逐个读完名字，最后一行由他自己收起。"],
              [add("rel.alt_a", 1), setf("peer_supported_edric")]),
            C("edric_press", "说他若敢再喝，就不配谈救人。", "CITY-HUB",
              ["他没有争辩，只把名单折得更小。夜里他还是去了酒馆；你听见椅脚划过石地的声音。"],
              [add("fall_edric", 1), add("corruption", 1), setf("peer_wounded_edric")]),
        ],
    )
    N["CITY-PEER-LIRIEL"] = make_node(
        "CITY-PEER-LIRIEL", "银链与停词",
        [
            "莉瑞尔把袖口卷到腕骨。银链留下细痕，却没有勒紧。她说饥月骨会把注意、欲望和服从都伪装成同一种温暖；最可怕的是，她并非每次都想推开。",
            P("你是艾德里克时，她问你是否曾把保护当成不容拒绝的命令。你想起撤离名单上自己替别人做过的决定，没有立刻回答。", cond={"pc": "edric"}),
            P("你是索林时，你把锤子放到两人够不着的地方。她笑你谨慎，又承认这让她敢说一句真话：她想被渴望，也想保留说停的权利。", cond={"pc": "thorin"}),
            SAY("莉瑞尔", "“别把我看成病，也别把我看成奖赏。我可以靠近你，也可以在下一秒离开。这两句话得同时是真的。”"),
            FOLD("情欲描写", "她的指腹沿银链慢慢滑到锁骨，呼吸乱了一拍。你没有替她完成这个动作；她也没有向你索取一个答案。"),
        ],
        [
            C("liriel_boundary", "和她约好停词；把她的选择交还给她。", "CITY-HUB",
              ["她选了一个再普通不过的词。你复述一遍。银链没有松，但她的肩终于松了。"],
              [add("rel.alt_a", 1), setf("peer_supported_liriel"), setf("liriel_stopword_shared")]),
            C("liriel_bargain", "问她能否用这种依恋换取情报。", "CITY-HUB",
              ["她把袖口拉下去：『你听懂了，却还是想把我当钥匙。』你得到她知道的钟律暗号，却失去今晚的信任。"],
              [add("fall_liriel", 1), add("sanctuary_clues", 1), setf("peer_wounded_liriel")]),
        ],
    )
    N["CITY-PEER-THORIN"] = make_node(
        "CITY-PEER-THORIN", "锤柄的背面",
        [
            "索林把修井锤翻过来给你看。背面刻着死去矿工的工号，最后一排是他自己的空格。『我该被记进去。那道闸是我砸错的。』",
            P("你是艾德里克时，听得出他在用认罪代替下一次的判断。你把撤离名单放在锤旁：名字可以留着，但今夜有人还等他修桥。", cond={"pc": "edric"}),
            P("你是莉瑞尔时，裂锤骨的热与你银链的热几乎同拍。你提醒他，把怒火交给锤子和把意愿交给项圈，是同一种省事。", cond={"pc": "liriel"}),
            SAY("索林", "“我每次说『只砸该砸的』，它都替我找到一个更像敌人的人。你若见我举锤没报名字，先喊停。”"),
        ],
        [
            C("thorin_name", "陪他逐个念工号，约好先报名字再动锤。", "CITY-HUB",
              ["他念到最后一个工号时声音发涩。锤头依然沉，握柄的人却肯再听一次『停』。"],
              [add("rel.alt_a", 1), setf("peer_supported_thorin")]),
            C("thorin_target", "把上环议员的名字写成下一块『该砸的东西』。", "CITY-HUB",
              ["他没有擦去那个名字。你知道自己利用了他最易失控的部分。"],
              [add("fall_thorin", 1), add("cruelty", 1), setf("peer_wounded_thorin")]),
        ],
    )


def patch_mine(N):
    road = N["A2-MINE-00"]
    road.setdefault("enter_effects", []).append(setf("companion", None))
    for choice in road["choices"]:
        previous = choice.get("cond")
        choice["cond"] = ALL(previous, flag("mine_party_fixed")) if previous else flag("mine_party_fixed")
    road["blocks"].append(P(
        "进山前，同行者必须由你点名。灰桥东仓曾与你并肩的人不会自动出现在矿道里；若让对方离队，之后的危险只由你承担。"
    ))
    for role, (name, _) in ROLES.items():
        road["choices"].insert(0, C(
            f"party_{role}", f"请{name}陪你进入矿区。", "__SELF__",
            [f"你当面说明塌方与残片的危险。{name}听完仍决定与你同行；这不是一句随叫随到的差事。"],
            [setf("companion", role), setf("mine_party_fixed")],
            cond=ALL(alive_other(role), {"not": flag("mine_party_fixed")}), once=True,
        ))
        road["blocks"].append(P(
            f"{name}走在你身侧。你知道若井架断裂，要付代价的会是这个具体的人。",
            cond=eq("companion", role),
        ))
    road["choices"].insert(3, C(
        "party_solo", "这段路独自走。", "__SELF__",
        ["你把同行者留在安全处。矿井里没人会替你接住第一根断绳。"],
        [setf("companion", None), setf("mine_party_fixed")],
        cond={"not": flag("mine_party_fixed")}, once=True,
    ))
    for block in N["A2-MINE-02"].get("blocks", []):
        role = (block.get("id") or "").removeprefix("comp_mine02_")
        if role in ROLES:
            block["cond"] = eq("companion", role)
    prep = next(c for c in N["A1-TOWN-08"]["choices"] if c["id"] == "prep_comp")
    for sub in prep.get("sub", []):
        for role in ROLES:
            if sub["id"] == {"edric": "comp_ed", "liriel": "comp_li", "thorin": "comp_th"}[role]:
                sub["cond"] = alive_other(role)

    collapse = N["A2-MINE-10"]
    collapse["blocks"].append(P(
        "上方传来三次敲击、两次停顿：这是矿工的求救信号，不是钟律。绞盘正在把最后一批人拖向裂缝。"
        "你可以先决定撤离方向；真正要不要放开同行者的手，还得在下一刻回答。"
    ))
    by_id = {c["id"]: c for c in collapse["choices"]}
    for cid, plan, result in [
        ("s1c1", "escort", "你让同行者带矿工上井。绳轮突然反咬，负责压住刹车的人被拖向裂口。"),
        ("s1c2", "together", "你把队伍带向古水道。最后一辆矿车翻进裂口，回头的人被绳索拽住。"),
        ("s1c3", "forced", "矿工们在你的命令下冲向古水道。绳轮反咬时，他们先看你要救谁。"),
        ("s1c4", "core", "临时核心让撤离动作整齐得可怕；绳轮却没有因此停下。有人仍被拖向裂口。"),
    ]:
        c = by_id[cid]
        c["next"] = "A2-MINE-10B"
        c["effects"].append(setf("mine_exit_plan", plan))
        c["result"] = [P(result)]
    by_id["s1c1"]["cond"] = {"not": eq("companion", None)}
    by_id["s1c2"]["label"] = "沿古水道带队撤离，后援负责最后一批矿工。"
    by_id["s1c5"]["effects"].extend([setf("mine_deserted"), setf("companion", None)])

    blocks = [
        "井架木梁在头顶一节节折断。你听见有人喊『拉』，也有人喊『松』。这一刻不是钟在替你决定；你的手正在决定另一个人会不会活到城里。",
        P("你独自进矿，绳下是一个不认识的年轻矿工。他把半截工作牌扔到你脚边，求你记住他的名字。", cond=eq("companion", None)),
    ]
    choices = [
        C("rescue_worker", "咬牙拉住矿工，自己承受落石。", "A2-MINE-11",
          ["你用肩撑住绳轮。矿工滚过安全线，反过来把你拖出裂口；你们都记住了他的工号。"],
          [{"op": "hp", "v": -2}, add("mercy", 1), setf("mine_worker_saved")],
          cond=eq("companion", None)),
        C("leave_worker", "松开绳子，独自冲进古水道。", "A2-MINE-11",
          ["工作牌在石面上跳了两下，掉进缝里。你还活着，却把那声『拉』带进了水道。"],
          [add("fall", 1), add("cruelty", 1), setf("mine_worker_lost")],
          cond=eq("companion", None)),
    ]
    fall_voices = {
        "edric": "旧雨骨把绳索变成边境那辆迟迟不来的车。艾德里克说『别松』，声音却越来越轻。",
        "liriel": "饥月骨要莉瑞尔把救命变成一场服从测试。她扯开银链，喊出你们约好的停词——若你们真的约过。",
        "thorin": "裂锤骨催索林一锤砸断缆索，省去选择。他把锤子反过来，以木柄卡住齿轮。",
    }
    for role, (name, _) in ROLES.items():
        blocks.extend([
            P(f"{name}吊在断绳尽头，另一只手还攥着矿工的安全扣。{fall_voices[role]}", cond=eq("companion", role)),
            P(f"你想起在城里听{name}说过的真话。那一晚不是一张关系票；此刻它决定你能否听出求救和残片的命令。",
              cond=ALL(eq("companion", role), flag(f"peer_supported_{role}"))),
            P(f"{name}先前的伤口在此刻发作。你说过的话也在绳上添了重量。",
              cond=ALL(eq("companion", role), flag(f"peer_wounded_{role}"))),
        ])
        choices.extend([
            C(f"rescue_{role}", f"抓住{name}，用自己挡住坠石。", "A2-MINE-11",
              [f"你喊{name}的名字，扑向绳轮。石块砸在背上；{pronoun(role)}被你拖过安全线，反手又拉出最后一名矿工。",
               f"{name}没有说谢谢，只把手留在你肩上，直到你能自己站稳。"],
              [{"op": "hp", "v": -2}, add("sacrifice", 1), setf(f"peer_saved_{role}"),
               {"cond": cmp(f"fall_{role}", ">=", 1), "ops": [add(f"fall_{role}", -1)]}],
              cond=eq("companion", role)),
            C(f"abandon_{role}", f"松开{name}的绳索，保住残片和自己。", "A2-MINE-11",
              [f"你松了手。{name}没有诅咒你，只把安全扣抛上来。扣环落地时，矿道深处已经没有回应。",
               f"同行者的死因很具体：不是『不够人手』，而是你在这一秒选择了放开。之后任何誓环都不能替{name}说话。"],
              [setf(f"alt_{role}_dead"), setf("companion", None), setf(f"mine_left_{role}"),
               add("fall", 1), add("cruelty", 1)],
              cond=eq("companion", role)),
        ])
    N["A2-MINE-10B"] = make_node("A2-MINE-10B", "绳轮反咬", blocks, choices)
    waterway = N["A2-MINE-11"]
    waterway["blocks"].append(P(
        "若你救回了同伴，对方会在城里再和你争一次。若绳索已经松开，城里的誓环只会保留一个空位；别人不能替死者追认。",
        cond=ANY(*(flag(f"peer_saved_{role}") for role in ROLES), *(flag(f"alt_{role}_dead") for role in ROLES)),
    ))
    for role, (name, _) in ROLES.items():
        waterway["blocks"].append(P(
            f"{name}没能走出矿井。你携带的不是一个抽象损失，而是{pronoun(role)}交回来的安全扣。",
            cond=flag(f"alt_{role}_dead"),
        ))

    witness = N["A2-MINE-09"]
    for role, (name, _) in ROLES.items():
        witness["choices"].append(C(
            f"witness_delegate_{role}", f"让{name}替你承受一段见证。", "__SELF__",
            [f"你把照心骨转向{name}，明知它会把人最不肯承认的愿望放大。{name}没有来得及同意，"
             "画面就已经把旧伤撕开。你获得了线索，也听见一声很轻的『为什么是我』。",
             NOTE(f"{name}的沉沦 +2；你得到一条真相，但失去一部分信任。")],
            [add(f"fall_{role}", 2), add("truth", 1), add("corruption", 1),
             add("rel.alt_a", -1), setf(f"peer_wounded_{role}")],
            cond=eq("companion", role), once=True,
        ))

    for role, (name, _) in ROLES.items():
        rescue = next(c for c in N["A2-MINE-10B"]["choices"] if c["id"] == f"rescue_{role}")
        rescue["effects"].insert(3, {"cond": cmp(f"fall_{role}", ">=", 4), "ops": [{"op": "hp", "v": -1}]})
        N["A2-MINE-10B"]["blocks"].append(P(
            f"{name}的残片已经把这次坠落写成某种必然。你若拉{pronoun(role)}，必须多挡一块石头；危险不再只是绳索。",
            cond=ALL(eq("companion", role), cmp(f"fall_{role}", ">=", 4)),
        ))


def patch_shrine_and_endings(N):
    shrine = N["A3-SHRINE-01"]
    shrine["blocks"].append(P(
        "在入口等候的幸存持有者各有来路：与你同行的人从古水道到了；留在灰桥或城里的，则凭伊索尔的拓片和六座错拍的钟找到这里。"
        "他们能够作证，不等于他们同意你的计划。"
    ))
    for role, (name, _) in ROLES.items():
        shrine["blocks"].append(P(
            f"誓环的第{list(ROLES).index(role) + 1}个刻位空着。{name}死在黑砧绳轮下，无法在这里补一声『我愿意』。",
            cond=flag(f"alt_{role}_dead"),
        ))
    companion_talk = N["D-ALT"]
    companion_talk["blocks"] = [P("你只和已经结识、仍能回应的持有者谈话。深谈不会自动让对方进矿；同行需在出发前明确邀请。")]
    for choice in companion_talk["choices"]:
        for role, (name, _) in ROLES.items():
            if choice["id"] == {"edric": "t1", "liriel": "t2", "thorin": "t3"}[role]:
                choice["label"] = f"与{name}深入交谈。"
    groups = {c["id"]: {s["id"]: s for s in c.get("sub", [])} for c in companion_talk["choices"]}
    groups["t1"]["s1c2"]["result"] = [P("艾德里克回答：『你可以问，不能替我答。我若留内环，先把父亲的军信交给莉莉。』他还没有作出承诺。")]
    groups["t1"]["s1c2"]["effects"] = [setf("edric_memory_oath_pending")]
    groups["t1"]["s1c3"]["effects"] = [add("fall_edric", 1), add("rel.alt_a", -2), setf("edric_refused_command"),
                                                {"cond": eq("companion", "edric"), "ops": [setf("companion", None)]}]
    groups["t1"]["s1c4"]["effects"] = [{"op": "item", "k": "lily_comb"}, add("rel.alt_a", 1), setf("peer_supported_edric")]
    groups["t2"]["s2c3"]["result"] = [P(
        "你要莉瑞尔用银链迷倒守卫。她先说不，你又拿病情和同伴安危压她。她最后照做，换到了过路暗号；"
        "出来时银链发烫，她不看你。那句拒绝被你听见过，所以不能把结果写成她自愿。"
    ), FOLD(
        "情欲描写",
        "饥月骨在她眼前摆出交合的幻象，逼她把守卫的目光当成邀请。她实际只让守卫在暗巷睡去，没有碰他；"
        "可身体仍被幻象点热。她把银链勒进掌心，直到那股热不再像一句命令。",
    )]
    groups["t2"]["s2c3"]["effects"] = [add("fall_liriel", 1), add("corruption", 1),
                                                add("rel.alt_a", -1), setf("liriel_compelled_guard")]
    groups["t2"]["s2c4"]["effects"] = [add("rel.alt_a", 1), setf("peer_supported_liriel"),
                                                setf("liriel_anchor_mark")]
    groups["t3"]["s3c2"]["result"] = [P(
        "索林先问谁下井、谁上来。你只说需要他守住绞盘，却拒绝交代救的是矿工还是残片。"
        "他没有答应；怀表却把你的催促放大成了对所有人的怒意。"
    )]
    groups["t3"]["s3c2"]["effects"] = [add("fall_thorin", 1), add("rel.alt_a", -1),
                                                setf("thorin_pressured_winch")]
    groups["t3"]["s3c3"]["result"] = [P("索林说，若毁订单真能直接救人，他愿意做；但父母与工棚会一起承担后果。他要先看清谁在下令。")]
    groups["t3"]["s3c3"]["effects"] = [add("rel.alt_a", 1), setf("thorin_order_doubt")]
    groups["t3"]["s3c4"]["result"] = [P("索林替你把武器握柄重缠。手工很丑，却抓得更稳；下次出手时，湿木不再从掌心滑开。")]
    groups["t3"]["s3c4"]["effects"] = [{"op": "adv", "k": "*"}, add("rel.alt_a", 1), setf("peer_supported_thorin")]

    final = N["A3-SHRINE-07"]
    p1 = next(c for c in final["choices"] if c["id"] == "p1")
    p1["sub"] = [c for c in p1["sub"] if c["id"] != "p1c"]
    for role, (name, _) in ROLES.items():
        p1["sub"].append(C(
            f"p1c_{role}", f"请{name}自愿留在内环。", "A3-SHRINE-08",
            [f"你把代价说到最具体：以后可能失去触觉、记忆，甚至不能再辨认自己的愿望。{name}听完，自己走进内环。你没有代他说『愿意』。"],
            [setf("ending", "END-02"), setf("inner_ring_peer", role)],
            cond=ALL(alive_other(role), flag("four_bones_present"),
                     ANY({"not": cmp(f"fall_{role}", ">=", 4)}, flag(f"peer_supported_{role}"))),
        ))

    p5 = next(c for c in final["choices"] if c["id"] == "p5")
    volunteer = next(c for c in p5["sub"] if c["id"] == "p5a")
    pairs = [ALL(alive_other(a), alive_other(b)) for a, b in
             [("edric", "liriel"), ("edric", "thorin"), ("liriel", "thorin")]]
    volunteer["cond"] = ANY(cmp("city_rep", ">=", 2), *pairs)
    volunteer["result"] = [P(
        "你逐个说清守护的年限、隔离与退出办法。若同行者不够，城里获你救助的人替你找来愿意签名的守护者。"
        "没人靠『英雄』两字就被送上路。"
    )]
    forced = next(c for c in p5["sub"] if c["id"] == "p5b")
    forced["effects"].append(setf("forced_guardian"))

    end2 = N["END-02"]
    for block in end2["blocks"]:
        text = block.get("text", "")
        if text.startswith("最后一个字裂开，冲击把你掀进内环"):
            block["cond"] = ALL({"not": flag("three_voice_break")}, {"not": flag("inner_ring_peer")})
        if text.startswith("照心骨没有到场。前三种声音"):
            block["cond"] = flag("three_voice_break")
    for role, (name, _) in ROLES.items():
        end2["blocks"].append(P(
            f"最后一个字剥落时，{name}独自站在内环。你负责外环，把拒绝的路径留给城里的人。四种回声划过{pronoun(role)}的身体；"
            f"余生会有一部分感官迟钝。你们都知道这不是你替{name}选的，却仍要一起承担后果。",
            cond=eq("inner_ring_peer", role),
        ))

    end10 = N["END-10"]
    for block in end10["blocks"]:
        if block.get("text", "").startswith(("黎明前，四个人", "当下危机结束", "城市把他们传成")):
            block["cond"] = {"not": flag("forced_guardian")}
    end10["blocks"].append(P(
        "你把一枚钟骨交给了毫不知情的人。四路封存暂时止住共鸣，但被挑中的守护者直到夜里病发才懂得自己带走了什么。"
        "他撕掉了你留的说明，选择回城。第七声没有出现：你借别人的身体完成的沉默，不是可以撤回的承诺。",
        cond=flag("forced_guardian"),
    ))
    for nid, n in N.items():
        if n.get("kind") != "ending" or not nid.startswith("END-"):
            continue
        for role, (name, _) in ROLES.items():
            n["blocks"].append(P(
                f"后来有人问起{name}为什么没回来。你只能从黑砧那根断绳讲起；无论结局如何，这个名字不能被写成『自愿缺席』。",
                cond=flag(f"alt_{role}_dead"),
            ))
            n["blocks"].append(P(
                f"{name}活着走出了矿井。你们仍会争吵、仍会彼此拒绝；救命没有把{pronoun(role)}变成你的附属。",
                cond=flag(f"peer_saved_{role}"),
            ))
            n["blocks"].append(P(
                f"{name}还活着，但残片留下的习惯没有随终局一起消失。你们必须继续面对那条已深的沉沦线，"
                "不能把一次胜利当成对人格的自动治疗。",
                cond=ALL(cmp(f"fall_{role}", ">=", 4), {"not": flag(f"alt_{role}_dead")}),
            ))


def apply_to_nodes(N):
    patch_city(N)
    patch_mine(N)
    patch_shrine_and_endings(N)
    return N


def patch_meta(meta):
    meta["version"] = "2.3.0-companions"
    meta["ui_revision"] = "phase3-party-rescue-2026-10-30"
