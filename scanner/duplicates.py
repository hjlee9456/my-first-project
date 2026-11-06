"""3. 완전 중복 묶기 — 내용(전체 해시)이 같은 파일끼리 묶는다.

0바이트 파일은 묶지 않고 따로 센다(내용이 없으니 '같다'는 말이 의미 없음).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DupStats:
    groups: int = 0
    files_in_groups: int = 0
    redundant_copies: int = 0
    reclaimable_bytes: int = 0
    zero_byte_files: int = 0


def analyze(con, run_id: int) -> DupStats:
    rows = con.execute(
        "SELECT full_hash, size, file_id, path FROM files "
        "WHERE seen_run=? AND size>0 AND hash_status='ok' AND full_hash IS NOT NULL",
        (run_id,)).fetchall()
    by_hash: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
    for h, size, fid, path in rows:
        by_hash[(h, size)].append((path, fid))
    groups = [(h, size, sorted(m)) for (h, size), m in by_hash.items() if len(m) > 1]
    # 회수 가능 용량이 큰 묶음부터 번호를 매긴다 (같으면 첫 경로 순)
    groups.sort(key=lambda g: (-(len(g[2]) - 1) * g[1], g[2][0][0]))
    st = DupStats()
    for no, (h, size, members) in enumerate(groups, 1):
        reclaim = (len(members) - 1) * size
        con.execute("INSERT INTO dup_groups(run_id, group_no, full_hash, size, member_count, reclaimable)"
                    " VALUES(?,?,?,?,?,?)", (run_id, no, h, size, len(members), reclaim))
        con.executemany("INSERT INTO dup_members(run_id, group_no, file_id) VALUES(?,?,?)",
                        [(run_id, no, fid) for _, fid in members])
        st.groups += 1
        st.files_in_groups += len(members)
        st.redundant_copies += len(members) - 1
        st.reclaimable_bytes += reclaim
    st.zero_byte_files = con.execute(
        "SELECT COUNT(*) FROM files WHERE seen_run=? AND size=0", (run_id,)).fetchone()[0]
    con.commit()
    return st
