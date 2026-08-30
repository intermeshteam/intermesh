"""
Négociation d'une parcelle entre deux entreprises.

Deux organisations, chacune avec son propre Hub, reliées par un pairage
fédéré. Aucune ne fait confiance à l'autre : les jetons sont signés en
Ed25519 par une clé qui ne quitte jamais son Hub, et chaque message relayé
est vérifié contre la clé publique publiée par le pair.

    TERRASEINE (acheteur)                DOMAINE VERDIER (vendeur)
      acquisition_lead                     sales_director
      finance_approver                     parcel_registry
      legal_auditor                        notary_signer

Le déroulé suit une vraie transaction : consultation du cadastre, offre,
contre-offre, arbitrage budgétaire interne côté acheteur, offre finale,
puis — si accord — audit juridique, signature notariée et libération du
séquestre. À la fin, une notification système annonce l'issue.

Usage :
    python3 examples/negociation_parcelle.py            # budget suffisant
    python3 examples/negociation_parcelle.py --budget 700000   # échec

Les deux Hubs sont démarrés et arrêtés par le script.
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from intermesh import InterMeshAgent

ACHETEUR_PORT = 8871
VENDEUR_PORT = 8872

PARCELLE = {
    "reference": "AB-1042",
    "lieu": "Les Hauts de Marly",
    "surface_m2": 4200,
    "constructible": True,
    "servitudes": ["passage réseau enterré (2 m)"],
}

PRIX_PLANCHER = 780_000.0   # sous ce prix, le vendeur refuse
PRIX_AFFICHE = 900_000.0

# Compte de service de l'acheteur. Le sequestre est une commande
# d'administration, et le Hub exige pour cela une identite prouvee par cle
# d'API : les roles qu'un agent se declare lui-meme ne suffisent pas.
CLE_ACHETEUR = "nx_demo_terraseine_escrow"
CLES_ACHETEUR = json.dumps({
    CLE_ACHETEUR: {
        "org_id": "terraseine",
        "roles": ["admin", "service_account"],
        "permissions": ["admin:*"],
    }
})


# ----------------------------------------------------------------------
# Présentation
# ----------------------------------------------------------------------

def etape(n: int, texte: str) -> None:
    print(f"\n\033[36m▸ ÉTAPE {n}\033[0m  {texte}")


def dire(qui: str, quoi: str) -> None:
    print(f"    \033[90m{qui:<28}\033[0m {quoi}")


def notifier(succes: bool, titre: str, corps: str) -> None:
    """Notification de bureau, avec repli sur le terminal.

    L'issue d'une transaction ne doit pas se lire uniquement dans un flot
    de journaux : c'est le seul moment qui demande l'attention d'un humain.
    """
    urgence = "normal" if succes else "critical"
    icone = "dialog-information" if succes else "dialog-error"

    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", urgence, "-i", icone, "-a", "InterMesh", titre, corps],
            check=False,
        )

    couleur = "\033[32m" if succes else "\033[31m"
    largeur = 74
    print(f"\n{couleur}{'═' * largeur}")
    print(f"  {titre}")
    print(f"{'─' * largeur}\033[0m")
    for ligne in corps.split("\n"):
        print(f"  {ligne}")
    print(f"{couleur}{'═' * largeur}\033[0m\n")


# ----------------------------------------------------------------------
# Hubs
# ----------------------------------------------------------------------

def demarrer_hub(port: int, org: str, pair: str | None = None, cles: str | None = None):
    racine = Path(__file__).resolve().parent.parent
    cmd = [
        sys.executable, "-u", str(racine / "server" / "hub.py"),
        "--port", str(port), "--org", org,
        "--ephemeral-state", "--ephemeral-secret",
    ]
    if pair:
        cmd += ["--peer", pair]
    env = {**os.environ}
    if cles:
        env["INTERMESH_API_KEYS"] = cles
    return subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def arreter(proc) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ----------------------------------------------------------------------
# Scénario
# ----------------------------------------------------------------------

async def scenario(budget_max: float) -> bool:
    url_acheteur = f"ws://localhost:{ACHETEUR_PORT}"
    url_vendeur = f"ws://localhost:{VENDEUR_PORT}"

    # ---- Agents du vendeur -------------------------------------------
    async def cadastre(entree, tache):
        dire("verdier/parcel_registry", f"Fiche cadastrale {entree['reference']} transmise")
        return {**PARCELLE, "prix_affiche": PRIX_AFFICHE}

    async def signature(entree, tache):
        dire("verdier/notary_signer", f"Acte signé pour {entree['prix']:,.0f} €".replace(",", " "))
        await asyncio.sleep(0.4)
        return {
            "statut": "SIGNE",
            "acte": "2026-AB-1042-NOT",
            "empreinte": "0x7f3a9c2e5b1d4086",
        }

    async def commercial(msg):
        contenu = msg.content
        action = contenu.get("action")

        if action == "OFFRE_INITIALE":
            offre = contenu["prix"]
            dire("verdier/sales_director", f"Offre reçue : {offre:,.0f} € — sous notre plancher".replace(",", " "))
            return {
                "statut": "CONTRE_OFFRE",
                "prix": PRIX_AFFICHE,
                "message": "Parcelle constructible, viabilisée. Nous proposons 900 000 €.",
            }

        if action == "OFFRE_FINALE":
            offre = contenu["prix"]
            if offre >= PRIX_PLANCHER:
                dire("verdier/sales_director", f"Offre de {offre:,.0f} € ACCEPTÉE".replace(",", " "))
                return {"statut": "ACCEPTE", "prix": offre}
            dire("verdier/sales_director",
                 f"Offre de {offre:,.0f} € refusée — plancher à {PRIX_PLANCHER:,.0f} €".replace(",", " "))
            return {"statut": "REFUSE", "plancher": PRIX_PLANCHER}

        return {"statut": "ACTION_INCONNUE"}

    registry = InterMeshAgent(name="parcel_registry", org_id="verdier",
                              capabilities=["cadastre"], roles=["worker"], hub_url=url_vendeur)
    registry.on_task(cadastre)
    await registry.connect()

    notaire = InterMeshAgent(name="notary_signer", org_id="verdier",
                             capabilities=["signature"], roles=["worker"], hub_url=url_vendeur)
    notaire.on_task(signature)
    await notaire.connect()

    commercial_agent = InterMeshAgent(name="sales_director", org_id="verdier",
                                      roles=["admin"], hub_url=url_vendeur)
    commercial_agent.on_request(commercial)
    await commercial_agent.connect()

    # ---- Agents de l'acheteur ----------------------------------------
    async def finance(entree, tache):
        demande = entree["montant"]
        ok = demande <= budget_max
        dire("terraseine/finance_approver",
             f"Budget max {budget_max:,.0f} € — demande {demande:,.0f} € : {'accordé' if ok else 'refusé'}".replace(",", " "))
        return {"accorde": ok, "plafond": budget_max, "contre_proposition": min(demande, budget_max)}

    async def juridique(entree, tache):
        dire("terraseine/legal_auditor",
             f"Audit : {len(entree['servitudes'])} servitude(s), constructible={entree['constructible']}")
        await asyncio.sleep(0.4)
        return {"avis": "FAVORABLE", "reserves": entree["servitudes"]}

    approbateur = InterMeshAgent(name="finance_approver", org_id="terraseine",
                                 capabilities=["validation_budget"], roles=["worker"], hub_url=url_acheteur)
    approbateur.on_task(finance)
    await approbateur.connect()

    auditeur = InterMeshAgent(name="legal_auditor", org_id="terraseine",
                              capabilities=["audit_juridique"], roles=["worker"], hub_url=url_acheteur)
    auditeur.on_task(juridique)
    await auditeur.connect()

    lead = InterMeshAgent(name="acquisition_lead", org_id="terraseine",
                          roles=["admin"], hub_url=url_acheteur)
    await lead.connect()

    await asyncio.sleep(1.2)

    # ---- Déroulé ------------------------------------------------------
    etape(1, "Consultation du cadastre chez le vendeur (tâche fédérée)")
    fiche = await lead.submit_task(
        title=f"Fiche cadastrale {PARCELLE['reference']}",
        assignee="verdier/parcel_registry",
        input_data={"reference": PARCELLE["reference"]},
        timeout=15,
    )
    dire("terraseine/acquisition_lead",
         f"{fiche['surface_m2']} m² au {fiche['lieu']} — affiché {fiche['prix_affiche']:,.0f} €".replace(",", " "))

    etape(2, "Première offre")
    offre_initiale = 700_000.0
    dire("terraseine/acquisition_lead", f"Offre de {offre_initiale:,.0f} €".replace(",", " "))
    reponse = await lead.ask(to="verdier/sales_director",
                             content={"action": "OFFRE_INITIALE", "prix": offre_initiale},
                             timeout=15)

    etape(3, "Arbitrage budgétaire interne")
    avis = await lead.submit_task(
        title="Validation budgétaire",
        assignee="terraseine/finance_approver",
        input_data={"montant": reponse["prix"]},
        timeout=15,
    )
    offre_finale = avis["contre_proposition"]

    etape(4, "Offre finale")
    dire("terraseine/acquisition_lead", f"Offre finale : {offre_finale:,.0f} €".replace(",", " "))
    verdict = await lead.ask(to="verdier/sales_director",
                             content={"action": "OFFRE_FINALE", "prix": offre_finale},
                             timeout=15)

    if verdict["statut"] != "ACCEPTE":
        notifier(
            False,
            "Négociation échouée — parcelle AB-1042",
            f"TerraSeine n'a pas obtenu la parcelle « {PARCELLE['lieu']} ».\n\n"
            f"Dernière offre  : {offre_finale:,.0f} €\n"
            f"Plancher vendeur: {verdict['plancher']:,.0f} €\n"
            f"Écart           : {verdict['plancher'] - offre_finale:,.0f} €\n\n"
            "Aucun acte signé. Aucun fonds engagé.".replace(",", " "),
        )
        return False

    etape(5, "Audit juridique interne")
    audit = await lead.submit_task(
        title="Audit juridique de la parcelle",
        assignee="terraseine/legal_auditor",
        input_data={"servitudes": fiche["servitudes"], "constructible": fiche["constructible"]},
        timeout=15,
    )

    etape(6, "Signature notariée, paiement sous séquestre")

    # Le registre de sequestre est simule : sans provision, la retenue est
    # refusee. Un tresorier approvisionne le compte de l'organisation.
    tresorier = InterMeshAgent(name="treasury", org_id="terraseine",
                               api_key=CLE_ACHETEUR, hub_url=url_acheteur, encrypt=False)
    await tresorier.connect()
    await tresorier.admin("escrow.grant", amount=offre_finale, currency="EUR")
    solde = await tresorier.admin("escrow.balance", currency="EUR")
    dire("terraseine/treasury", f"Provision du séquestre : {solde['balance']:,.0f} €".replace(",", " "))
    acte = await lead.submit_task(
        title="Signature de l'acte de vente",
        assignee="verdier/notary_signer",
        input_data={"prix": offre_finale, "reference": PARCELLE["reference"]},
        timeout=15,
        escrow={"amount": offre_finale, "currency": "EUR", "auto_release": True},
    )
    dire("hub", "Séquestre libéré à la complétion de la tâche")

    notifier(
        True,
        "Acquisition réussie — parcelle AB-1042",
        f"TerraSeine acquiert « {PARCELLE['lieu']} » ({PARCELLE['surface_m2']} m²).\n\n"
        f"Prix convenu : {offre_finale:,.0f} €\n"
        f"Acte         : {acte['acte']}\n"
        f"Empreinte    : {acte['empreinte']}\n"
        f"Avis juridique: {audit['avis']}\n\n"
        "Paiement libéré du séquestre.".replace(",", " "),
    )

    for agent in (registry, notaire, commercial_agent, approbateur, auditeur, lead, tresorier):
        if agent.ws:
            await agent.ws.close()
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Négociation fédérée d'une parcelle")
    parser.add_argument("--budget", type=float, default=850_000.0,
                        help="Budget maximal de l'acheteur (défaut : 850000)")
    args = parser.parse_args()

    print("\n\033[1m  NÉGOCIATION INTER-ENTREPRISES — PARCELLE AB-1042\033[0m")
    print(f"  TerraSeine (acheteur, budget {args.budget:,.0f} €)".replace(",", " ")
          + f"  ↔  Domaine Verdier (vendeur, plancher {PRIX_PLANCHER:,.0f} €)".replace(",", " "))

    vendeur = demarrer_hub(VENDEUR_PORT, "verdier")
    time.sleep(1.5)
    acheteur = demarrer_hub(ACHETEUR_PORT, "terraseine",
                            pair=f"verdier=ws://localhost:{VENDEUR_PORT}",
                            cles=CLES_ACHETEUR)
    time.sleep(2.0)

    try:
        succes = await scenario(args.budget)
        return 0 if succes else 1
    finally:
        arreter(acheteur)
        arreter(vendeur)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
