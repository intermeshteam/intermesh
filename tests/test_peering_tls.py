"""
Transport du lien de fédération : TLS obligatoire hors machine locale.

La signature Ed25519 des jetons ne vaut que si les clés publiques ont été
échangées sur un canal non modifiable. Ces tests verrouillent les deux
moitiés : le refus du clair vers un hôte distant, et la vérification
effective du certificat du pair.
"""

import asyncio
import datetime
import os
import ssl
import subprocess
import sys
import time

import pytest
import websockets
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from intermesh import InterMeshAgent
from intermesh.peering import (
    assert_peer_link_is_secure, build_peer_ssl_context, build_server_ssl_context,
    is_loopback_url, parse_peer_spec,
)

TLS_PORT = 8831
PLAIN_PORT = 8832


# ----------------------------------------------------------------------
# Unitaires
# ----------------------------------------------------------------------

def test_parse_peer_spec_accepts_both_schemes():
    assert parse_peer_spec("globex=wss://hub.globex.com:8765") == (
        "globex", "wss://hub.globex.com:8765")
    assert parse_peer_spec("globex=ws://localhost:8766") == ("globex", "ws://localhost:8766")


@pytest.mark.parametrize("spec", [
    "pas-de-signe-egal",
    "=wss://hub.globex.com",
    "globex=http://hub.globex.com",
])
def test_parse_peer_spec_rejects_malformed(spec):
    with pytest.raises(ValueError):
        parse_peer_spec(spec)


@pytest.mark.parametrize("url,expected", [
    ("ws://localhost:8765", True),
    ("ws://127.0.0.1:8765", True),
    ("wss://[::1]:8765", True),
    ("ws://hub.globex.com:8765", False),
    ("ws://10.0.0.7:8765", False),
])
def test_is_loopback_url(url, expected):
    assert is_loopback_url(url) is expected


def test_plaintext_peering_to_a_remote_host_is_refused():
    """Le cas qui rendait l'échange de clés publiques interceptable."""
    with pytest.raises(ValueError, match="clair"):
        assert_peer_link_is_secure("globex", "ws://hub.globex.com:8765")


def test_plaintext_peering_is_allowed_locally_and_on_explicit_override():
    assert_peer_link_is_secure("globex", "ws://localhost:8766")
    assert_peer_link_is_secure("globex", "wss://hub.globex.com:8765")
    assert_peer_link_is_secure("globex", "ws://hub.globex.com:8765", allow_insecure=True)


def test_peer_ssl_context_never_disables_verification():
    context = build_peer_ssl_context("wss://hub.globex.com:8765")

    assert context is not None
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_peer_ssl_context_is_absent_in_plaintext():
    assert build_peer_ssl_context("ws://localhost:8766") is None


# ----------------------------------------------------------------------
# Intégration : fédération réelle par-dessus TLS
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def self_signed_cert(tmp_path_factory):
    """Certificat auto-signé pour `localhost`, façon PKI privée d'un partenaire."""
    work = tmp_path_factory.mktemp("tls")
    cert_path, key_path = work / "hub.crt", work / "hub.key"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    return str(cert_path), str(key_path)


def _start_hub(*args):
    return subprocess.Popen(
        [sys.executable, "-u", "server/hub.py", *args,
         "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_server_ssl_context_loads_the_certificate(self_signed_cert):
    cert, key = self_signed_cert
    context = build_server_ssl_context(cert, key)
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


@pytest.mark.asyncio
async def test_peer_certificate_is_actually_verified(self_signed_cert):
    """Sans l'autorité du pair, la connexion doit échouer — pas passer."""
    cert, key = self_signed_cert
    os.system(f"fuser -k {TLS_PORT}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    hub = _start_hub("--port", str(TLS_PORT), "--org", "globex",
                     "--tls-cert", cert, "--tls-key", key)
    await asyncio.sleep(1.5)
    try:
        url = f"wss://localhost:{TLS_PORT}"

        # Certificat auto-signé inconnu du magasin système : refus attendu.
        with pytest.raises(ssl.SSLCertVerificationError):
            async with websockets.connect(url, ssl=build_peer_ssl_context(url)):
                pass

        # La même connexion, avec l'autorité du partenaire, aboutit.
        async with websockets.connect(url, ssl=build_peer_ssl_context(url, ca_file=cert)) as ws:
            assert ws.close_code is None
    finally:
        _stop(hub)


@pytest.mark.asyncio
async def test_federation_works_over_tls(self_signed_cert):
    """Une tâche cross-org doit aboutir avec le lien de pairage en wss://."""
    cert, key = self_signed_cert
    os.system(f"fuser -k {TLS_PORT}/tcp {PLAIN_PORT}/tcp 2>/dev/null")
    await asyncio.sleep(0.4)

    globex = _start_hub("--port", str(TLS_PORT), "--org", "globex",
                        "--tls-cert", cert, "--tls-key", key)
    await asyncio.sleep(1.5)
    acme = _start_hub("--port", str(PLAIN_PORT), "--org", "acme",
                      "--peer", f"globex=wss://localhost:{TLS_PORT}", "--peer-ca", cert)
    await asyncio.sleep(2.0)

    worker = orchestrator = None
    try:
        async def handler(input_data, task):
            return {"doubled": input_data["value"] * 2}

        worker = InterMeshAgent(name="tls_worker", org_id="globex", capabilities=["compute"],
                                roles=["worker"], hub_url=f"wss://localhost:{TLS_PORT}",
                                ssl=build_peer_ssl_context(f"wss://localhost:{TLS_PORT}", cert))
        worker.on_task(handler)
        await worker.connect()

        orchestrator = InterMeshAgent(name="tls_lead", org_id="acme", roles=["admin"],
                                      hub_url=f"ws://localhost:{PLAIN_PORT}")
        await orchestrator.connect()
        await asyncio.sleep(1.0)

        result = await orchestrator.submit_task(
            title="Calcul fédéré sur lien TLS",
            assignee="globex/tls_worker",
            input_data={"value": 21},
            timeout=10.0,
        )
        assert result["doubled"] == 42
    finally:
        for agent in (worker, orchestrator):
            if agent is not None and agent.ws is not None:
                await agent.ws.close()
        _stop(acme)
        _stop(globex)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
