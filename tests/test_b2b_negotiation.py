import asyncio
import os
import sys
import subprocess
import pytest

from nexus_sdk import NexusAgent


# ============================================================================
# 1. LOGIQUE DES 3 AGENTS DE GLOBEX INC (NEW YORK - HUB 8766)
# ============================================================================

async def globex_pricing_handler(input_data, task):
    """Moteur de prix interne Globex : Calcule le prix plancher et la contre-offre."""
    requested_qty = input_data.get("quantity", 1000)
    cost_per_unit = 110.0  # Prix plancher absolu = 110 000 $
    target_price = 130000.0
    min_floor = requested_qty * cost_per_unit
    
    print(f"  📊 [globex/pricing_engine] Analyse marge : Plancher min = {min_floor:.2f} $ | Prix cible = {target_price:.2f} $")
    return {
        "min_floor": min_floor,
        "target_price": target_price,
        "can_accept_115k": 115000.0 >= min_floor
    }


async def globex_signer_handler(input_data, task):
    """Agent Signataire officiel de Globex Inc."""
    deal_price = input_data.get("price")
    print(f"  ✍️  [globex/contract_signer] Signature numérique du contrat au montant de {deal_price:.2f} $")
    await asyncio.sleep(0.5)
    return {
        "signature_status": "SIGNED",
        "contract_hash": "0x98f7a6b5c4d3e2f10987654321fedcba",
        "timestamp": "2026-08-26T18:00:00Z"
    }


async def globex_sales_request_handler(msg):
    """Directeur Commercial Globex : Négocie avec Acme."""
    content = msg.content
    action = content.get("action")
    
    if action == "INITIAL_OFFER":
        offer = content.get("offer_price", 0)
        print(f"  💬 [globex/sales_director] Offre reçue d'Acme : {offer:.2f} $. Trop bas ! Consultation du moteur de prix...")
        return {
            "status": "COUNTER_OFFER",
            "counter_price": 130000.0,
            "message": "100 000 $ est sous notre coût. Nous proposons 130 000 $ avec SLA 24/7."
        }
    elif action == "FINAL_OFFER":
        offer = content.get("offer_price", 0)
        print(f"  💬 [globex/sales_director] Dernier prix proposé par Acme : {offer:.2f} $")
        if offer >= 110000.0:
            print(f"  ✅ [globex/sales_director] Offre de {offer:.2f} $ ACCEPTÉE !")
            return {"status": "ACCEPTED", "agreed_price": offer}
        else:
            return {"status": "REJECTED"}
    return {"status": "UNKNOWN_ACTION"}


# ============================================================================
# 2. LOGIQUE DES 3 AGENTS DE ACME CORP (PARIS - HUB 8765)
# ============================================================================

async def acme_finance_handler(input_data, task):
    """Direction Financière Acme : Valide le budget maximal."""
    requested_amount = input_data.get("amount", 0)
    max_budget = 120000.0  # Budget max autorisé = 120 000 $
    
    print(f"  💰 [acme/finance_approver] Vérification budget pour {requested_amount:.2f} $ (Plafond max = {max_budget:.2f} $)")
    if requested_amount <= max_budget:
        return {"approved": True, "max_budget": max_budget, "recommended_offer": requested_amount}
    else:
        return {"approved": False, "max_budget": max_budget, "recommended_offer": 115000.0}


async def acme_legal_handler(input_data, task):
    """Direction Juridique Acme : Audite les clauses contractuelles."""
    price = input_data.get("price")
    print(f"  ⚖️  [acme/legal_auditor] Audit du contrat RFC-001 de {price:.2f} $...")
    await asyncio.sleep(0.5)
    return {"legal_status": "APPROVED", "compliance": "SOC2_ISO27001_VALID"}


# ============================================================================
# 3. LE SCÉNARIO DE NÉGOCIATION GLOBAL (TEST ASYNCHRONE)
# ============================================================================

