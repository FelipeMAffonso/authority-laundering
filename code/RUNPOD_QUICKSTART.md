# RunPod Quickstart — API-driven, two tokens, one command

You have $25 credit on RunPod. Below is the shortest path from zero to results,
fully API-driven so you don't have to click through the console.

## Step 1 — Get a RunPod API key (1 minute, 1 click)

1. Open https://console.runpod.io/user/settings
2. Click the **API Keys** tab
3. Click **+ Create API Key**
4. Name it `authority-laundering`
5. Permissions: **Read/Write** (default)
6. Click **Create**, copy the `runpod-...` token

## Step 2 — Get a Hugging Face token (2 minutes, 2 clicks)

1. Open https://huggingface.co/settings/tokens
2. Click **+ Create new token**, name it `authority-laundering`, select **Read** permission
3. Copy the `hf_...` token

**No gating needed.** The default subject model is `Qwen/Qwen2.5-7B-Instruct`,
which is fully ungated (Apache 2.0) and has direct precedent in Cloud et al. 2026
(Nature, subliminal learning) as a cross-model probe target. If you later want
to re-run on Llama 3.1 8B Instruct, request gated access at
https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct (queue can take 30 min
to 24 hr) and edit `mechanism/config.py`'s `MODEL_NAME`.

## Step 3 — Add the two tokens to config/.env (30 seconds)

```bash
cd projects/authority-laundering
cat >> config/.env <<EOF
RUNPOD_API_KEY=runpod-xxxxx_replace_me
HF_TOKEN=hf_xxxxx_replace_me
EOF
```

Replace the `xxxxx` values with the actual tokens you copied.
`ANTHROPIC_API_KEY` is already in there.

## Step 4 — Run one command

```bash
cd projects/authority-laundering
python mechanism/runpod_launch.py --pairs-limit 10
```

That's it. The script will:

1. Generate an SSH key in `~/.ssh/id_ed25519` if you don't have one.
2. Register the public key with your RunPod account via API.
3. Provision an A100 80GB Pod on Community Cloud (~$1.19/hr) with PyTorch 2.4 + CUDA 12.4.
4. Wait for SSH to come up.
5. Upload `mechanism/`, `harness/`, `experiment/` to `/workspace/authority-laundering/`.
6. Install Python deps.
7. Log in to Hugging Face and download Llama 3.1 8B Instruct (~16 GB).
8. Run `extract_matched_pairs.py`, `run_subject_local.py --capture --pairs-limit 10`,
   `rejudge_llama_trials.py`, `exp1_linear_probe.py`.
9. Download all results to `mechanism/outputs/`.
10. Print the pod ID and the stop command.

`--pairs-limit 10` is the smoke test (~$2 of compute, ~30 minutes).
Drop the flag for the full run (~$15-20, ~3-4 hours).

## Step 5 — Stop the pod when done

The script does NOT stop the pod automatically (because you may want to inspect
the activations or run additional scripts). To stop:

```bash
python mechanism/runpod_launch.py --pod-id <id_from_step_4> --stop
```

To terminate (wipes data, $0 ongoing):

```bash
python mechanism/runpod_launch.py --pod-id <id_from_step_4> --terminate
```

## Reusing a stopped pod

```bash
python mechanism/runpod_launch.py --pod-id <id> --resume
```

## Sanity-check before launching the full run

```bash
# Dry-run: just provision and print the SSH command, don't run anything
python mechanism/runpod_launch.py --provision-only
```

## Cost cheat sheet

| What | Time | Cost |
|---|---|---|
| Smoke run (`--pairs-limit 10`) | ~30 min | ~$1-2 |
| Full Llama 3.1 8B activation capture (no pairs limit) | ~2-3 hr | ~$5-7 |
| Plus Exp 3 patching (+ judge calls) | +1 hr | +$2 |
| Forgotten overnight (10 hr) | 10 hr | ~$12 |
| Stopped pod, storage only | 24 hr | ~$0.50 |

Your $25 covers the full pipeline twice over.

## Troubleshooting

- **"missing environment variables"** — check `config/.env` has all three:
  `RUNPOD_API_KEY`, `HF_TOKEN`, `ANTHROPIC_API_KEY`.
- **"pod did not become RUNNING within 900s"** — RunPod is out of A100 80GB
  PCIe in Community Cloud at the moment. Try `--cloud SECURE` (~$0.20/hr extra)
  or `--gpu "NVIDIA H100 80GB"` (~$2/hr).
- **"could not register SSH key"** — manually paste your `~/.ssh/id_ed25519.pub`
  contents at https://console.runpod.io/user/settings → SSH Public Keys.
- **403 on Llama download** — you didn't request access at huggingface.co/meta-llama/Llama-3.1-8B-Instruct, or the request hasn't been approved yet (usually <5 min).
- **"Permission denied (publickey)"** on SSH — wait 30s, re-try; sometimes the
  pod's sshd needs a moment.
