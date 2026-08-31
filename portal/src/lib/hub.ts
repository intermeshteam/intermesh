/**
 * Where the portal reaches the InterMesh hub.
 *
 * The URL used to be fixed at build time through NEXT_PUBLIC_INTERMESH_HUB_URL,
 * which meant every visitor of a deployment shared one hardcoded address. For a
 * hosted Control Plane that is the wrong model: there is no single hub everyone
 * should talk to, and standing up a public one would mean a persistent server
 * plus an abuse surface from unauthenticated traffic.
 *
 * The model is the other way round — each person runs `intermesh hub` on their
 * own machine and the browser connects to it. Verified against the deployed
 * HTTPS site: browsers treat localhost as a trustworthy origin, so a ws://
 * connection to it from an https:// page is not blocked as mixed content, and
 * the full intermesh/v1 handshake completes.
 *
 * The value therefore has to be resolved per browser at runtime, not baked into
 * the bundle — hence localStorage, with the env var kept as the default for
 * deployments that really do have one shared hub.
 */

const STORAGE_KEY = 'intermesh.hub_url';

/** Default when the visitor has not chosen anything: their own local hub. */
export const DEFAULT_HUB_URL: string =
  process.env.NEXT_PUBLIC_INTERMESH_HUB_URL ?? 'ws://localhost:8765';

/** Rejects anything that is not a ws:// or wss:// URL, so a typo cannot throw inside `new WebSocket`. */
export function isValidHubUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === 'ws:' || u.protocol === 'wss:';
  } catch {
    return false;
  }
}

/** Hosts the browser treats as trustworthy, where plain ws:// stays allowed from an https:// page. */
function isLoopbackHost(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname.endsWith('.localhost') ||
    hostname === '127.0.0.1' ||
    hostname === '[::1]' ||
    hostname === '::1'
  );
}

/**
 * True when the browser will refuse this URL outright rather than fail to reach it.
 *
 * A page served over HTTPS may not open a plain ws:// socket to anything other
 * than a loopback host: `new WebSocket()` throws a SecurityError synchronously,
 * before a single packet leaves the machine. Verified from the deployed site —
 * ws:// to a remote host throws, wss:// to the same host does not.
 *
 * This distinction is the whole point of the function. Both cases otherwise
 * surface as "not reachable", which sends someone off to inspect firewalls and
 * server logs for a connection their own browser declined to attempt. A hub on
 * a VPS, at Hostinger or anywhere else off the local machine, has to be wss://.
 */
export function isBlockedByMixedContent(value: string): boolean {
  if (typeof window === 'undefined') return false;
  if (window.location.protocol !== 'https:') return false;
  try {
    const u = new URL(value);
    return u.protocol === 'ws:' && !isLoopbackHost(u.hostname);
  } catch {
    return false;
  }
}

/**
 * Resolves the hub URL for this browser. Safe to call during SSR, where there
 * is no localStorage — it falls back to the default.
 */
export function getHubUrl(): string {
  if (typeof window === 'undefined') return DEFAULT_HUB_URL;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && isValidHubUrl(stored)) return stored;
  } catch {
    // Private browsing or storage disabled — the default still works.
  }
  return DEFAULT_HUB_URL;
}

/** Persists a hub URL for this browser. Returns false when the value is not a usable WebSocket URL. */
export function setHubUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!isValidHubUrl(trimmed)) return false;
  try {
    window.localStorage.setItem(STORAGE_KEY, trimmed);
  } catch {
    return false;
  }
  return true;
}

/** Clears the override and goes back to {@link DEFAULT_HUB_URL}. */
export function resetHubUrl(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}

/** True when the given hub URL is reached over TLS. */
export function isSecureHub(url: string): boolean {
  return url.startsWith('wss://');
}

/**
 * Opens a socket to the hub, returning null instead of throwing.
 *
 * `new WebSocket()` throws synchronously on a blocked mixed-content URL. The
 * pages call it inside an effect, where an uncaught throw takes the whole page
 * down — so a hub address typed with the wrong scheme would blank the screen
 * rather than show a disconnected state. Callers treat null as "no connection
 * this attempt" and rely on their existing retry.
 */
export function openHubSocket(url: string = getHubUrl()): WebSocket | null {
  try {
    return new WebSocket(url);
  } catch {
    return null;
  }
}

/**
 * @deprecated Evaluated once at module load, so it cannot see a change made
 * after the page mounted. Call {@link getHubUrl} inside the effect that opens
 * the socket instead.
 */
export const HUB_URL: string = DEFAULT_HUB_URL;
