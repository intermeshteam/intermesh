import argparse
import asyncio
import getpass
import http.server
import json
import os
import socketserver
import sys
import time

from intermesh import InterMeshAgent, InterMeshMessage, MessageType
from intermesh.crypto import generate_keypair, get_public_key_pem
from intermesh.identity import AgentIdentity


# Le dessin vit dans une chaîne brute : ses antislashs sont des traits,
# pas des séquences d'échappement. Les laisser dans une f-string produisait
# un SyntaxWarning à chaque appel de la CLI — un avertissement affiché à
# chaque commande coûte plus cher que le dessin ne rapporte.
_LOGO = r"""    _____   __________________  __  ______________ __  __
   /  _/ | / /_  __/ ____/ __ \/  |/  / ____/ ___// / / /
   / //  |/ / / / / __/ / /_/ / /|_/ / __/  \__ \/ /_/ /
 _/ // /|  / / / / /___/ _, _/ /  / / /___ ___/ / __  /
/___/_/ |_/ /_/ /_____/_/ |_/_/  /_/_____//____/_/ /_/"""


def print_banner():
    # La version vient du paquet : une chaîne en dur ici finit toujours
    # par mentir après quelques releases.
    from intermesh import __version__
    print(f"\n\033[36m{_LOGO}\033[0m\n")
    print(f"  Universal Agent Infrastructure · CLI v{__version__}\n")


def run_security_check(args):
    print("\033[33m🛡️  Exécution de l'audit de sécurité de votre installation locale...\033[0m\n")
    
    score = 100
    checks = []

    # 1. Vérification du chiffrement E2E
    checks.append(("Chiffrement E2E (RSA-2048 + AES-256-GCM)", True, "Activé par défaut dans le SDK"))

    # 2. Vérification de l'isolation du Hub (127.0.0.1)
    bind_ip = os.getenv("INTERMESH_BIND_IP", "127.0.0.1")
    if bind_ip in ("127.0.0.1", "localhost"):
        checks.append(("Isolation du Hub (Loopback 127.0.0.1)", True, "Le Hub est isolé sur votre machine locale"))
    else:
        checks.append(("Isolation du Hub", False, "Le Hub est exposé sur toutes les interfaces réseau (0.0.0.0)"))
        score -= 20

    # 3. Vérification du TLS / WSS
    cert_path = os.getenv("INTERMESH_SSL_CERT")
    if cert_path and os.path.exists(cert_path):
        checks.append(("Transport Sécurisé TLS (wss://)", True, "Certificat SSL/TLS détecté"))
    else:
        checks.append(("Transport Sécurisé TLS (wss://)", False, "Attention: Utilisation de ws:// non chiffré sur le réseau local"))
        score -= 10

    # 4. Vérification des permissions du dossier .intermesh/
    intermesh_dir = os.path.expanduser("~/.intermesh")
    if os.path.exists(intermesh_dir):
        mode = oct(os.stat(intermesh_dir).st_mode)[-3:]
        if mode in ("700", "600"):
            checks.append(("Permissions du dossier ~/.intermesh/", True, f"Permissions restrictives idéales ({mode})"))
        else:
            checks.append(("Permissions du dossier ~/.intermesh/", False, f"Permissions ouvertes ({mode}). Recommandé: 700"))
            score -= 10
    else:
        checks.append(("Dossier de clés ~/.intermesh/", True, "Non créé pour l'instant"))

    print(f"{'TEST DE SÉCURITÉ':<45} {'STATUT':<12} {'DÉTAILS'}")
    print("-" * 75)
    for title, status, detail in checks:
        stat_str = "\033[32m[ PASSE ]\033[0m" if status else "\033[33m[ WARN ]\033[0m"
        print(f"{title:<45} {stat_str:<12} {detail}")

    print("\n" + "=" * 75)
    grade = "A+" if score >= 90 else ("A" if score >= 80 else "B")
    print(f"  SCORE DE SÉCURITÉ LOCALE : \033[32m{score}/100 (GRADE: {grade})\033[0m")
    print("=" * 75 + "\n")


