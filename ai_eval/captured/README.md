# Captured AI candidate evidence

This directory is reserved for **deliberate, bounded candidate-model evaluation evidence** against `ai_eval/golden_set.json`.

Default GitHub Actions do **not** call a live model. When a pull request changes one of these contract sources:

- `cloudflare/wandering-wave-4418/worker.js`
- `monthly_patch_parts/99z.essay-trust-layer.part`
- `ai_eval/golden_set.json`

the PR must refresh `ai_eval/captured/candidate.json` before it can pass the AI Feedback Eval gate.

`candidate.json` must be produced from the actual candidate SWSI prompt/model path using only the synthetic Golden Set cases. It must include:

- `schema_version: 1`
- `golden_set`: exact current Golden Set name
- `model`: exact current public model
- `prompt_version`: exact current guide version
- `generated_at`: non-empty timestamp
- `capture_kind: actual_candidate_model_outputs`
- `human_review_completed: true`
- `contract_fingerprint`: generated for the exact Golden Set + prompt source + public model source
- one output record for every Golden Set case
- complete `human_scores` for every rubric dimension on every case

The gate also runs the existing deterministic evaluator with `--require-human-scores`. A matching fingerprint alone is not a pass: missing cases, forbidden authoritative claims, missing uncertainty language, poor human scores, or other evaluator failures still fail closed.

## Generate a review template

```bash
python3 scripts/ai_feedback_eval.py --write-template /tmp/swsi-ai-feedback-eval.json
```

Run the synthetic cases through the **actual candidate path**, fill the output and human-score fields, then add the required metadata above. To print the exact current fingerprint:

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
root = Path.cwd()
spec = importlib.util.spec_from_file_location('gate', root / 'scripts' / 'ai_feedback_candidate_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
dataset = gate.load_json(root / 'ai_eval' / 'golden_set.json')
print(gate.contract_fingerprint(dataset))
PY
```

Place the reviewed file at:

```text
ai_eval/captured/candidate.json
```

Then run:

```bash
python3 scripts/ai_feedback_candidate_gate.py --force --outputs ai_eval/captured/candidate.json
```

## Safety boundary

Do not put real student submissions, names, phone numbers, addresses, IDs, health/case records, tokens, cookies, API keys, service-role keys, passwords, or private institutional material in this directory. The Golden Set is synthetic specifically so candidate output evidence can be reviewed without copying production user data.

This gate proves that a reviewed candidate snapshot matches the current contract and passes the defined checks. It does **not** prove that the model is universally correct, and it does not replace expert review of factual/legal content.
