# RunPod Walkthrough: NNsight Activation Probing on Llama 3.1 8B

A click-by-click guide to renting an A100 80GB GPU on RunPod, SSH-ing in from
Windows 11, and running the `run_subject_local.py` capture pipeline. Use **Pods**,
not Serverless. Serverless is for HTTP endpoints and bills per request — it is
the wrong product for an interactive research session that loads a model once
and runs probes for hours.

Prices and UI labels verified against RunPod's public docs and pricing page in
late 2025 / early 2026. RunPod ships UI changes frequently, so if a button name
has shifted, look for the closest equivalent in the same area of the screen.

---

## Step 1 — Get out of the Serverless tab

You are at `https://console.runpod.io/hub?tabSelected=serverless`. Close that
tab, or click **Pods** in the **left sidebar**. The sidebar in the RunPod
console shows, top to bottom: **Home**, **Pods**, **Serverless**, **Storage**,
**Templates**, **Settings**, **Billing**. You want **Pods**, not Serverless and
not the Hub. The direct URL is:

```
https://console.runpod.io/pods
```

If the page is empty, that's normal — you have no pods yet. The page header
should read "Pods" with a large purple/orange **+ Deploy** button on the right.

---

## Step 2 — Add credits before you click Deploy

RunPod is prepay. If your account balance is $0 you'll be blocked at the final
deploy click with a "Please add a payment method" prompt. Click **Billing** in
the sidebar, then **Add Credits**. $25 is plenty for a few overnight runs at
A100 80GB rates. Use a credit card — they don't accept PayPal for new accounts.

---

## Step 3 — Add your SSH public key (do this BEFORE deploying)

You only need to do this once per RunPod account. Pods inherit whatever keys
are in your account settings at deploy time, so adding the key after the pod
launches is a hassle.

### 3a. Generate a key on Windows 11 (skip if you already have `~/.ssh/id_ed25519`)

Open **Windows Terminal** (right-click Start → Terminal) or **PowerShell**.
Run:

```powershell
ssh-keygen -t ed25519 -C "your.email@example.com"
```

Press Enter at each prompt to accept the default path
(`C:\Users\natal\.ssh\id_ed25519`) and skip the passphrase. If you set a
passphrase, you'll be prompted for it on every SSH connection.

### 3b. Copy the public key

```powershell
Get-Content $HOME\.ssh\id_ed25519.pub | Set-Clipboard
```

(The Linux/WSL equivalent is `cat ~/.ssh/id_ed25519.pub | clip`.) The clipboard
now holds a single line starting with `ssh-ed25519 AAAA...` and ending with
your email.

### 3c. Paste into RunPod

In the RunPod console, click **Settings** in the left sidebar. Scroll to
**SSH Public Keys**. Paste the entire line into the textarea. If you already
have keys there, add yours on a new line. Click **Update Public Key** (or
whatever Save button is shown). Done.

---

## Step 4 — Click Deploy and pick a GPU

Back to **Pods** → click the orange **+ Deploy** button (top right).

You'll see a GPU grid. Each card shows GPU name, VRAM, vCPU/RAM defaults, and
two prices: a lower **Community Cloud** price and a higher **Secure Cloud**
price.

### Community Cloud vs Secure Cloud

- **Community Cloud** — GPUs hosted by independent operators on RunPod's
  network. Cheaper. Generally fine for research. Some hosts can be preempted
  or have variable I/O.
- **Secure Cloud** — RunPod-operated datacenters. SOC2-compliant, more
  reliable, slightly faster network. Pay ~$0.20–$0.40/hr more per A100.

For a research smoke test, **Community Cloud is fine**. For an unattended
overnight run where a host failure would cost you 8 hours of compute time,
**Secure Cloud** is worth the premium.

### A100 80GB pricing (verified late 2025 / early 2026)

| GPU            | Community Cloud | Secure Cloud |
|----------------|-----------------|--------------|
| A100 PCIe 80GB | ~$1.19/hr       | ~$1.39/hr    |
| A100 SXM 80GB  | ~$1.69/hr       | ~$1.89/hr    |
| H100 PCIe 80GB | ~$1.99/hr       | ~$2.39/hr    |

For Llama 3.1 8B activation probing, A100 PCIe 80GB is the sweet spot — the
model in bf16 is ~16GB, so 80GB leaves plenty of headroom for activation
caches at long context. RTX 4090 (24GB) is too small; H100 is overkill.

There is no separate "spot" tier on Pods (spot pricing only exists on
Serverless). Community Cloud is RunPod's analogue to spot.

