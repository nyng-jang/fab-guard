"""간단한 기준선 탐지기로 주입 결과를 점검한다.

목적은 탐지기 성능 자랑이 아니라 더미데이터 자체의 점검이다.
  1) 깨끗한 로트에서 오탐이 거의 없는가 (원본에 숨은 이상이 없는가)
  2) 7가지 사건이 각각 잡힐 수 있는 크기인가 (너무 쉽거나 불가능하지 않은가)

탐지 규칙 (의도적으로 단순하게):
  - 평소 기준: 앞 25로트. 공정 값은 전체 평균·σ, 계측 값·yield는 기술 노드별 평균·σ (ADR 0008)
  - 웨이퍼 규칙: 어떤 센서든 |z| > WAFER_Z
  - 로트 규칙: 로트 평균 z를 "깨끗한 로트들의 로트 평균 z" 분포(평균·σ)와 비교해 |z| > LOT_Z.
    원본은 로트 간 변동이 웨이퍼 독립 가정보다 1.5~2.8배 커서, 평균 z × √n 방식은 오탐이 많다.
  - leakage_current는 오른쪽 꼬리가 길어(왜도 2.7) 로그를 씌운 뒤 z를 계산한다.
  - 수신 오류: 값이 비어 있음 (이상 판정과 별도로 센다)

사용법:
    python scripts/validate_injection.py            # 결과를 reports/validation_report.md 에 저장
    python scripts/validate_injection.py --data data/injected_keep_trend --report reports/validation_report_keep_trend.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INJ = ROOT / "data" / "injected"
REPORT = ROOT / "reports" / "validation_report.md"

PROCESS_COLS = [
    "etch_rate", "pressure", "temperature", "exposure_time", "focus_offset",
    "dose", "deposition_rate", "implant_energy", "tilt_angle",
]
METROLOGY_COLS = [
    "thickness_uniformity", "critical_dimension", "oxide_thickness", "resistivity",
    "defect_count", "defect_density", "vth", "leakage_current", "resistance",
]
ALL_COLS = PROCESS_COLS + METROLOGY_COLS + ["yield"]
BASELINE_LOTS = [f"LOT_{i:04d}" for i in range(1, 26)]
WAFER_Z = 4.0
LOT_Z = 3.5
LOG_COLS = ["leakage_current"]


def zscores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in LOG_COLS:
        df[c] = np.log(df[c])
    clean = df[df["lot_id"].isin(BASELINE_LOTS)]
    z = pd.DataFrame(index=df.index)
    for c in PROCESS_COLS:
        z[c] = (df[c] - clean[c].mean()) / clean[c].std()
    node_mean = clean.groupby("technology_node")[METROLOGY_COLS + ["yield"]].mean()
    node_std = clean.groupby("technology_node")[METROLOGY_COLS + ["yield"]].std()
    for c in METROLOGY_COLS + ["yield"]:
        m = df["technology_node"].map(node_mean[c])
        s = df["technology_node"].map(node_std[c])
        z[c] = (df[c] - m) / s
    return z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=INJ)
    ap.add_argument("--report", type=Path, default=REPORT)
    args = ap.parse_args()
    inj, report = args.data, args.report
    df = pd.read_csv(inj / "wafer_injected.csv", float_precision="round_trip")
    labels = pd.read_csv(inj / "wafer_labels.csv", keep_default_na=False)
    events = pd.read_csv(inj / "anomaly_events.csv", keep_default_na=False)
    assert (df["lot_id"].values == labels["lot_id"].values).all()

    z = zscores(df)
    wafer_flag_cols = (z.abs() > WAFER_Z)
    wafer_flag = wafer_flag_cols.any(axis=1)
    missing = df[ALL_COLS].isna().any(axis=1)

    lot_mean = z.groupby(df["lot_id"]).mean()
    base_lots = lot_mean.loc[BASELINE_LOTS]
    lot_z = (lot_mean - base_lots.mean()) / base_lots.std()
    lot_flag_cols = lot_z.abs() > LOT_Z
    lot_flag = lot_flag_cols.any(axis=1)

    lines = [f"# 주입 데이터 점검 결과 ({inj.name})", "",
             f"기준선 탐지기: 웨이퍼 |z| > {WAFER_Z}, 로트 평균 |z| > {LOT_Z}. "
             "`python scripts/validate_injection.py` 로 다시 만들 수 있다(맨 위 사용법 참고).", ""]

    # 1) 깨끗한 구간 오탐
    is_anom = labels["is_anomaly"] == 1
    base = labels["in_baseline_period"] == 1
    clean_late = (~is_anom) & (~base)
    lot_anom = labels.groupby("lot_id")["is_anomaly"].max()
    lot_base = labels.groupby("lot_id")["in_baseline_period"].max()
    lines += ["## 1. 깨끗한 데이터에서의 오탐", "",
              "| 구간 | 웨이퍼 수 | 웨이퍼 오탐 | 로트 수 | 로트 오탐 |", "|---|---|---|---|---|"]
    for name, wm, lm in [
        ("앞 25로트 (평소 기준)", base, lot_base == 1),
        ("뒤 25로트 중 주입 안 한 곳", clean_late, (lot_base == 0) & (lot_anom == 0)),
    ]:
        lines.append(f"| {name} | {int(wm.sum())} | {int((wafer_flag & wm).sum())} | "
                     f"{int(lm.sum())} | {int((lot_flag & lm).sum())} |")
    lines.append("")
    # 웨이퍼 오탐이 있으면 어떤 센서인지 남긴다
    fp = wafer_flag & ~is_anom
    if fp.any():
        lines.append("웨이퍼 오탐 상세 (주입 안 한 웨이퍼):")
        lines.append("")
        for i in df.index[fp]:
            cols = [f"{c} z={z.loc[i, c]:+.1f}" for c in ALL_COLS if wafer_flag_cols.loc[i, c]]
            lines.append(f"- {df.loc[i, 'lot_id']} {df.loc[i, 'wafer_id']}: {', '.join(cols)}")
        lines.append("")
    lot_clean = lot_anom[lot_anom == 0].index
    lines.append(f"주입 안 한 로트의 로트 평균 |z| 최댓값: {lot_z.loc[lot_clean].abs().max().max():.2f}")
    lines.append("")

    # 2) 사건별 탐지
    lines += ["## 2. 사건별 탐지 가능성", "",
              "| 사건 | 유형 | 대상 웨이퍼 | 웨이퍼 규칙 | 로트 규칙 | 수신 오류 | 로트 규칙에 걸린 센서(최대 로트 z) |",
              "|---|---|---|---|---|---|---|"]
    for _, ev in events.iterrows():
        m = labels["event_id"] == ev["event_id"]
        lots = ev["lots"].split("|")
        wf = int((wafer_flag & m).sum())
        lf = int(lot_flag.loc[lots].sum())
        ms = int((missing & m).sum())
        sens = []
        for c in ALL_COLS:
            v = lot_z.loc[lots, c]
            if (v.abs() > LOT_Z).any():
                sens.append(f"{c} {v.abs().max():.0f}")
        lines.append(f"| {ev['event_id']} | {ev['name_ko']} | {int(m.sum())} | {wf} | "
                     f"{lf}/{len(lots)} 로트 | {ms} | {', '.join(sens) or '-'} |")
    lines.append("")

    # 드리프트: 몇 번째 로트부터 잡히는가
    e1 = events.set_index("event_id").loc["E1"]
    lines += ["### 드리프트(E1) 로트별", "",
              "| 순서 | 로트 | 주입 크기(σ) | etch_rate 로트 z | 웨이퍼 규칙 걸린 수 | 로트 규칙 |",
              "|---|---|---|---|---|---|"]
    for j, lot in enumerate(e1["lots"].split("|"), 1):
        m = df["lot_id"] == lot
        k = float(labels.loc[m, "shift_sigma"].iloc[0])
        lines.append(f"| {j} | {lot} | {k:.1f} | {lot_z.loc[lot, 'etch_rate']:+.1f} | "
                     f"{int((wafer_flag & m).sum())}/25 | {'잡힘' if lot_flag.loc[lot] else '-'} |")
    lines.append("")

    # 부분 웨이퍼: 로트 안에서 어느 웨이퍼가 걸렸는가
    m49 = df["lot_id"] == "LOT_0049"
    flagged = df.loc[m49 & wafer_flag, "wafer_id"].tolist()
    lines += ["### 일부 웨이퍼(E7)", "",
              f"LOT_0049에서 웨이퍼 규칙에 걸린 웨이퍼: {', '.join(flagged) or '없음'} "
              f"(정답: {events.set_index('event_id').loc['E7', 'wafers'].replace('|', ', ')})", ""]

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
