#!/usr/bin/env python3
"""Keycloak process + admin helpers for the centralized OAuth variant.

Each domain runs one native Keycloak (kc.sh start-dev) on a dedicated
HTTP port. Admin API is reached over the same port; admin credentials
come from the dev-mode env defaults (admin/admin).
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTEFACTS = PROJECT_ROOT / "artefacts"
KC_HOME = ARTEFACTS / "keycloak"   # extracted distribution lives here
KC_DATA_ROOT = ARTEFACTS / "keycloak-data"
KC_BIN = KC_HOME / "bin" / "kc.sh"

ADMIN_USER = "admin"
ADMIN_PASS = "admin"

KC_BASE_PORT = 8081  # domain i -> port KC_BASE_PORT + i - 1


def kc_port(domain_index: int) -> int:
    return KC_BASE_PORT + domain_index - 1


def kc_url(domain_index: int) -> str:
    return f"http://localhost:{kc_port(domain_index)}"


def realm_name(domain_index: int) -> str:
    return f"domain-{domain_index}"


def jwks_url(domain_index: int) -> str:
    return f"{kc_url(domain_index)}/realms/{realm_name(domain_index)}/protocol/openid-connect/certs"


def require_kc_dist():
    if not KC_BIN.exists():
        print(f"ERROR: Keycloak not installed at {KC_HOME}", file=sys.stderr)
        print(f"Run: {PROJECT_ROOT}/oauth/centralized/install_keycloak.sh", file=sys.stderr)
        sys.exit(1)


def start_keycloak(domain_index: int) -> subprocess.Popen:
    """Spawn a Keycloak dev-mode process for one domain."""
    require_kc_dist()
    data_dir = KC_DATA_ROOT / f"domain-{domain_index}"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    log = open(data_dir / "keycloak.log", "w")
    env = os.environ.copy()
    env["KEYCLOAK_ADMIN"] = ADMIN_USER
    env["KEYCLOAK_ADMIN_PASSWORD"] = ADMIN_PASS
    env["KC_HOME"] = str(data_dir)
    # Byte Buddy bundled in Keycloak 26.0.x officially supports up to JDK 23;
    # allow newer JDKs (25+) via the experimental flag.
    env["JAVA_OPTS_APPEND"] = (
        env.get("JAVA_OPTS_APPEND", "") + " -Dnet.bytebuddy.experimental=true"
    ).strip()
    db_dir = data_dir / "h2"
    db_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        [
            str(KC_BIN),
            "start-dev",
            "--http-port", str(kc_port(domain_index)),
            "--hostname-strict=false",
            "--features=token-exchange,admin-fine-grained-authz",
            f"--db-url=jdbc:h2:file:{db_dir}/keycloakdb;NON_KEYWORDS=VALUE;AUTO_SERVER=TRUE",
            f"-Djboss.server.config.dir={data_dir}",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print(f"[keycloak] started domain-{domain_index} pid={p.pid} port={kc_port(domain_index)}", file=sys.stderr)
    return p


def wait_ready(domain_index: int, timeout: float = 180.0):
    """Wait until KC can actually issue an admin token (covers bootstrap)."""
    realm_url = f"{kc_url(domain_index)}/realms/master"
    tok_url = f"{kc_url(domain_index)}/realms/master/protocol/openid-connect/token"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(realm_url, timeout=2)
            if r.status_code == 200:
                tr = requests.post(
                    tok_url,
                    data={
                        "grant_type": "password",
                        "client_id": "admin-cli",
                        "username": ADMIN_USER,
                        "password": ADMIN_PASS,
                    },
                    timeout=5,
                )
                if tr.status_code == 200:
                    return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"keycloak domain-{domain_index} not ready")


def admin_token(domain_index: int) -> str:
    r = requests.post(
        f"{kc_url(domain_index)}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASS,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _hdrs(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def bump_master_token_lifespan(domain_index: int, tok: str, seconds: int = 86400):
    r = requests.put(
        f"{kc_url(domain_index)}/admin/realms/master",
        headers=_hdrs(tok),
        json={"accessTokenLifespan": seconds},
        timeout=10,
    )
    r.raise_for_status()


def create_realm(domain_index: int, tok: str, access_token_ttl: int = 300):
    name = realm_name(domain_index)
    body = {
        "realm": name,
        "enabled": True,
        "accessTokenLifespan": access_token_ttl,
    }
    r = requests.post(
        f"{kc_url(domain_index)}/admin/realms",
        headers=_hdrs(tok),
        json=body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()


def create_service_account_client(
    domain_index: int, tok: str, client_id: str
) -> str:
    """Create a confidential client with service-account enabled. Returns secret."""
    realm = realm_name(domain_index)
    body = {
        "clientId": client_id,
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "serviceAccountsEnabled": True,
        "directAccessGrantsEnabled": False,
        "standardFlowEnabled": False,
        "clientAuthenticatorType": "client-secret",
    }
    r = requests.post(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients",
        headers=_hdrs(tok),
        json=body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()
    # fetch client uuid + secret
    r = requests.get(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients",
        headers=_hdrs(tok),
        params={"clientId": client_id},
        timeout=10,
    )
    r.raise_for_status()
    cid = r.json()[0]["id"]
    r = requests.get(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients/{cid}/client-secret",
        headers=_hdrs(tok),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["value"]


def create_idp_alias(
    domain_index: int, tok: str, alias: str, jwks_uri: str, issuer: str
):
    realm = realm_name(domain_index)
    body = {
        "alias": alias,
        "providerId": "oidc",
        "enabled": True,
        "config": {
            "issuer": issuer,
            "useJwksUrl": "true",
            "jwksUrl": jwks_uri,
            "validateSignature": "true",
            "clientId": alias,
            "clientSecret": "unused",
            "tokenUrl": f"{issuer}/protocol/openid-connect/token",
            "authorizationUrl": f"{issuer}/protocol/openid-connect/auth",
        },
    }
    r = requests.post(
        f"{kc_url(domain_index)}/admin/realms/{realm}/identity-provider/instances",
        headers=_hdrs(tok),
        json=body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()


def create_public_exchange_client(domain_index: int, tok: str, client_id: str):
    realm = realm_name(domain_index)
    body = {
        "clientId": client_id,
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": True,
        "directAccessGrantsEnabled": False,
        "standardFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "attributes": {"oauth2.token.exchange.grant.enabled": "true"},
    }
    r = requests.post(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients",
        headers=_hdrs(tok),
        json=body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()


def get_client_uuid(domain_index: int, tok: str, client_id: str):
    realm = realm_name(domain_index)
    r = requests.get(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients",
        headers=_hdrs(tok),
        params={"clientId": client_id},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        return None
    return items[0]["id"]


def set_client_not_before(domain_index: int, tok: str, client_id: str, epoch: int):
    realm = realm_name(domain_index)
    uuid = get_client_uuid(domain_index, tok, client_id)
    if uuid is None:
        return
    r = requests.put(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients/{uuid}",
        headers=_hdrs(tok),
        json={"notBefore": epoch},
        timeout=10,
    )
    r.raise_for_status()


def disable_idp(domain_index: int, tok: str, alias: str):
    realm = realm_name(domain_index)
    url = f"{kc_url(domain_index)}/admin/realms/{realm}/identity-provider/instances/{alias}"
    r = requests.get(url, headers=_hdrs(tok), timeout=10)
    if r.status_code == 404:
        return
    r.raise_for_status()
    body = r.json()
    body["enabled"] = False
    r = requests.put(url, headers=_hdrs(tok), json=body, timeout=10)
    r.raise_for_status()


def disable_client(domain_index: int, tok: str, client_id: str):
    realm = realm_name(domain_index)
    uuid = get_client_uuid(domain_index, tok, client_id)
    if uuid is None:
        return
    r = requests.put(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients/{uuid}",
        headers=_hdrs(tok),
        json={"enabled": False},
        timeout=10,
    )
    r.raise_for_status()


def _realm_mgmt_uuid(domain_index: int, tok: str) -> str:
    realm = realm_name(domain_index)
    r = requests.get(
        f"{kc_url(domain_index)}/admin/realms/{realm}/clients",
        headers=_hdrs(tok),
        params={"clientId": "realm-management"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()[0]["id"]


def allow_client_to_exchange(
    domain_index: int, tok: str, idp_alias: str, exchanger_client_id: str
):
    """Enable IDP fine-grained permissions and bind a client policy to the
    token-exchange scope permission so `exchanger_client_id` may use this IDP
    as subject_issuer for token exchange.
    """
    realm = realm_name(domain_index)
    base = f"{kc_url(domain_index)}/admin/realms/{realm}"

    # 1) Enable fine-grained permissions on the IDP alias
    r = requests.put(
        f"{base}/identity-provider/instances/{idp_alias}/management/permissions",
        headers=_hdrs(tok),
        json={"enabled": True},
        timeout=10,
    )
    r.raise_for_status()
    perms = r.json()
    te_perm_id = perms["scopePermissions"]["token-exchange"]

    rm_uuid = _realm_mgmt_uuid(domain_index, tok)
    ex_uuid = get_client_uuid(domain_index, tok, exchanger_client_id)
    if ex_uuid is None:
        raise RuntimeError(f"client {exchanger_client_id} missing on domain-{domain_index}")

    # 2) Create (or fetch) a client-policy that targets the exchanger client
    policy_name = f"allow-{exchanger_client_id}"
    policy_body = {
        "name": policy_name,
        "type": "client",
        "logic": "POSITIVE",
        "decisionStrategy": "UNANIMOUS",
        "clients": [ex_uuid],
    }
    r = requests.post(
        f"{base}/clients/{rm_uuid}/authz/resource-server/policy/client",
        headers=_hdrs(tok),
        json=policy_body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()
    # Lookup policy id
    r = requests.get(
        f"{base}/clients/{rm_uuid}/authz/resource-server/policy",
        headers=_hdrs(tok),
        params={"name": policy_name},
        timeout=10,
    )
    r.raise_for_status()
    policies = r.json()
    if not policies:
        raise RuntimeError(f"policy {policy_name} not visible after create")
    policy_id = policies[0]["id"]

    # 3) Fetch current permission, patch policies list, PUT it back
    r = requests.get(
        f"{base}/clients/{rm_uuid}/authz/resource-server/permission/scope/{te_perm_id}",
        headers=_hdrs(tok),
        timeout=10,
    )
    r.raise_for_status()
    perm = r.json()
    existing = set(perm.get("policies") or [])
    existing.add(policy_id)
    perm["policies"] = list(existing)
    r = requests.put(
        f"{base}/clients/{rm_uuid}/authz/resource-server/permission/scope/{te_perm_id}",
        headers=_hdrs(tok),
        json=perm,
        timeout=10,
    )
    r.raise_for_status()


def reload_idp_keys(domain_index: int, tok: str, alias: str) -> bool:
    """Force the broker to refetch JWKS for an IDP alias. Returns True on success."""
    realm = realm_name(domain_index)
    url = f"{kc_url(domain_index)}/admin/realms/{realm}/identity-provider/instances/{alias}/reload-keys"
    r = requests.get(url, headers=_hdrs(tok), timeout=10)
    if r.status_code != 200:
        print(f"[kc] reload_idp_keys domain-{domain_index} {alias}: {r.status_code} {r.text[:200]}", file=sys.stderr)
        return False
    return True


def rotate_signing_key(domain_index: int, tok: str):
    """Generate a new RSA key in the realm and mark it active."""
    realm = realm_name(domain_index)
    body = {
        "name": "rsa-generated-rotated",
        "providerId": "rsa-generated",
        "providerType": "org.keycloak.keys.KeyProvider",
        "config": {
            "priority": ["200"],
            "enabled": ["true"],
            "active": ["true"],
            "keySize": ["2048"],
            "algorithm": ["RS256"],
        },
    }
    r = requests.post(
        f"{kc_url(domain_index)}/admin/realms/{realm}/components",
        headers=_hdrs(tok),
        json=body,
        timeout=10,
    )
    if r.status_code not in (201, 409):
        r.raise_for_status()
