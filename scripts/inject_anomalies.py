"""archive.zip 합성 데이터에 정답을 아는 이상 7종을 심어 검증용 더미데이터를 만든다.

사용법:
    python scripts/inject_anomalies.py
    python scripts/inject_anomalies.py --input data/raw/semiconductor_yield_forecasting_data.csv --out data/injected --seed 42
    python scripts/inject_anomalies.py --background keep --out data/injected_keep_trend   # 원본의 시간 추세를 남긴 변형

산출물 (out 폴더):
    wafer_injected.csv  원본과 같은 컬럼 + replay_seq, replay_cycle. 정답 정보는 들어 있지 않다.
    anomaly_events.csv  정답지(사건 단위)
    wafer_labels.csv    정답지(웨이퍼 단위)

설계 근거: docs/adr/0002, docs/adr/0008, docs/adr/0009
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "semiconductor_yield_forecasting_data.csv"
DEFAULT_OUT = ROOT / "data" / "injected"
DEFAULT_SEED = 42

# 앞 25로트(2023-01-01 ~ 01-25)는 깨끗하게 두고 평소 기준으로 쓴다.
BASELINE_LOTS = [f"LOT_{i:04d}" for i in range(1, 26)]

PROCESS_COLS = [
    "etch_rate", "pressure", "temperature", "exposure_time", "focus_offset",
    "dose", "deposition_rate", "implant_energy", "tilt_angle",
]
METROLOGY_COLS = [
    "thickness_uniformity", "critical_dimension", "oxide_thickness", "resistivity",
    "defect_count", "defect_density", "vth", "leakage_current", "resistance",
]

# 원본에는 50일에 걸쳐 여러 센서가 함께 서서히 움직이는 추세가 들어 있다(ADR 0009).
# 기본값(remove)은 이 추세를 선형으로 걷어내 "평소"를 정상 상태로 만든 뒤 이상을 심는다.
# 로그 척도로 걷어낼 센서는 LOG_TREND_COLS (값이 음수가 되지 않게).
TREND_COLS = [
    "etch_rate", "pressure", "temperature", "focus_offset", "deposition_rate",
    "thickness_uniformity", "defect_count", "defect_density", "leakage_current",
]
LOG_TREND_COLS = ["leakage_current"]

# ---------------------------------------------------------------------------
# 시나리오 설정. 크기는 표준편차(σ) 배수이며 출발값이다(ADR 0002).
# 공정 값 σ는 깨끗한 25로트 전체 기준, 계측 값·yield σ는 기술 노드별 기준(ADR 0008).
# 너무 쉽거나 어려우면 여기 숫자만 바꾸고 다시 돌리면 된다.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "E1": dict(
        type="drift", name_ko="서서히 변함(드리프트)",
        lots=[27, 29, 36, 37, 39, 41, 42, 43], equipment="ETCH_04",
        sensor="etch_rate", k_start=0.5, k_end=4.0,
        coupled={"critical_dimension": 0.6},  # etch_rate 1σ당 CD +0.6σ
        yield_drop_per_k=0.5,                 # etch_rate 1σ당 yield -0.5σ
        severity="warning_to_urgent",
        expected="몇 번째 로트부터 잡는지 측정, 원인 후보 ETCH_04 / etch_rate",
    ),
    "E2": dict(
        type="step_change", name_ko="급변",
        lots=[31], sensor="temperature", k=5.0,
        coupled={"oxide_thickness": 0.5},
        yield_drop_per_k=0.5,
        severity="urgent",
        expected="긴급 후보, 원인 후보 temperature",
    ),
    "E3": dict(
        type="sensor_spike", name_ko="센서 튐",
        lots=[33], n_wafers=1, sensor="pressure", factor=10.0,
        severity="sensor_suspect",
        expected="공정 이상이 아니라 센서 의심으로 분류(함께 변한 값 없음)",
    ),
    "E4": dict(
        type="ingestion_error", name_ko="수신 오류",
        lots=[38], sensor="deposition_rate",
        severity="ingestion_error",
        expected="'수신 오류' 별도 알림, 나머지 센서 분석은 계속",
    ),
    "E5": dict(
        type="shared_equipment", name_ko="장비 공통 문제",
        lots=[44, 46, 48], equipment="LITHO_01",
        sensors={"focus_offset": 3.0, "exposure_time": 2.5},
        coupled={"critical_dimension": 2.0},
        yield_drop=2.0,
        severity="urgent",
        expected="여러 로트의 공통 장비 LITHO_01을 원인 후보로",
    ),
    "E6": dict(
        type="unexplained_defect", name_ko="원인 불명 결함",
        lots=[35], sensors=["defect_count", "defect_density"], k=5.0,
        yield_drop=1.5,
        severity="warning",
        expected="공정 값 근거가 없으면 '원인 불명'이라고 말하는지",
    ),
    "E7": dict(
        type="partial_wafer", name_ko="일부 웨이퍼만",
        lots=[49], wafers=[f"W{i:03d}" for i in range(20, 26)],
        sensor="implant_energy", k=4.0,
        coupled={"vth": 0.6},
        yield_drop_per_k=0.4,
        severity="warning",
        expected="로트 전체가 아니라 웨이퍼 W020~W025만 짚는지",
    ),
}


def remove_background_trend(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """로트 평균을 날짜 순번에 선형 회귀해 그 기울기만큼 빼낸다. 전체 평균은 그대로 둔다."""
    df = df.copy()
    day = df["lot_id"].str[-4:].astype(int)
    center = day.mean()
    rows = []
    for c in TREND_COLS:
        vals = np.log(df[c]) if c in LOG_TREND_COLS else df[c]
        lot_mean = vals.groupby(day).mean()
        slope, _ = np.polyfit(lot_mean.index.to_numpy(), lot_mean.to_numpy(), 1)
        corr = float(np.corrcoef(lot_mean.index, lot_mean.to_numpy())[0, 1])
        adjusted = vals - slope * (day - center)
        df[c] = np.exp(adjusted) if c in LOG_TREND_COLS else adjusted
        rows.append(dict(sensor=c, scale="log" if c in LOG_TREND_COLS else "linear",
                         slope_per_lot=slope, lot_mean_corr_with_day=round(corr, 3),
                         change_over_50_lots_in_sigma=round(slope * 49 / vals.std(), 2)))
    df["defect_count"] = df["defect_count"].round()
    return df, pd.DataFrame(rows)


def lot_id(n: int) -> str:
    return f"LOT_{n:04d}"


def build_baseline(df: pd.DataFrame) -> dict:
    clean = df[df["lot_id"].isin(BASELINE_LOTS)]
    proc_std = clean[PROCESS_COLS].std()
    node_std = clean.groupby("technology_node")[METROLOGY_COLS + ["yield"]].std()
    # 깨끗한 25로트에 없는 노드가 생기면 전체 σ로 대신한다.
    overall = clean[METROLOGY_COLS + ["yield"]].std()
    for node in df["technology_node"].unique():
        if node not in node_std.index:
            node_std.loc[node] = overall
    return {"proc_std": proc_std, "node_std": node_std}


def node_sigma(base: dict, df: pd.DataFrame, idx, col: str) -> pd.Series:
    return df.loc[idx, "technology_node"].map(base["node_std"][col])


def shift_metrology(df, idx, base, coupled: dict, k: float):
    for col, per_k in coupled.items():
        df.loc[idx, col] += per_k * k * node_sigma(base, df, idx, col)


def drop_yield(df, idx, base, sigmas: float):
    df.loc[idx, "yield"] -= sigmas * node_sigma(base, df, idx, "yield")
    df.loc[idx, "yield"] = df.loc[idx, "yield"].clip(lower=0.01)


def inject(df: pd.DataFrame, seed: int):
    rng = np.random.default_rng(seed)
    df = df.copy()
    base = build_baseline(df)
    proc_std = base["proc_std"]
    events, labels = [], []

    def label(idx, eid, sc, sensors, k_sigma, note=""):
        for i in idx:
            labels.append(dict(
                row=i, event_id=eid, anomaly_type=sc["type"],
                injected_sensors="|".join(sensors), shift_sigma=round(float(k_sigma), 3),
                intended_severity=sc["severity"], note=note,
            ))

    # 각 이상에는 웨이퍼마다 작은 흔들림(σ의 10%)을 더해 너무 깔끔하지 않게 한다.
    def jitter(n):
        return rng.normal(0.0, 0.1, size=n)

    # E1 드리프트: 로트 순서대로 k_start → k_end 선형 증가
    sc = SCENARIOS["E1"]
    ks = np.linspace(sc["k_start"], sc["k_end"], len(sc["lots"]))
    for n, k in zip(sc["lots"], ks):
        idx = df.index[df["lot_id"] == lot_id(n)]
        assert (df.loc[idx, "etch_tool"] == sc["equipment"]).all(), f"{lot_id(n)} is not {sc['equipment']}"
        df.loc[idx, sc["sensor"]] += (k + jitter(len(idx))) * proc_std[sc["sensor"]]
        shift_metrology(df, idx, base, sc["coupled"], k)
        drop_yield(df, idx, base, sc["yield_drop_per_k"] * k)
        label(idx, "E1", sc, [sc["sensor"]], k)

    # E2 급변
    sc = SCENARIOS["E2"]
    idx = df.index[df["lot_id"] == lot_id(sc["lots"][0])]
    df.loc[idx, sc["sensor"]] += (sc["k"] + jitter(len(idx))) * proc_std[sc["sensor"]]
    shift_metrology(df, idx, base, sc["coupled"], sc["k"])
    drop_yield(df, idx, base, sc["yield_drop_per_k"] * sc["k"])
    label(idx, "E2", sc, [sc["sensor"]], sc["k"])

    # E3 센서 튐: 웨이퍼 1장을 시드로 골라 값만 10배. 연동 값은 건드리지 않는다.
    sc = SCENARIOS["E3"]
    lot_idx = df.index[df["lot_id"] == lot_id(sc["lots"][0])]
    idx = rng.choice(lot_idx, size=sc["n_wafers"], replace=False)
    before = df.loc[idx, sc["sensor"]].to_numpy()
    df.loc[idx, sc["sensor"]] *= sc["factor"]
    k_equiv = float(((df.loc[idx, sc["sensor"]].to_numpy() - before) / proc_std[sc["sensor"]]).mean())
    label(idx, "E3", sc, [sc["sensor"]], k_equiv, note=f"x{sc['factor']:g}")
    e3_wafers = df.loc[idx, "wafer_id"].tolist()

    # E4 수신 오류: 값을 비운다(0으로 채우지 않음)
    sc = SCENARIOS["E4"]
    idx = df.index[df["lot_id"] == lot_id(sc["lots"][0])]
    df.loc[idx, sc["sensor"]] = np.nan
    label(idx, "E4", sc, [sc["sensor"]], 0.0, note="missing")

    # E5 장비 공통 문제
    sc = SCENARIOS["E5"]
    for n in sc["lots"]:
        idx = df.index[df["lot_id"] == lot_id(n)]
        assert (df.loc[idx, "litho_tool"] == sc["equipment"]).all(), f"{lot_id(n)} is not {sc['equipment']}"
        for col, k in sc["sensors"].items():
            df.loc[idx, col] += (k + jitter(len(idx))) * proc_std[col]
        shift_metrology(df, idx, base, sc["coupled"], 1.0)
        drop_yield(df, idx, base, sc["yield_drop"])
        label(idx, "E5", sc, list(sc["sensors"]), max(sc["sensors"].values()))

    # E6 원인 불명 결함: 결함 수만 늘고 공정 값은 그대로
    sc = SCENARIOS["E6"]
    idx = df.index[df["lot_id"] == lot_id(sc["lots"][0])]
    add_count = (sc["k"] + jitter(len(idx))) * node_sigma(base, df, idx, "defect_count")
    ratio = (df.loc[idx, "defect_count"] + add_count) / df.loc[idx, "defect_count"]
    df.loc[idx, "defect_count"] = (df.loc[idx, "defect_count"] * ratio).round()
    df.loc[idx, "defect_density"] *= ratio  # 밀도는 개수와 같은 비율로
    drop_yield(df, idx, base, sc["yield_drop"])
    label(idx, "E6", sc, sc["sensors"], sc["k"])

    # E7 일부 웨이퍼만
    sc = SCENARIOS["E7"]
    idx = df.index[(df["lot_id"] == lot_id(sc["lots"][0])) & (df["wafer_id"].isin(sc["wafers"]))]
    assert len(idx) == len(sc["wafers"])
    df.loc[idx, sc["sensor"]] += (sc["k"] + jitter(len(idx))) * proc_std[sc["sensor"]]
    shift_metrology(df, idx, base, sc["coupled"], sc["k"])
    drop_yield(df, idx, base, sc["yield_drop_per_k"] * sc["k"])
    label(idx, "E7", sc, [sc["sensor"]], sc["k"])

    df["defect_count"] = df["defect_count"].astype(int)

    # 사건 단위 정답지
    for eid, sc in SCENARIOS.items():
        lots = [lot_id(n) for n in sc["lots"]]
        if eid == "E3":
            wafers = "|".join(e3_wafers)
        elif eid == "E7":
            wafers = "|".join(sc["wafers"])
        else:
            wafers = "ALL"
        if "sensors" in sc:
            sensors = sc["sensors"] if isinstance(sc["sensors"], list) else list(sc["sensors"])
        else:
            sensors = [sc["sensor"]]
        coupled = list(sc.get("coupled", {}))
        if "yield_drop" in sc or "yield_drop_per_k" in sc:
            coupled.append("yield")
        lot_rows = df[df["lot_id"].isin(lots)]
        if "equipment" in sc:
            cause_equipment = sc["equipment"]
        else:
            cause_equipment = ""
        if eid == "E1":
            magnitude = f"{sc['k_start']}σ→{sc['k_end']}σ"
        elif eid == "E3":
            magnitude = f"x{sc['factor']:g}"
        elif eid == "E4":
            magnitude = "missing"
        elif eid == "E5":
            magnitude = ", ".join(f"{c} +{k}σ" for c, k in sc["sensors"].items())
        else:
            magnitude = f"+{sc['k']}σ"
        events.append(dict(
            event_id=eid, anomaly_type=sc["type"], name_ko=sc["name_ko"],
            lots="|".join(lots), wafers=wafers,
            start_date=lot_rows["process_date"].min(), end_date=lot_rows["process_date"].max(),
            injected_sensors="|".join(sensors), coupled_sensors="|".join(coupled),
            cause_equipment=cause_equipment, magnitude=magnitude,
            intended_severity=sc["severity"], expected_response=sc["expected"],
        ))

    # 웨이퍼 단위 정답지 (한 웨이퍼에 사건이 겹치지 않게 설계했으므로 1:1)
    lab = pd.DataFrame(labels)
    assert not lab["row"].duplicated().any(), "한 웨이퍼에 사건이 두 개 겹쳤다"
    wl = df[["lot_id", "wafer_id", "process_date", "technology_node"]].copy()
    wl["is_anomaly"] = 0
    wl = wl.join(lab.set_index("row"))
    wl.loc[wl["event_id"].notna(), "is_anomaly"] = 1
    wl["in_baseline_period"] = wl["lot_id"].isin(BASELINE_LOTS).astype(int)
    wl = wl.fillna({"event_id": "", "anomaly_type": "", "injected_sensors": "",
                    "intended_severity": "", "note": ""})

    return df, pd.DataFrame(events), wl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--background", choices=["remove", "keep"], default="remove",
                    help="원본의 시간 추세를 걷어낼지(remove, 기본) 남길지(keep)")
    args = ap.parse_args()

    raw = pd.read_csv(args.input, float_precision="round_trip")
    raw = raw.sort_values(["process_date", "lot_id", "wafer_id"]).reset_index(drop=True)
    trend = None
    if args.background == "remove":
        raw, trend = remove_background_trend(raw)
    injected, events, labels = inject(raw, args.seed)

    injected.insert(0, "replay_seq", np.arange(1, len(injected) + 1))
    injected.insert(1, "replay_cycle", injected["lot_id"].str[-4:].astype(int))  # 1로트 = 1주기

    args.out.mkdir(parents=True, exist_ok=True)
    injected.to_csv(args.out / "wafer_injected.csv", index=False)
    events.to_csv(args.out / "anomaly_events.csv", index=False)
    labels.to_csv(args.out / "wafer_labels.csv", index=False)
    if trend is not None:
        trend.to_csv(args.out / "background_trend_removed.csv", index=False)

    n_anom = int(labels["is_anomaly"].sum())
    print(f"background={args.background}  seed={args.seed}  wafers={len(injected)}  anomalous={n_anom}  events={len(events)}")
    print(events[["event_id", "anomaly_type", "lots", "wafers", "magnitude"]].to_string(index=False))


if __name__ == "__main__":
    main()
