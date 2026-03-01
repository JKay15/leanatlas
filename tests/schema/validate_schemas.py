#!/usr/bin/env python3
import json, sys
from pathlib import Path

try:
  import jsonschema
except Exception:
  print("[schema] jsonschema is required. Install: pip install jsonschema", file=sys.stderr)
  raise

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "docs" / "schemas"
POS = Path(__file__).resolve().parent / "fixtures" / "positive"
NEG = Path(__file__).resolve().parent / "fixtures" / "negative"

RUNREPORT = json.loads((SCHEMAS_DIR / "RunReport.schema.json").read_text(encoding="utf-8"))
RETRIEVAL = json.loads((SCHEMAS_DIR / "RetrievalTrace.schema.json").read_text(encoding="utf-8"))
ATTEMPT = json.loads((SCHEMAS_DIR / "AttemptLogLine.schema.json").read_text(encoding="utf-8"))
DEDUP = json.loads((SCHEMAS_DIR / "DedupReport.schema.json").read_text(encoding="utf-8"))
PROMOTION = json.loads((SCHEMAS_DIR / "PromotionReport.schema.json").read_text(encoding="utf-8"))
PROMOTION_PLAN = json.loads((SCHEMAS_DIR / "PromotionPlan.schema.json").read_text(encoding="utf-8"))
GC = json.loads((SCHEMAS_DIR / "GCReport.schema.json").read_text(encoding="utf-8"))
GC_PLAN = json.loads((SCHEMAS_DIR / "GCPlan.schema.json").read_text(encoding="utf-8"))
GC_STATE = json.loads((SCHEMAS_DIR / "GCState.schema.json").read_text(encoding="utf-8"))
PROBLEM_STATE = json.loads((SCHEMAS_DIR / "ProblemState.schema.json").read_text(encoding="utf-8"))
TEST_MANIFEST = json.loads((SCHEMAS_DIR / "TestManifest.schema.json").read_text(encoding="utf-8"))
AGENT_EVAL_TASK = json.loads((SCHEMAS_DIR / "AgentEvalTask.schema.json").read_text(encoding="utf-8"))
AGENT_EVAL_REPORT = json.loads((SCHEMAS_DIR / "AgentEvalReport.schema.json").read_text(encoding="utf-8"))
AGENT_EVAL_SCENARIO = json.loads((SCHEMAS_DIR / "AgentEvalScenario.schema.json").read_text(encoding="utf-8"))
AGENT_EVAL_SCENARIO_REPORT = json.loads((SCHEMAS_DIR / "AgentEvalScenarioReport.schema.json").read_text(encoding="utf-8"))
PINS_USED = json.loads((SCHEMAS_DIR / "PinsUsed.schema.json").read_text(encoding="utf-8"))
FEEDBACK_DIGEST = json.loads((SCHEMAS_DIR / "FeedbackDigest.schema.json").read_text(encoding="utf-8"))
FEEDBACK_LEDGER_LINE = json.loads((SCHEMAS_DIR / "FeedbackLedgerLine.schema.json").read_text(encoding="utf-8"))


def pick_schema(fpath: Path):
  n = fpath.name
  if n.startswith("runreport_"):
    return RUNREPORT, "RunReport"
  if n.startswith("retrievaltrace_"):
    return RETRIEVAL, "RetrievalTrace"
  if n.startswith("attemptlog_"):
    return ATTEMPT, "AttemptLogLine"
  if n.startswith("dedupreport_"):
    return DEDUP, "DedupReport"
  if n.startswith("promotionplan_"):
    return PROMOTION_PLAN, "PromotionPlan"
  if n.startswith("promotionreport_"):
    return PROMOTION, "PromotionReport"
  if n.startswith("gcplan_"):
    return GC_PLAN, "GCPlan"
  if n.startswith("gcreport_"):
    return GC, "GCReport"
  if n.startswith("gcstate_"):
    return GC_STATE, "GCState"
  if n.startswith("problemstate_"):
    return PROBLEM_STATE, "ProblemState"
  if n.startswith("testmanifest_"):
    return TEST_MANIFEST, "TestManifest"
  if n.startswith("agentevaltask_"):
    return AGENT_EVAL_TASK, "AgentEvalTask"
  if n.startswith("agentevalreport_"):
    return AGENT_EVAL_REPORT, "AgentEvalReport"
  if n.startswith("agentevalscenario_"):
    return AGENT_EVAL_SCENARIO, "AgentEvalScenario"
  if n.startswith("agentevalscenarioreport_"):
    return AGENT_EVAL_SCENARIO_REPORT, "AgentEvalScenarioReport"
  if n.startswith("pinsused_"):
    return PINS_USED, "PinsUsed"
  if n.startswith("feedbackdigest_"):
    return FEEDBACK_DIGEST, "FeedbackDigest"
  if n.startswith("feedbackledger_"):
    return FEEDBACK_LEDGER_LINE, "FeedbackLedgerLine"
  raise RuntimeError(
    f"Cannot infer schema for fixture: {n}. Prefix with runreport_, retrievaltrace_, attemptlog_, dedupreport_, promotionplan_, promotionreport_, gcplan_, gcreport_, gcstate_, problemstate_, testmanifest_, agentevaltask_, agentevalreport_, agentevalscenario_, agentevalscenarioreport_, pinsused_, feedbackdigest_, or feedbackledger_."
  )

def validate_one(fpath: Path) -> list[str]:
  inst = json.loads(fpath.read_text(encoding="utf-8"))
  schema, sname = pick_schema(fpath)
  v = jsonschema.Draft202012Validator(schema)
  errors = sorted(v.iter_errors(inst), key=lambda e: list(e.absolute_path))
  msgs = []
  for e in errors:
    path = "/" + "/".join(str(p) for p in e.absolute_path)
    msgs.append(f"{sname}:{fpath.name}:{path}: {e.message}")
  return msgs

def main():
  bad = 0

  for f in sorted(POS.glob("*.json")):
    errs = validate_one(f)
    if errs:
      bad += 1
      print("[schema][FAIL][positive]", *errs, sep="\n  ")
    else:
      print(f"[schema][OK][positive] {f.name}")

  for f in sorted(NEG.glob("*.json")):
    errs = validate_one(f)
    if not errs:
      bad += 1
      print(f"[schema][FAIL][negative] {f.name}: expected validation errors but got none")
    else:
      print(f"[schema][OK][negative] {f.name} (got {len(errs)} errors)")
  return 1 if bad else 0

if __name__ == "__main__":
  raise SystemExit(main())
