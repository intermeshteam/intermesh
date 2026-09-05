"""
Le Quick start du README, pris au mot.

Ces commandes étaient documentées mais absentes du CLI : un développeur
qui suivait le README butait dès l'étape 1. Le Hub vivait en plus hors du
paquet, donc `pip install intermesh` ne le livrait pas du tout.
"""

import asyncio
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

PORT = 8930
HUB_URL = f"ws://localhost:{PORT}"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node.js absent de la machine")

CLI = [sys.executable, "-m", "intermesh.cli"]


def _run(*args, timeout=30):
    return subprocess.run(CLI + list(args), capture_output=True, text=True, timeout=timeout)


# ----------------------------------------------------------------------
# Packaging : le Hub doit être livré avec le paquet
# ----------------------------------------------------------------------

def test_hub_lives_inside_the_installed_package():
    """
    Régression : `server/hub.py` était hors du paquet, donc absent du
    wheel publié sur PyPI. `intermesh hub` ne pouvait pas exister.
    """
    import intermesh

    package_dir = Path(intermesh.__file__).resolve().parent
    assert (package_dir / "hub.py").is_file(), "le Hub doit être dans le paquet"

    # setuptools embarque `intermesh*` : ce qui est dans ce dossier est publié.
    import intermesh.hub as hub_module
    assert Path(hub_module.__file__).resolve().parent == package_dir


def test_legacy_entrypoint_still_works():
    """`python3 server/hub.py` reste valable — la doc existante y renvoie."""
    source = Path(__file__).resolve().parent.parent / "server" / "hub.py"

    assert source.is_file()
    assert "from intermesh.hub import main" in source.read_text(encoding="utf-8")


def test_hub_help_is_reachable_through_the_cli():
    result = _run("hub", "--help")

    assert result.returncode == 0
    for option in ("--port", "--org", "--peer", "--tls-cert", "--egress-policy"):
        assert option in result.stdout, f"{option} devrait apparaître dans l'aide du Hub"


# ----------------------------------------------------------------------
# keygen
# ----------------------------------------------------------------------

def test_keygen_never_prints_the_private_key():
    """Une clé privée ne doit pas finir dans un historique de terminal."""
    result = _run("keygen")

    assert result.returncode == 0
    assert "BEGIN PUBLIC KEY" in result.stdout
    assert "PRIVATE KEY" not in result.stdout


def test_keygen_writes_the_private_key_with_owner_only_permissions(tmp_path):
    target = tmp_path / "agent_key"
    result = _run("keygen", "--out", str(target))

    assert result.returncode == 0
    assert target.is_file()
    assert Path(f"{target}.pub").is_file()
    assert "BEGIN PRIVATE KEY" in target.read_text()
    assert "BEGIN PUBLIC KEY" in Path(f"{target}.pub").read_text()

    mode = target.stat().st_mode
    assert not mode & stat.S_IRWXG, "le groupe ne doit avoir aucun droit"
    assert not mode & stat.S_IRWXO, "les autres ne doivent avoir aucun droit"


# ----------------------------------------------------------------------
# Le parcours complet : hub → serve → ping → task
# ----------------------------------------------------------------------

def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def cli_hub():
    os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
    time.sleep(0.4)
    proc = subprocess.Popen(
        CLI + ["hub", "--port", str(PORT), "--ephemeral-state", "--ephemeral-secret"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.0)
    yield
    _stop(proc)


def test_invalid_json_is_rejected_with_a_clear_message(cli_hub):
    result = _run("task", "someone", "Titre", "{pas du json}")

    assert result.returncode == 2
    assert "JSON" in result.stdout


@needs_node
def test_full_quick_start_hub_serve_ping_task(cli_hub, tmp_path):
    """
    Bout en bout, uniquement des commandes du README : le Hub démarre,
    un script Node est exposé comme agent, on le ping, on lui délègue une
    tâche. Aucun code d'intégration.
    """
    script = tmp_path / "calc.js"
    script.write_text("""
let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const input = JSON.parse(data);
  process.stdout.write(JSON.stringify({result: input.a * input.b}));
});
""", encoding="utf-8")

    served = subprocess.Popen(
        CLI + ["serve", "--name", "calc_bot", "--exec", f"{NODE} {script}",
               "--capability", "calculate", "--hub", HUB_URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.5)

    try:
        ping = _run("ping", "calc_bot", "--hub", HUB_URL)
        assert ping.returncode == 0, ping.stdout + ping.stderr
        assert "calc_bot répond" in ping.stdout
        assert "calculate" in ping.stdout

        task = _run("task", "calc_bot", "Compute", '{"a": 42, "b": 2}',
                    "--hub", HUB_URL, timeout=40)
        assert task.returncode == 0, task.stdout + task.stderr
        assert '"result": 84' in task.stdout
    finally:
        _stop(served)


def test_ping_reports_an_unknown_agent_as_a_failure(cli_hub):
    result = _run("ping", "fantome", "--hub", HUB_URL, "--timeout", "3")

    assert result.returncode == 1
    assert "introuvable" in result.stdout


# ----------------------------------------------------------------------
# Viser un autre Hub, une autre organisation
# ----------------------------------------------------------------------

def test_discover_can_target_a_hub_and_an_org():
    """
    Régression : `discover` était la seule commande sans --hub ni --org.
    Un agent lancé avec `serve --org demo` était connecté, joignable, et
    introuvable — sans qu'aucun message n'explique pourquoi.
    """
    result = _run("discover", "--help")

    assert result.returncode == 0
    assert "--hub" in result.stdout
    assert "--org" in result.stdout


@pytest.mark.parametrize("command", ["ping", "ask", "task"])
def test_every_addressing_command_accepts_an_org(command):
    """`--org` sur `serve` est un piège si l'on ne peut pas viser cette org."""
    result = _run(command, "--help")

    assert result.returncode == 0
    assert "--org" in result.stdout, f"'{command}' doit accepter --org"


def test_discover_says_where_it_looked_when_it_finds_nothing(cli_hub):
    """Sans cette phrase, on soupçonne l'agent plutôt que l'adresse."""
    result = _run("discover", "--hub", HUB_URL, "--org", "vide")

    assert result.returncode == 0
    assert HUB_URL in result.stdout
    assert "vide" in result.stdout


def test_timeout_explains_itself_instead_of_dumping_a_traceback(cli_hub):
    """
    Régression : viser un agent absent produisait quarante lignes de pile
    d'appels Python. C'est une erreur d'usage courante, pas un plantage.
    """
    result = _run("task", "fantome", "Titre", "{}",
                  "--hub", HUB_URL, "--org", "demo", "--timeout", "3", timeout=40)

    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert "expirée" in result.stdout
    # Hors de l'organisation par défaut, le nom qualifié est la cause n° 1.
    assert "demo/fantome" in result.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
