"""
Authentification mutuelle sur les connexions au Hub.

Le Hub savait servir en `wss://` : le trafic était chiffré, et l'agent
vérifiait le certificat du Hub. L'inverse n'existait pas. N'importe qui
atteignant le port pouvait ouvrir la poignée de main TLS, puis tenter sa
chance sur l'enregistrement.

`--tls-client-ca` renverse cela : le Hub exige un certificat client signé
par l'autorité nommée, et refuse la connexion **au niveau TLS** — avant le
premier octet de protocole, donc avant tout enregistrement, toute clé
d'API et tout journal applicatif.

Ce contrôle se cumule aux clés d'API, il ne les remplace pas. La clé dit
*qui* est l'agent ; le certificat dit que la machine au bout du câble fait
partie du parc. Une banque exige les deux, et l'un ne rattrape pas
l'absence de l'autre — c'est pourquoi les tests ci-dessous vérifient les
deux dimensions séparément.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import websockets
import websockets.exceptions
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from intermesh import InterMeshAgent
from intermesh.peering import build_peer_ssl_context, build_server_ssl_context

PORT = 8910
API_KEY = "nx_live_mtls_test_key"


# ----------------------------------------------------------------------
# Fabrique de certificats — tout est jetable et vit dans un tmpdir
# ----------------------------------------------------------------------

def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _write(directory: Path, name: str, cert, key) -> tuple[str, str]:
    cert_path = directory / f"{name}.crt"
    key_path = directory / f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    os.chmod(key_path, 0o600)
    return str(cert_path), str(key_path)


def _make_ca(directory: Path, name: str):
    key = _key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            # OpenSSL 3 refuse une chaîne sans identifiant de clé :
            # « Missing Authority Key Identifier ». Ces deux extensions ne
            # sont pas décoratives, la vérification échoue sans elles.
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                           critical=False)
            # keyCertSign est également exigé : « CA cert does not include
            # key usage extension ». Une autorité de test doit porter les
            # mêmes extensions qu'une vraie, sinon elle ne teste rien.
            .add_extension(x509.KeyUsage(
                digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path, _ = _write(directory, name, cert, key)
    return cert, key, cert_path


def _issue(directory: Path, name: str, common_name: str, ca_cert, ca_key,
           server: bool = False):
    key = _key()
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (x509.CertificateBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
               .issuer_name(ca_cert.subject)
               .public_key(key.public_key())
               .serial_number(x509.random_serial_number())
               .not_valid_before(now - datetime.timedelta(minutes=5))
               .not_valid_after(now + datetime.timedelta(days=1))
               .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                              critical=False)
               .add_extension(
                   x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                   critical=False)
               .add_extension(x509.KeyUsage(
                   digital_signature=True, content_commitment=False,
                   key_encipherment=True, data_encipherment=False,
                   key_agreement=False, key_cert_sign=False, crl_sign=False,
                   encipher_only=False, decipher_only=False), critical=True))
    usage = (x509.ExtendedKeyUsageOID.SERVER_AUTH if server
             else x509.ExtendedKeyUsageOID.CLIENT_AUTH)
    builder = builder.add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
    if server:
        # Sans SAN, la vérification du nom d'hôte échoue côté client : le
        # CN seul n'est plus accepté depuis longtemps.
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
    cert = builder.sign(ca_key, hashes.SHA256())
    return _write(directory, name, cert, key)


@pytest.fixture(scope="module")
def pki():
    directory = Path(tempfile.mkdtemp())
    ca_cert, ca_key, ca_path = _make_ca(directory, "ca")
    # Autorité étrangère : sert à prouver qu'un certificat valide *en soi*
    # mais signé ailleurs ne passe pas.
    rogue_cert, rogue_key, rogue_ca_path = _make_ca(directory, "rogue-ca")

    server_crt, server_key = _issue(directory, "server", "localhost", ca_cert, ca_key, server=True)
    client_crt, client_key = _issue(directory, "client", "agent-de-la-banque", ca_cert, ca_key)
    rogue_crt, rogue_key_path = _issue(directory, "rogue", "intrus", rogue_cert, rogue_key)

    return {
        "dir": directory, "ca": ca_path, "rogue_ca": rogue_ca_path,
        "server_crt": server_crt, "server_key": server_key,
        "client_crt": client_crt, "client_key": client_key,
        "rogue_crt": rogue_crt, "rogue_key": rogue_key_path,
    }


# ----------------------------------------------------------------------
# Contextes SSL (unitaire, sans réseau)
# ----------------------------------------------------------------------

def test_server_context_without_a_ca_asks_for_nothing(pki):
    context = build_server_ssl_context(pki["server_crt"], pki["server_key"])
    assert context.verify_mode == ssl.CERT_NONE


def test_server_context_with_a_ca_requires_a_client_certificate(pki):
    context = build_server_ssl_context(pki["server_crt"], pki["server_key"], pki["ca"])
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_client_context_still_verifies_the_hub(pki):
    """Présenter un certificat ne dispense pas d'en vérifier un."""
    context = build_peer_ssl_context("wss://hub.example", pki["ca"],
                                     pki["client_crt"], pki["client_key"])
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_plain_ws_gets_no_context_even_with_certificates(pki):
    assert build_peer_ssl_context("ws://localhost:8765", pki["ca"],
                                  pki["client_crt"], pki["client_key"]) is None


# ----------------------------------------------------------------------
# Intégration
# ----------------------------------------------------------------------

