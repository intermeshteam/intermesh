import React from 'react';

interface InterMeshLogoProps {
  className?: string;
}

/**
 * Marque InterMesh : le fichier fourni (`public/intermesh-logo.png`), pas une
 * reconstruction vectorielle — la couleur est déjà dans l'image, donc
 * `className` ne sert qu'à la taille/le positionnement, pas la teinte.
 */
export default function InterMeshLogo({ className = 'w-7 h-7' }: InterMeshLogoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src="/intermesh-logo.png" alt="InterMesh" className={`object-contain ${className}`} />
  );
}
