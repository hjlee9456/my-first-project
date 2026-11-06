"""검사 제외 목록 (인계서 5장 규칙 12).

제외 경로(--exclude): 그 폴더와 그 아래 전부. 예) D:\\옛날\\설치파일
제외 패턴(--exclude-pattern): 드라이브 맨 위 기준, 대소문자 무시, 구분자는 / 와 \\ 모두 가능
    /Windows                드라이브 맨 위의 Windows 폴더
    /Users/*/AppData        * 는 폴더 이름 하나
    **/$Recycle.Bin         ** 는 아무 깊이
    node_modules            / 로 시작하지 않으면 아무 깊이 (**/node_modules 와 같음)
이 프로그램의 출력 폴더와, 표지 파일(.filetidy-output)이 든 폴더(예전 출력)도 자동 제외한다.
"""
from __future__ import annotations

import fnmatch
import unicodedata

from .winpath import normalize_root

DEFAULT_EXCLUDES: tuple[str, ...] = (
    # 인계서 지정
    "/Windows",
    "/Program Files",
    "/Program Files (x86)",
    "/ProgramData",
    "/Users/*/AppData",
    "**/$Recycle.Bin",
    "**/System Volume Information",
    # 운영체제가 쓰는 드라이브 맨 위 파일·폴더 (읽으면 접근 거부만 남김)
    "/pagefile.sys",
    "/hiberfil.sys",
    "/swapfile.sys",
    "/DumpStack.log.tmp",
    "/Recovery",
    "/Config.Msi",
    "/$WinREAgent",
    "/$Windows.~BT",
    "/$Windows.~WS",
    # 예전 윈도우 설치본 안의 시스템 폴더 (사용자 문서는 검사)
    "/Windows.old/Windows",
    "/Windows.old/Program Files",
    "/Windows.old/Program Files (x86)",
    "/Windows.old/ProgramData",
    "/Windows.old/Users/*/AppData",
)


def norm_name(s: str) -> str:
    """이름 비교용: 유니코드 NFC + 대소문자 무시 (윈도우는 대소문자를 가리지 않음)."""
    return unicodedata.normalize("NFC", s).casefold()


def _match(pat: list[str], parts: list[str]) -> bool:
    if not pat:
        return not parts
    head = pat[0]
    if head == "**":
        return any(_match(pat[1:], parts[i:]) for i in range(len(parts) + 1))
    if not parts:
        return False
    return fnmatch.fnmatchcase(parts[0], head) and _match(pat[1:], parts[1:])


class Exclusions:
    def __init__(self, patterns: list[str], abs_paths: list[str]):
        self.patterns = list(patterns)
        self._pats: list[list[str]] = []
        for p in patterns:
            t = p.replace("\\", "/").strip()
            parts = [norm_name(c) for c in t.strip("/").split("/") if c]
            if not parts:
                continue
            if not t.startswith("/") and parts[0] != "**":
                parts = ["**"] + parts
            self._pats.append(parts)
        self.abs_paths = [normalize_root(a) for a in abs_paths]
        self._abs = {norm_name(a.rstrip("\\/")) for a in self.abs_paths}

    @classmethod
    def build(cls, user_paths: list[str], user_patterns: list[str], use_defaults: bool,
              output_dir: str | None) -> "Exclusions":
        pats: list[str] = (list(DEFAULT_EXCLUDES) if use_defaults else []) + list(user_patterns)
        abss: list[str] = list(user_paths)
        if output_dir:
            abss.append(output_dir)
        return cls(pats, abss)

    def match(self, full_path: str, parts_from_anchor: list[str]) -> str | None:
        """제외 대상이면 사유 글을, 아니면 None."""
        if self._abs and norm_name(full_path.rstrip("\\/")) in self._abs:
            return "제외 경로"
        np = [norm_name(c) for c in parts_from_anchor]
        for pat in self._pats:
            if _match(pat, np):
                return "제외 목록"
        return None
