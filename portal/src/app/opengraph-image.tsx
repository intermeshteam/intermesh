import { ImageResponse } from 'next/og';

/**
 * The card shown when the site is linked on X, LinkedIn, Slack or Hacker News.
 * Without one, those links render as a bare URL with no preview, which is a
 * real cost on the day you actually announce something.
 *
 * Generated rather than committed as a PNG so the wording stays editable in
 * code. ImageResponse supports only a subset of CSS — flexbox, no grid — and
 * every element with more than one child needs an explicit `display: flex`.
 */

export const alt = 'InterMesh — The coordination protocol for AI agents';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          backgroundColor: '#08080A',
          padding: '80px',
        }}
      >
        <div
          style={{
            display: 'flex',
            fontSize: 22,
            letterSpacing: '0.18em',
            color: '#67E8F9',
            fontWeight: 700,
          }}
        >
          INTERMESH
        </div>

        <div
          style={{
            display: 'flex',
            marginTop: 36,
            fontSize: 76,
            lineHeight: 1.05,
            color: '#FFFFFF',
            fontWeight: 700,
            letterSpacing: '-0.03em',
          }}
        >
          Agents that work together.
        </div>

        <div
          style={{
            display: 'flex',
            marginTop: 32,
            fontSize: 30,
            lineHeight: 1.4,
            color: '#94A3B8',
            maxWidth: 900,
          }}
        >
          An open-source coordination protocol — across teams, and across two
          organizations that do not trust each other.
        </div>

        <div
          style={{
            display: 'flex',
            marginTop: 48,
            alignItems: 'center',
            gap: 20,
            fontSize: 24,
            color: '#64748B',
          }}
        >
          <span style={{ color: '#A78BFA' }}>Apache 2.0</span>
          <span>·</span>
          <span>End-to-end encrypted</span>
          <span>·</span>
          <span>intermesh.site</span>
        </div>
      </div>
    ),
    size,
  );
}
