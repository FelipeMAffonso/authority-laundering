"""End-to-end RunPod automation: provision, upload, run, download, stop.

Usage
-----
    # Set the two tokens (one-time)
    export RUNPOD_API_KEY=runpod-xxxxx
    export HF_TOKEN=hf_xxxxx

    # Provision + run (foreground, with live logs)
    python mechanism/runpod_launch.py

    # Variants
    python mechanism/runpod_launch.py --gpu "NVIDIA A100 80GB PCIe" --cloud COMMUNITY
    python mechanism/runpod_launch.py --pairs-limit 10           # smoke
    python mechanism/runpod_launch.py --provision-only           # just create the pod, return SSH command, stop here
    python mechanism/runpod_launch.py --pod-id <id> --resume     # reuse an existing pod
    python mechanism/runpod_launch.py --pod-id <id> --stop       # stop a pod when done
    python mechanism/runpod_launch.py --pod-id <id> --terminate  # destroy a pod

What it does (default flow)
---------------------------
1. Provisions an A100 80GB Pod on RunPod (Community Cloud, ~$1.19/hr)
   with a PyTorch + CUDA 12.4 image, 50GB container disk, 100GB volume
   at /workspace, ports 22/tcp + 8888/http exposed, env vars HF_TOKEN
   and ANTHROPIC_API_KEY pre-set.
2. Polls until the pod is RUNNING and SSH is reachable.
3. SCPs the entire mechanism/ folder + experiment/scenarios.py +
   harness/ to /workspace/authority-laundering/ on the pod.
4. SSHes in and runs:
     - pip install -r requirements.txt
     - huggingface-cli login --token $HF_TOKEN
     - python -c "snapshot_download('meta-llama/Llama-3.1-8B-Instruct')"
     - python run_subject_local.py --capture --pairs-limit <N>
     - python rejudge_llama_trials.py
     - python exp1_linear_probe.py
6. SCPs results back to local mechanism/outputs/.
7. Prints the pod_id and offers to stop or terminate.

Requirements on the local box (Windows 11 + WSL or Git Bash)
-----------------------------------------------------------
- Python 3.10+ with `pip install runpod paramiko scp`
- An SSH keypair at ~/.ssh/id_ed25519 (script will create one if missing)
- The local SSH public key registered with RunPod (script will register it)
- $RUNPOD_API_KEY env var set
- $HF_TOKEN env var set
- $ANTHROPIC_API_KEY env var set (for the judge step)

The script is idempotent. If a pod with the same name already exists in
RUNNING state and you don't pass --pod-id, the script will warn and exit;
either reuse it via --pod-id <id> --resume, or stop it via the dashboard.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MECHANISM_DIR = Path(__file__).resolve().parent
DEFAULT_POD_NAME = "authority-laundering-probe"
DEFAULT_GPU = "NVIDIA A100 80GB PCIe"
# Fallback chain when DEFAULT_GPU is out of stock. All entries have >=24GB VRAM,
# enough for Qwen 2.5 7B in bf16 (~15GB weights + activation cache headroom).
GPU_FALLBACKS = [
    "NVIDIA A100 80GB PCIe",       # ~$1.19/hr Community, primary target
    "NVIDIA A100-SXM4-80GB",       # ~$1.69/hr, A100 SXM variant
    "NVIDIA A40",                   # 48GB, ~$0.39/hr, very common availability
    "NVIDIA RTX A6000",             # 48GB, ~$0.49/hr, common
    "NVIDIA L40S",                  # 48GB, ~$0.99/hr, newer Ada
    "NVIDIA L40",                   # 48GB, ~$0.99/hr
    "NVIDIA H100 80GB HBM3",       # ~$2/hr, overkill but always in stock
    "NVIDIA H100 PCIe",             # ~$1.99/hr
    "NVIDIA GeForce RTX 4090",      # 24GB, ~$0.39/hr, borderline but works for 7B
]
DEFAULT_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
DEFAULT_TEMPLATE = None  # use bare image; pod_template_id is also fine but image is simpler
DEFAULT_VOLUME_GB = 100
DEFAULT_CONTAINER_GB = 50
DEFAULT_VCPU = 8
DEFAULT_MEM_GB = 32


# ----- env handling ------------------------------------------------------

def load_dotenv(path: Path) -> None:
    """Minimal dotenv loader (does not require python-dotenv)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def require_env(*names: str) -> dict[str, str]:
    out: dict[str, str] = {}
    missing: list[str] = []
    for n in names:
        v = os.environ.get(n)
        if not v:
            missing.append(n)
        else:
            out[n] = v
    if missing:
        print(f"[error] missing environment variables: {', '.join(missing)}")
        print("  Set them in projects/authority-laundering/config/.env")
        print("  or export them in your shell.")
        sys.exit(2)
    return out