In the GPU grid, click the **A100 80GB PCIe** card. It will highlight.

---

## Step 5 — Pick a template (PyTorch 2.x + CUDA 12.x)

After selecting a GPU, the page reveals configuration options below. Find the
**Pod Template** row. The default may be a generic Ubuntu — change it.

Click the template selector → search for **"RunPod Pytorch 2.4"** → pick:

```
runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04
```

This is RunPod's official template. It ships Ubuntu 22.04, Python 3.11,
PyTorch 2.4.0, CUDA 12.4.1, cuDNN, and a JupyterLab server. NNsight 0.3+ is
compatible. If RunPod has rolled to 2.5 or 2.6 by the time you read this, pick
the highest official `runpod/pytorch:2.x-py3.11-cuda12.x` — same family, same
behavior.

Avoid the `vllm` and `axolotl` templates — they pin specific transformers
versions that fight with NNsight.

---

## Step 6 — Configure container disk, volume disk, and ports

Below the template selector you'll see **Customize Deployment** (or
**Edit Template**). Click it. Set:

- **Container Disk: 50 GB**. Default is 5–10 GB which is too small. Llama 3.1
  8B weights alone are ~16 GB, plus pip caches and CUDA libs. Container disk
  is ephemeral — wiped on terminate.
- **Volume Disk: 100 GB**, mount path `/workspace`. This is the persistent
  disk; everything you save here survives stops and restarts. Models, code,
  outputs go in `/workspace`.
- **Expose HTTP Ports: 8888** (JupyterLab, prefilled) and **7860** if you
  ever want a Gradio UI.
- **Expose TCP Ports: 22** for full SSH (SCP/SFTP support). Without 22
  exposed, you can still SSH via RunPod's proxy at `ssh.runpod.io`, but you
  lose `scp` and `rsync`.

### Environment variables

In the **Environment Variables** section add:

- `HF_TOKEN` = `hf_...` (your Hugging Face read token; generate at
  `huggingface.co/settings/tokens`. Llama 3.1 is gated — you must accept the
  license on the Llama 3.1 8B Instruct model page first.)
- `HUGGING_FACE_HUB_TOKEN` = same value (some libs read this name).
- `ANTHROPIC_API_KEY` = `sk-ant-...` if `run_subject_local.py` calls Claude.

Do **not** put secrets into the template name or pod name — those show up in
support tickets.

---

## Step 7 — Click Deploy On-Demand

At the bottom of the configuration panel: **Deploy On-Demand**. Click it.
RunPod will reserve the GPU and pull the container image. This takes 30–90
seconds.

You'll be redirected back to `console.runpod.io/pods`. Your new pod appears
with status **Initializing** (yellow), then **Running** (green). The pod card
shows GPU, hourly cost, uptime, and a **Connect** button.

---

## Step 8 — Connect via SSH from Windows 11

Click **Connect** on the pod card. A modal pops with several options.

- **Connection Options** tab → look for **SSH over exposed TCP**. It shows a
  command like:

  ```
  ssh root@69.30.85.123 -p 12345 -i ~/.ssh/id_ed25519
  ```

  Copy that. The IP and port are unique to your pod.

