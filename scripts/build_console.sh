#!/usr/bin/env bash
#
# Construit la console locale : un export statique de l'interface du
# Control Plane, servi ensuite par `intermesh dashboard`.
#
#     ./scripts/build_console.sh
#
# Le résultat atterrit dans sdk-python/intermesh/console/, d'où il voyage
# avec le paquet Python. Il remplace l'ancienne page statique écrite à la
# main : maintenir deux interfaces pour le même travail les faisait
# diverger, et c'est ce qui a conduit un premier utilisateur à croire que
# la mauvaise s'affichait.
#
# Ce que ce script écarte le temps du build, et pourquoi :
#
#   * `src/app/api/` — `output: 'export'` refuse un gestionnaire de route.
#     Ces routes servent le site hébergé (devis, invitations, licences) et
#     n'ont aucun sens en local.
#   * `src/app/auth/`, `src/app/signup/` — la console locale s'authentifie
#     auprès du Hub par clé d'API, pas par un compte Supabase.
#
# Tout est remis en place par un `trap`, y compris si le build échoue ou si
# l'on interrompt : un dépôt à moitié démonté serait pire que pas de build.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORTAL="$ROOT/portal"
OUT="$ROOT/sdk-python/intermesh/console"
STASH="$(mktemp -d)"

restore() {
  for name in api auth signup; do
    if [ -d "$STASH/$name" ]; then
      rm -rf "$PORTAL/src/app/$name"
      mv "$STASH/$name" "$PORTAL/src/app/$name"
    fi
  done
  # `next build` ne prend pas de --config : il lit next.config.js à la
  # racine. On y pose donc celui de la console le temps du build, et on
  # remet exactement ce qui s'y trouvait — y compris rien.
  rm -f "$PORTAL/next.config.js"
  if [ -f "$STASH/next.config.js.orig" ]; then
    mv "$STASH/next.config.js.orig" "$PORTAL/next.config.js"
  fi
  rm -rf "$STASH"
}
trap restore EXIT INT TERM

cd "$PORTAL"

echo "→ mise à l'écart des routes API et des pages de compte…"
for name in api auth signup; do
  [ -d "src/app/$name" ] && mv "src/app/$name" "$STASH/$name"
done

[ -f next.config.js ] && cp next.config.js "$STASH/next.config.js.orig"
cp next.config.console.js next.config.js

echo "→ export statique (police système, aucun réseau requis)…"
rm -rf .next-console
npx next build 2>&1 | tail -20

if [ ! -f ".next-console/index.html" ]; then
  echo "✗ export absent — le build a échoué." >&2
  exit 1
fi

# Le site public n'a rien à faire dans une console d'exploitation : un
# utilisateur qui ouvre localhost:8080 doit voir le tableau de bord, pas
# la page d'accueil commerciale.
echo "→ retrait des pages publiques…"
for page in index pricing privacy terms docs; do
  rm -f ".next-console/$page.html" ".next-console/$page.txt"
done
rm -f .next-console/robots.txt .next-console/sitemap.xml
cp .next-console/dashboard.html .next-console/index.html

# Le titre vient du layout racine, partagé avec le site public. Dans un
# onglet de console, « The coordination protocol for AI agents » ne dit pas
# ce qu'on regarde.
echo "→ titre des pages…"
find .next-console -name "*.html" -exec sed -i \
  's|<title>[^<]*</title>|<title>InterMesh — Control Plane</title>|g' {} +

echo "→ installation dans $OUT…"
# __init__.py est conservé : c'est lui qui fait de console/ un sous-paquet,
# donc ce qui fait embarquer les fichiers dans la roue.
find "$OUT" -mindepth 1 -not -name "__init__.py" -delete
cp -r .next-console/. "$OUT/"
rm -rf .next-console

echo
echo "✓ console construite — $(du -sh "$OUT" | cut -f1), $(find "$OUT" -type f | wc -l) fichiers"
echo "  vérifier :  intermesh dashboard"
