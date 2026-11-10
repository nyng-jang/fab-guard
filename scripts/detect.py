"""탐지기 v1: wafer_injected.csv 만 보고 이상 알림 후보를 만든다.

정답지(anomaly_events.csv, wafer_labels.csv)는 읽지 않는다. 채점은 scripts/score_detector.py 가 한다.

처리 순서 (replay_cycle 순서로 1로트씩, 지난 로트 정보만 쓴다)
  1) 전처리: 비어 있는 값은 '수신 오류'로 따로 기록하고, 나머지 센서로 분석을 계속한다.
  2) z 점수: 평소 기준은 앞 25로트. 공정 값은 전체 기준, 계측 값·yield는 기술 노드별 기준(ADR 0008).
     leakage_current는 로그 척도.
  3) 센서 의심: 웨이퍼 한 장의 공정 센서 하나만 |z| > SPIKE_Z 이고, 같은 로트 다른 웨이퍼는 그 센서가 평소와
     같으며(중앙값 |z| < 2, |z| > 3인 웨이퍼 없음), 그 웨이퍼의 다른 값은 모두 |z| < 3 이면 공정 이상이 아니라 센서 의심으로 분류한다.
     이 값은 로트 평균 계산에서 뺀다.
  4) 웨이퍼 규칙: 어떤 값이든 |z| > WAFER_Z.
  5) 로트 규칙: 로트 평균 z를 깨끗한 25로트의 로트 평균 분포와 비교해 |z| > LOT_Z.
  6) 일부 웨이퍼: 같은 센서로 웨이퍼 규칙에 걸린 웨이퍼가 2장 이상·로트의 절반 이하이고, 나머지 웨이퍼는
     그 센서가 평소와 같으면(평균 |z| < 1.5) 로트 전체가 아니라 해당 웨이퍼만 짚는다.
     이 웨이퍼들로 설명되는 센서는 로트 규칙에서 뺀다.
  7) 원인 후보: 로트 규칙에 걸린 공정 센서를 |z| 순으로, 그 공정 단계의 장비를 함께 붙인다.
     공정 센서 근거가 없으면(모두 |z| < EVIDENCE_Z) '원인 불명'으로 둔다.
     같은 장비·센서가 최근 RECUR_WINDOW 주기 안의 다른 알림에도 원인 후보였으면 '반복 장비'로 표시한다.

긴급/주의 등급은 아직 정하지 않았다(TODO). 알림마다 최대 |z|만 남긴다.

사용법:
    python scripts/detect.py
    python scripts/detect.py --data data/injected_keep_trend --out results/detector_v1_keep_trend
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "injected"
DEFAULT_OUT = ROOT / "results" / "detector_v1"

PROCESS_COLS = [
    "etch_rate", "pressure", "temperature", "exposure_time", "focus_offset",
    "dose", "deposition_rate", "implant_energy", "tilt_angle",
]
METROLOGY_COLS = [
    "thickness_uniformity", "critical_dimension", "oxide_thickness", "resistivity",
    "defect_count", "defect_density", "vth", "leakage_current", "resistance",
]
ALL_COLS = PROCESS_COLS + METROLOGY_COLS + ["yield"]
LOG_COLS = ["leakage_current"]

# 공정 센서가 어느 장비 단계에서 나오는 값인지
SENSOR_TOOL = {
    "etch_rate": "etch_tool", "pressure": "etch_tool", "temperature": "etch_tool",
    "exposure_time": "litho_tool", "focus_offset": "litho_tool", "dose": "litho_tool",
    "deposition_rate": "deposition_tool",
    "implant_energy": "implant_tool", "tilt_angle": "implant_tool",
}

BASELINE_N_LOTS = 25
WAFER_Z = 4.0
LOT_Z = 3.5
SPIKE_Z = 10.0
EVIDENCE_Z = 2.5
PARTIAL_MIN_WAFERS = 2
PARTIAL_REST_Z = 1.5
RECUR_WINDOW = 10


def compute_z(df: pd.DataFrame, baseline_lots: list[str]) -> pd.DataFrame:
    x = df[ALL_COLS].copy()
    for c in LOG_COLS:
        x[c] = np.log(x[c])
    base = df["lot_id"].isin(baseline_lots)
    z = pd.DataFrame(index=df.index, columns=ALL_COLS, dtype=float)
    for c in PROCESS_COLS:
        z[c] = (x[c] - x.loc[base, c].mean()) / x.loc[base, c].std()
    node_cols = METROLOGY_COLS + ["yield"]
    g = x.loc[base, node_cols].groupby(df.loc[base, "technology_node"])
    mean, std = g.mean(), g.std()
    for c in node_cols:
        z[c] = (x[c] - df["technology_node"].map(mean[c])) / df["technology_node"].map(std[c])
    return z


def find_sensor_spikes(df, z):
    """센서 하나만 튄 웨이퍼 칸을 찾는다. 반환: (행 번호, 센서) 목록."""
    spikes = []
    for i in df.index[(z[PROCESS_COLS].abs() > SPIKE_Z).any(axis=1)]:
        hot = [c for c in PROCESS_COLS if abs(z.loc[i, c]) > SPIKE_Z]
        if len(hot) != 1:
            continue
        c = hot[0]
        others = z.loc[i, [k for k in ALL_COLS if k != c]].abs()
        same_lot = (df["lot_id"] == df.loc[i, "lot_id"]) & (df.index != i)
        neighbors_high = (z.loc[same_lot, c].abs() > WAFER_Z - 1.0).sum()
        if others.max() < 3.0 and abs(z.loc[same_lot, c].median()) < 2.0 and neighbors_high == 0:
            spikes.append((i, c))
    return spikes


def run(df: pd.DataFrame):
    df = df.sort_values("replay_seq").reset_index(drop=True)
    lot_order = df.drop_duplicates("lot_id").sort_values("replay_cycle")["lot_id"].tolist()
    baseline_lots = lot_order[:BASELINE_N_LOTS]
    lot_cycle = df.groupby("lot_id")["replay_cycle"].first()

    # 1) 전처리: 수신 오류
    miss = df[ALL_COLS].isna()
    ingestion = []
    for lot, g in miss.groupby(df["lot_id"]):
        for c in ALL_COLS:
            n = int(g[c].sum())
            if n:
                ingestion.append(dict(lot_id=lot, replay_cycle=int(lot_cycle[lot]), sensor=c,
                                      missing_wafers=n, lot_wafers=len(g)))
    ingestion = pd.DataFrame(ingestion, columns=["lot_id", "replay_cycle", "sensor", "missing_wafers", "lot_wafers"])

    # 2) z 점수
    z = compute_z(df, baseline_lots)

    # 3) 센서 의심
    spikes = find_sensor_spikes(df, z)
    z_clean = z.copy()
    for i, c in spikes:
        z_clean.loc[i, c] = np.nan

    # 4) 웨이퍼 규칙
    wflag = z_clean.abs() > WAFER_Z
    wafer_rows = []
    for i in df.index[wflag.any(axis=1)]:
        cols = [c for c in ALL_COLS if wflag.loc[i, c]]
        wafer_rows.append(dict(lot_id=df.loc[i, "lot_id"], wafer_id=df.loc[i, "wafer_id"],
                               replay_cycle=int(df.loc[i, "replay_cycle"]), kind="wafer_rule",
                               sensors="|".join(cols),
                               max_abs_z=round(float(z_clean.loc[i, cols].abs().max()), 2)))
    for i, c in spikes:
        wafer_rows.append(dict(lot_id=df.loc[i, "lot_id"], wafer_id=df.loc[i, "wafer_id"],
                               replay_cycle=int(df.loc[i, "replay_cycle"]), kind="sensor_suspect",
                               sensors=c, max_abs_z=round(float(abs(z.loc[i, c])), 2)))
    wafer_flags = pd.DataFrame(wafer_rows, columns=["lot_id", "wafer_id", "replay_cycle", "kind", "sensors", "max_abs_z"])

    # 5) 로트 규칙
    lot_mean = z_clean.groupby(df["lot_id"]).mean()
    base_lot = lot_mean.loc[baseline_lots]
    lot_z = (lot_mean - base_lot.mean()) / base_lot.std()

    # 로트 순서대로 알림을 만든다 (반복 장비는 지난 알림만 본다)
    alerts = []
    history = []  # (cycle, tool, sensor)
    for lot in lot_order:
        cyc = int(lot_cycle[lot])
        m = df["lot_id"] == lot
        rows = df[m]
        lz = lot_z.loc[lot]
        tools = {t: rows[t].iloc[0] for t in set(SENSOR_TOOL.values())}
        base_info = dict(lot_id=lot, replay_cycle=cyc, process_date=rows["process_date"].iloc[0],
                         technology_node=rows["technology_node"].iloc[0])

        # 수신 오류 알림
        for _, r in ingestion[ingestion["lot_id"] == lot].iterrows():
            alerts.append({**base_info, "kind": "ingestion_error", "scope": "lot", "wafers": "",
                           "flagged_sensors": r["sensor"], "cause_sensors": "", "cause_equipment": "",
                           "cause_status": "", "recurring_equipment": "", "max_abs_z": np.nan,
                           "evidence": f"{r['sensor']} 값 {r['missing_wafers']}/{r['lot_wafers']}장 비어 있음"})

        # 센서 의심 알림
        for i, c in spikes:
            if df.loc[i, "lot_id"] != lot:
                continue
            alerts.append({**base_info, "kind": "sensor_suspect", "scope": "wafer", "wafers": df.loc[i, "wafer_id"],
                           "flagged_sensors": c, "cause_sensors": c, "cause_equipment": "",
                           "cause_status": "sensor_suspect", "recurring_equipment": "",
                           "max_abs_z": round(float(abs(z.loc[i, c])), 2),
                           "evidence": f"{df.loc[i, 'wafer_id']} {c} z={z.loc[i, c]:+.1f}, 함께 변한 값 없음, 같은 로트 다른 웨이퍼는 평소와 같음"})

        # 일부 웨이퍼: 같은 센서로 걸린 웨이퍼가 2장 이상, 로트의 절반 이하, 나머지 웨이퍼는 평소와 같음
        groups = []  # (scope, wafers, flagged, strength)
        partial_sensors = []
        for c in ALL_COLS:
            hit = wflag.loc[m, c]
            if PARTIAL_MIN_WAFERS <= hit.sum() <= m.sum() / 2:
                rest = z_clean.loc[m & ~wflag[c], c]
                if abs(rest.mean()) < PARTIAL_REST_Z:
                    partial_sensors.append(c)
        if partial_sensors:
            # 가장 강한 센서 하나를 기준으로 웨이퍼를 고른다:
            # 그 센서가 웨이퍼 규칙에 걸렸거나, 거의 걸린(|z| > WAFER_Z - 1, 같은 방향) 웨이퍼
            key = max(partial_sensors, key=lambda c: z_clean.loc[m, c].abs().max())
            zc = z_clean.loc[m, key]
            sign = np.sign(zc[wflag.loc[m, key]].mean())
            pick = (zc * sign) > (WAFER_Z - 1.0)
            wafers = rows.loc[pick[pick].index, "wafer_id"].tolist()
            sel = m & df["wafer_id"].isin(wafers)
            sub_z = z_clean.loc[sel].mean()
            flagged = [c for c in ALL_COLS if abs(sub_z[c]) > WAFER_Z - 1.0]
            groups.append(("wafer", wafers, flagged, sub_z))
            explained = set(flagged)
        else:
            explained = set()

        # 로트 규칙 (일부 웨이퍼로 설명된 센서는 뺀다)
        lot_hit = [c for c in ALL_COLS if abs(lz[c]) > LOT_Z and c not in explained]
        if lot_hit:
            groups.append(("lot", [], lot_hit, lz))

        for scope, wafers, flagged, strength in groups:
            thr = LOT_Z if scope == "lot" else WAFER_Z - 1.0
            proc = sorted([c for c in PROCESS_COLS if abs(strength[c]) > EVIDENCE_Z and c not in
                           (explained if scope == "lot" else set())],
                          key=lambda c: -abs(strength[c]))
            proc_strong = [c for c in proc if abs(strength[c]) > thr]
            cause = proc_strong or proc
            status = "candidate" if cause else "unexplained"
            equipment = [f"{tools[SENSOR_TOOL[c]]}({c})" for c in cause]
            recurring = []
            for c in cause:
                tool = tools[SENSOR_TOOL[c]]
                past = sorted({hc for hc, ht, hs in history if ht == tool and hs == c and cyc - hc <= RECUR_WINDOW})
                if past:
                    recurring.append(f"{tool}:{c}:{len(past) + 1}로트")
                history.append((cyc, tool, c))

            ev_parts = [f"{c} z={strength[c]:+.1f}" for c in sorted(flagged, key=lambda c: -abs(strength[c]))]
            prefix = "로트 평균 " if scope == "lot" else f"웨이퍼 {len(wafers)}장 평균 "
            alerts.append({**base_info, "kind": "process_anomaly", "scope": scope, "wafers": "|".join(wafers),
                           "flagged_sensors": "|".join(flagged), "cause_sensors": "|".join(cause),
                           "cause_equipment": "|".join(equipment), "cause_status": status,
                           "recurring_equipment": "|".join(recurring),
                           "max_abs_z": round(float(strength[flagged].abs().max()), 2),
                           "evidence": prefix + ", ".join(ev_parts)})

    alerts = pd.DataFrame(alerts)
    return alerts, wafer_flags, ingestion, lot_z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    df = pd.read_csv(args.data / "wafer_injected.csv", float_precision="round_trip")
    alerts, wafer_flags, ingestion, lot_z = run(df)

    args.out.mkdir(parents=True, exist_ok=True)
    alerts.to_csv(args.out / "alerts.csv", index=False)
    wafer_flags.to_csv(args.out / "wafer_flags.csv", index=False)
    lot_z.round(3).to_csv(args.out / "lot_z.csv")
    # 분석글 단계(Claude API)에 넘길 근거 묶음
    records = json.loads(alerts.to_json(orient="records", force_ascii=False))
    (args.out / "alerts.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"알림 {len(alerts)}건 → {args.out}")
    print(alerts["kind"].value_counts().to_string())


if __name__ == "__main__":
    main()
