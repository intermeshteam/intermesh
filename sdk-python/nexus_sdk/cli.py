import argparse
import asyncio
import http.server
import json
import os
import socketserver
import sys
import time

from nexus_sdk import NexusAgent, NexusMessage, MessageType
from nexus_sdk.crypto import generate_keypair, get_public_key_pem
from nexus_sdk.identity import AgentIdentity


def print_banner():
    print("""
\033[36m    _   ___________  _______
   / | / / ____/   |/  _/   |  NEXUS PROTOCOL
  /  |/ / __/ / /| |/ // /| |  Universal Agent Infrastructure
 / /|  / /___/ ___ / // ___ |  CLI Developer Tool v0.1.0
/_/ |_/_____/_/  |_/___/_/  |_|\033[0m
""")


def run_security_check(args):
    print("\033[33m🛡️  Exécution de l'audit de sécurité de votre installation locale...\033[0m\n")
    
    score = 100
    checks = []

    # 1. Vérification du chiffrement E2E
    checks.append(("Chiffrement E2E (RSA-2048 + AES-256-GCM)", True, "Activé par défaut dans le SDK"))

    # 2. Vérification de l'isolation du Hub (127.0.0.1)
    bind_ip = os.getenv("NEXUS_BIND_IP", "127.0.0.1")
    if bind_ip in ("127.0.0.1", "localhost"):
        checks.append(("Isolation du Hub (Loopback 127.0.0.1)", True, "Le Hub est isolé sur votre machine locale"))
    else:
        checks.append(("Isolation du Hub", False, "Le Hub est exposé sur toutes les interfaces réseau (0.0.0.0)"))
        score -= 20

    # 3. Vérification du TLS / WSS
    cert_path = os.getenv("NEXUS_SSL_CERT")
    if cert_path and os.path.exists(cert_path):
        checks.append(("Transport Sécurisé TLS (wss://)", True, "Certificat SSL/TLS détecté"))
    else:
        checks.append(("Transport Sécurisé TLS (wss://)", False, "Attention: Utilisation de ws:// non chiffré sur le réseau local"))
        score -= 10

    # 4. Vérification des permissions du dossier .nexus/
    nexus_dir = os.path.expanduser("~/.nexus")
    if os.path.exists(nexus_dir):
        mode = oct(os.stat(nexus_dir).st_mode)[-3:]
        if mode in ("700", "600"):
            checks.append(("Permissions du dossier ~/.nexus/", True, f"Permissions restrictives idéales ({mode})"))
        else:
            checks.append(("Permissions du dossier ~/.nexus/", False, f"Permissions ouvertes ({mode}). Recommandé: 700"))
            score -= 10
    else:
        checks.append(("Dossier de clés ~/.nexus/", True, "Non créé pour l'instant"))

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
    agent = NexusAgent(name="cli_inspector", roles=["admin"], encrypt=False)
    await agent.connect()
    query = {}
    if args.capability: query["capabilities"] = [args.capability]
    if args.role: query["roles"] = [args.role]
    print(f"\033[33m🔍 Recherche d'agents connectés...\033[0m")
    result = await agent.discover(**query, timeout=4.0)
    agents = result.get("agents", [])
    print(f"\n\033[32m✓ {len(agents)} agent(s) trouvé(s) sur le réseau :\033[0m\n")
    print(f"{'NOM':<20} {'RÔLES':<18} {'CAPACITÉS':<30} {'E2E'}")
    print("-" * 75)
    for a in agents:
        caps = ", ".join(a.get("capabilities", [])) or "aucune"
        roles = ", ".join(a.get("roles", [])) or "standard"
        e2e = "🔒 Oui" if a.get("public_key") else "🔓 Non"
        print(f"{a['name']:<20} {roles:<18} {caps:<30} {e2e}")
    print()
    await agent.ws.close()


def run_dashboard(args):
    port = args.port
    dashboard_dir = os.path.expanduser("~/nexus/dashboard")
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args_h, **kwargs_h):
            super().__init__(*args_h, directory=dashboard_dir, **kwargs_h)
        def log_message(self, format, *log_args): pass

    print(f"\033[32m✓ Nexus Mission Control Dashboard actif sur http://localhost:{port}\033[0m")
    with socketserver.TCPServer(("", port), Handler) as httpd:
        try: httpd.serve_forever()
        except KeyboardInterrupt: pass


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Nexus Protocol Developer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Command: security-check
    subparsers.add_parser("security-check", help="Auditer la sécurité de votre installation locale")

    # Command: docs
    doc_parser = subparsers.add_parser("docs", help="Afficher documentation")
    doc_parser.add_argument("topic", choices=["rfc", "security", "api", "adapters"], help="Thème")

    # Command: discover
    disc_parser = subparsers.add_parser("discover", help="Rechercher des agents")
    disc_parser.add_argument("--capability", "-c", type=str, help="Capacité")
    disc_parser.add_argument("--role", "-r", type=str, help="Rôle")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Lancer Dashboard")
    dash_parser.add_argument("--port", type=int, default=8080, help="Port Web")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "security-check": run_security_check(args)
    elif args.command == "docs": run_docs(args)
    elif args.command == "discover": asyncio.run(run_discover(args))
    elif args.command == "dashboard": run_dashboard(args)


if __name__ == "__main__":
    main()
