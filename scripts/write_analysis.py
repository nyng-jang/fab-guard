"""탐지기 알림의 근거 묶음으로 분석글을 쓴다 (ADR 0004, 0013).

AI는 글만 쓴다. 이상 여부와 원인 후보 계산은 탐지기(scripts/detect.py)가 이미 끝냈고,
AI에게는 그 결과와 수치(근거 묶음)만 넘긴다. 정답지는 읽지 않는다.

제공자 (환경 변수 LLM_PROVIDER 또는 --provider)
  gemini    기본값. GEMINI_API_KEY 필요, 모델은 GEMINI_MODEL (기본 gemini-2.5-flash)
  claude    ANTHROPIC_API_KEY 필요, 모델은 CLAUDE_MODEL (기본 claude-sonnet-5-5)
  template  AI 없이 탐지기 결과를 정해진 문장에 채워 넣는 기준선. 키 없이 돌아가고, AI 분석글과 비교하는 용도

사용법:
    python scripts/write_analysis.py                          # 기본 로트(E1·E2·E6에 해당하는 알림), gemini
    python scripts/write_analysis.py --provider template
    python scripts/write_analysis.py --lots LOT_0031,LOT_0035
    python scripts/write_analysis.py --all                    # 수신 오류를 뺀 모든 알림
    python scripts/write_analysis.py --dry-run                # 호출 없이 프롬프트만 저장

산출물: results/analyses/<provider>/<lot_id>.json, .md   (--dry-run 이면 results/analyses/prompts/)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "injected"
DEFAULT_RESULTS = ROOT / "results" / "detector_v1"
DEFAULT_OUT = ROOT / "results" / "analyses"

# E2(급변), E6(원인 불명), E1(드리프트) 첫 탐지 로트와 마지막 로트.
# 로트 번호로만 고르며, 탐지기와 분석글 단계는 정답지를 보지 않는다.
DEFAULT_LOTS = ["LOT_0031", "LOT_0035", "LOT_0036", "LOT_0043"]

TOOL_COLS = ["etch_tool", "litho_tool", "deposition_tool", "implant_tool"]
EVIDENCE_Z = 2.5   # 이보다 작은 |z|는 근거로 쓰지 말라고 AI에게 알린다 (detect.py 와 같은 값)
HISTORY_WINDOW = 10

SYSTEM_PROMPT = """당신은 반도체 공정 이상 알림의 분석글을 쓰는 보조자입니다.
규칙:
1. 아래 [근거 묶음]에 있는 숫자와 사실만 씁니다. 묶음에 없는 센서, 장비, 수치, 공정 지식을 원인으로 내세우지 않습니다.
2. z는 평소(앞 25로트) 대비 표준편차 배수입니다. 공정 센서의 |z|가 2.5보다 작으면 원인 근거로 쓰지 않습니다.
3. 계측 값(결함 수, CD 등)이나 yield만 나빠지고 공정 센서에 근거가 없으면 verdict를 "unexplained"로 하고 본문에 "원인 불명"이라고 분명히 씁니다. 추측으로 원인을 만들지 않습니다.
4. 탐지기가 센서 의심이나 수신 오류로 분류했으면 공정 원인을 찾지 말고 그 분류를 설명합니다.
5. 같은 장비가 최근 다른 알림에도 원인 후보였으면 반복 여부를 언급합니다.
6. 한국어로, 담당 엔지니어가 3분 안에 읽을 분량(본문 5~10문장)으로 씁니다.

