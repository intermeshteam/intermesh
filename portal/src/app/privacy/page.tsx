'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[#08080A] text-slate-300 font-sans">
      <div className="max-w-3xl mx-auto px-6 py-10 space-y-10">
        <div className="space-y-4">
          <Link href="/auth" className="inline-flex items-center space-x-2 text-xs text-slate-500 hover:text-white transition">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Retour</span>
          </Link>

          <div>
            <div className="text-[11px] font-mono tracking-widest text-slate-500 uppercase mb-2">
              LEGAL
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              Politique de confidentialité
            </h1>
            <p className="text-sm text-slate-500 mt-2">
              Dernière mise à jour : 26 août 2026
            </p>
          </div>
        </div>

        <div className="space-y-8 text-sm leading-relaxed">
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">1. Introduction</h2>
            <p>
              La présente Politique de confidentialité décrit comment Nexus Protocol collecte,
              utilise et protège vos informations lorsque vous utilisez le site, le Control Plane,
              les SDKs et les services associés.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">2. Données que nous collectons</h2>
            <p>Selon votre usage, nous pouvons collecter :</p>
            <ul className="list-disc pl-5 space-y-1 text-slate-400">
              <li><span className="text-slate-200">Données de compte</span> : email, nom d&apos;organisation, identifiants OAuth (ex. GitHub) ;</li>
              <li><span className="text-slate-200">Données techniques</span> : logs d&apos;accès, adresse IP, type de navigateur, horodatages ;</li>
              <li><span className="text-slate-200">Données d&apos;usage produit</span> : nombre d&apos;agents, événements de quota, génération de clés/licences ;</li>
              <li><span className="text-slate-200">Données de facturation</span> : informations de paiement traitées par notre prestataire (ex. Stripe).</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">3. Données que nous ne collectons pas par défaut</h2>
            <p>
              Dans un déploiement self-hosted, le contenu des messages échangés entre agents
              (payloads chiffrés E2E) reste sur votre infrastructure. Nexus n&apos;accède pas au
              contenu en clair des communications agent-à-agent chiffrées de bout en bout.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">4. Finalités d&apos;utilisation</h2>
            <p>Nous utilisons vos données pour :</p>
            <ul className="list-disc pl-5 space-y-1 text-slate-400">
              <li>fournir, sécuriser et améliorer le Service ;</li>
              <li>authentifier les utilisateurs et gérer les accès ;</li>
              <li>appliquer les quotas et licences ;</li>
              <li>assurer le support, la facturation et la conformité ;</li>
              <li>prévenir la fraude, les abus et les incidents de sécurité.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">5. Base légale (RGPD)</h2>
            <p>
              Lorsque le RGPD s&apos;applique, nos traitements reposent notamment sur :
              l&apos;exécution du contrat, l&apos;intérêt légitime (sécurité, amélioration produit),
              et le consentement lorsque requis.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">6. Partage des données</h2>
            <p>
              Nous ne vendons pas vos données personnelles. Nous pouvons partager certaines
              informations avec des prestataires strictement nécessaires (hébergement, paiement,
              email transactionnel, monitoring), sous obligations de confidentialité appropriées.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">7. Conservation</h2>
            <p>
              Nous conservons les données aussi longtemps que nécessaire aux finalités décrites,
              aux obligations légales, comptables et de sécurité. Les logs techniques peuvent être
              conservés pour une durée limitée selon le plan et les besoins opérationnels.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">8. Sécurité</h2>
            <p>
              Nous mettons en œuvre des mesures techniques et organisationnelles adaptées :
              chiffrement en transit, contrôles d&apos;accès, journaux d&apos;audit, bonnes pratiques
              de gestion des secrets. Aucun système n&apos;étant parfaitement inviolable, nous
              recommandons également de sécuriser vos propres environnements self-hosted.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">9. Vos droits</h2>
            <p>
              Selon votre juridiction, vous pouvez disposer de droits d&apos;accès, de rectification,
              d&apos;effacement, de limitation, d&apos;opposition et de portabilité. Pour exercer ces droits,
              contactez-nous à l&apos;adresse ci-dessous.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">10. Cookies</h2>
            <p>
              Le site peut utiliser des cookies essentiels au fonctionnement (session, sécurité)
              et, le cas échéant, des cookies de mesure d&apos;audience. Vous pouvez configurer votre
              navigateur pour limiter les cookies non essentiels.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">11. Transferts internationaux</h2>
            <p>
              Si des données sont transférées hors de votre pays, nous mettons en place les
              garanties appropriées lorsque la loi l&apos;exige.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">12. Contact</h2>
            <p>
              Pour toute demande relative à la confidentialité :{' '}
              <span className="text-white font-mono text-xs">privacy@nexusprotocol.org</span>
            </p>
          </section>
        </div>

        <div className="pt-6 border-t border-slate-900 flex items-center justify-between text-xs text-slate-600">
          <span>© 2026 Nexus Protocol</span>
          <div className="flex items-center space-x-4">
            <Link href="/terms" className="hover:text-slate-300 transition">Conditions</Link>
            <Link href="/auth" className="hover:text-slate-300 transition">Connexion</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
