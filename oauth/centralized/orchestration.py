#!/usr/bin/env python3
"""Shared orchestration helpers for the centralized-OAuth driver scripts."""

import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

import keycloak as kc

VARIANT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VARIANT_DIR.parent.parent
ARTEFACTS = PROJECT_ROOT / "artefacts"
BIN_DIR = ARTEFACTS / "bin"
LOG_DIR = VARIANT_DIR / "logs"
PID_DIR = VARIANT_DIR / "pids"
EPOCH_DIR = VARIANT_DIR / "epochs"

METADATA_REPO_BIN = VARIANT_DIR / "metadata-repo" / "oauth-metadata-repo"
WORKLOAD_BIN = PROJECT_ROOT / "oauth" / "workload" / "oauth-workload"

# Port allocation
WORKLOAD_BASE_PORT = 7000  # workload domain-i index j -> 7000 + i*10 + j
WORKLOADS_PER_DOMAIN = 4
FEDERATION_ID = "fed1"


def workload_port(domain_index: int, idx: int) -> int:
    return WORKLOAD_BASE_PORT + domain_index * 10 + idx


def workload_name(domain_index: int, idx: int) -> str:
    return f"workload-{domain_index}-{idx}"


def workload_url(domain_index: int, idx: int) -> str:
    return f"http://localhost:{workload_port(domain_index, idx)}"


def _ensure_dirs():
    for d in (LOG_DIR, PID_DIR, EPOCH_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _spawn(name: str, argv, env=None):
    _ensure_dirs()
    log = open(LOG_DIR / f"{name}.log", "w")
    p = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
    (PID_DIR / f"{name}.pid").write_text(str(p.pid))
    return p


def kill_all():
    """Terminate every process whose pid we recorded."""
    if not PID_DIR.exists():
        return
    for f in PID_DIR.glob("*.pid"):
        try:
            pid = int(f.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
        f.unlink(missing_ok=True)


def start_metadata_repo():
    print("starting metadata-repo", file=sys.stderr)
    return _spawn("metadata-repo", [str(METADATA_REPO_BIN)])


def wait_metadata_repo(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get("http://localhost:9080/metadata", params={"federation_id": FEDERATION_ID}, timeout=1)
            return
        except requests.RequestException:
            time.sleep(0.2)
    raise RuntimeError("metadata-repo not ready")


def start_workload(domain_index: int, idx: int, client_id: str, client_secret: str):
    name = workload_name(domain_index, idx)
    env = os.environ.copy()
    peers_file = str(PID_DIR / f"peers-domain-{domain_index}.json")
    env.update({
        "CLIENT_ID": client_id,
        "CLIENT_SECRET": client_secret,
        "KEYCLOAK_URL": kc.kc_url(domain_index),
        "FEDERATION_ID": FEDERATION_ID,
        "DOMAIN_NAME": kc.realm_name(domain_index),
        "WORKLOAD_NAME": name,
        "PORT": str(workload_port(domain_index, idx)),
        "PEERS_FILE": peers_file,
    })
    return _spawn(name, [str(WORKLOAD_BIN)], env=env)


def wait_workload(domain_index: int, idx: int, timeout=10):
    url = workload_url(domain_index, idx) + "/healthz"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"workload {workload_name(domain_index, idx)} not ready")


def start_listener(domain_index: int):
    name = f"listener-domain-{domain_index}"
    return _spawn(
        name,
        ["python3", str(VARIANT_DIR / "listen_and_react.py"),
         "--domain-index", str(domain_index)],
    )


def setup_domain(domain_index: int):
    """Boot Keycloak + realm + 4 service-account clients + 4 workloads for one domain.

    Returns dict {client_id -> client_secret} so the listener / orchestrator
    can reuse it.
    """
    kc.start_keycloak(domain_index)
    kc.wait_ready(domain_index)
    tok = kc.admin_token(domain_index)
    kc.bump_master_token_lifespan(domain_index, tok)
    kc.create_realm(domain_index, tok)

    secrets = {}
    for idx in range(WORKLOADS_PER_DOMAIN):
        cid = workload_name(domain_index, idx)
        secret = kc.create_service_account_client(domain_index, tok, cid)
        secrets[cid] = secret

    _ensure_dirs()
    (PID_DIR / f"secrets-domain-{domain_index}.json").write_text(json.dumps(secrets))

    (PID_DIR / f"peers-domain-{domain_index}.json").write_text("{}")

    start_listener(domain_index)
    time.sleep(2)

    for idx in range(WORKLOADS_PER_DOMAIN):
        cid = workload_name(domain_index, idx)
        start_workload(domain_index, idx, cid, secrets[cid])
    for idx in range(WORKLOADS_PER_DOMAIN):
        wait_workload(domain_index, idx)

    return secrets


def load_domain_secrets(domain_index: int) -> dict:
    return json.loads((PID_DIR / f"secrets-domain-{domain_index}.json").read_text())


def self_register(domain_index: int):
    import repo_client
    repo_client.register(
        kc.realm_name(domain_index),
        kc.kc_url(domain_index),
        kc.jwks_url(domain_index),
    )


def wait_peer_registered_at(domain_index: int, peer_domain: str, timeout=30) -> bool:
    """Block until this domain's Keycloak has IDP alias <fid>-<peer> visible."""
    tok = kc.admin_token(domain_index)
    realm = kc.realm_name(domain_index)
    alias = f"{FEDERATION_ID}-{peer_domain}"
    url = f"{kc.kc_url(domain_index)}/admin/realms/{realm}/identity-provider/instances/{alias}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=2)
        if r.status_code == 200:
            return True
        time.sleep(0.1)
    return False


def call_pair(src_dom: int, src_idx: int, tgt_dom: int, tgt_idx: int, timeout=5):
    body = {
        "target_domain": kc.realm_name(tgt_dom),
        "target_url": workload_url(tgt_dom, tgt_idx),
    }
    r = requests.post(workload_url(src_dom, src_idx) + "/call", json=body, timeout=timeout)
    return r.status_code, r.text


def drive_full_mesh(n: int, max_workers: int = 100, retry_sleep: float = 0.1):
    """Drive every (src_dom, src_idx) -> (tgt_dom, tgt_idx) pair across distinct domains.

    Retries failures with `retry_sleep` cadence until all pairs succeed.
    Returns wall-clock epoch of the last successful 200.
    """
    pairs = []
    for sd in range(1, n + 1):
        for si in range(WORKLOADS_PER_DOMAIN):
            for td in range(1, n + 1):
                if td == sd:
                    continue
                for ti in range(WORKLOADS_PER_DOMAIN):
                    pairs.append((sd, si, td, ti))

    last_ok = {}

    def attempt(pair):
        sd, si, td, ti = pair
        while True:
            try:
                status, _ = call_pair(sd, si, td, ti)
                if status == 200:
                    return pair, time.time()
            except requests.RequestException:
                pass
            time.sleep(retry_sleep)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for fut in concurrent.futures.as_completed([ex.submit(attempt, p) for p in pairs]):
            pair, ts = fut.result()
            last_ok[pair] = ts

    return max(last_ok.values())


def record_epoch(name: str, value: float = None):
    _ensure_dirs()
    if value is None:
        value = time.time()
    (EPOCH_DIR / f"{name}.epoch").write_text(f"{value}\n")
    return value


def read_epoch(name: str) -> float:
    return float((EPOCH_DIR / f"{name}.epoch").read_text().strip())
