import React from 'react';

/**
 * Le nom du produit, protégé de la traduction automatique.
 *
 * Google Traduction rendait « INTERMESH » par « ENTRETIENS » dans la barre
 * latérale du Control Plane : un visiteur francophone voyait un autre
 * produit que le vôtre, sur la page même où il évalue l'outil.
 *
 * L'attribut existait déjà sur les pages publiques, mais avait été oublié
 * dans l'application, l'écran d'authentification et un tableau
 * comparatif. Le répéter à la main garantissait qu'on l'oublie encore —
 * d'où ce composant : le nom ne s'écrit plus qu'à travers lui.
 *
 * `translate="no"` est l'attribut HTML standard ; la classe `notranslate`
 * est ce que Google respecte depuis plus longtemps. Les deux, parce que
 * l'enjeu est le nom de la marque et que la redondance ne coûte rien.
 */
export default function BrandName({
  className = '',
  as: Tag = 'span',
}: {
  className?: string;
  /** `span` par défaut ; `strong` ou `td` selon le contexte typographique. */
  as?: 'span' | 'strong';
}) {
  return (
    <Tag className={`notranslate ${className}`} translate="no">
      INTERMESH
    </Tag>
  );
}
