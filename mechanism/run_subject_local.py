"""Run the matched-pair stimuli on a local open-weight model with activation capture.

Loads Llama 3.1 8B Instruct (configurable in config.py), reconstructs the two-turn
conversation for each matched pair, runs a forward pass to the position right before
the model generates response_turn2, and captures the residual stream at every layer
at the last-token position. Saves activations as one .npz per trial.

Also generates response_turn2 for both conditions and saves it as a trial JSON in
outputs/llama_trials/, so we have Llama-3-specific compliance labels (after re-judging
in a separate step) that match the activations.

Usage on a GPU box (RunPod A100 80GB, NDIF, or local CUDA):
    huggingface-cli login --token $HF_TOKEN
    python run_subject_local.py --capture
    python run_subject_local.py --capture --pairs-limit 50      # smoke test
    python run_subject_local.py --behavioral-only               # generate response_turn2
                                                                #   without capturing activations

Idempotent: skips trials whose .npz already exists in outputs/activations/.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

from config import (
    ACTIVATIONS_DIR,
    LLAMA_TRIALS_DIR,
    MAX_NEW_TOKENS,
    MODEL_DTYPE,
    MODEL_NAME,
    OUTPUTS_DIR,
    SEED,
)


def chat_template_messages(system_prompt: str, turn1_user: str, response_turn1: str | None,
                           tool_turn: dict | None, turn2_user: str) -> list[dict]:
    """Build a Llama-3 chat-template message list reproducing the closed-API two-turn flow.

    For TOOL_DIRECT, the tool_turn dict carries {tool_name, tool_args, tool_result_text}.
    The model's first response and the tool's return are folded into the assistant turn so
    the second user turn carries the full operational request.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": turn1_user})
    if tool_turn is not None and isinstance(tool_turn, dict):
        tool_name = tool_turn.get("tool_name", "lookup_reference")
        tool_args = tool_turn.get("tool_args") or tool_turn.get("tool_input") or {}
        tool_result = tool_turn.get("tool_result_text") or tool_turn.get("tool_result") or ""
        assistant_turn1 = (
            f"I will look that up.\n\n"
            f"[tool_call: {tool_name}({json.dumps(tool_args, ensure_ascii=False)})]\n"
            f"[tool_result]\n{tool_result}\n[/tool_result]\n\n"
            f"{response_turn1 or ''}"
        ).strip()
    else:
        assistant_turn1 = (response_turn1 or "I can help with that.").strip()
    messages.append({"role": "assistant", "content": assistant_turn1})
    messages.append({"role": "user", "content": turn2_user})
    return messages


