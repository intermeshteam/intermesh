import React from 'react';

interface NexusLogoProps {
  className?: string;
}

/**
 * Marque Nexus : le fichier fourni (`public/nexus-logo.png`), pas une
 * reconstruction vectorielle — la couleur est déjà dans l'image, donc
 * `className` ne sert qu'à la taille/le positionnement, pas la teinte.
 */
export default function NexusLogo({ className = 'w-7 h-7' }: NexusLogoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src="/nexus-logo.png" alt="Nexus" className={`object-contain ${className}`} />
  );
}