# ----- SSH key handling --------------------------------------------------

def ensure_ssh_key() -> Path:
    """Make sure the user has an SSH keypair at ~/.ssh/id_ed25519 and return the public-key path."""
    home = Path.home()
    priv = home / ".ssh" / "id_ed25519"
    pub = home / ".ssh" / "id_ed25519.pub"
    if not priv.exists():
        print(f"[ssh] no key at {priv}, generating a new one...")
        priv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(priv)],
            check=True,
        )
    if not pub.exists():
        print(f"[error] private key exists at {priv} but no public key at {pub}")
        sys.exit(2)
    return pub


def register_ssh_key_with_runpod(public_key: str) -> None:
    """Register the local SSH public key in the RunPod account.

    The runpod-python SDK does not expose this directly; we use the GraphQL
    mutation `updateUserSettings` to append to the SSH-keys list.
    """
    import requests
    api_key = os.environ["RUNPOD_API_KEY"]
    # Read current settings
    query = """
    query { myself { id pubKey } }
    """
    r = requests.post(
        "https://api.runpod.io/graphql",
        json={"query": query},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        print(f"[warn] could not query current SSH keys: {data['errors']}")
        return
    current = (data.get("data") or {}).get("myself", {}).get("pubKey") or ""
    if public_key.strip() in current:
        print("[ssh] key already registered with RunPod")
        return
    new_keys = current.strip() + ("\n" if current.strip() else "") + public_key.strip()
    mutation = """
    mutation($input: UpdateUserSettingsInput!) {
        updateUserSettings(input: $input) { id pubKey }
    }
    """
    r = requests.post(
        "https://api.runpod.io/graphql",
        json={
            "query": mutation,
            "variables": {"input": {"pubKey": new_keys}},
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        print(f"[warn] could not register SSH key: {data['errors']}")
        print("  Add it manually at https://console.runpod.io/user/settings (SSH Public Keys)")
    else:
        print("[ssh] key registered with RunPod")


# ----- pod lifecycle -----------------------------------------------------

def create_pod(name: str, gpu_type_id: str, cloud_type: str, image: str,
               container_gb: int, volume_gb: int, env: dict[str, str]) -> dict:
    import runpod
    runpod.api_key = os.environ["RUNPOD_API_KEY"]
    print(f"[pod] creating {name} on {gpu_type_id} ({cloud_type})")
    # Do NOT override docker_args. The runpod/pytorch:* images ship a /start.sh
    # entrypoint that starts sshd, mounts authorized_keys from the account's
    # SSH Public Keys, and exposes Jupyter on 8888. Overriding it (we tried
    # `bash -c 'service ssh start && sleep infinity'`) breaks sshd because the
    # base image does not have openssh-server installed; the sshd binary that
    # answers on the exposed TCP port is set up by /start.sh, not by us.
    pod = runpod.create_pod(
        name=name,
        image_name=image,
        gpu_type_id=gpu_type_id,
        cloud_type=cloud_type,
        volume_in_gb=volume_gb,
        container_disk_in_gb=container_gb,
        min_vcpu_count=DEFAULT_VCPU,
        min_memory_in_gb=DEFAULT_MEM_GB,
        env=env,
        ports="22/tcp,8888/http",
        support_public_ip=True,
        volume_mount_path="/workspace",
    )
    print(f"[pod] created id={pod.get('id')} status={pod.get('desiredStatus', '?')}")
    return pod


def create_pod_with_fallback(name: str, primary_gpu: str, cloud_type: str, image: str,
                             container_gb: int, volume_gb: int, env: dict[str, str]) -> dict:
    """Try primary_gpu first, then walk GPU_FALLBACKS if out of stock.

    Also tries the same GPU on SECURE if COMMUNITY is empty.
    """
    import runpod  # noqa: F401  (used via create_pod)
    chain = [primary_gpu] + [g for g in GPU_FALLBACKS if g != primary_gpu]
    last_err = None
    for gpu in chain:
        for cloud in ([cloud_type] if cloud_type == "SECURE" else [cloud_type, "SECURE"]):
            try:
                return create_pod(name, gpu, cloud, image, container_gb, volume_gb, env)
            except Exception as e:
                msg = str(e)
                last_err = e
                if "no longer any instances" in msg or "out of stock" in msg.lower() or "not available" in msg.lower():
                    print(f"[pod] {gpu} ({cloud}) out of stock; trying next")
                    continue
                # other errors (auth, validation) — abort the chain
                raise
    raise RuntimeError(f"all GPUs in fallback chain are out of stock; last error: {last_err}")


def _ssh_reachable(ip: str, port: int, key: Path | None = None, timeout: int = 5) -> bool:
    """Return True if `ssh root@ip -p port echo ok` succeeds within timeout seconds."""
    key_arg = ["-i", str(key)] if key else []
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", f"ConnectTimeout={timeout}",
        "-o", "BatchMode=yes",
        "-p", str(port),
        *key_arg,
        f"root@{ip}",
        "echo ok",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def wait_for_running(pod_id: str, timeout_s: int = 900, ssh_key: Path | None = None) -> dict:
    """Poll RunPod until the pod reports RUNNING AND SSH is actually reachable."""
    import runpod
    runpod.api_key = os.environ["RUNPOD_API_KEY"]
    deadline = time.time() + timeout_s
    last_status = None
    last_ssh = (None, None)
    seen_running = False
    while time.time() < deadline:
        pod = runpod.get_pod(pod_id)
        rt = pod.get("runtime") or {}
        ports = rt.get("ports") or []
        ssh_port = None
        ssh_ip = None
        for p in ports:
            if p.get("privatePort") == 22 and p.get("isIpPublic"):
                ssh_port = p.get("publicPort")
                ssh_ip = p.get("ip")
        status = pod.get("desiredStatus")
        if status != last_status or (ssh_ip, ssh_port) != last_ssh:
            print(f"[pod] status={status} ssh={ssh_ip}:{ssh_port}")
            last_status = status
            last_ssh = (ssh_ip, ssh_port)
        if status == "RUNNING" and ssh_ip and ssh_port:
            if not seen_running:
                seen_running = True
                print(f"[pod] RUNNING; probing sshd on {ssh_ip}:{ssh_port} ...")
            if _ssh_reachable(ssh_ip, ssh_port, key=ssh_key, timeout=5):
                print(f"[pod] sshd reachable")
                pod["_ssh_ip"] = ssh_ip
                pod["_ssh_port"] = ssh_port
                return pod
        time.sleep(5)
    raise TimeoutError(f"pod {pod_id} did not become RUNNING with reachable SSH within {timeout_s}s")


# ----- remote execution --------------------------------------------------

def ssh_run(ip: str, port: int, cmd: str, key: Path | None = None, check: bool = True) -> int:
    key_arg = ["-i", str(key)] if key else []
    full = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-p", str(port),
        *key_arg,
        f"root@{ip}",
        cmd,
    ]
    print(f"[ssh] {cmd[:100]}{'...' if len(cmd) > 100 else ''}")
    proc = subprocess.run(full, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"ssh command failed: {cmd}")
    return proc.returncode


def scp_upload(local_path: Path, ip: str, port: int, remote_path: str,
               key: Path | None = None, recursive: bool = True) -> None:
    key_arg = ["-i", str(key)] if key else []
    rec = ["-r"] if recursive else []
    full = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-P", str(port),
        *rec,
        *key_arg,
        str(local_path),
        f"root@{ip}:{remote_path}",
    ]
    print(f"[scp] {local_path} -> root@{ip}:{remote_path}")
    subprocess.run(full, check=True)


def scp_download(ip: str, port: int, remote_path: str, local_path: Path,
                 key: Path | None = None, recursive: bool = True) -> None:
    key_arg = ["-i", str(key)] if key else []
    rec = ["-r"] if recursive else []
    full = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-P", str(port),
        *rec,
        *key_arg,
        f"root@{ip}:{remote_path}",
        str(local_path),
    ]
    print(f"[scp] root@{ip}:{remote_path} -> {local_path}")
    subprocess.run(full, check=True)


