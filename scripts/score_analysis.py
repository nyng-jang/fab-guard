"""분석글(results/analyses/<provider>/*.json)을 정답지와 비교해 채점한다.

채점 항목 (분석글마다)
  - 판정: E6(원인 불명 결함)은 "unexplained", 그 밖의 공정 이상은 "cause_candidate"여야 맞음
  - 원인 센서: 1순위가 심은 센서인가, 후보 중에 심은 센서가 있는가
  - 원인 장비: 정답 장비가 있는 사건(E1 ETCH_04, E5 LITHO_01)에서 맞혔는가
  - 근거 밖 주장: 원인으로 쓴 센서가 근거 묶음에서 |z| < 2.5이거나, 장비가 그 로트의 장비가 아니면 근거 밖
  - E6에서 본문에 "원인 불명"이라는 말을 썼는가

사용법:
    python scripts/score_analysis.py --provider gemini
    python scripts/score_analysis.py --provider template
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "injected"
DEFAULT_IN = ROOT / "results" / "analyses"
PROCESS_COLS = [
    "etch_rate", "pressure", "temperature", "exposure_time", "focus_offset",
    "dose", "deposition_rate", "implant_energy", "tilt_angle",
]
EVIDENCE_Z = 2.5


def split(v) -> list[str]:
    return [x for x in str(v).split("|") if x]


def score(data: Path, folder: Path) -> list[dict]:
    events = pd.read_csv(data / "anomaly_events.csv", keep_default_na=False)
    lot_event = {}
    for _, ev in events.iterrows():
        for lot in split(ev["lots"]):
            lot_event[lot] = ev
    rows = []
    for f in sorted(folder.glob("LOT_*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        a, b = rec["analysis"], rec["bundle"]
        lot = rec["lot_id"]
        sensors = [s for s in (a.get("cause_sensors") or [])]
        equipment = [e for e in (a.get("cause_equipment") or [])]
        z = b["lot_mean_z_abs_ge_2_5"]
        tools = set(b["equipment"].values())
        outside = [s for s in sensors if s not in z or abs(z[s]) < EVIDENCE_Z]
        outside += [s for s in sensors if s not in PROCESS_COLS and s not in outside]
        outside += [e for e in equipment if e not in tools]
        r = dict(lot_id=lot, provider=rec["provider"], model=rec["model"], verdict=a.get("verdict"),
                 confidence=a.get("confidence"), cause_sensors=sensors, cause_equipment=equipment,
                 outside_evidence=outside)
        ev = lot_event.get(lot)
        if ev is None:
            r.update(event_id="-", expected_verdict="(정답 없음: 이상을 심지 않은 로트)")
        else:
            injected = set(split(ev["injected_sensors"]))
            exp = "unexplained" if ev["anomaly_type"] == "unexplained_defect" else "cause_candidate"
            r.update(event_id=ev["event_id"], expected_verdict=exp, verdict_ok=a.get("verdict") == exp)
            if exp == "cause_candidate":
                r["sensor_top1_ok"] = bool(sensors) and sensors[0] in injected
                r["sensor_any_ok"] = bool(set(sensors) & injected)
            else:
                r["said_unexplained"] = "원인 불명" in (a.get("body_markdown") or "")
            if ev["cause_equipment"]:
                r["equipment_ok"] = ev["cause_equipment"] in equipment
        rows.append(r)
    return rows


def yn(v):
    return "-" if v is None else ("맞음" if v else "틀림")


def render(rows: list[dict], provider: str) -> str:
    graded = [r for r in rows if r["event_id"] != "-"]
    n_ok = sum(r["verdict_ok"] for r in graded)
    n_out = sum(bool(r["outside_evidence"]) for r in rows)
    L = [f"# 분석글 채점 결과 ({provider})", "",
         "`python scripts/write_analysis.py --provider " + provider + "` → `python scripts/score_analysis.py --provider "
         + provider + "` 로 다시 만들 수 있습니다.", "",
         f"- 분석글 {len(rows)}개, 정답이 있는 {len(graded)}개 중 판정 맞음 {n_ok}개",
         f"- 근거 밖 주장이 있는 분석글: {n_out}개", "",
         "| 로트 | 사건 | 모델 | 판정 | 기대 판정 | 판정 맞음 | 원인 센서 1순위 | 원인 장비 | 근거 밖 주장 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        sens = yn(r.get("sensor_top1_ok")) if "sensor_top1_ok" in r else (
            "원인 불명이라고 씀" if r.get("said_unexplained") else ("원인 불명이라고 안 씀" if "said_unexplained" in r else "-"))
        L.append(f"| {r['lot_id']} | {r['event_id']} | {r['model']} | {r['verdict']} | {r['expected_verdict']} | "
                 f"{yn(r.get('verdict_ok'))} | {sens} | {yn(r.get('equipment_ok'))} | "
                 f"{', '.join(r['outside_evidence']) or '없음'} |")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--in", dest="inp", type=Path, default=DEFAULT_IN)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    folder = args.inp / args.provider
    rows = score(args.data, folder)
    if not rows:
        raise SystemExit(f"{folder} 에 분석글이 없습니다. 먼저 scripts/write_analysis.py 를 돌리세요.")
    text = render(rows, args.provider)
    report = args.report or ROOT / "reports" / f"score_analysis_{args.provider}.md"
    report.write_text(text, encoding="utf-8")
    (folder / "score.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