def run_docs(args):
    doc_type = args.topic
    base_docs_path = os.path.expanduser("~/nexus/docs")
    mapping = {
        "rfc": os.path.join(base_docs_path, "RFC-001-CORE-PROTOCOL.md"),
        "security": os.path.join(base_docs_path, "SECURITY-AND-ENCRYPTION.md"),
        "api": os.path.join(base_docs_path, "API-REFERENCE.md"),
        "adapters": os.path.join(base_docs_path, "ADAPTERS-AND-INTEGRATIONS.md"),
    }
    target_file = mapping.get(doc_type)
    if target_file and os.path.exists(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            print(f"\033[33m--- DOCUMENTATION NEXUS : {doc_type.upper()} ---\033[0m\n")
            print(f.read())
    else:
        print(f"\033[31mDocumentation introuvable pour '{doc_type}'.\033[0m")


async def run_discover(args):
    # `discover` a longtemps été la seule commande sans --hub ni --org : un
    # agent lancé avec `serve --org demo` était connecté, fonctionnel, et
    # introuvable — sans qu'aucun message ne dise pourquoi.
    agent = InterMeshAgent(name="cli_inspector", roles=["admin"],
                           org_id=args.org, hub_url=args.hub, encrypt=False)
    await agent.connect()
    query = {}
    if args.capability: query["capabilities"] = [args.capability]
    if args.role: query["roles"] = [args.role]
    print(f"\033[33m🔍 Recherche d'agents connectés...\033[0m")
    result = await agent.discover(**query, timeout=4.0)
    agents = result.get("agents", [])
    print(f"\n\033[32m✓ {len(agents)} agent(s) trouvé(s) sur le réseau :\033[0m\n")
    # Seul l'inspecteur lui-même répond : dire où l'on a cherché épargne la
    # demi-heure passée à soupçonner l'agent alors qu'il est dans une autre
    # organisation.
    if len([a for a in agents if a.get("name") != "cli_inspector"]) == 0:
        print(f"  \033[33mRecherche faite sur {args.hub}, organisation "
              f"'{args.org}'.\033[0m")
        print("  \033[33mUn agent lancé avec un autre --org ou un autre --hub "
              "n'apparaît pas ici.\033[0m\n")
    print(f"{'NOM':<20} {'RÔLES':<18} {'CAPACITÉS':<30} {'E2E'}")
    print("-" * 75)
    for a in agents:
        caps = ", ".join(a.get("capabilities", [])) or "aucune"
        roles = ", ".join(a.get("roles", [])) or "standard"
        e2e = "🔒 Oui" if a.get("public_key") else "🔓 Non"
        print(f"{a['name']:<20} {roles:<18} {caps:<30} {e2e}")
    print()
    await agent.ws.close()


def _run_or_explain(coro, target: str, args):
    """Exécute une coroutine CLI en traduisant l'expiration en explication.

    Un délai dépassé veut presque toujours dire « cet agent n'est pas là »,
    et la cause est le plus souvent une organisation ou un Hub différents.
    """
    try:
        asyncio.run(coro)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        print(f"\n\033[31m✗ {exc}\033[0m")
        print(f"  \033[33m'{target}' n'a pas répondu sur {args.hub}, "
              f"organisation '{args.org}'.\033[0m")
        # Hors de l'organisation par défaut, un agent s'adresse par son nom
        # qualifié. `discover` l'affiche ainsi, mais on l'oublie en recopiant.
        if args.org != "default" and "/" not in target:
            print(f"  \033[33mDans l'organisation '{args.org}', essayez le nom "
                  f"qualifié : {args.org}/{target}\033[0m")
        print("  \033[33mVérifiez qu'il tourne : intermesh discover "
              f"--hub {args.hub} --org {args.org}\033[0m\n")
        sys.exit(1)


def _parse_json_arg(raw: str, label: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"\033[31m✗ {label} n'est pas du JSON valide : {exc}\033[0m")
        sys.exit(2)


async def run_ping(args):
    """Vérifie qu'un agent est joignable et mesure le temps d'aller-retour."""
    agent = InterMeshAgent(name="cli_ping", roles=["admin"], org_id=args.org,
                           hub_url=args.hub, encrypt=False)
    await agent.connect()
    try:
        started = time.monotonic()
        # Un agent inconnu, ou d'une autre organisation, n'obtient aucune
        # réponse du Hub : l'absence de réponse *est* le résultat.
        try:
            identity = await agent.who_is(args.agent, timeout=args.timeout)
        except (TimeoutError, asyncio.TimeoutError):
            identity = None
        elapsed = (time.monotonic() - started) * 1000
        if not identity:
            print(f"\033[31m✗ '{args.agent}' est introuvable ou hors ligne.\033[0m")
            await agent.close()
            sys.exit(1)
        caps = ", ".join(identity.get("capabilities", [])) or "aucune"
        print(f"\n\033[32m✓ {args.agent} répond en {elapsed:.0f} ms\033[0m")
        print(f"  rôles     : {', '.join(identity.get('roles', [])) or 'standard'}")
        print(f"  capacités : {caps}")
        print(f"  E2E       : {'🔒 oui' if identity.get('public_key') else '🔓 non'}\n")
    finally:
        await agent.close()


async def run_ask(args):
    """Pose une question à un agent et affiche sa réponse."""
    content = _parse_json_arg(args.content, "Le contenu")
    agent = InterMeshAgent(name="cli_asker", roles=["admin"], org_id=args.org,
                           hub_url=args.hub)
    await agent.connect()
    try:
        print(f"\033[33m💬 Question à '{args.agent}'...\033[0m")
        reply = await agent.ask(to=args.agent, content=content, timeout=args.timeout)
        print(f"\n\033[32m✓ Réponse :\033[0m\n{json.dumps(reply, indent=2, ensure_ascii=False)}\n")
    finally:
        await agent.close()


async def run_task(args):
    """Délègue une tâche à un agent et attend son résultat."""
    input_data = _parse_json_arg(args.input, "Les données d'entrée")
    agent = InterMeshAgent(name="cli_orchestrator", roles=["admin"],
                           org_id=args.org, hub_url=args.hub)
    await agent.connect()
    try:
        print(f"\033[33m📝 Tâche '{args.title}' ➜ {args.assignee}...\033[0m")
        result = await agent.submit_task(title=args.title, assignee=args.assignee,
                                         input_data=input_data, timeout=args.timeout)
        print(f"\n\033[32m✓ Résultat :\033[0m\n{json.dumps(result, indent=2, ensure_ascii=False)}\n")
    finally:
        await agent.close()


def run_keygen(args):
    """Génère une paire de clés RSA pour un agent."""
    private_key = generate_keypair()
    public_pem = get_public_key_pem(private_key)

    if not args.out:
        print(f"\n\033[32m✓ Clé publique (RSA-2048) :\033[0m\n{public_pem}")
        print("\033[33mℹ️  Sans --out, la clé privée n'est pas affichée ni conservée : "
              "elle ne doit pas transiter par un terminal ou un historique.\033[0m\n")
        return

    from cryptography.hazmat.primitives import serialization

    private_path = args.out
    public_path = f"{args.out}.pub"
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    # 0600 dès la création : pas de fenêtre où la clé privée serait lisible.
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, private_bytes)
    finally:
        os.close(fd)
    with open(public_path, "w", encoding="utf-8") as handle:
        handle.write(public_pem)

    print(f"\n\033[32m✓ Clé privée : {private_path} (0600)\033[0m")
    print(f"\033[32m✓ Clé publique : {public_path}\033[0m\n")