- **SSH via RunPod proxy** (fallback if you didn't expose port 22) is shown
  as:

  ```
  ssh abc123def456-44551234@ssh.runpod.io -i ~/.ssh/id_ed25519
  ```

  Use this only if exposed TCP isn't working. No SCP/SFTP.

In **Windows Terminal** or **PowerShell**, paste the SSH command. Replace
`~/.ssh/id_ed25519` with the explicit Windows path if needed:

```powershell
ssh root@69.30.85.123 -p 12345 -i $HOME\.ssh\id_ed25519
```

First connection will ask "Are you sure you want to continue connecting
(yes/no)?" Type `yes`. You should land at a `root@a1b2c3d4:/#` shell. **No
password should ever be requested.** If it asks for a password, your key
isn't registered — go back to Step 3 and verify, then **Stop and redeploy**
the pod (account keys are read at deploy time).

### Web Terminal and JupyterLab (alternatives)

If SSH fails or you want a quick check, the same Connect modal has:

- **Open Web Terminal** — browser shell. Fine for one-liners, not for long
  jobs (the tab closing kills the session unless you use `tmux`).
- **Open Jupyter Lab** — link on port 8888. Good for inspecting outputs and
  running quick notebooks.

---

## Step 9 — Run the experiment

Once you have a shell prompt:

```bash
cd /workspace

# Clone your repo. Replace with your actual remote URL.
git clone https://github.com/YOUR_USER/authority-laundering.git
cd authority-laundering/mechanism

# Install Python deps
pip install -r requirements.txt

# HF auth (token already in env from Step 6, but log in for the CLI cache)
huggingface-cli login --token $HF_TOKEN

# Pre-download Llama 3.1 8B Instruct into the HF cache
python -c "from huggingface_hub import snapshot_download; \
  snapshot_download('meta-llama/Llama-3.1-8B-Instruct')"

# Smoke test on 10 pairs first — should finish in a minute or two
python run_subject_local.py --capture --pairs-limit 10

# Full run only after the smoke test produces sane output
python run_subject_local.py --capture
```

Run the full job inside `tmux` so a dropped SSH connection doesn't kill it:

```bash
tmux new -s probe
python run_subject_local.py --capture
# detach: Ctrl-B then D
# reattach later: tmux attach -t probe
```

Save outputs into `/workspace/...` (volume disk) so they survive a Stop. Files
under `/root` or `/tmp` will be **wiped** when the pod is terminated.

Pull results back to your laptop with SCP (works only if port 22 is exposed):

```powershell
scp -P 12345 -i $HOME\.ssh\id_ed25519 -r root@69.30.85.123:/workspace/authority-laundering/mechanism/outputs ./outputs_runpod
```

---

## Step 10 — Cost control: Stop vs Terminate

This is the most expensive thing to get wrong. RunPod bills **per second** on
running pods. An A100 80GB Community Cloud at $1.19/hr left running overnight
for 10 hours is **$11.90**. For a week unattended, **~$200**. Bills can
accumulate silently — there is no email warning before you blow through your
prepaid credits.

On the pod card, there are two buttons (you may need to click the pod row to
expand the controls):

- **Stop** (square icon) — Releases the GPU. Compute billing stops. Container
  disk and volume disk are preserved. Restarting picks up where you left off
  but is **not guaranteed to get the same physical GPU back** (especially on
  Community Cloud — the host may be in use). Stopped pods still cost
  approximately **$0.20/GB/month for container disk** and **$0.07/GB/month for
  volume disk**. A 50 GB container + 100 GB volume stopped costs about
  $17/month.
- **Terminate** (trash icon) — Permanent. Wipes container disk. Wipes volume
  disk unless you converted it to a Network Volume. Use this when you're
  done with the project. Always download outputs first.

**Recommended pattern:**

1. Active session → leave running.
2. Going to lunch / overnight → **Stop**.
3. Project finished → SCP outputs off, then **Terminate**.

Set a calendar reminder if you Stop a pod, because storage charges keep
accruing. If you only need the pod for a single 4-hour run and don't plan
to come back, Terminate when done — don't Stop.

---

## Troubleshooting: pod won't start

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| "No GPU available" / stuck on Initializing >5 min | A100 80GB out of stock at this moment | Pick a different region in the GPU filter, or try Secure Cloud, or pick A100 SXM as a substitute |
| "Image pull failed" | Template image transient registry issue | Click **Stop**, then **Start** (or **Edit Pod** → change template to a different PyTorch version and back) |
| Pod runs but `nvidia-smi` says no GPU | CUDA mismatch with template | Use Additional Filters → CUDA Version 12.4+ when picking the GPU; redeploy |
| "Out of disk space" during pip install | Container disk too small (default 5GB) | Stop, Edit Pod, raise Container Disk to 50GB, restart |
| SSH asks for password | Public key wasn't registered when pod deployed | Add key in Settings → **Stop and redeploy** the pod (live pods don't pick up new keys) |
| Pod stuck in "Throttled" state | Community Cloud host overloaded | Terminate and redeploy — preferably to a different GPU/host or Secure Cloud |

If logs are needed for support, expand the pod card and click **Logs** to see
the full container lifecycle.

---

## Quick cost cheat sheet

| Activity | A100 80GB Community ($1.19/hr) | A100 80GB Secure ($1.39/hr) |
|---------|-------------------------------|------------------------------|
| 10-pair smoke test (~5 min) | $0.10 | $0.12 |
| 1000-pair full capture (~2 hr) | $2.38 | $2.78 |
| Overnight run (10 hr) | $11.90 | $13.90 |
| Forgotten for a week | $200 | $234 |
| Stopped, 100 GB volume, 1 month | ~$7 storage only | ~$7 storage only |

Stopping kills 95%+ of the cost. Get into the habit of stopping the pod every
time you walk away from it.
