/**
 * Police de la console locale : celle du système, aucune au téléchargement.
 *
 * Substitué à `fonts.ts` par le build de la console. En ne définissant pas
 * `--font-inter`, la déclaration de `globals.css` retombe d'elle-même sur
 * `-apple-system, BlinkMacSystemFont, "Segoe UI", …`. Le build n'a alors
 * besoin d'aucun réseau, ce qui le rend possible dans un réseau fermé.
 */
export const appFont = { variable: '', className: '' };
