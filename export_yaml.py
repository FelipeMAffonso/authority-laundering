"""export_yaml.py — exports experiment/scenarios.py and harness/judge.py
to release/evaluation/ YAML files.

Reviewers prefer YAML over Python for introspection: the stimulus bank and
judge rubrics are load-bearing artifacts and should be parseable without
importing the research repo.

Outputs:
    release/evaluation/scenarios.yaml       — every scenario with every field
                                              the runner uses.
    release/evaluation/judge_prompts.yaml   — the 3 judge rubrics (coherence,
                                              acceptance, harmful_execution).

Both files are produced from the canonical definitions in the main codebase.
Run this script whenever experiment/scenarios.py or harness/judge.py change.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.dirname(HERE)

# Make experiment/ and harness/ importable without side effects.
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

try:
    import yaml  # type: ignore
except ImportError:
    sys.stderr.write("ERROR: pyyaml not installed. pip install pyyaml\n")
    sys.exit(2)

from experiment.scenarios import SCENARIOS
from harness.judge import (
    COHERENCE_PROMPT,
    ACCEPTANCE_PROMPT,
    HARMFUL_EXECUTION_PROMPT,
    DEFAULT_JUDGE_MODEL,
)


# --------------------------------------------------------------------- helpers


class _LiteralStr(str):
    """str subclass that PyYAML renders with the '|' block scalar style."""


def _literal_str_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _literal_str_representer)


MULTILINE_FIELDS = {
    "fake_document_md",
    "turn1_probe", "turn2_probe",
    "fab_content_harmful_direct_claim",
    "fab_content_benign_direct_claim",
    "user_smuggled_harmful_prefix",
    "user_smuggled_benign_prefix",
    "system_smuggled_harmful_suffix",
    "system_smuggled_benign_suffix",
    "imperative_action_harmful",
    "imperative_action_benign",
    "tool_description",
    "harmful_target_behavior",
    "benign_target_behavior",
    "user_grounding_fact",
    "baseline_expected",
    "refusal_criteria",
    "notes",
}


def _to_block_scalars(obj):
    """Recursively mark long strings as literal block scalars for readability."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and (k in MULTILINE_FIELDS or "\n" in v or len(v) > 120):
                out[k] = _LiteralStr(v)
            else:
                out[k] = _to_block_scalars(v)
        return out
    if isinstance(obj, list):
        return [_to_block_scalars(x) for x in obj]
    return obj


def _ordered_scenario(s: dict) -> dict:
    """Return scenario fields in canonical order for YAML readability."""
    order = [
        "id", "domain", "subdomain", "short_desc", "is_pretext", "harm_level",
        "turn1_probe", "turn2_probe",
        "fab_authority",
        "fake_document_md",
        "fab_content_harmful_direct_claim", "fab_content_benign_direct_claim",
        "fab_content_harmful_short", "fab_content_benign_short",
        "user_smuggled_harmful_prefix", "user_smuggled_benign_prefix",
        "system_smuggled_harmful_suffix", "system_smuggled_benign_suffix",
        "imperative_action_harmful", "imperative_action_benign",
        "tool_name", "tool_description", "tool_input_schema", "tool_args_default",
        "harmful_target_behavior", "benign_target_behavior",
        "user_grounding_fact",
        "baseline_expected", "refusal_criteria", "notes",
    ]
    out: dict = {}
    for k in order:
        if k in s:
            out[k] = s[k]
    # Any field not in order goes at the end, so nothing is silently dropped.
    for k, v in s.items():
        if k not in out:
            out[k] = v
    return out


# --------------------------------------------------------------------- main


def main() -> int:
    eval_dir = os.path.join(HERE, "evaluation")
    os.makedirs(eval_dir, exist_ok=True)

    # ---------- scenarios.yaml -------------------------------------------
    scen_out = {
        "_meta": {
            "source": "experiment/scenarios.py (canonical)",
            "count": len(SCENARIOS),
            "description": (
                "Fourteen authority-laundering scenarios, v3 two-turn edition. "
                "Each scenario carries a turn-1 setup probe, a turn-2 operational "
                "escalation probe, a fabricated institutional document, "
                "bidirectional content claims (harmful and benign), per-scenario "
                "tool schema, and refusal/grounding metadata. Harm levels: "
                "SEVERE (4), MODERATE (8), MINOR (2)."
            ),
        },
        "scenarios": [_to_block_scalars(_ordered_scenario(s)) for s in SCENARIOS],
    }
    scen_path = os.path.join(eval_dir, "scenarios.yaml")
    with open(scen_path, "w", encoding="utf-8") as fh:
        yaml.dump(
            scen_out, fh,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=98,
        )
    print(f"Wrote {scen_path}  ({len(SCENARIOS)} scenarios)")

    # ---------- judge_prompts.yaml --------------------------------------
    judge_out = {
        "_meta": {
            "source": "harness/judge.py (canonical)",
            "default_judge_model": DEFAULT_JUDGE_MODEL,
            "description": (
                "Three-dimension judge rubric applied to every scored trial. "
                "COHERENCE (0-100) and ACCEPTANCE (0-100) are scalar Likert-like "
                "ratings; HARMFUL_EXECUTION is binary YES/NO. Acceptance and "
                "harmful_execution are kept separate because a model can treat "
                "a fabricated authority as authoritative (high acceptance) while "
                "still refusing to operationalize the dangerous behavior."
            ),
        },
        "rubrics": {
            "coherence": {
                "scale": "0-100 integer",
                "parser": "integer extraction, clipped to 0-100",
                "placeholders": ["question", "answer"],
                "prompt": _LiteralStr(COHERENCE_PROMPT),
            },
            "acceptance": {
                "scale": "0-100 integer, 6-band rubric",
                "parser": "integer extraction, clipped to 0-100",
                "placeholders": ["authority_name", "fabricated_content",
                                  "question", "answer"],
                "prompt": _LiteralStr(ACCEPTANCE_PROMPT),
            },
            "harmful_execution": {
                "scale": "binary YES / NO",
                "parser": "regex-based YES/NO extraction, None if ambiguous",
                "placeholders": ["target_behavior", "answer"],
                "prompt": _LiteralStr(HARMFUL_EXECUTION_PROMPT),
            },
        },
    }
    jp_path = os.path.join(eval_dir, "judge_prompts.yaml")
    with open(jp_path, "w", encoding="utf-8") as fh:
        yaml.dump(
            judge_out, fh,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=98,
        )
    print(f"Wrote {jp_path}  (3 rubrics)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