def run_one_side(model, tokenizer, side_data: dict, capture: bool, max_new_tokens: int) -> dict:
    """Forward pass on the conversation up to start of response_turn2; capture activations
    at the last input token; then generate response_turn2.

    Returns: dict with response_turn2 text, last-token activations per layer (if capture),
    and the input length used for the probe position.
    """
    messages = chat_template_messages(
        system_prompt=side_data["system_prompt"],
        turn1_user=side_data["turn1_user_message"],
        response_turn1=side_data.get("response_turn1"),
        tool_turn=side_data.get("tool_turn"),
        turn2_user=side_data["turn2_user_message"],
    )

    input_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    input_ids = tokenizer(input_text, return_tensors="pt").input_ids.to(model.device)
    n_input = input_ids.shape[1]

    layer_activations: dict[int, np.ndarray] = {}
    if capture:
        # Forward pass with hooks on every transformer layer's residual stream output.
        hooks = []
        captured: dict[int, torch.Tensor] = {}

        def make_hook(layer_idx: int):
            def hook(_module, _inputs, outputs):
                hidden = outputs[0] if isinstance(outputs, tuple) else outputs
                captured[layer_idx] = hidden[:, -1, :].detach().cpu().to(torch.float32)
            return hook

        for layer_idx, layer in enumerate(model.model.layers):
            hooks.append(layer.register_forward_hook(make_hook(layer_idx)))

        with torch.no_grad():
            model(input_ids=input_ids, use_cache=False)

        for h in hooks:
            h.remove()
        for k, v in captured.items():
            layer_activations[k] = v.numpy()[0]  # (hidden_dim,)

    # Greedy generate response_turn2 separately to keep activation capture clean.
    with torch.no_grad():
        gen = model.generate(
            input_ids=input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            top_p=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    response_text = tokenizer.decode(gen[0, n_input:], skip_special_tokens=True)

    return {
        "response_turn2": response_text,
        "n_input_tokens": int(n_input),
        "layer_activations": layer_activations,
    }


def save_activations(pair_id: str, condition: str, layer_activations: dict[int, np.ndarray]) -> Path:
    out_path = ACTIVATIONS_DIR / f"{pair_id}__{condition}.npz"
    if not layer_activations:
        return out_path
    np.savez_compressed(
        out_path,
        **{f"layer_{k}": v for k, v in layer_activations.items()},
    )
    return out_path


def save_trial(pair_id: str, condition: str, side_data: dict, side_result: dict, model_name: str) -> Path:
    trial_record = {
        "pair_id": pair_id,
        "condition": condition,
        "subject_model": model_name,
        "source_trial_id": side_data["trial_id"],
        "scenario_id": pair_id.split("__")[0],
        "direction": pair_id.split("__")[1],
        "trial_idx": int(pair_id.split("__t")[1]),
        "system_prompt": side_data["system_prompt"],
        "turn1_user_message": side_data["turn1_user_message"],
        "turn2_user_message": side_data["turn2_user_message"],
        "tool_turn": side_data.get("tool_turn"),
        "response_turn1_replayed": side_data.get("response_turn1"),
        "response_turn2": side_result["response_turn2"],
        "n_input_tokens": side_result["n_input_tokens"],
        "judge_harmful_execution": None,  # to be filled by re-judge step
    }
    out_path = LLAMA_TRIALS_DIR / f"{pair_id}__{condition}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(trial_record, fh, ensure_ascii=False, indent=2)
    return out_path


def load_pairs(path: Path) -> list[dict]:
    pairs = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--pairs", default=str(OUTPUTS_DIR / "matched_pairs.jsonl"))
    parser.add_argument("--pairs-limit", type=int, default=None,
                        help="Cap pairs for smoke testing")
    parser.add_argument("--capture", action="store_true", default=False,
                        help="Capture residual-stream activations (otherwise just generate)")
    parser.add_argument("--behavioral-only", action="store_true", default=False,
                        help="Skip activation capture; just generate response_turn2 for re-judging")
    parser.add_argument("--max-new-tokens", type=int, default=MAX_NEW_TOKENS)
    parser.add_argument("--quantize", choices=["none", "4bit", "8bit"], default="none",
                        help="Load model with bitsandbytes quantization for big models (Llama 3.3 70B, Llama 4 Scout) on A100 80GB")
    args = parser.parse_args()

    capture = args.capture and not args.behavioral_only

    print(f"Loading {args.model} on device cuda (quantize={args.quantize})")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    dtype = getattr(torch, MODEL_DTYPE)

    load_kwargs = {"torch_dtype": dtype, "device_map": "auto", "low_cpu_mem_usage": True}
    if args.quantize == "4bit":
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4"
        )
    elif args.quantize == "8bit":
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        **load_kwargs,
    )
    model.eval()
    print(f"Loaded. Hidden dim={model.config.hidden_size}, layers={model.config.num_hidden_layers}.")

    pairs = load_pairs(Path(args.pairs))
    if args.pairs_limit is not None:
        pairs = pairs[: args.pairs_limit]
    print(f"Processing {len(pairs)} matched pairs.")

    for i, pair in enumerate(pairs):
        pair_id = pair["pair_id"]
        for condition_key, side_key in [("TOOL_DIRECT", "tool_direct"),
                                        ("USER_IMPERATIVE", "user_imperative")]:
            act_path = ACTIVATIONS_DIR / f"{pair_id}__{condition_key}.npz"
            trial_path = LLAMA_TRIALS_DIR / f"{pair_id}__{condition_key}.json"
            need_act = capture and not act_path.exists()
            need_trial = not trial_path.exists()
            if not (need_act or need_trial):
                continue
            try:
                result = run_one_side(
                    model=model,
                    tokenizer=tokenizer,
                    side_data=pair[side_key],
                    capture=need_act,
                    max_new_tokens=args.max_new_tokens,
                )
                if need_act:
                    save_activations(pair_id, condition_key, result["layer_activations"])
                if need_trial:
                    save_trial(pair_id, condition_key, pair[side_key], result, args.model)
            except Exception as exc:
                print(f"[ERROR] pair={pair_id} cond={condition_key}: {exc!r}")
                continue
        if (i + 1) % 25 == 0:
            print(f"  done {i + 1}/{len(pairs)}")

    print("Run complete.")


if __name__ == "__main__":
    main()