@pytest.mark.asyncio
async def test_full_b2b_6_agents_negotiation():
    print("\n==========================================================================")
    print("   NEXUS PROTOCOL — SIMULATION DE NÉGOCIATION B2B (6 AGENTS / 2 HUBS)")
    print("==========================================================================\n")

    # 1. Libérer les ports et démarrer les 2 Hubs en Peering
    os.system("fuser -k 8765/tcp 8766/tcp || true")
    await asyncio.sleep(0.5)

    hub_globex = subprocess.Popen([sys.executable, "server/hub_telemetry.py", "--port", "8766", "--org", "globex"])
    await asyncio.sleep(1.0)

    hub_acme = subprocess.Popen([sys.executable, "server/hub_telemetry.py", "--port", "8765", "--org", "acme", "--peer", "globex=ws://localhost:8766"])
    await asyncio.sleep(1.5)

    try:
        # --- CONNEXION DES 3 AGENTS DE GLOBEX (NEW YORK - HUB 8766) ---
        sales_director = NexusAgent(name="sales_director", org_id="globex", roles=["admin"], hub_url="ws://localhost:8766")
        sales_director.on_request(globex_sales_request_handler)
        await sales_director.connect()

        pricing_engine = NexusAgent(name="pricing_engine", org_id="globex", capabilities=["pricing"], roles=["worker"], hub_url="ws://localhost:8766")
        pricing_engine.on_task(globex_pricing_handler)
        await pricing_engine.connect()

        contract_signer = NexusAgent(name="contract_signer", org_id="globex", capabilities=["signing"], roles=["worker"], hub_url="ws://localhost:8766")
        contract_signer.on_task(globex_signer_handler)
        await contract_signer.connect()

        # --- CONNEXION DES 3 AGENTS DE ACME (PARIS - HUB 8765) ---
        procurement_lead = NexusAgent(name="procurement_lead", org_id="acme", roles=["admin"], hub_url="ws://localhost:8765")
        await procurement_lead.connect()

        finance_approver = NexusAgent(name="finance_approver", org_id="acme", capabilities=["finance_approval"], roles=["worker"], hub_url="ws://localhost:8765")
        finance_approver.on_task(acme_finance_handler)
        await finance_approver.connect()

        legal_auditor = NexusAgent(name="legal_auditor", org_id="acme", capabilities=["legal_audit"], roles=["worker"], hub_url="ws://localhost:8765")
        legal_auditor.on_task(acme_legal_handler)
        await legal_auditor.connect()

        await asyncio.sleep(1.0)

        # ====================================================================
        # ÉTAPE 1 : ACME FAIT UNE PREMIÈRE OFFRE À 100 000 $
        # ====================================================================
        print("🤝 [ÉTAPE 1] Acme (Paris) ouvre les négociations avec Globex (New York)...")
        res1 = await procurement_lead.ask(
            to="globex/sales_director",
            content={"action": "INITIAL_OFFER", "offer_price": 100000.0, "quantity": 1000}
        )
        print(f"  📩 [Acme] Réponse de Globex : {res1['message']} (Contre-offre: {res1['counter_price']:.2f} $)\n")

        # ====================================================================
        # ÉTAPE 2 : ACME CONSULTE SA DIRECTION FINANCIÈRE EN INTERNE
        # ====================================================================
        print("🤝 [ÉTAPE 2] Acme consulte sa Direction Financière en interne pour 130 000 $...")
        fin_res = await procurement_lead.submit_task(
            title="Validation Budget 130k",
            assignee="acme/finance_approver",
            input_data={"amount": 130000.0}
        )
        recommended_price = fin_res["recommended_offer"]
        print(f"  💡 [Acme] Décision Finance : 130k $ Refusé (Max budget: {fin_res['max_budget']:.2f} $). Contre-offre fixée à {recommended_price:.2f} $\n")

        # ====================================================================
        # ÉTAPE 3 : ACME FAIT SA DERNIÈRE OFFRE À 115 000 $
        # ====================================================================
        print(f"🤝 [ÉTAPE 3] Acme soumet son ultime proposition de {recommended_price:.2f} $ à Globex...")
        res2 = await procurement_lead.ask(
            to="globex/sales_director",
            content={"action": "FINAL_OFFER", "offer_price": recommended_price}
        )
        agreed_price = res2["agreed_price"]
        print(f"  🎯 [Acme ↔ Globex] Accord commercial trouvé au prix de {agreed_price:.2f} $ !\n")

        # ====================================================================
        # ÉTAPE 4 : AUDIT JURIDIQUE ET SIGNATURE FINALE DU CONTRAT
        # ====================================================================
        print("🤝 [ÉTAPE 4] Audit Juridique Acme & Signature du Contrat Globex...")
        
        # Audit Juridique Acme
        legal_res = await procurement_lead.submit_task(
            title="Audit Juridique Contrat",
            assignee="acme/legal_auditor",
            input_data={"price": agreed_price}
        )
        print(f"  ⚖️  [Acme Legal] Statut : {legal_res['legal_status']} (Conformité: {legal_res['compliance']})")

        # Signature du Contrat par Globex
        sign_res = await procurement_lead.submit_task(
            title="Signature du Contrat Officiel",
            assignee="globex/contract_signer",
            input_data={"price": agreed_price}
        )
        print(f"  ✍️  [Globex Signer] Contrat Signé ! Hash : {sign_res['contract_hash']}\n")

        # ====================================================================
        # VERIFICATION FINALE DU TEST
        # ====================================================================
        print("==========================================================================")
        print("   BILAN DE LA NÉGOCIATION B2B MULTI-AGENTS")
        print("==========================================================================")
        print(f"  • Offre Initiale Acme  : 100 000.00 $ (Refusée)")
        print(f"  • Contre-Offre Globex  : 130 000.00 $ (Refusée par Finance)")
        print(f"  • Prix Final Négocié   : {agreed_price:.2f} $ (ACCEPTÉ & AUDITÉ)")
        print(f"  • Hash du Contrat      : {sign_res['contract_hash']}")
        print(f"  🔒 Toutes les 4 étapes ont été chiffrées de bout en bout en RSA-2048/AES-256.")
        print("==========================================================================\n")

        assert agreed_price == 115000.0
        assert legal_res["legal_status"] == "APPROVED"
        assert sign_res["signature_status"] == "SIGNED"

        # Fermeture des connexions
        await sales_director.ws.close()
        await pricing_engine.ws.close()
        await contract_signer.ws.close()
        await procurement_lead.ws.close()
        await finance_approver.ws.close()
        await legal_auditor.ws.close()

    finally:
        hub_acme.terminate()
        hub_globex.terminate()
        hub_acme.wait()
        hub_globex.wait()


if __name__ == "__main__":
    asyncio.run(test_full_b2b_6_agents_negotiation())
