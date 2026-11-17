"""Mini NPU Simulator - MAC 연산으로 Cross / X 패턴을 판별한다. (표준 라이브러리만 사용)"""
import json
import os
import sys
import time

EPSILON = 1e-9
REPEAT = 10
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


# ---------- 라벨 정규화 ----------
def normalize_label(raw):
    """'+', 'cross' -> Cross / 'x' -> X. 알 수 없으면 None."""
    key = str(raw).strip().lower()
    if key in ("+", "cross"):
        return "Cross"
    if key == "x":
        return "X"
    return None


# ---------- MAC 연산 ----------
def mac(pattern, filt):
    """위치별 곱셈 후 누적 합 (반복문 직접 구현)."""
    n = len(pattern)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += pattern[i][j] * filt[i][j]
    return total


def measure(pattern, filt, repeat=REPEAT):
    """MAC 연산 구간만 repeat회 측정한 평균 시간(ms)."""
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filt)
    return (time.perf_counter() - start) / repeat * 1000


def judge(score_a, score_b, label_a="A", label_b="B"):
    if abs(score_a - score_b) < EPSILON:
        return "UNDECIDED"
    return label_a if score_a > score_b else label_b


# ---------- 패턴 생성기 (보너스) ----------
def make_cross(n):
    mid = n // 2
    return [[1 if i == mid or j == mid else 0 for j in range(n)] for i in range(n)]


def make_x(n):
    return [[1 if i == j or i + j == n - 1 else 0 for j in range(n)] for i in range(n)]


# ---------- 모드 1 ----------
def read_matrix(title, n=3):
    print(f"{title} ({n}줄 입력, 공백 구분)")
    while True:
        rows = []
        try:
            for _ in range(n):
                parts = input().split()
                if len(parts) != n:
                    raise ValueError
                rows.append([float(p) for p in parts])
            return rows
        except ValueError:
            print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요. 처음부터 다시 입력합니다.")


def mode_user():
    print("\n#----------------------------------------\n# [1] 필터 입력\n#----------------------------------------")
    a = read_matrix("필터 A")
    print()
    b = read_matrix("필터 B")
    print("✓ 필터 A, B 저장 완료")
    print("\n#----------------------------------------\n# [2] 패턴 입력\n#----------------------------------------")
    p = read_matrix("패턴")
    print("\n#----------------------------------------\n# [3] MAC 결과\n#----------------------------------------")
    sa, sb = mac(p, a), mac(p, b)
    print(f"A 점수: {sa}")
    print(f"B 점수: {sb}")
    print(f"연산 시간(평균/{REPEAT}회): {measure(p, a):.3f} ms")
    if judge(sa, sb) == "UNDECIDED":
        print(f"판정: 판정 불가 (|A-B| < {EPSILON})")
    else:
        print(f"판정: {judge(sa, sb)}")
    print_performance([3])


# ---------- 모드 2 ----------
def validate_matrix(m, n=None):
    if not isinstance(m, list) or not m:
        return "2차원 배열이 아님"
    for row in m:
        if not isinstance(row, list) or len(row) != len(m):
            return "정사각 2차원 배열이 아님"
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return "숫자가 아닌 값 포함"
    if n is not None and len(m) != n:
        return f"크기 불일치(필터 {n}x{n}, 패턴 {len(m)}x{len(m)})"
    return None


def load_filters(data):
    filters = {}
    print("\n#----------------------------------------\n# [1] 필터 로드\n#----------------------------------------")
    for size_key, group in data.get("filters", {}).items():
        try:
            n = int(size_key.split("_")[1])
            std = {}
            for raw_label, mat in group.items():
                label = normalize_label(raw_label)
                err = validate_matrix(mat, n)
                if label is None or err:
                    raise ValueError(err or f"알 수 없는 라벨 '{raw_label}'")
                std[label] = mat
            if set(std) != {"Cross", "X"}:
                raise ValueError("Cross/X 필터가 모두 필요함")
            filters[n] = std
            print(f"✓ {size_key} 필터 로드 완료 (Cross, X)")
        except (ValueError, IndexError, AttributeError) as e:
            print(f"✗ {size_key} 필터 로드 실패: {e}")
    return filters


def mode_json():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"data.json을 읽을 수 없습니다: {e}")
        return
    filters = load_filters(data)

    print("\n#----------------------------------------\n# [2] 패턴 분석 (라벨 정규화 적용)\n#----------------------------------------")
    total, passed, failures = 0, 0, []
    for key, item in data.get("patterns", {}).items():
        total += 1
        print(f"--- {key} ---")
        reason = None
        try:
            n = int(key.split("_")[1])
            expected = normalize_label(item["expected"])
            pat = item["input"]
            if n not in filters:
                reason = f"size_{n} 필터 없음"
            elif expected is None:
                reason = f"expected 라벨 오류({item['expected']!r})"
            else:
                reason = validate_matrix(pat, n)
        except (ValueError, IndexError, KeyError, TypeError) as e:
            reason = f"스키마 오류({e!r})"

        if reason:
            print(f"판정: 오류 | FAIL ({reason})")
            failures.append((key, reason))
            continue

        sc, sx = mac(pat, filters[n]["Cross"]), mac(pat, filters[n]["X"])
        result = judge(sc, sx, "Cross", "X")
        ok = result == expected
        print(f"Cross 점수: {sc}\nX 점수: {sx}")
        print(f"판정: {result} | expected: {expected} | {'PASS' if ok else 'FAIL'}")
        if ok:
            passed += 1
        else:
            failures.append((key, "동점(UNDECIDED) 규칙에 따라 FAIL" if result == "UNDECIDED" else f"판정 {result} != expected {expected}"))

    print_performance([3, 5, 13, 25])
    print("\n#----------------------------------------\n# [4] 결과 요약\n#----------------------------------------")
    print(f"총 테스트: {total}개\n통과: {passed}개\n실패: {len(failures)}개")
    if failures:
        print("\n실패 케이스:")
        for k, r in failures:
            print(f"- {k}: {r}")


def print_performance(sizes):
    print("\n#----------------------------------------\n# 성능 분석 (평균/10회)\n#----------------------------------------")
    print(f"{'크기':<10}{'평균 시간(ms)':<16}{'연산 횟수(N²)'}")
    print("-" * 40)
    for n in sizes:
        t = measure(make_cross(n), make_x(n))
        print(f"{f'{n}×{n}':<10}{t:<16.4f}{n * n}")


def main():
    print("=== Mini NPU Simulator ===\n\n[모드 선택]\n1. 사용자 입력 (3x3)\n2. data.json 분석")
    while True:
        choice = input("선택: ").strip()
        if choice == "1":
            return mode_user()
        if choice == "2":
            return mode_json()
        print("1 또는 2를 입력하세요.")


if __name__ == "__main__":
    try:  # 윈도우 cp949 콘솔/파이프에서도 ✓ 같은 문자가 깨지지 않게
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    main()