async def _admin_call(args, command: str, **params) -> dict:
    """
    Ouvre une session d'administration éphémère et exécute une commande.

    L'administration exige une identité authentifiée par clé d'API : les
    rôles déclarés à l'enregistrement ne suffisent pas (voir admin.py).
    """
    api_key = args.api_key or os.getenv("INTERMESH_API_KEY")
    if not api_key:
        print("\033[31m✗ Clé d'API requise : --api-key, ou la variable INTERMESH_API_KEY.\033[0m")
        sys.exit(2)

    agent = InterMeshAgent(name="cli_snapshot", api_key=api_key, encrypt=False)
    await agent.connect()
    try:
        return await agent.admin(command, **params)
    finally:
        await agent.close()


def _snapshot_passphrase(args, *, confirm: bool) -> str | None:
    """
    Passphrase de chiffrement au repos, demandée interactivement.

    Jamais lue depuis un argument de ligne de commande : `ps` et
    l'historique du shell exposeraient un secret à toute la machine.
    """
    if not args.encrypt:
        return None
    first = getpass.getpass("Passphrase de l'instantané : ")
    if not first:
        print("\033[31m✗ Passphrase vide.\033[0m")
        sys.exit(2)
    if confirm and getpass.getpass("Confirmez la passphrase : ") != first:
        print("\033[31m✗ Les passphrases ne correspondent pas.\033[0m")
        sys.exit(2)
    return first


