/**
 * Where the portal reaches the InterMesh hub.
 *
 * The URL was previously hardcoded as `ws://localhost:8765` in every page
 * that opened a socket, which pinned the portal to the hub's own machine:
 * any other deployment silently tried to connect to the visitor's laptop.
 *
 * `NEXT_PUBLIC_` is required for the value to reach the browser, and it means
 * the URL is embedded in the client bundle at build time — that is fine, it is
 * an endpoint, not a secret. It also means changing it requires a rebuild.
 */
export const HUB_URL: string =
  process.env.NEXT_PUBLIC_INTERMESH_HUB_URL ?? "ws://localhost:8765";

/** True when the hub is reached over TLS. */
export const HUB_IS_SECURE: boolean = HUB_URL.startsWith("wss://");
