import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def pytest_collection_modifyitems(config, items):
    if os.environ.get("FILETIDY_SCALE"):
        return
    skip = pytest.mark.skip(reason="규모 시험은 FILETIDY_SCALE=파일묶음수 를 줄 때만 실행")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def base_dataset(tmp_path_factory):
    """기본 합성 정답셋(시드 42)을 한 번 만들어 여러 시험이 함께 쓴다. 읽기만 할 것."""
    from testkit.generator import generate
    out = tmp_path_factory.mktemp("정답셋") / "set"
    info = generate(str(out), seed=42)
    return info