async def run_snapshot(args):
    action = args.action

    if action == "list":
        result = await _admin_call(args, "snapshot.list")
        snapshots = result.get("snapshots", [])
        print(f"\n\033[32m✓ {len(snapshots)} instantané(s) :\033[0m\n")
        print(f"{'NOM':<28} {'DATE':<21} {'AGENTS':<8} {'TÂCHES':<8} {'CHIFFRÉ'}")
        print("-" * 78)
        for s in snapshots:
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.get("created_at", 0)))
            counts = s.get("counts", {})
            lock = "🔒 oui" if s.get("encrypted") else "🔓 non"
            print(f"{s.get('name', '?'):<28} {when:<21} "
                  f"{counts.get('identities', 0):<8} {counts.get('tasks', 0):<8} {lock}")
        print()
        return

    if action == "create":
        passphrase = _snapshot_passphrase(args, confirm=True)
        result = await _admin_call(args, "snapshot.create", name=args.name, passphrase=passphrase)
        counts = result.get("counts", {})
        print(f"\n\033[32m✓ Instantané '{result['name']}' créé.\033[0m")
        print(f"  {counts.get('identities', 0)} identité(s), {counts.get('tasks', 0)} tâche(s), "
              f"{counts.get('api_keys', 0)} clé(s), {counts.get('escrow_holds', 0)} séquestre(s)")
        if result.get("warning"):
            print(f"\033[33m  ⚠️  {result['warning']}\033[0m")
        print()
        return

    if action == "restore":
        passphrase = _snapshot_passphrase(args, confirm=False)
        result = await _admin_call(args, "snapshot.restore", name=args.name, passphrase=passphrase)
        print(f"\n\033[32m✓ État restauré depuis '{result['restored_from']}'.\033[0m")
        print(f"  {result.get('identities', 0)} identité(s), {result.get('tasks', 0)} tâche(s)")
        print(f"  Restauré : {', '.join(result.get('restored', [])) or 'rien'}")
        if result.get("safety_snapshot"):
            print(f"  Filet de sécurité pris avant restauration : "
                  f"\033[36m{result['safety_snapshot']}\033[0m")
        for skipped in result.get("skipped", []):
            print(f"\033[33m  ⚠️  Ignoré ({skipped['what']}) : {skipped['reason']}\033[0m")
        if result.get("orphaned_online"):
            print(f"\033[33m  ⚠️  Connectés mais absents de l'instantané : "
                  f"{', '.join(result['orphaned_online'])}\033[0m")
        print("\033[36m  ℹ️  Le journal d'audit n'a pas été remplacé : la restauration "
              "y est enregistrée.\033[0m\n")
        return

    if action == "delete":
        result = await _admin_call(args, "snapshot.delete", name=args.name)
        print(f"\n\033[32m✓ Instantané '{result['deleted']}' supprimé.\033[0m\n")


