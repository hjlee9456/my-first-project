"""4. 중첩 백업(폴더 중복) 찾기.

정의 (자세한 설명과 예시는 docs/진단기_설계.md)
- 내용 번호(cid): 파일 내용의 이름표. 중복이 있는 내용은 공유 번호, 0바이트는 '빈 내용',
  중복이 없거나 읽지 못한 파일은 그 파일만의 번호.
- 깨끗한 폴더: 하위 전체에 파일이 있고, 그 모든 파일의 내용이 다른 곳에도 있으며,
  목록을 끝까지 읽은 폴더. 용량이 0보다 크면 '비교 대상'.
- (a) 구조·이름까지 같음: 하위 (상대경로, 내용) 목록이 같다.
- (b) 내용만 같음: 하위 내용 집합이 같다(이름·배치는 다름).
- (c) 포함: A의 내용 집합이 B에 모두 들어 있고 B가 더 많다. B는 그런 폴더 중 가장 작은 것.
- 접기: 상위 폴더가 이미 중복(묶음 구성원)이거나 포함되는 쪽이면, 그 아래는 따로 보고하지 않는다.
  다만 접히지 않은 폴더가 묶음에 하나뿐이면, 접힌 짝 하나를 '참고'로 함께 보여 준다.
"""
from __future__ import annotations

import hashlib
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass

from .exclusions import norm_name

EMPTY = 0


@dataclass
class FolderStats:
    groups: int = 0
    groups_a: int = 0
    groups_b: int = 0
    contains_pairs: int = 0
    nested_pairs: int = 0
    redundant_bytes: int = 0


def _key(path: str) -> tuple[str, ...]:
    """경로 정렬 열쇠: 구분자와 무관하게 폴더 이름 순."""
    return tuple(c for c in path.replace("\\", "/").split("/") if c)


