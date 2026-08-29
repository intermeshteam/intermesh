"""
Pont universel : brancher un agent écrit dans n'importe quel langage.

Écrire un SDK natif par langage ne passe pas à l'échelle — il y en aurait
toujours un qui manque. Ce module prend le problème par l'autre bout : le
protocole reste du JSON, et l'agent étranger n'a qu'à savoir lire du JSON
sur son entrée standard, ou répondre à une requête HTTP. Go, Rust, Java,
PHP, C, un script shell : tout ce qui sait faire ça devient un agent
InterMesh sans une ligne de code d'intégration.

Deux modes, selon ce que le programme existant sait déjà faire :

  * `exec`  — un processus est lancé par tâche. Le JSON d'entrée arrive sur
              stdin, la réponse est lue sur stdout. C'est le mode des
              binaires, des scripts et des CLI.
  * `http`  — la tâche est POSTée en JSON sur une URL. C'est le mode des
              services déjà en ligne, qu'on ne veut pas relancer.

Tolérance assumée en mode `exec` : si stdout n'est pas du JSON valide, le
texte brut est renvoyé sous `{"output": ...}`. Un `echo` en shell doit
suffire à faire un agent ; exiger du JSON parfait tuerait le cas d'usage.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shlex
import signal
import urllib.error
import urllib.request
from typing import Any, Optional, Sequence

DEFAULT_TIMEOUT = 30.0


class BridgeError(RuntimeError):
    """L'agent externe a échoué : code de sortie non nul, timeout, ou HTTP en erreur."""


def _decode_output(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"output": text}


def _kill_process_group(process) -> None:
    """Tue le programme et toute sa descendance.

    Un agent qui dépasse son délai ne doit pas laisser d'orphelins derrière
    lui : ils continueraient de consommer des ressources et de tenir les
    tuyaux d'un appel qu'on a déjà abandonné.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return
    with contextlib.suppress(ProcessLookupError):
        process.kill()


async def run_command(command: str | Sequence[str], payload: Any,
                      timeout: float = DEFAULT_TIMEOUT) -> Any:
    """Exécute `command`, lui passe `payload` en JSON sur stdin, lit sa réponse.

    `command` accepte une chaîne (interprétée par le shell, pratique pour
    les pipelines) ou une liste d'arguments (sans shell, à préférer quand
    la commande vient d'une source non maîtrisée).
    """
    stdin_data = json.dumps(payload).encode("utf-8")

    # start_new_session place le programme dans son propre groupe de processus.
    # Sans ça, un timeout ne tue que le shell : ses enfants survivent, gardent
    # les tuyaux ouverts, et l'appel reste bloqué jusqu'à leur propre fin — le
    # délai maximal ne protégeait alors de rien.
    spawn = dict(
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    if isinstance(command, str):
        process = await asyncio.create_subprocess_shell(command, **spawn)
        shown = command
    else:
        process = await asyncio.create_subprocess_exec(*command, **spawn)
        shown = shlex.join(command)

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=stdin_data), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_process_group(process)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(process.wait(), timeout=5.0)
        raise BridgeError(f"'{shown}' n'a pas répondu en {timeout}s.")

    if process.returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip() or "(stderr vide)"
        raise BridgeError(f"'{shown}' a terminé avec le code {process.returncode} : {detail}")

    return _decode_output(stdout.decode("utf-8", "replace"))


def _post_json(url: str, payload: Any, timeout: float) -> Any:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return _decode_output(response.read().decode("utf-8", "replace"))


async def post_task(url: str, payload: Any, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """POSTe `payload` en JSON sur `url` et retourne la réponse décodée.

    urllib plutôt qu'un client HTTP tiers : le pont ne doit pas imposer une
    dépendance de plus à qui veut juste brancher un service existant.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _post_json, url, payload, timeout)
    except urllib.error.HTTPError as exc:
        raise BridgeError(f"{url} a répondu {exc.code} : {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise BridgeError(f"{url} injoignable : {exc.reason}") from exc


def exec_handler(command: str | Sequence[str], timeout: float = DEFAULT_TIMEOUT):
    """Handler de tâche déléguant à un programme externe."""
    async def handler(input_data: Any, task: Any):
        return await run_command(command, input_data, timeout)
    return handler


def http_handler(url: str, timeout: float = DEFAULT_TIMEOUT):
    """Handler de tâche déléguant à un service HTTP."""
    async def handler(input_data: Any, task: Any):
        return await post_task(url, input_data, timeout)
    return handler


def _build_agent(name: str, handler, capabilities, roles, org_id, hub_url,
                 encrypt, **kwargs):
    from intermesh.agent import InterMeshAgent

    agent = InterMeshAgent(
        name=name, org_id=org_id, capabilities=capabilities or ["compute"],
        roles=roles or ["worker"], hub_url=hub_url, encrypt=encrypt, **kwargs,
    )
    agent.on_task(handler)
    return agent


def from_command(command: str | Sequence[str], name: str,
                 capabilities: Optional[list] = None, roles: Optional[list] = None,
                 org_id: str = "default", hub_url: str = "ws://localhost:8765",
                 encrypt: bool = True, timeout: float = DEFAULT_TIMEOUT, **kwargs):
    """Transforme n'importe quel exécutable en agent InterMesh.

        agent = from_command("./mon-agent-en-go", name="pricing")
    """
    return _build_agent(name, exec_handler(command, timeout), capabilities, roles,
                        org_id, hub_url, encrypt, **kwargs)


def from_http(url: str, name: str,
              capabilities: Optional[list] = None, roles: Optional[list] = None,
              org_id: str = "default", hub_url: str = "ws://localhost:8765",
              encrypt: bool = True, timeout: float = DEFAULT_TIMEOUT, **kwargs):
    """Transforme n'importe quel service HTTP en agent InterMesh.

        agent = from_http("http://localhost:9000/task", name="scoring")
    """
    return _build_agent(name, http_handler(url, timeout), capabilities, roles,
                        org_id, hub_url, encrypt, **kwargs)
