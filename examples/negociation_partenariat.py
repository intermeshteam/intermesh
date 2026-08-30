"""
Négociation d'un partenariat commercial entre deux entreprises.

La question que cet exemple répond : comment dit-on à un agent de négocier ?

On ne lui dit rien pendant la négociation. On lui donne un MANDAT avant :
ce qu'il cherche, ce qu'il refuse, et ce qu'il peut lâcher. Le mandat est la
seule chose qu'un humain écrit. Ensuite les agents s'échangent des
propositions tour par tour, chacun jugeant celles de l'autre à l'aune de son
propre mandat — qu'il ne divulgue jamais.

C'est exactement ainsi qu'on brieferait un négociateur humain avant de
l'envoyer en réunion.

    TERRASEINE (distributeur)            DOMAINE VERDIER (producteur)
      partnership_lead                     partnership_desk
      (mandat côté distributeur)           (mandat côté producteur)

Usage :
    python3 examples/negociation_partenariat.py
    python3 examples/negociation_partenariat.py --commission-max 14
"""

import argparse
import asyncio
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from intermesh import InterMeshAgent

PORT_DISTRIBUTEUR = 8875
PORT_PRODUCTEUR = 8876
TOURS_MAX = 5


# ----------------------------------------------------------------------
# Le mandat — la seule chose qu'un humain écrit
# ----------------------------------------------------------------------

@dataclass
class Mandat:
    """Ce qu'un dirigeant confie à son négociateur avant la réunion.

    Rien ici ne décrit *comment* négocier. Uniquement les bornes : au-delà,
    l'agent n'a pas le droit de signer, et c'est ce qui rend la délégation
    acceptable.
    """
    objectif: str
    commission_pct: tuple[float, float]      # (souhaitée, limite absolue)
    duree_mois: tuple[int, int]              # (souhaitée, minimale acceptable)
    volume_min: int                          # engagement de volume annuel
    exclusivite_souhaitee: bool
    exclusivite_negociable: bool
    rompre_si: list[str] = field(default_factory=list)


MANDAT_DISTRIBUTEUR = Mandat(
    objectif="Distribuer la gamme Verdier sur le Grand Ouest",
    commission_pct=(12.0, 18.0),     # veut 12 %, ne dépassera pas 18 %
    duree_mois=(36, 24),
    volume_min=300,
    exclusivite_souhaitee=True,
    exclusivite_negociable=True,
    rompre_si=["commission au-delà du plafond", "durée sous 24 mois"],
)

MANDAT_PRODUCTEUR = Mandat(
    objectif="Ouvrir le Grand Ouest sans brader la marge",
    commission_pct=(20.0, 15.0),     # veut 20 %, ne descendra pas sous 15 %
    duree_mois=(24, 24),
    volume_min=400,                  # exige 400 unités pour l'exclusivité
    exclusivite_souhaitee=False,
    exclusivite_negociable=True,
    rompre_si=["commission sous le plancher", "exclusivité sans volume"],
)


# ----------------------------------------------------------------------
# La logique de négociation
#
# Déterministe ici : chaque agent compare la proposition reçue à son mandat
# et concède par paliers. C'est le seul endroit à remplacer par un appel à
# un modèle de langage — le mandat deviendrait l'invite système, la
# proposition reçue le message, et la réponse serait analysée en JSON. Le
# protocole, lui, ne changerait pas d'une ligne.
# ----------------------------------------------------------------------

def evaluer(mandat: Mandat, offre: dict, tour: int, cote_producteur: bool) -> dict:
    commission = offre["commission_pct"]
    duree = offre["duree_mois"]
    exclusivite = offre["exclusivite"]
    volume = offre["volume_annuel"]

    if cote_producteur:
        acceptable = commission >= mandat.commission_pct[1]
        if exclusivite and volume < mandat.volume_min:
            return {
                "statut": "CONTRE",
                "motif": f"exclusivité impossible sous {mandat.volume_min} unités",
                "offre": {**offre, "exclusivite": False},
            }
    else:
        acceptable = commission <= mandat.commission_pct[1]

    if duree < mandat.duree_mois[1]:
        return {"statut": "ROMPU", "motif": f"durée sous {mandat.duree_mois[1]} mois"}

    if acceptable:
        return {"statut": "ACCEPTE", "offre": offre}

    # Concession : on se rapproche de sa propre limite, sans jamais la franchir.
    pas = (mandat.commission_pct[1] - commission) / max(1, TOURS_MAX - tour)
    proposee = round(commission + pas, 1)
    borne = mandat.commission_pct[1]
    proposee = min(proposee, borne) if cote_producteur else max(proposee, borne)

    if abs(proposee - commission) < 0.2:
        return {"statut": "ROMPU", "motif": "positions figées, plus de marge de concession"}

    return {"statut": "CONTRE", "motif": "commission à ajuster",
            "offre": {**offre, "commission_pct": proposee}}


# ----------------------------------------------------------------------
# Présentation
# ----------------------------------------------------------------------

def dire(qui: str, quoi: str) -> None:
    print(f"    \033[90m{qui:<26}\033[0m {quoi}")


def resumer(offre: dict) -> str:
    excl = "exclusivité" if offre["exclusivite"] else "non exclusif"
    return (f"{offre['commission_pct']} % · {offre['duree_mois']} mois · "
            f"{offre['volume_annuel']} u/an · {excl}")


def notifier(succes: bool, titre: str, corps: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "normal" if succes else "critical",
                        "-i", "dialog-information" if succes else "dialog-error",
                        "-a", "InterMesh", titre, corps], check=False)
    couleur = "\033[32m" if succes else "\033[31m"
    print(f"\n{couleur}{'═' * 74}\n  {titre}\n{'─' * 74}\033[0m")
    for l in corps.split("\n"):
        print(f"  {l}")
    print(f"{couleur}{'═' * 74}\033[0m\n")


