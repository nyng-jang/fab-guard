"""알림 등급: 규칙 점수를 더해 긴급(urgent) / 주의(warning) / 참고(info)를 정한다 (ADR 0018).

점수와 등급은 코드가 정한다. 같은 입력이면 항상 같은 등급이 나와야 확인 순서가 흔들리지 않는다.
분석글 AI는 이 등급을 바꾸지 않는다.

공정 이상 알림의 점수 (POINTS)
  - 원인 후보 있음(공정 센서 근거)        30
  - 원인 불명(계측 값만 변함)             20
  - 로트 규칙에서 걸린 값이 1개뿐          위 기본 점수 대신 10
  - yield 함께 하락(알림 범위의 yield z <= YIELD_DROP_Z)  +30
  - 반복 장비(같은 장비·센서가 최근 알림에도 원인 후보)    +20
  합계 >= URGENT_MIN 이면 긴급, >= WARNING_MIN 이면 주의, 그 아래는 참고.

수신 오류와 센서 의심은 점수 대신 따로 분류한다. 담당자와 할 일이 공정 이상과 다르다.
  - ingestion_error → data_check (데이터 담당 확인)
  - sensor_suspect  → sensor_check (센서 점검, 공정은 계속)

사용법 (detect.py가 자동으로 부르지만 따로 다시 매길 수도 있다):
    python scripts/grade.py --results results/detector_v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

POINTS = {
    "candidate": 30,
    "unexplained": 20,
    "single_value_lot": 10,
    "yield_drop": 30,
    "recurring_equipment": 20,
}
YIELD_DROP_Z = -3.0
URGENT_MIN = 60
WARNING_MIN = 30

GRADE_KO = {
    "urgent": "긴급", "warning": "주의", "info": "참고",
    "data_check": "수신 오류 확인", "sensor_check": "센서 점검",
}

REASON_KO = {
    "candidate": "원인 후보 있음",
    "unexplained": "원인 불명(계측 값만 변함)",
    "single_value_lot": "로트 규칙에서 걸린 값 1개뿐",
    "yield_drop": "yield 함께 하락",
    "recurring_equipment": "반복 장비",
}


def _split(v) -> list[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    return [s for s in str(v).split("|") if s]


def grade_one(a: dict) -> tuple[int | None, str, list[str]]:
    """알림 한 건 → (점수, 등급, 이유 목록). 이유는 REASON_KO 의 키."""
    if a["kind"] == "ingestion_error":
        return None, "data_check", []
    if a["kind"] == "sensor_suspect":
        return None, "sensor_check", []

    reasons = []
    flagged = _split(a.get("flagged_sensors"))
    if a.get("scope") == "lot" and len(flagged) == 1:
        reasons.append("single_value_lot")
    elif a.get("cause_status") == "unexplained":
        reasons.append("unexplained")
    else:
        reasons.append("candidate")

    yz = a.get("yield_z")
    if yz is not None and not pd.isna(yz) and float(yz) <= YIELD_DROP_Z:
        reasons.append("yield_drop")
    if _split(a.get("recurring_equipment")):
        reasons.append("recurring_equipment")

    score = sum(POINTS[r] for r in reasons)
    if score >= URGENT_MIN:
        grade = "urgent"
    elif score >= WARNING_MIN:
        grade = "warning"
    else:
        grade = "info"
    return score, grade, reasons


def grade_alerts(alerts: pd.DataFrame) -> pd.DataFrame:
    """alerts 표에 grade_score, grade, grade_reasons 열을 붙여 돌려준다."""
    alerts = alerts.copy()
    rows = [grade_one(a) for a in alerts.to_dict(orient="records")]
    alerts["grade_score"] = pd.array([r[0] for r in rows], dtype="Int64")
    alerts["grade"] = [r[1] for r in rows]
    alerts["grade_reasons"] = ["|".join(REASON_KO[k] for k in r[2]) for r in rows]
    return alerts


def write_alerts(alerts: pd.DataFrame, out: Path) -> None:
    alerts.to_csv(out / "alerts.csv", index=False)
    records = json.loads(alerts.to_json(orient="records", force_ascii=False))
    (out / "alerts.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=ROOT / "results" / "detector_v1")
    args = ap.parse_args()
    alerts = pd.read_csv(args.results / "alerts.csv")
    alerts = grade_alerts(alerts.drop(columns=[c for c in ("grade_score", "grade", "grade_reasons") if c in alerts]))
    write_alerts(alerts, args.results)
    print(alerts["grade"].map(GRADE_KO).value_counts().to_string())


if __name__ == "__main__":
    main()