출력은 JSON 하나만 씁니다. 다른 글은 쓰지 않습니다.
{
  "verdict": "cause_candidate" | "unexplained" | "sensor_suspect" | "ingestion_error",
  "cause_sensors": ["원인 후보 공정 센서, 강한 순서, 없으면 빈 목록"],
  "cause_equipment": ["원인 후보 장비 ID, 없으면 빈 목록"],
  "confidence": "high" | "medium" | "low",
  "title": "한 줄 제목",
  "body_markdown": "본문 (Markdown)",
  "evidence_cited": ["본문에서 근거로 쓴 수치, 예: temperature z=+18.7"],
  "next_checks": ["담당자가 확인할 것 1~3개"]
}"""


def split(v) -> list[str]:
    return [x for x in str(v).split("|") if x and x != "nan"] if v not in (None, "") else []


def build_bundle(lot: str, alerts: list[dict], lot_z: pd.DataFrame, df: pd.DataFrame) -> dict:
    rows = df[df["lot_id"] == lot]
    cyc = int(rows["replay_cycle"].iloc[0])
    lot_alerts = [a for a in alerts if a["lot_id"] == lot]
    z = lot_z.loc[lot].round(1)
    strong = {c: float(v) for c, v in z.items() if abs(v) >= EVIDENCE_Z}
    history = []
    for a in alerts:
        if cyc - HISTORY_WINDOW <= a["replay_cycle"] < cyc and a["kind"] == "process_anomaly":
            history.append(dict(lot_id=a["lot_id"], replay_cycle=a["replay_cycle"],
                                cause_sensors=split(a["cause_sensors"]),
                                cause_equipment=split(a["cause_equipment"]), evidence=a["evidence"]))
    return dict(
        lot_id=lot, replay_cycle=cyc, process_date=rows["process_date"].iloc[0],
        technology_node=rows["technology_node"].iloc[0], product_type=rows["product_type"].iloc[0],
        wafers=len(rows), equipment={t: rows[t].iloc[0] for t in TOOL_COLS},
        detector_alerts=[{k: a[k] for k in ("kind", "scope", "wafers", "flagged_sensors", "cause_sensors",
                                             "cause_equipment", "cause_status", "recurring_equipment",
                                             "max_abs_z", "evidence")} for a in lot_alerts],
        lot_mean_z_abs_ge_2_5=strong,
        recent_alerts=history,
        notes=["공정 센서: etch_rate, pressure, temperature(식각), exposure_time, focus_offset, dose(노광), "
               "deposition_rate(증착), implant_energy, tilt_angle(이온 주입)",
               "계측 값과 yield는 결과 값이라 원인이 아닌 영향으로 봅니다."],
    )


def user_prompt(bundle: dict) -> str:
    return "[근거 묶음]\n" + json.dumps(bundle, ensure_ascii=False, indent=2) + "\n\n위 규칙대로 이 알림의 분석글을 JSON으로 써 주세요."


def http_json(url: str, body: dict, headers: dict, retries: int = 3) -> dict:
    data = json.dumps(body).encode()
    for k in range(retries):
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 503) and k < retries - 1:
                time.sleep(10 * (k + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}") from None
    raise RuntimeError("unreachable")


def call_gemini(system: str, user: str) -> tuple[str, str]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY 환경 변수가 없습니다. --provider template 또는 --dry-run 으로 먼저 확인할 수 있습니다.")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    r = http_json(url, body, {"x-goog-api-key": key})
    text = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    return text, model


def call_claude(system: str, user: str) -> tuple[str, str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY 환경 변수가 없습니다.")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
    body = {"model": model, "max_tokens": 2000, "temperature": 0.2, "system": system,
            "messages": [{"role": "user", "content": user}]}
    r = http_json("https://api.anthropic.com/v1/messages", body,
                  {"x-api-key": key, "anthropic-version": "2023-06-01"})
    text = "".join(b.get("text", "") for b in r["content"] if b.get("type") == "text")
    return text, model


def template_analysis(bundle: dict) -> dict:
    """AI 없이 탐지기 결과를 문장에 채워 넣는다. AI 분석글과 비교하는 기준선."""
    a = next((x for x in bundle["detector_alerts"] if x["kind"] == "process_anomaly"), bundle["detector_alerts"][0])
    status = a["cause_status"] or a["kind"]
    verdict = {"candidate": "cause_candidate"}.get(status, status)
    sensors = split(a["cause_sensors"])
    equipment = [e.split("(")[0] for e in split(a["cause_equipment"])]
    lines = [f"{bundle['lot_id']}({bundle['process_date']}, {bundle['technology_node']})에서 {a['evidence']}."]
    if verdict == "cause_candidate":
        lines.append(f"원인 후보는 {', '.join(sensors)}이고, 해당 장비는 {', '.join(dict.fromkeys(equipment))}입니다.")
        if a["recurring_equipment"]:
            lines.append(f"최근 알림에서도 같은 장비·센서가 원인 후보였습니다: {a['recurring_equipment']}.")
    elif verdict == "unexplained":
        lines.append("공정 센서에는 근거가 없어 원인 불명입니다.")
    return dict(verdict=verdict, cause_sensors=sensors, cause_equipment=list(dict.fromkeys(equipment)),
                confidence="medium", title=f"{bundle['lot_id']} {a['kind']}", body_markdown=" ".join(lines),
                evidence_cited=[a["evidence"]], next_checks=[])


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("응답에서 JSON을 찾지 못함")
    return json.loads(m.group(0))


def to_markdown(lot: str, provider: str, model: str, r: dict) -> str:
    L = [f"# {r.get('title', lot)}", "",
         f"- 로트: {lot} · 판정: {r.get('verdict')} · 확신: {r.get('confidence')} · 작성: {provider}({model})",
         f"- 원인 후보 센서: {', '.join(r.get('cause_sensors') or []) or '없음'}",
         f"- 원인 후보 장비: {', '.join(r.get('cause_equipment') or []) or '없음'}", "",
         r.get("body_markdown", ""), ""]
    if r.get("evidence_cited"):
        L += ["**인용한 근거**", ""] + [f"- {e}" for e in r["evidence_cited"]] + [""]
    if r.get("next_checks"):
        L += ["**확인할 것**", ""] + [f"- {e}" for e in r["next_checks"]] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "gemini"),
                    choices=["gemini", "claude", "template"])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--lots", default=",".join(DEFAULT_LOTS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=4.0, help="호출 사이 대기(초). 무료 등급 분당 한도 대비")
    args = ap.parse_args()

    alerts = json.loads((args.results / "alerts.json").read_text(encoding="utf-8"))
    lot_z = pd.read_csv(args.results / "lot_z.csv", index_col=0)
    df = pd.read_csv(args.data / "wafer_injected.csv")
    if args.all:
        lots = list(dict.fromkeys(a["lot_id"] for a in alerts if a["kind"] != "ingestion_error"))
    else:
        lots = [x.strip() for x in args.lots.split(",") if x.strip()]
    missing = [l for l in lots if not any(a["lot_id"] == l for a in alerts)]
    if missing:
        raise SystemExit(f"알림이 없는 로트: {missing}")

    out = args.out / ("prompts" if args.dry_run else args.provider)
    out.mkdir(parents=True, exist_ok=True)
    for n, lot in enumerate(lots):
        bundle = build_bundle(lot, alerts, lot_z, df)
        up = user_prompt(bundle)
        if args.dry_run:
            (out / f"{lot}.txt").write_text(SYSTEM_PROMPT + "\n\n---\n\n" + up, encoding="utf-8")
            print(f"{lot}: 프롬프트 저장")
            continue
        if args.provider == "template":
            r, model, raw = template_analysis(bundle), "-", ""
        else:
            if n:
                time.sleep(args.sleep)
            raw, model = (call_gemini if args.provider == "gemini" else call_claude)(SYSTEM_PROMPT, up)
            r = parse_json(raw)
        record = dict(lot_id=lot, provider=args.provider, model=model, bundle=bundle, analysis=r, raw_response=raw)
        (out / f"{lot}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / f"{lot}.md").write_text(to_markdown(lot, args.provider, model, r), encoding="utf-8")
        print(f"{lot}: {r.get('verdict')} / {r.get('cause_sensors')} / {r.get('cause_equipment')}")


if __name__ == "__main__":
    main()
