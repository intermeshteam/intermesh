const path = require('path');

/**
 * Build de la console locale : un export statique de l'interface, sans
 * compte ni service externe.
 *
 * Trois différences avec le site hébergé :
 *
 *   * `output: 'export'` produit des fichiers statiques, servis par
 *     `intermesh dashboard` — donc aucun Node à l'exécution.
 *   * La police vient du système (alias ci-dessous) : le build n'a besoin
 *     d'aucun réseau, ce qui le rend possible dans un réseau fermé.
 *   * Les routes API et les pages de compte ne font pas partie de cette
 *     sortie ; le script de build les écarte, `output: 'export'` étant
 *     incompatible avec un gestionnaire de route.
 */
module.exports = {
  output: 'export',
  distDir: '.next-console',
  images: { unoptimized: true },
  webpack: (config) => {
    config.resolve.alias['./fonts'] = path.resolve(__dirname, 'src/app/fonts.system.ts');
    config.resolve.alias['@/app/fonts'] = path.resolve(__dirname, 'src/app/fonts.system.ts');
    return config;
  },
};
