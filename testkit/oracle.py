"""정답 계산기 — 합성 정답셋의 '정답'을 진단기와 다른 방식(무식하게 전부 비교)으로 구한다.

진단기(scanner/folders.py)는 해시·오일러 순회로 빠르게 계산하고, 여기서는 모든 폴더 쌍을
집합으로 직접 비교한다. 두 계산이 같은 정의(docs/진단기_설계.md)를 따르되 구현은 서로 독립이라,
정답셋 시험에서 결과가 같으면 진단기 구현이 맞다고 본다. 폴더가 수천 개를 넘으면 느리므로
규모 시험에서는 쓰지 않는다.
"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).casefold()


def _comp(p: str) -> tuple[str, ...]:
    return tuple(p.split("/"))


def content_ids(files: list[dict]) -> dict[str, str]:
    """검사되는 파일마다 내용 번호. files: [{"path", "content", "size"}]."""
    count = Counter(f["content"] for f in files if f["size"] > 0)
    out = {}
    for f in files:
        if f["size"] == 0:
            out[f["path"]] = "empty"
        elif count[f["content"]] >= 2:
            out[f["path"]] = "k:" + f["content"]
        else:
            out[f["path"]] = "u:" + f["path"]
    return out


def exact_dup_groups(files: list[dict]) -> list[list[str]]:
    by = defaultdict(list)
    for f in files:
        if f["size"] > 0:
            by[f["content"]].append(f["path"])
    return sorted(sorted(v) for v in by.values() if len(v) > 1)


def folder_truth(files: list[dict]) -> dict:
    cid = content_ids(files)
    size = {f["path"]: f["size"] for f in files}
    dirs: set[str] = set()
    for p in cid:
        parts = p.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))

    def is_anc(a: str, b: str) -> bool:  # a 가 b 의 (진짜) 조상
        return b.startswith(a + "/")

    sub: dict[str, list[tuple[str, str]]] = {d: [] for d in dirs}
    nbytes: dict[str, int] = {d: 0 for d in dirs}
    for p, c in cid.items():
        parts = p.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            rel = "/".join(parts[i:])
            sub[d].append((rel, c))
            nbytes[d] += size[p]

    allc = {d: {c for _, c in sub[d]} for d in dirs}
    clean = {d: bool(sub[d]) and not any(c.startswith("u:") for c in allc[d]) for d in dirs}
    eligible = {d for d in dirs if clean[d] and nbytes[d] > 0}
    akey = {d: tuple(sorted(("/".join(_norm(x) for x in rel.split("/")), c) for rel, c in sub[d]))
            for d in dirs if clean[d]}
    bset = {d: frozenset(allc[d]) for d in dirs if clean[d]}

    # (a)(b) 묶음
    by = defaultdict(list)
    for d in eligible:
        by[bset[d]].append(d)
    groups = []
    for members in by.values():
        kept = [m for m in members if not any(is_anc(o, m) for o in members if o != m)]
        if len(kept) >= 2:
            groups.append(sorted(kept, key=_comp))
    member_of = {m for g in groups for m in g}

    # 위에서 아래로: 접기와 포함
    blocked: dict[str, bool] = {}
    covering: dict[str, bool] = {}
    contains: dict[str, list[str]] = {}
    for d in sorted(dirs, key=lambda x: (x.count("/"), _comp(x))):
        b = any(covering.get(a, False) for a in dirs if is_anc(a, d))
        blocked[d] = b
        if b:
            covering[d] = False
            continue
        cov = d in member_of
        if d in eligible:
            s = bset[d]
            outers = [x for x in dirs if x != d and not is_anc(x, d) and not is_anc(d, x) and s <= allc[x]]
            minimal = [x for x in outers if not any(is_anc(x, y) for y in outers)]
            strict = [x for x in minimal if allc[x] != s]
            if strict:
                contains[d] = sorted(strict, key=_comp)
                cov = True
        covering[d] = cov

    out_groups = []
    for g in groups:
        unblocked = [m for m in g if not blocked[m]]
        if len(unblocked) >= 2:
            shown = [(m, "보고") for m in unblocked]
        elif len(unblocked) == 1:
            ref = min((m for m in g if blocked[m]), key=_comp)
            shown = sorted([(unblocked[0], "보고"), (ref, "참고")], key=lambda x: _comp(x[0]))
        else:
            continue
        classes: dict[tuple, int] = {}
        for m, _ in shown:
            classes.setdefault(akey[m], len(classes) + 1)
        out_groups.append({
            "level": "a" if len(classes) == 1 else "b",
            "bytes": nbytes[shown[0][0]],
            "members": [{"path": m, "role": r, "a_class": classes[akey[m]]} for m, r in shown],
        })
    out_groups.sort(key=lambda g: (-g["bytes"], _comp(g["members"][0]["path"])))
    out_contains = [{"inner": d, "outer": x} for d in sorted(contains, key=_comp) for x in contains[d]]
    return {"folder_groups": out_groups, "folder_contains": out_contains}
