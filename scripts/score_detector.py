"""탐지기 결과(results/.../alerts.csv)를 정답지와 비교해 채점한다.

정답지: anomaly_events.csv(사건 단위), wafer_labels.csv(웨이퍼 단위). 탐지기는 정답지를 보지 않는다.

채점 항목
  1) 웨이퍼 단위: 알림이 짚은 웨이퍼(로트 알림이면 로트 전체, 웨이퍼 알림이면 그 웨이퍼) vs is_anomaly
  2) 로트 단위: 알림이 난 로트 vs 이상을 심은 로트. 깨끗한 로트의 알림은 오탐
  3) 사건 단위: 잡혔는지, 기대한 분류로 잡혔는지, 원인 후보가 정답 센서·장비를 맞혔는지,
     드리프트(E1)는 몇 번째 로트(몇 σ)부터 잡았는지, 일부 웨이퍼(E7)는 웨이퍼를 얼마나 정확히 짚었는지

사용법:
    python scripts/score_detector.py
    python scripts/score_detector.py --data data/injected_keep_trend --results results/detector_v1_keep_trend \\
        --report reports/score_detector_v1_keep_trend.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "injected"
DEFAULT_RESULTS = ROOT / "results" / "detector_v1"
DEFAULT_REPORT = ROOT / "reports" / "score_detector_v1.md"

# 사건 유형별로 "제대로 잡았다"고 볼 알림 모양
EXPECTED = {
    "drift": dict(kind="process_anomaly", scope="lot"),
    "step_change": dict(kind="process_anomaly", scope="lot"),
    "sensor_spike": dict(kind="sensor_suspect", scope="wafer"),
    "ingestion_error": dict(kind="ingestion_error", scope="lot"),
    "shared_equipment": dict(kind="process_anomaly", scope="lot"),
    "unexplained_defect": dict(kind="process_anomaly", scope="lot", cause_status="unexplained"),
    "partial_wafer": dict(kind="process_anomaly", scope="wafer"),
}


def split(v) -> list[str]:
    return [x for x in str(v).split("|") if x and x != "nan"] if pd.notna(v) else []


def alert_wafers(a: pd.Series, labels: pd.DataFrame) -> set[tuple[str, str]]:
    if a["scope"] == "wafer":
        return {(a["lot_id"], w) for w in split(a["wafers"])}
    ws = labels.loc[labels["lot_id"] == a["lot_id"], "wafer_id"]
    return {(a["lot_id"], w) for w in ws}


def pct(n, d):
    return f"{n / d * 100:.1f}%" if d else "-"


def score(data: Path, results: Path):
    labels = pd.read_csv(data / "wafer_labels.csv", keep_default_na=False)
    events = pd.read_csv(data / "anomaly_events.csv", keep_default_na=False)
    alerts = pd.read_csv(results / "alerts.csv", keep_default_na=True)
    alerts["wafers"] = alerts["wafers"].fillna("")

    out = {}
    # 1) 웨이퍼 단위
    pred = set()
    for _, a in alerts.iterrows():
        pred |= alert_wafers(a, labels)
    truth = set(map(tuple, labels.loc[labels["is_anomaly"] == 1, ["lot_id", "wafer_id"]].values))
    allw = set(map(tuple, labels[["lot_id", "wafer_id"]].values))
    tp, fp, fn = len(pred & truth), len(pred - truth), len(truth - pred)
    tn = len(allw) - tp - fp - fn
    out["wafer"] = dict(tp=tp, fp=fp, fn=fn, tn=tn, recall=tp / (tp + fn), precision=tp / (tp + fp) if tp + fp else 0,
                        false_positive_rate=fp / (fp + tn))

    # 2) 로트 단위
    lot_anom = labels.groupby("lot_id")["is_anomaly"].max()
    lot_base = labels.groupby("lot_id")["in_baseline_period"].max()
    alerted = set(alerts["lot_id"])
    clean_lots = lot_anom[lot_anom == 0].index
    fp_lots = sorted(set(clean_lots) & alerted)
    out["lot"] = dict(
        anomaly_lots=int((lot_anom == 1).sum()),
        anomaly_lots_alerted=int(sum(l in alerted for l in lot_anom[lot_anom == 1].index)),
        clean_lots=len(clean_lots),
        clean_lots_baseline=int(((lot_anom == 0) & (lot_base == 1)).sum()),
        clean_lots_late=int(((lot_anom == 0) & (lot_base == 0)).sum()),
        false_alert_lots=fp_lots,
        false_alerts=[dict(lot_id=r["lot_id"], kind=r["kind"], evidence=r["evidence"])
                      for _, r in alerts[alerts["lot_id"].isin(fp_lots)].iterrows()],
    )

    # 3) 사건 단위
    ev_rows = []
    for _, ev in events.iterrows():
        lots = split(ev["lots"])
        exp = EXPECTED[ev["anomaly_type"]]
        ev_alerts = alerts[alerts["lot_id"].isin(lots)]
        match = ev_alerts[(ev_alerts["kind"] == exp["kind"]) & (ev_alerts["scope"] == exp["scope"])]
        if "cause_status" in exp:
            match_ok = match[match["cause_status"] == exp["cause_status"]]
        else:
            match_ok = match
        lots_hit = sorted(set(match["lot_id"]))
        injected = set(split(ev["injected_sensors"]))
        r = dict(event_id=ev["event_id"], type=ev["anomaly_type"], name_ko=ev["name_ko"],
                 lots=len(lots), lots_detected=len(lots_hit), detected=bool(lots_hit),
                 classified_ok=bool(len(match_ok)))
        # 원인 센서: 수신 오류는 flagged_sensors, 나머지는 cause_sensors 첫 후보(1순위)와 후보 전체
        col = "flagged_sensors" if ev["anomaly_type"] == "ingestion_error" else "cause_sensors"
        if ev["anomaly_type"] == "unexplained_defect":
            r["cause_sensor_top1"] = None
            r["cause_sensor_any"] = None
            r["said_unexplained"] = bool(len(match_ok))
        elif len(match):
            top1 = [split(v)[0] for v in match[col] if split(v)]
            anyc = [set(split(v)) for v in match[col]]
            r["cause_sensor_top1"] = sum(t in injected for t in top1) / len(match)
            r["cause_sensor_any"] = sum(bool(s & injected) for s in anyc) / len(match)
        else:
            r["cause_sensor_top1"] = r["cause_sensor_any"] = 0.0
        if ev["cause_equipment"]:
            eq = ev["cause_equipment"]
            r["cause_equipment_hit"] = sum(eq in str(v) for v in match["cause_equipment"]) / len(match) if len(match) else 0.0
            rec = [v for v in match["recurring_equipment"].fillna("") if eq in v]
            first_rec = match.loc[match["recurring_equipment"].fillna("").str.contains(eq), "lot_id"]
            r["recurring_flag_from"] = first_rec.iloc[0] if len(first_rec) else None
        if ev["anomaly_type"] == "drift":
            first = None
            for j, lot in enumerate(lots, 1):
                if lot in lots_hit:
                    k = labels.loc[labels["lot_id"] == lot, "shift_sigma"].iloc[0]
                    first = dict(order=j, lot_id=lot, shift_sigma=float(k))
                    break
            r["first_detected"] = first
        if ev["anomaly_type"] == "partial_wafer":
            tw = set(split(ev["wafers"]))
            pw = set()
            for v in match["wafers"]:
                pw |= set(split(v))
            r["wafers_true"] = sorted(tw)
            r["wafers_pred"] = sorted(pw)
            r["wafer_recall"] = len(tw & pw) / len(tw)
            r["wafer_precision"] = len(tw & pw) / len(pw) if pw else 0.0
            other = ev_alerts[~ev_alerts.index.isin(match.index)]
            r["other_alerts_same_lot"] = [f"{a['kind']}/{a['scope']}: {a['evidence']}" for _, a in other.iterrows()]
        ev_rows.append(r)
    out["events"] = ev_rows
    return out, alerts


def fmt_ratio(v):
    return "-" if v is None else f"{v * 100:.0f}%"


def render(out, data: Path, results: Path) -> str:
    w, l = out["wafer"], out["lot"]
    ev = out["events"]
    n_ok = sum(e["classified_ok"] for e in ev)
    L = [f"# 탐지기 v1 채점 결과 ({data.name})", "",
         f"탐지기 결과 `{results.relative_to(ROOT)}`를 `{data.relative_to(ROOT)}`의 정답지와 비교했습니다. "
         "`python scripts/detect.py` → `python scripts/score_detector.py` 로 다시 만들 수 있습니다.", "",
         "## 요약", "",
         f"- 사건 {len(ev)}개 중 {sum(e['detected'] for e in ev)}개 탐지, {n_ok}개는 기대한 분류까지 맞음",
         f"- 웨이퍼 단위: 탐지율(재현율) {pct(w['tp'], w['tp'] + w['fn'])} ({w['tp']}/{w['tp'] + w['fn']}), "
         f"정밀도 {pct(w['tp'], w['tp'] + w['fp'])}, 깨끗한 웨이퍼 오탐 {w['fp']}/{w['fp'] + w['tn']}장",
         f"- 로트 단위: 이상 로트 {l['anomaly_lots_alerted']}/{l['anomaly_lots']}개에 알림, "
         f"깨끗한 로트 {l['clean_lots']}개 중 {len(l['false_alert_lots'])}개 오탐"
         f"(앞 25로트 {l['clean_lots_baseline']}개, 뒤쪽 {l['clean_lots_late']}개)", ""]

    L += ["## 사건별", "",
          "| 사건 | 유형 | 탐지 로트 | 기대한 분류 | 원인 센서 1순위 적중 | 원인 장비 적중 | 비고 |",
          "|---|---|---|---|---|---|---|"]
    for e in ev:
        note = []
        if e.get("first_detected"):
            f = e["first_detected"]
            note.append(f"{f['order']}번째 로트 {f['lot_id']}({f['shift_sigma']:.1f}σ)부터 잡음")
        elif e["type"] == "drift":
            note.append("못 잡음")
        if e.get("recurring_flag_from"):
            note.append(f"반복 장비 표시는 {e['recurring_flag_from']}부터")
        if e["type"] == "unexplained_defect":
            note.append("'원인 불명'으로 분류함" if e["said_unexplained"] else "'원인 불명'으로 분류 못 함")
        if e["type"] == "partial_wafer":
            note.append(f"짚은 웨이퍼 {', '.join(e['wafers_pred']) or '없음'} "
                        f"(재현율 {fmt_ratio(e['wafer_recall'])}, 정밀도 {fmt_ratio(e['wafer_precision'])})")
        eq = fmt_ratio(e["cause_equipment_hit"]) if "cause_equipment_hit" in e else "-"
        L.append(f"| {e['event_id']} | {e['name_ko']} | {e['lots_detected']}/{e['lots']} | "
                 f"{'맞음' if e['classified_ok'] else '틀림'} | {fmt_ratio(e['cause_sensor_top1'])} | {eq} | "
                 f"{'; '.join(note) or '-'} |")
    L.append("")
    L += ["원인 센서 적중은 그 사건으로 낸 알림 중 1순위 원인 후보가 심은 센서인 비율입니다. "
          "E6은 심은 공정 센서가 없으므로 '원인 불명'이라고 했는지만 봅니다.", ""]

    part = next((e for e in ev if e["type"] == "partial_wafer"), None)
    if part and part["other_alerts_same_lot"]:
        L += ["같은 로트(E7)에서 함께 나온 다른 알림:", ""]
        L += [f"- {s}" for s in part["other_alerts_same_lot"]]
        L.append("")

    L += ["## 깨끗한 로트의 오탐", ""]
    if l["false_alerts"]:
        L += ["| 로트 | 알림 종류 | 근거 |", "|---|---|---|"]
        L += [f"| {a['lot_id']} | {a['kind']} | {a['evidence']} |" for a in l["false_alerts"]]
    else:
        L.append("없음")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args()
    data, results = args.data.resolve(), args.results.resolve()
    out, _ = score(data, results)
    text = render(out, data, results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text, encoding="utf-8")
    (results / "score.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
