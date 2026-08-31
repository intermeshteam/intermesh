import type { MetadataRoute } from 'next';
import { BASE_URL } from './sitemap';

/**
 * The Control Plane routes are already unreachable without a session — the
 * middleware redirects them to /auth. Disallowing them here is not a security
 * measure (robots.txt is advisory and public), it just keeps crawl budget on
 * the pages that have content, and keeps redirect chains out of the index.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/dashboard', '/topology', '/agents', '/keys', '/security', '/billing', '/settings', '/api/'],
    },
    sitemap: `${BASE_URL}/sitemap.xml`,
    host: BASE_URL,
  };
}
