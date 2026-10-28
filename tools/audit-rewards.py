#!/usr/bin/env python3
"""Fail when player-facing payments or key quest rewards are only prose."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODES = json.loads((ROOT / "public/data/nodes.json").read_text(encoding="utf-8"))

CN = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十二": 12,
    "十八": 18,
    "二十": 20,
    "二十五": 25,
    "二十八": 28,
    "三十": 30,
    "三十二": 32,
}
MONEY = re.compile(
    r"(?:花|付|支付|塞|赔|垫上|收下|得到|获得|拿到|换来|换得|出价|出了|开价)"
    r"[^。；，]{0,20}?([一二三四五六七八九十两\d]+)\s*张?(?:商会)?(?:券|票据)"
)


def blocks_text(blocks):
    return "".join(block.get("text") or "" for block in blocks or [])


def choices(node):
    stack = list(node.get("choices") or [])
    while stack:
        choice = stack.pop()
        yield choice
        stack.extend(choice.get("sub") or [])


def voucher_changes(choice):
    values = []

    def collect(source):
        for effect in source.get("effects") or []:
            if effect.get("op") == "add" and effect.get("k") == "vouchers":
                values.append(int(effect.get("v") or 0))

    collect(choice)
    cost = int((choice.get("cost") or {}).get("vouchers") or 0)
    if cost:
        values.append(-cost)
    for name in ("success", "fail"):
        collect(choice.get(name) or {})
    for sub in choice.get("sub") or []:
        values.extend(voucher_changes(sub))
    return values


def find_choice(node_id, choice_id):
    for choice in choices(NODES[node_id]):
        if choice.get("id") == choice_id:
            return choice
    raise KeyError(f"{node_id}: missing choice {choice_id}")


def source(choice, branch=None):
    return choice if branch is None else choice.get(branch) or {}


def has_item(choice, item_key, branch=None):
    return any(
        effect.get("op") == "item" and effect.get("k") == item_key and effect.get("v") is not False
        for effect in source(choice, branch).get("effects") or []
    )


def voucher_total(choice, branch=None):
    target = source(choice, branch)
    total = sum(
        int(effect.get("v") or 0)
        for effect in target.get("effects") or []
        if effect.get("op") == "add" and effect.get("k") == "vouchers"
    )
    if branch is None:
        total -= int((choice.get("cost") or {}).get("vouchers") or 0)
    return total


issues = []

# Heuristic pass: every numeric payment or receipt described by a choice must have
# a matching mutation in that choice, one of its check branches, or a sub-choice.
for node_id, node in NODES.items():
    for choice in choices(node):
        base_text = (choice.get("label") or "") + " " + blocks_text(choice.get("result"))
        amounts = [CN.get(raw, int(raw) if raw.isdigit() else -1) for raw in MONEY.findall(base_text)]
        changes = voucher_changes(choice)
        for amount in amounts:
            if amount > 0 and amount not in {abs(value) for value in changes}:
                issues.append(f"{node_id}/{choice['id']}: prose mentions {amount} vouchers but state changes are {changes}")
        for branch in ("success", "fail"):
            branch_data = choice.get(branch) or {}
            text = blocks_text(branch_data.get("result"))
            amounts = [CN.get(raw, int(raw) if raw.isdigit() else -1) for raw in MONEY.findall(text)]
            changes = [
                int(effect.get("v") or 0)
                for effect in branch_data.get("effects") or []
                if effect.get("op") == "add" and effect.get("k") == "vouchers"
            ]
            for amount in amounts:
                if amount > 0 and amount not in {abs(value) for value in changes}:
                    issues.append(
                        f"{node_id}/{choice['id']}.{branch}: prose mentions {amount} vouchers but branch changes are {changes}"
                    )

# Regression contracts for the rewards most likely to silently disappear when
# source prose is reparsed.
VOUCHER_CONTRACTS = [
    ("T-PRO-02", "s1c3", None, 5),
    ("T-PRO-03", "s1c4", None, 18),
    ("A1-TOWN-02", "s2c2", "success", 4),
    ("A1-TOWN-02", "s3c3", None, 20),
    ("A1-TOWN-04", "s2c3", None, 10),
    ("SQ-CITY-02~2", "s3c1", "success", 20),
    ("SQ-CITY-02~2", "s3c2", None, 20),
    ("SQ-CITY-04", "s3c1", None, 8),
    ("SQ-CITY-04", "s3c4", None, 20),
    ("SQ-CITY-05", "s2c1", None, 25),
    ("SQ-CITY-05", "s2c6", "success", 32),
]
for node_id, choice_id, branch, amount in VOUCHER_CONTRACTS:
    actual = voucher_total(find_choice(node_id, choice_id), branch)
    if actual != amount:
        issues.append(f"{node_id}/{choice_id}{'.' + branch if branch else ''}: expected {amount} vouchers, got {actual}")

ITEM_CONTRACTS = [
    ("T-PRO-01", "s1c3", "success", "mine_access_token"),
    ("SQ-CITY-01~2", "s2c2", None, "free_storage_token"),
    ("SQ-CITY-01~2", "s2c4", None, "sewn_pack_strap"),
    ("SQ-CITY-02~2", "s3c1", "success", "upper_house_key"),
    ("SQ-CITY-02~2", "s3c3", "success", "varick_ledger"),
    ("SQ-CITY-03", "s2c1", None, "archive_cabinet_key"),
    ("SQ-CITY-03", "s2c5", "success", "stable_medicine"),
    ("SQ-CITY-04", "s3c1", None, "smugglers_canal_route"),
    ("SQ-CITY-04", "s3c3", None, "silver_shard_amulet"),
    ("SQ-CITY-04", "s3c5", None, "city_old_map_access"),
    ("SQ-CITY-05", "s2c1", None, "merchant_storage_token"),
    ("SQ-CITY-05", "s2c4", "success", "leona_testimony"),
]
for node_id, choice_id, branch, item_key in ITEM_CONTRACTS:
    if not has_item(find_choice(node_id, choice_id), item_key, branch):
        issues.append(f"{node_id}/{choice_id}{'.' + branch if branch else ''}: missing item {item_key}")

if issues:
    print(f"reward audit: {len(issues)} issue(s)")
    for issue in issues:
        print(f"  - {issue}")
    sys.exit(1)

print(f"reward audit: OK ({len(NODES)} nodes, {len(VOUCHER_CONTRACTS)} currency contracts, {len(ITEM_CONTRACTS)} item contracts)")