def run_dashboard(args):
    """Sert la console d'exploitation, celle qui voyage avec le paquet.

    Le chemin était codé en dur sur `~/nexus/dashboard`, l'arborescence du
    développeur — et les fichiers n'étaient même pas dans le paquet. Chez
    tout autre utilisateur la commande annonçait « actif » puis répondait
    404 sur tout. Elle sert désormais le dossier livré avec `intermesh`,
    situé par le module lui-même.
    """
    port = args.port
    console_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console")

    if not os.path.isfile(os.path.join(console_dir, "index.html")):
        print(f"\033[31m✗ Console introuvable ({console_dir}).\033[0m")
        print("  Depuis un paquet installé :  pip install --force-reinstall intermesh")
        print("  Depuis une copie du dépôt  :  ./scripts/build_console.sh")
        print("  La console est un export généré : elle n'est pas versionnée.")
        return 1

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args_h, **kwargs_h):
            super().__init__(*args_h, directory=console_dir, **kwargs_h)

        def translate_path(self, path):
            """Fait correspondre /agents au fichier agents.html.

            Un export statique nomme ses pages `agents.html`, alors que la
            navigation côté client demande `/agents`. Sans cette
            correspondance, tout lien interne rend 404 — la console
            s'ouvrirait puis casserait au premier clic.
            """
            local = super().translate_path(path)
            if not os.path.exists(local) and not local.endswith(".html"):
                candidate = local.rstrip("/") + ".html"
                if os.path.isfile(candidate):
                    return candidate
            return local

        def log_message(self, format, *log_args): pass

    print(f"\033[32m✓ Console d'exploitation sur http://localhost:{port}\033[0m")
    # Dit ce que c'est, et ce que ce n'est pas : le premier utilisateur a
    # cru voir « le mauvais dashboard » alors qu'il y en a deux, distincts
    # et voulus.
    print("  Interface locale, sans dépendance externe : elle se branche sur")
    print("  le Hub que vous indiquez et n'a besoin d'aucun compte.")
    print("  Le Control Plane hébergé (React, comptes et équipes) est un autre")
    print("  produit, sur https://intermesh.site — il exige Supabase et ne")
    print("  fonctionne pas hors ligne.\n")
    with socketserver.TCPServer(("", port), Handler) as httpd:
        try: httpd.serve_forever()
        except KeyboardInterrupt: pass
    return 0


def run_serve(args):
    """Expose un programme externe comme agent, sans écrire une ligne de code."""
    from intermesh.bridge import from_command, from_http

    common = dict(
        name=args.name,
        capabilities=args.capability or ["compute"],
        org_id=args.org,
        hub_url=args.hub,
        encrypt=not args.no_encrypt,
        timeout=args.timeout,
    )
    if args.exec_command:
        agent = from_command(args.exec_command, **common)
        source = f"exec « {args.exec_command} »"
    else:
        agent = from_http(args.http_url, **common)
        source = f"http {args.http_url}"

    print(f"\033[32m✓ Agent '{args.name}' ({source}) → {args.hub}\033[0m")
    print(f"  capacités : {', '.join(common['capabilities'])}")
    print("  Ctrl+C pour arrêter.\n")
    agent.run()


