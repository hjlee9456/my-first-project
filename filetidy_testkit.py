"""exe 빌드용 진입점 — 합성 정답셋 생성기 (PyInstaller: pyinstaller --onefile --name filetidy-testkit filetidy_testkit.py)."""
import sys

from testkit.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
