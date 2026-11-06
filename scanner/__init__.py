"""업무 PC 파일 정리 — 1단계 진단기 (읽기 전용).

검사 대상 파일은 읽기만 한다. 결과(DB·보고서)는 출력 폴더에만 쓰며,
쓰기는 scanner/output.py 한 곳에서만 한다 (tests/test_safety_static.py 가 검사).
"""
__version__ = "0.1.0"
TOOL_NAME = "filetidy-scan"