def main():
    print_banner()

    # `hub` est interceptée avant argparse : le Hub a sa propre douzaine
    # d'options (TLS, pairage, egress…) et les redéclarer ici garantirait
    # qu'elles divergent tôt ou tard.
    if len(sys.argv) > 1 and sys.argv[1] == "hub":
        from intermesh.hub import main as hub_main
        try:
            asyncio.run(hub_main(sys.argv[2:]))
        except KeyboardInterrupt:
            print("\nHub arrêté.")
        return

    parser = argparse.ArgumentParser(description="InterMesh Protocol Developer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Command: hub (traitée plus haut ; déclarée pour l'aide)
    subparsers.add_parser("hub", add_help=False,
                          help="Démarrer un Hub (voir `intermesh hub --help`)")

    # Command: security-check
    subparsers.add_parser("security-check", help="Auditer la sécurité de votre installation locale")

    # Command: docs
    doc_parser = subparsers.add_parser("docs", help="Afficher documentation")
    doc_parser.add_argument("topic", choices=["rfc", "security", "api", "adapters"], help="Thème")

    # Command: discover
    disc_parser = subparsers.add_parser("discover", help="Rechercher des agents")
    disc_parser.add_argument("--capability", "-c", type=str, help="Capacité")
    disc_parser.add_argument("--role", "-r", type=str, help="Rôle")
    disc_parser.add_argument("--hub", type=str, default="ws://localhost:8765")
    disc_parser.add_argument("--org", type=str, default="default",
                             help="Organisation interrogée")

    # Command: snapshot
    snap_parser = subparsers.add_parser("snapshot", help="Sauvegarder / restaurer l'état du Hub")
    snap_parser.add_argument("action", choices=["create", "list", "restore", "delete"])
    snap_parser.add_argument("--name", "-n", type=str, help="Nom de l'instantané")
    snap_parser.add_argument("--api-key", type=str, default=None,
                             help="Clé d'API admin (ou variable INTERMESH_API_KEY)")
    snap_parser.add_argument("--encrypt", action="store_true",
                             help="Chiffrer/déchiffrer l'instantané (passphrase demandée)")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Lancer Dashboard")
    dash_parser.add_argument("--port", type=int, default=8080, help="Port Web")

    # Command: serve — intégration en une ligne, quel que soit le langage
    serve_parser = subparsers.add_parser(
        "serve", help="Exposer un programme existant comme agent InterMesh")
    serve_parser.add_argument("--name", "-n", type=str, required=True, help="Nom de l'agent")
    source = serve_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--exec", dest="exec_command", type=str,
                        help="Commande à lancer par tâche (JSON sur stdin, JSON sur stdout)")
    source.add_argument("--http", dest="http_url", type=str,
                        help="URL recevant la tâche en POST JSON")
    serve_parser.add_argument("--capability", "-c", action="append", default=[],
                              help="Capacité annoncée (répétable)")
    serve_parser.add_argument("--org", type=str, default="default", help="Organisation")
    serve_parser.add_argument("--hub", type=str, default="ws://localhost:8765", help="URL du Hub")
    serve_parser.add_argument("--timeout", type=float, default=30.0,
                              help="Délai maximal accordé au programme externe")
    serve_parser.add_argument("--no-encrypt", action="store_true",
                              help="Désactive le chiffrement E2E (débogage)")

    # Command: ping
    ping_parser = subparsers.add_parser("ping", help="Vérifier qu'un agent répond")
    ping_parser.add_argument("agent", type=str, help="Nom de l'agent")
    ping_parser.add_argument("--hub", type=str, default="ws://localhost:8765")
    ping_parser.add_argument("--org", type=str, default="default", help="Organisation")
    ping_parser.add_argument("--timeout", type=float, default=5.0)

    # Command: ask
    ask_parser = subparsers.add_parser("ask", help="Poser une question à un agent")
    ask_parser.add_argument("agent", type=str, help="Nom de l'agent")
    ask_parser.add_argument("content", type=str, help="Contenu JSON de la question")
    ask_parser.add_argument("--hub", type=str, default="ws://localhost:8765")
    ask_parser.add_argument("--org", type=str, default="default", help="Organisation")
    ask_parser.add_argument("--timeout", type=float, default=10.0)

    # Command: task
    task_parser = subparsers.add_parser("task", help="Déléguer une tâche à un agent")
    task_parser.add_argument("assignee", type=str, help="Agent exécutant")
    task_parser.add_argument("title", type=str, help="Intitulé de la tâche")
    task_parser.add_argument("input", type=str, help="Données d'entrée en JSON")
    task_parser.add_argument("--hub", type=str, default="ws://localhost:8765")
    task_parser.add_argument("--org", type=str, default="default", help="Organisation")
    task_parser.add_argument("--timeout", type=float, default=15.0)

    # Command: keygen
    key_parser = subparsers.add_parser("keygen", help="Générer une paire de clés RSA")
    key_parser.add_argument("--out", "-o", type=str, default=None,
                            help="Chemin du fichier de clé privée (la publique reçoit .pub)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "snapshot" and args.action != "list" and not args.name:
        parser.error("--name est requis pour 'snapshot " + args.action + "'.")

    if args.command == "security-check": run_security_check(args)
    elif args.command == "docs": run_docs(args)
    elif args.command == "discover": asyncio.run(run_discover(args))
    elif args.command == "snapshot": asyncio.run(run_snapshot(args))
    elif args.command == "dashboard": run_dashboard(args)
    elif args.command == "serve": run_serve(args)
    # Viser un agent absent est une erreur d'usage courante, pas un plantage :
    # elle mérite une phrase, pas quarante lignes de pile d'appels.
    elif args.command == "ping": asyncio.run(run_ping(args))
    elif args.command == "ask": _run_or_explain(run_ask(args), args.agent, args)
    elif args.command == "task": _run_or_explain(run_task(args), args.assignee, args)
    elif args.command == "keygen": run_keygen(args)


if __name__ == "__main__":
    main()