def analyze(con, run_id: int) -> FolderStats:
    # ── 읽어 오기 ───────────────────────────────────────────────
    parent: dict[int, int | None] = {}
    name: dict[int, str] = {}
    depth: dict[int, int] = {}
    listed_ok: dict[int, bool] = {}
    path: dict[int, str] = {}
    for did, pid, nm, dp, ok, p in con.execute(
            "SELECT dir_id, parent_id, name, depth, listed_ok, path FROM dirs WHERE seen_run=?", (run_id,)):
        parent[did], name[did], depth[did], listed_ok[did], path[did] = pid, nm, dp, bool(ok), p
    children: dict[int, list[int]] = defaultdict(list)
    for d, p in parent.items():
        if p is not None and p in parent:
            children[p].append(d)
    for lst in children.values():
        lst.sort(key=lambda d: name[d])

    dup_hashes = sorted(h for (h,) in con.execute(
        "SELECT full_hash FROM dup_groups WHERE run_id=?", (run_id,)))
    hash_id = {h: i for i, h in enumerate(dup_hashes, 1)}

    direct: dict[int, list[tuple[str, int, int]]] = defaultdict(list)  # dir → (이름, cid, 크기)
    for fid, did, nm, size, status, hstat, full in con.execute(
            "SELECT file_id, dir_id, name, size, status, hash_status, full_hash FROM files WHERE seen_run=?",
            (run_id,)):
        if status != "ok" or hstat == "error":
            cid = -fid
        elif size == 0:
            cid = EMPTY
        elif hstat == "ok" and full in hash_id:
            cid = hash_id[full]
        else:
            cid = -fid
        direct[did].append((norm_name(nm), cid, size))

    # ── 아래에서 위로: 파일 수·용량·깨끗함·구조 해시·내용 집합 ─────────
    nfiles: dict[int, int] = {}
    nbytes: dict[int, int] = {}
    clean: dict[int, bool] = {}
    ahash: dict[int, str] = {}
    bset: dict[int, frozenset] = {}
    bad: dict[int, bool] = {}  # 고유 내용이나 못 읽은 부분이 있음
    for d in sorted(parent, key=lambda d: -depth[d]):
        fl = direct.get(d, [])
        nf = len(fl)
        nb = sum(s for _, _, s in fl)
        b = (not listed_ok[d]) or any(c < 0 for _, c, _ in fl)
        kids = children.get(d, [])
        for c in kids:
            nf += nfiles[c]
            nb += nbytes[c]
            b = b or bad[c]
        nfiles[d], nbytes[d], bad[d] = nf, nb, b
        clean[d] = nf > 0 and not b
        if clean[d]:
            entries = [f"f\x00{nn}\x00{cid}" for nn, cid, _ in fl]
            entries += [f"d\x00{norm_name(name[c])}\x00{ahash[c]}" for c in kids if nfiles[c] > 0]
            entries.sort()
            ahash[d] = hashlib.blake2b("\n".join(entries).encode("utf-8", "surrogatepass"),
                                       digest_size=20).hexdigest()
            s = {cid for _, cid, _ in fl}
            for c in kids:
                if nfiles[c] > 0:
                    s |= bset[c]
            bset[d] = frozenset(s)

    eligible = {d for d in parent if clean[d] and nbytes[d] > 0}

    def ancestors(d: int):
        p = parent[d]
        while p is not None:
            yield p
            p = parent.get(p)

    # ── (a)(b) 묶음: 내용 집합이 같은 폴더끼리. 서로 조상·자손이면 위쪽만 남긴다 ──
    by_set: dict[frozenset, list[int]] = defaultdict(list)
    for d in eligible:
        by_set[bset[d]].append(d)
    groups: list[list[int]] = []
    for members in by_set.values():
        if len(members) < 2:
            continue
        mset = set(members)
        kept = [m for m in members if not any(a in mset for a in ancestors(m))]
        if len(kept) >= 2:
            groups.append(sorted(kept, key=lambda d: _key(path[d])))
    member_of = {m for g in groups for m in g}

    # ── 포함 관계 계산 준비: 오일러 순회 번호와 내용별 위치 ──────────────
    tin: dict[int, int] = {}
    tout: dict[int, int] = {}
    t = 0
    for r in sorted((d for d in parent if parent[d] is None or parent[d] not in parent),
                    key=lambda d: _key(path[d])):
        stack = [(r, False)]
        while stack:
            d, done = stack.pop()
            if done:
                tout[d] = t - 1
                continue
            tin[d] = t
            t += 1
            stack.append((d, True))
            for c in reversed(children.get(d, [])):
                stack.append((c, False))
    occ_dirs: dict[int, list[int]] = defaultdict(list)
    for d, fl in direct.items():
        for _, cid, _ in fl:
            if cid >= 0:
                occ_dirs[cid].append(d)
    occ_tin = {c: sorted(tin[d] for d in ds) for c, ds in occ_dirs.items()}

    def in_subtree(x: int, root: int) -> bool:
        return tin[root] <= tin[x] <= tout[root]

    def subtree_has(x: int, cid: int) -> bool:
        arr = occ_tin[cid]
        i = bisect_left(arr, tin[x])
        return i < len(arr) and arr[i] <= tout[x]

    def find_outers(d: int) -> list[int]:
        s = bset[d]
        anc = set(ancestors(d))
        order = sorted(s, key=lambda c: (len(occ_dirs[c]), c))
        cand: set[int] = set()
        for dd in occ_dirs[order[0]]:
            if in_subtree(dd, d):
                continue
            x: int | None = dd
            while x is not None and x not in cand and x not in anc:
                cand.add(x)
                x = parent.get(x)
        for c in order[1:]:
            if not cand:
                return []
            cand = {x for x in cand if subtree_has(x, c)}
        if not cand:
            return []
        parents_of = {parent[y] for y in cand}
        minimal = [x for x in cand if x not in parents_of]
        strict = [x for x in minimal if not (clean[x] and bset[x] == s)]
        return sorted(strict, key=lambda x: _key(path[x]))

    # ── 위에서 아래로: 접기와 포함 관계 ─────────────────────────────
    blocked: dict[int, bool] = {}
    covering: dict[int, bool] = {}
    contains: dict[int, list[int]] = {}
    for d in sorted(parent, key=lambda d: (depth[d], _key(path[d]))):
        p = parent[d]
        b = p is not None and p in blocked and (blocked[p] or covering[p])
        blocked[d] = b
        if b:
            covering[d] = False
            continue
        cov = d in member_of
        if d in eligible:
            outs = find_outers(d)
            if outs:
                contains[d] = outs
                cov = True
        covering[d] = cov

    # ── 결과 적기 ─────────────────────────────────────────────────
    st = FolderStats()
    shown_groups = []
    for g in groups:
        unblocked = [m for m in g if not blocked[m]]
        if len(unblocked) >= 2:
            shown = [(m, "보고") for m in unblocked]
        elif len(unblocked) == 1:
            ref = min((m for m in g if blocked[m]), key=lambda d: _key(path[d]))
            shown = sorted([(unblocked[0], "보고"), (ref, "참고")], key=lambda x: _key(path[x[0]]))
        else:
            continue
        shown_groups.append(shown)
    shown_groups.sort(key=lambda sh: (-nbytes[sh[0][0]], _key(path[sh[0][0]])))
    redundant: set[int] = set()  # 없애도 내용이 다른 곳에 남는 폴더 (용량 추정용)
    for no, shown in enumerate(shown_groups, 1):
        classes: dict[str, int] = {}
        for m, _ in shown:
            classes.setdefault(ahash[m], len(classes) + 1)
        level = "a" if len(classes) == 1 else "b"
        first = shown[0][0]
        con.execute("INSERT INTO folder_groups(run_id, group_no, level, file_count, total_bytes, member_count)"
                    " VALUES(?,?,?,?,?,?)", (run_id, no, level, nfiles[first], nbytes[first], len(shown)))
        con.executemany("INSERT INTO folder_members(run_id, group_no, dir_id, a_class, role) VALUES(?,?,?,?,?)",
                        [(run_id, no, m, classes[ahash[m]], role) for m, role in shown])
        st.groups += 1
        st.groups_a += level == "a"
        st.groups_b += level == "b"
        st.nested_pairs += len(shown) - 1
        reported = [m for m, role in shown if role == "보고"]
        redundant.update(reported if len(reported) < len(shown) else reported[1:])
    for d in sorted(contains, key=lambda d: _key(path[d])):
        for x in contains[d]:
            con.execute("INSERT INTO folder_contains(run_id, inner_dir_id, outer_dir_id, inner_files,"
                        " inner_bytes, outer_files, outer_bytes) VALUES(?,?,?,?,?,?,?)",
                        (run_id, d, x, nfiles[d], nbytes[d], nfiles[x], nbytes[x]))
            st.contains_pairs += 1
            st.nested_pairs += 1
        redundant.add(d)
    st.redundant_bytes = sum(nbytes[d] for d in redundant)
    con.commit()
    return st