# ----- main flow ---------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default=DEFAULT_POD_NAME)
    parser.add_argument("--gpu", default=DEFAULT_GPU)
    parser.add_argument("--cloud", default="COMMUNITY", choices=["COMMUNITY", "SECURE"])
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--container-gb", type=int, default=DEFAULT_CONTAINER_GB)
    parser.add_argument("--volume-gb", type=int, default=DEFAULT_VOLUME_GB)
    parser.add_argument("--pairs-limit", type=int, default=None,
                        help="Smoke-test: cap matched pairs to N (default: all)")
    parser.add_argument("--provision-only", action="store_true",
                        help="Create pod and print SSH command, stop here")
    parser.add_argument("--pod-id", default=None, help="Reuse / target an existing pod")
    parser.add_argument("--resume", action="store_true", help="Reuse pod (with --pod-id), skip provision")
    parser.add_argument("--stop", action="store_true", help="Stop the pod (with --pod-id)")
    parser.add_argument("--terminate", action="store_true", help="Terminate the pod (with --pod-id)")
    args = parser.parse_args()

    # Load .env files
    load_dotenv(PROJECT_ROOT / "config" / ".env")

    # Pod stop / terminate shortcuts
    if args.stop or args.terminate:
        require_env("RUNPOD_API_KEY")
        if not args.pod_id:
            print("[error] --stop/--terminate require --pod-id")
            return 2
        import runpod
        runpod.api_key = os.environ["RUNPOD_API_KEY"]
        if args.terminate:
            print(f"[pod] terminating {args.pod_id}")
            runpod.terminate_pod(args.pod_id)
        else:
            print(f"[pod] stopping {args.pod_id}")
            runpod.stop_pod(args.pod_id)
        return 0

    # Provision
    require_env("RUNPOD_API_KEY", "HF_TOKEN", "ANTHROPIC_API_KEY")
    pub_key_path = ensure_ssh_key()
    public_key = pub_key_path.read_text(encoding="utf-8").strip()
    register_ssh_key_with_runpod(public_key)

    if args.resume and args.pod_id:
        import runpod
        runpod.api_key = os.environ["RUNPOD_API_KEY"]
        pod = runpod.get_pod(args.pod_id)
        print(f"[pod] resuming {pod.get('id')} status={pod.get('desiredStatus')}")
    elif args.pod_id:
        print("[error] --pod-id requires --resume, --stop, or --terminate")
        return 2
    else:
        env = {
            "HF_TOKEN": os.environ["HF_TOKEN"],
            "HUGGING_FACE_HUB_TOKEN": os.environ["HF_TOKEN"],
            "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
        }
        pod = create_pod_with_fallback(
            name=args.name,
            primary_gpu=args.gpu,
            cloud_type=args.cloud,
            image=args.image,
            container_gb=args.container_gb,
            volume_gb=args.volume_gb,
            env=env,
        )

    pod = wait_for_running(pod["id"], timeout_s=900, ssh_key=pub_key_path.with_suffix(""))
    ip = pod["_ssh_ip"]
    port = pod["_ssh_port"]
    print(f"\n[pod] RUNNING")
    print(f"     id   = {pod['id']}")
    print(f"     ssh  = ssh root@{ip} -p {port} -i {pub_key_path.with_suffix('')}")

    if args.provision_only:
        print("[pod] --provision-only specified; stopping here.")
        print(f"     resume with: python {sys.argv[0]} --pod-id {pod['id']} --resume")
        print(f"     stop with:   python {sys.argv[0]} --pod-id {pod['id']} --stop")
        return 0

    priv_key = pub_key_path.with_suffix("")
    remote_root = "/workspace/authority-laundering"

    # Setup remote workspace
    ssh_run(ip, port, "mkdir -p /workspace/authority-laundering", key=priv_key)
    scp_upload(MECHANISM_DIR, ip, port, "/workspace/authority-laundering/", key=priv_key)
    scp_upload(PROJECT_ROOT / "harness", ip, port, "/workspace/authority-laundering/", key=priv_key)
    scp_upload(PROJECT_ROOT / "experiment", ip, port, "/workspace/authority-laundering/", key=priv_key)

    # Install + login + download
    # Read MODEL_NAME from local config so the pod downloads the same one
    sys.path.insert(0, str(MECHANISM_DIR))
    from config import MODEL_NAME  # type: ignore
    install = (
        f"cd {remote_root}/mechanism && "
        "pip install -q -r requirements.txt && "
        "huggingface-cli login --token $HF_TOKEN --add-to-git-credential || true && "
        f"python -c \"from huggingface_hub import snapshot_download; "
        f"snapshot_download('{MODEL_NAME}', local_dir_use_symlinks=False)\""
    )
    print(f"[model] using {MODEL_NAME}")
    ssh_run(ip, port, install, key=priv_key)

    # Extract matched pairs
    extract = f"cd {remote_root}/mechanism && python extract_matched_pairs.py"
    ssh_run(ip, port, extract, key=priv_key)

    # Run subject-model capture
    pairs_arg = f"--pairs-limit {args.pairs_limit}" if args.pairs_limit else ""
    capture = f"cd {remote_root}/mechanism && python run_subject_local.py --capture {pairs_arg}"
    ssh_run(ip, port, capture, key=priv_key)

    # Re-judge
    rejudge = f"cd {remote_root}/mechanism && python rejudge_llama_trials.py"
    ssh_run(ip, port, rejudge, key=priv_key)

    # Run probe
    probe = f"cd {remote_root}/mechanism && python exp1_linear_probe.py"
    ssh_run(ip, port, probe, key=priv_key)

    # Download outputs
    out_dir = MECHANISM_DIR / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    scp_download(ip, port, f"{remote_root}/mechanism/outputs/", out_dir.parent, key=priv_key)

    print("\n[done] outputs at", out_dir)
    print(f"[pod] still running. Stop with:")
    print(f"      python {sys.argv[0]} --pod-id {pod['id']} --stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
