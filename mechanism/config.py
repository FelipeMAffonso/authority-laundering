"""Mechanism extension configuration.

Edit MODEL_NAME to switch between Llama 3.1 8B (default, MVP) and Llama 3.3 70B
(scale-up if 8B does not show the effect). Everything else is downstream.
"""

from pathlib import Path

# --- Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
MECHANISM_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = MECHANISM_DIR / "outputs"
ACTIVATIONS_DIR = OUTPUTS_DIR / "activations"
PROBES_DIR = OUTPUTS_DIR / "probes"
PATCHES_DIR = OUTPUTS_DIR / "patches"
LLAMA_TRIALS_DIR = OUTPUTS_DIR / "llama_trials"
FIGURES_DIR = OUTPUTS_DIR / "figures"

for d in [OUTPUTS_DIR, ACTIVATIONS_DIR, PROBES_DIR, PATCHES_DIR, LLAMA_TRIALS_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- Subject model
# Defaulting to Qwen 2.5 7B Instruct: ungated (Apache 2.0), 7B-class instruction-tuned,
# precedent in Cloud et al. 2026 (Nature, subliminal learning) as a cross-model probe target.
# Switch to "meta-llama/Llama-3.1-8B-Instruct" once your HF gated-access request clears.
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MODEL_DTYPE = "bfloat16"
MAX_NEW_TOKENS = 1024
TEMPERATURE = 0.0  # greedy for deterministic activation capture
SEED = 42

# --- Source-trial selection
SOURCE_MODEL_KEY = "llama-4-scout"  # which closed/open-weight panel model's matched pairs we mirror
CONDITIONS = ["TOOL_DIRECT", "USER_IMPERATIVE"]  # the two we contrast for probing
DIRECTIONS = ["harmful"]  # mechanism focuses on harmful direction; benign is supplementary
REPLICATES_PER_CELL = 5  # match the closed-weight panel's N

# --- Activation capture
PROBE_POSITION = "last_token_of_turn2_user"  # position right before model generates response_turn2
CAPTURE_LAYERS = "all"  # or list of ints for a sweep subset
CAPTURE_DTYPE = "float32"  # save activations as float32 for probe training stability

# --- Probe
PROBE_C = 1.0  # L2 regularization strength for logistic regression
PROBE_TRAIN_FRAC = 0.6
PROBE_VAL_FRAC = 0.2
PROBE_TEST_FRAC = 0.2  # implicit; train + val + test = 1.0
STRATIFY_BY = "scenario_id"  # held-out scenarios test OOD generalization
LEAVE_ONE_DOMAIN_OUT = True  # also report LOO-domain accuracy

# --- Causal patching
PATCH_LAYER = None  # set after Experiment 1; None means use argmax(probe_accuracy)
PATCH_POSITION = "last_token_of_turn2_user"
PATCH_DIRECTIONS = ["tool_to_user", "user_to_tool"]  # forward and reverse patches
N_PATCHES_PER_DIRECTION = 250  # cap; will sample if more pairs available

# --- Judge (re-judging patched completions in Experiment 3)
JUDGE_MODEL = "claude-haiku-4-5"
JUDGE_MAX_TOKENS = 600
JUDGE_TEMPERATURE = 0.0
