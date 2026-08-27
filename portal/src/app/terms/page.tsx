'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function TermsPage() {
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
              Conditions d&apos;utilisation
            </h1>
            <p className="text-sm text-slate-500 mt-2">
              Dernière mise à jour : 26 août 2026
            </p>
          </div>
        </div>

        <div className="space-y-8 text-sm leading-relaxed">
          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">1. Acceptation des conditions</h2>
            <p>
              En accédant à Nexus Protocol, au Control Plane, aux SDKs, à la CLI ou à tout service associé
              (ci-après « le Service »), vous acceptez les présentes Conditions d&apos;utilisation.
              Si vous n&apos;acceptez pas ces conditions, vous ne devez pas utiliser le Service.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">2. Description du Service</h2>
            <p>
              Nexus est un protocole open source et une infrastructure de coordination pour agents IA.
              Le Service comprend notamment :
            </p>
            <ul className="list-disc pl-5 space-y-1 text-slate-400">
              <li>les SDKs Python et JavaScript/TypeScript ;</li>
              <li>la CLI développeur ;</li>
              <li>le Hub self-hosted et le Control Plane ;</li>
              <li>les fonctionnalités Enterprise (quotas, licences, audit, RBAC) selon le plan souscrit.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">3. Comptes et accès</h2>
            <p>
              Vous êtes responsable de la confidentialité de vos identifiants, clés API et clés de licence.
              Toute activité réalisée via votre compte ou vos clés est réputée effectuée sous votre responsabilité.
              Vous devez nous informer sans délai de toute utilisation non autorisée.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">4. Plans Free, Pro et Enterprise</h2>
            <p>
              Le plan Free est limité à un maximum de 10 agents actifs simultanés, sauf licence contraire.
              Les plans Pro et Enterprise débloquent des quotas et fonctionnalités supplémentaires
              conformément à la page Pricing et à votre contrat applicable.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">5. Usage autorisé et interdit</h2>
            <p>Vous vous engagez à utiliser le Service de manière légale et responsable. Il est interdit de :</p>
            <ul className="list-disc pl-5 space-y-1 text-slate-400">
              <li>contourner les quotas, licences, contrôles d&apos;accès ou mécanismes de sécurité ;</li>
              <li>utiliser le Service pour des activités illégales, frauduleuses ou nuisibles ;</li>
              <li>perturber l&apos;infrastructure, procéder à des attaques ou du reverse engineering malveillant ;</li>
              <li>revendre le Service sans autorisation écrite.</li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">6. Propriété intellectuelle</h2>
            <p>
              Le code open source de Nexus est distribué sous licence Apache 2.0, sauf mention contraire.
              Les composants propriétaires (Control Plane commercial, fonctionnalités Enterprise, marque)
              restent la propriété de Nexus Protocol et de ses ayants droit.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">7. Données et confidentialité</h2>
            <p>
              Le traitement des données personnelles est décrit dans notre{' '}
              <Link href="/privacy" className="text-white underline underline-offset-4 hover:text-slate-300">
                Politique de confidentialité
              </Link>
              . Pour les déploiements self-hosted, vous restez responsable des données traitées
              sur votre propre infrastructure.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">8. Disponibilité et support</h2>
            <p>
              Le Service est fourni « en l&apos;état ». Les niveaux de disponibilité (SLA) et de support
              dépendent du plan souscrit. Aucune garantie absolue de disponibilité ininterrompue
              n&apos;est fournie hors engagement contractuel Enterprise.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">9. Limitation de responsabilité</h2>
            <p>
              Dans les limites autorisées par la loi, Nexus Protocol ne saurait être tenu responsable
              des dommages indirects, pertes de données, pertes de profits ou interruptions d&apos;activité
              résultant de l&apos;utilisation ou de l&apos;impossibilité d&apos;utiliser le Service.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">10. Résiliation</h2>
            <p>
              Nous pouvons suspendre ou résilier l&apos;accès au Service en cas de violation des présentes
              conditions, d&apos;usage abusif, de non-paiement ou de risque de sécurité. Vous pouvez cesser
              d&apos;utiliser le Service à tout moment.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">11. Droit applicable</h2>
            <p>
              Les présentes conditions sont régies par les lois applicables dans le pays d&apos;établissement
              de l&apos;éditeur du Service, sous réserve des dispositions impératives locales.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-base font-semibold text-white">12. Contact</h2>
            <p>
              Pour toute question relative aux présentes conditions :{' '}
              <span className="text-white font-mono text-xs">legal@nexusprotocol.org</span>
            </p>
          </section>
        </div>

        <div className="pt-6 border-t border-slate-900 flex items-center justify-between text-xs text-slate-600">
          <span>© 2026 Nexus Protocol</span>
          <div className="flex items-center space-x-4">
            <Link href="/privacy" className="hover:text-slate-300 transition">Confidentialité</Link>
            <Link href="/auth" className="hover:text-slate-300 transition">Connexion</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