def demarrer_hub(port: int, org: str, pair: str | None = None):
    racine = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-u", str(racine / "server" / "hub.py"),
           "--port", str(port), "--org", org,
           "--ephemeral-state", "--ephemeral-secret"]
    if pair:
        cmd += ["--peer", pair]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def arreter(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()


# ----------------------------------------------------------------------

async def scenario(mandat_distributeur: Mandat) -> bool:
    url_d = f"ws://localhost:{PORT_DISTRIBUTEUR}"
    url_p = f"ws://localhost:{PORT_PRODUCTEUR}"

    async def desk_producteur(msg):
        c = msg.content
        verdict = evaluer(MANDAT_PRODUCTEUR, c["offre"], c["tour"], cote_producteur=True)
        if verdict["statut"] == "ACCEPTE":
            dire("verdier/partnership_desk", f"Tour {c['tour']} — ACCEPTE : {resumer(c['offre'])}")
        elif verdict["statut"] == "ROMPU":
            dire("verdier/partnership_desk", f"Tour {c['tour']} — rupture : {verdict['motif']}")
        else:
            dire("verdier/partnership_desk",
                 f"Tour {c['tour']} — contre : {resumer(verdict['offre'])} ({verdict['motif']})")
        return verdict

    desk = InterMeshAgent(name="partnership_desk", org_id="verdier",
                          roles=["admin"], hub_url=url_p)
    desk.on_request(desk_producteur)
    await desk.connect()

    lead = InterMeshAgent(name="partnership_lead", org_id="terraseine",
                          roles=["admin"], hub_url=url_d)
    await lead.connect()
    await asyncio.sleep(1.2)

    print(f"\n  Mandat distributeur : commission ≤ {mandat_distributeur.commission_pct[1]} %, "
          f"durée ≥ {mandat_distributeur.duree_mois[1]} mois")
    print(f"  Mandat producteur   : commission ≥ {MANDAT_PRODUCTEUR.commission_pct[1]} %, "
          f"exclusivité si ≥ {MANDAT_PRODUCTEUR.volume_min} u/an")
    print(f"\n\033[36m  Les deux mandats restent privés. Chacun ne voit que les propositions.\033[0m\n")

    offre = {
        "commission_pct": mandat_distributeur.commission_pct[0],
        "duree_mois": mandat_distributeur.duree_mois[0],
        "volume_annuel": mandat_distributeur.volume_min,
        "exclusivite": mandat_distributeur.exclusivite_souhaitee,
    }

    for tour in range(1, TOURS_MAX + 1):
        dire("terraseine/partnership_lead", f"Tour {tour} — propose : {resumer(offre)}")
        reponse = await lead.ask(to="verdier/partnership_desk",
                                 content={"tour": tour, "offre": offre}, timeout=15)

        if reponse["statut"] == "ACCEPTE":
            o = reponse["offre"]
            notifier(True, "Partenariat conclu — Grand Ouest",
                     f"TerraSeine distribuera la gamme Verdier.\n\n"
                     f"Commission : {o['commission_pct']} %\n"
                     f"Durée      : {o['duree_mois']} mois\n"
                     f"Volume     : {o['volume_annuel']} unités/an\n"
                     f"Exclusivité: {'oui' if o['exclusivite'] else 'non'}\n\n"
                     f"Accord trouvé en {tour} tour(s).")
            for a in (desk, lead):
                if a.ws:
                    await a.ws.close()
            return True

        if reponse["statut"] == "ROMPU":
            notifier(False, "Partenariat non conclu — Grand Ouest",
                     f"Les positions n'ont pas convergé.\n\n"
                     f"Motif : {reponse['motif']}\n"
                     f"Tours : {tour}\n\n"
                     "Aucun engagement pris de part et d'autre.")
            return False

        contre = reponse["offre"]
        notre = evaluer(mandat_distributeur, contre, tour, cote_producteur=False)
        if notre["statut"] == "ROMPU":
            notifier(False, "Partenariat non conclu — Grand Ouest",
                     f"La contre-proposition sort du mandat.\n\n"
                     f"Motif : {notre['motif']}\n"
                     f"Dernière contre-offre : {resumer(contre)}\n\n"
                     "Aucun engagement pris de part et d'autre.")
            return False
        if notre["statut"] == "ACCEPTE":
            offre = contre
            continue
        offre = notre["offre"]

    notifier(False, "Partenariat non conclu — Grand Ouest",
             f"Aucun accord après {TOURS_MAX} tours.\n\nLes mandats sont incompatibles en l'état.")
    return False


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commission-max", type=float, default=18.0,
                        help="Plafond de commission du distributeur (défaut : 18)")
    args = parser.parse_args()

    mandat = Mandat(**{**MANDAT_DISTRIBUTEUR.__dict__,
                       "commission_pct": (MANDAT_DISTRIBUTEUR.commission_pct[0], args.commission_max)})

    print("\n\033[1m  NÉGOCIATION D'UN PARTENARIAT — GRAND OUEST\033[0m")
    producteur = demarrer_hub(PORT_PRODUCTEUR, "verdier")
    time.sleep(1.5)
    distributeur = demarrer_hub(PORT_DISTRIBUTEUR, "terraseine",
                                pair=f"verdier=ws://localhost:{PORT_PRODUCTEUR}")
    time.sleep(2.0)
    try:
        return 0 if await scenario(mandat) else 1
    finally:
        arreter(distributeur)
        arreter(producteur)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
