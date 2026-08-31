import type { MetadataRoute } from 'next';

/**
 * Only the pages a search engine should index.
 *
 * /auth and /signup are deliberately absent: they are account plumbing with no
 * standalone content, and having them compete in results is worse than not
 * ranking them at all. Everything under (app) is behind the middleware, so a
 * crawler would only ever see a redirect.
 */

export const BASE_URL = 'https://intermesh.site';

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return [
    { url: BASE_URL, lastModified, changeFrequency: 'weekly', priority: 1 },
    { url: `${BASE_URL}/docs`, lastModified, changeFrequency: 'weekly', priority: 0.8 },
    { url: `${BASE_URL}/pricing`, lastModified, changeFrequency: 'monthly', priority: 0.6 },
    { url: `${BASE_URL}/terms`, lastModified, changeFrequency: 'yearly', priority: 0.2 },
    { url: `${BASE_URL}/privacy`, lastModified, changeFrequency: 'yearly', priority: 0.2 },
  ];
}
