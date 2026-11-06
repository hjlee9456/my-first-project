"""무작위 교차 검사 — 무작위로 만든 폴더 나무에서 진단기(빠른 계산)와 정답 계산기(전부 비교)가 같은 답을 내는지.

정답셋 시나리오가 놓친 모양(깊은 감싸기, 여러 겹 포함, 빈 파일 섞임 등)을 찾기 위한 시험이다.
"""
import os
import random

import pytest

from helpers import group_signature, rel_of
from scanner.scan import run_scan
from testkit.oracle import exact_dup_groups, folder_truth

# 기본 12개. 더 세게 돌릴 때: FILETIDY_RANDOM_SEEDS=300 pytest tests/test_random_trees.py
SEEDS = int(os.environ.get("FILETIDY_RANDOM_SEEDS", "12"))


def _make_tree(seed: int, root: str) -> list[dict]:
    r = random.Random(seed)
    files: dict[str, str] = {}  # 상대 경로 → 내용 이름
    n = 0

    def new_content():
        nonlocal n
        n += 1
        return "empty" if r.random() < 0.05 else f"c{seed}-{n}"

    def folder(prefix, depth):
        for i in range(r.randrange(1, 4)):
            files[f"{prefix}/f{i}.txt"] = new_content()
        if depth < 3:
            for j in range(r.randrange(0, 3)):
                folder(f"{prefix}/d{j}", depth + 1)

    for top in ("A", "B", "C"):
        folder(top, 0)
    for k in range(r.randrange(3, 8)):
        dirs = sorted({p.rsplit("/", 1)[0] for p in files})
        src = r.choice(dirs)
        sub = {p: c for p, c in files.items() if p.startswith(src + "/")}
        dst_parent = r.choice(["A", "B", "C"]) + f"/copy{k}"
        mode = r.choice(["same", "same", "wrap", "extra", "flat", "partial"])
        if mode == "wrap":
            dst_parent += "/감쌈"
        for p, c in sub.items():
            relp = p[len(src) + 1:]
            if mode == "flat":
                relp = relp.replace("/", "_")
            if mode == "partial" and r.random() < 0.3:
                continue
            files[f"{dst_parent}/{relp}"] = c
        if mode == "extra":
            files[f"{dst_parent}/추가{k}.txt"] = new_content()
    out = []
    for p, c in sorted(files.items()):
        full = os.path.join(root, *p.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        data = b"" if c == "empty" else c.encode()
        with open(full, "xb") as f:
            f.write(data)
        out.append({"path": p, "content": c, "size": len(data)})
    return out


@pytest.mark.parametrize("seed", range(SEEDS))
def test_scanner_matches_oracle(tmp_path, seed):
    root = str(tmp_path / "t")
    files = _make_tree(seed, root)
    sims = [(d, os.path.join(root, d)) for d in ("A", "B", "C")]
    res = run_scan([], str(tmp_path / "out"), simulated=sims, use_default_excludes=False,
                   progress=lambda *_: None)
    import sqlite3
    con = sqlite3.connect(res.db_path)
    rel = lambda p: rel_of(root, p)  # noqa: E731
    dup = {}
    for no, p in con.execute("SELECT m.group_no, f.path FROM dup_members m JOIN files f USING(file_id)"):
        dup.setdefault(no, set()).add(rel(p))
    groups = {}
    for no, level, p, ac, role in con.execute(
            """SELECT g.group_no, g.level, d.path, m.a_class, m.role FROM folder_groups g
               JOIN folder_members m ON m.group_no=g.group_no JOIN dirs d ON d.dir_id=m.dir_id"""):
        groups.setdefault(no, {"level": level, "members": []})["members"].append(
            {"path": rel(p), "role": role, "a_class": ac})
    contains = {(rel(a), rel(b)) for a, b in con.execute(
        """SELECT di.path, dx.path FROM folder_contains c JOIN dirs di ON di.dir_id=c.inner_dir_id
           JOIN dirs dx ON dx.dir_id=c.outer_dir_id""")}
    con.close()
    truth = folder_truth(files)
    assert {frozenset(g) for g in dup.values()} == {frozenset(g) for g in exact_dup_groups(files)}
    assert {group_signature(g) for g in groups.values()} == {group_signature(g) for g in truth["folder_groups"]}
    assert contains == {(c["inner"], c["outer"]) for c in truth["folder_contains"]}