def _start_hub(port: int, pki: dict, *extra: str, admin: bool = False):
    work = tempfile.mkdtemp()
    keys = os.path.join(work, "keys.json")
    roles = ["admin", "service_account"] if admin else ["worker", "service_account"]
    perms = ["admin:*"] if admin else []
    with open(keys, "w") as handle:
        json.dump({API_KEY: {"org_id": "banque", "roles": roles,
                             "permissions": perms}}, handle)
    os.chmod(keys, 0o600)

    env = dict(os.environ)
    env["INTERMESH_API_KEYS_FILE"] = keys

    os.system(f"fuser -k {port}/tcp >/dev/null 2>&1")
    proc = subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", "--port", str(port), "--org", "banque",
         "--ephemeral-state", "--ephemeral-secret",
         "--tls-cert", pki["server_crt"], "--tls-key", pki["server_key"], *extra],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(2.5)
    return proc


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_a_client_without_a_certificate_is_refused_at_the_tls_layer(pki):
    """Le refus tombe avant le protocole : pas d'enregistrement, pas de clé."""
    hub = _start_hub(PORT, pki, "--tls-client-ca", pki["ca"])
    try:
        context = build_peer_ssl_context(f"wss://localhost:{PORT}", pki["ca"])
        with pytest.raises((ssl.SSLError, OSError, websockets.exceptions.WebSocketException)):
            async with websockets.connect(f"wss://localhost:{PORT}", ssl=context):
                pass
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_a_certificate_from_another_authority_is_refused(pki):
    """Un certificat valide en soi, mais signé ailleurs, ne vaut rien ici."""
    hub = _start_hub(PORT + 1, pki, "--tls-client-ca", pki["ca"])
    try:
        context = build_peer_ssl_context(f"wss://localhost:{PORT + 1}", pki["ca"],
                                         pki["rogue_crt"], pki["rogue_key"])
        with pytest.raises((ssl.SSLError, OSError, websockets.exceptions.WebSocketException)):
            async with websockets.connect(f"wss://localhost:{PORT + 1}", ssl=context):
                pass
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_a_valid_certificate_and_api_key_connect(pki):
    hub = _start_hub(PORT + 2, pki, "--tls-client-ca", pki["ca"], "--require-api-key")
    try:
        context = build_peer_ssl_context(f"wss://localhost:{PORT + 2}", pki["ca"],
                                         pki["client_crt"], pki["client_key"])
        agent = InterMeshAgent(name="légitime", org_id="banque",
                               hub_url=f"wss://localhost:{PORT + 2}",
                               api_key=API_KEY, encrypt=False, ssl=context)
        await agent.connect()
        assert agent.ws is not None
        await agent.ws.close()
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_a_certificate_does_not_replace_the_api_key(pki):
    """Les deux contrôles se cumulent : mTLS n'ouvre pas l'enregistrement.

    C'est le point que confond une lecture rapide — « on a mTLS, donc on
    peut relâcher les clés ». Le certificat atteste la machine, pas
    l'identité de l'agent ni ses rôles.
    """
    hub = _start_hub(PORT + 3, pki, "--tls-client-ca", pki["ca"], "--require-api-key")
    try:
        context = build_peer_ssl_context(f"wss://localhost:{PORT + 3}", pki["ca"],
                                         pki["client_crt"], pki["client_key"])
        agent = InterMeshAgent(name="sans_clé", org_id="banque",
                               hub_url=f"wss://localhost:{PORT + 3}",
                               roles=["admin"], encrypt=False, ssl=context)
        with pytest.raises(PermissionError) as exc:
            await agent.connect()
        assert "SELF_DECLARED_REFUSED" in str(exc.value)
    finally:
        _stop(hub)


def test_client_ca_without_a_server_certificate_is_refused():
    """Sans TLS il n'y a pas de poignée de main où réclamer un certificat.

    Accepter l'option laisserait croire que mTLS est actif alors qu'il
    serait inerte — le pire des deux mondes.
    """
    proc = subprocess.run(
        [sys.executable, "server/hub.py", "--port", str(PORT + 4),
         "--tls-client-ca", "/dev/null"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode != 0
    assert "--tls-client-ca" in proc.stderr


@pytest.mark.asyncio
async def test_the_certificate_holder_is_named_in_the_audit_log(pki):
    """mTLS refuse les inconnus, mais doit aussi dire qui il a accepté.

    Sans cette trace, le journal montre une connexion acceptée sans jamais
    indiquer quelle machine la portait — la première chose qu'une revue de
    sécurité demandera. C'est le nom porté par le certificat qui est
    consigné, pas le certificat : le journal ne contient jamais de matière
    cryptographique.
    """
    hub = _start_hub(PORT + 5, pki, "--tls-client-ca", pki["ca"],
                     "--require-api-key", admin=True)
    try:
        context = build_peer_ssl_context(f"wss://localhost:{PORT + 5}", pki["ca"],
                                         pki["client_crt"], pki["client_key"])
        async with websockets.connect(f"wss://localhost:{PORT + 5}", ssl=context) as ws:
            await ws.send(json.dumps({
                "id": "1", "version": "intermesh/v1", "type": "register",
                "sender": "console",
                "content": {"name": "console", "api_key": API_KEY,
                            "roles": ["admin", "observer"],
                            "capabilities": ["administration"]},
            }))
            recorded = None
            for _ in range(5):
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
                if message.get("type") == "telemetry_event":
                    for entry in (message["content"].get("audit_chain") or []):
                        if entry.get("event_type") == "AGENT_REGISTERED":
                            recorded = entry.get("metadata") or {}
                    break

        assert recorded is not None, "aucune entrée AGENT_REGISTERED reçue"
        assert recorded.get("client_cert_cn") == "agent-de-la-banque"
        assert recorded.get("auth_method") == "api_key"
        # Le journal nomme le porteur, il ne recopie pas le certificat.
        assert "BEGIN CERTIFICATE" not in json.dumps(recorded)
    finally:
        _stop(hub)
