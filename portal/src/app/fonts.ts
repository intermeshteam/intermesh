import { Inter } from 'next/font/google';

/**
 * Police du site hébergé.
 *
 * `next/font/google` télécharge Inter **au moment du build** et la sert
 * ensuite depuis notre propre domaine : la page finie n'appelle pas Google.
 * Mais le build, lui, exige un accès réseau — ce qui interdit de compiler
 * dans un réseau fermé, et c'est précisément ce que reproche
 * docs/AIR-GAPPED.md au Control Plane.
 *
 * Le build de la console locale substitue `fonts.system.ts` à ce module
 * (alias webpack dans next.config.console.js). `globals.css` déclarant
 * déjà `var(--font-inter), -apple-system, …`, l'absence de variable fait
 * simplement retomber sur la pile système : rien à changer ailleurs.
 */
export const appFont = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});
