/**
 * Control Plane design tokens.
 *
 * The pages had drifted into two grey scales at once — `zinc` and `slate`
 * mixed across 75 borders and 49 label colours — with no brand colour
 * anywhere. Two neutrals never quite agree, and the result reads as flat
 * rather than restrained.
 *
 * One neutral ramp, one accent, and colours that carry meaning instead of
 * decoration: a green dot must mean healthy, never "this bit needed
 * brightening".
 */

/* -- Surfaces ------------------------------------------------------------ */

/** Page background. */
export const SURFACE_BASE = 'bg-[#0A0A0C]';
/** Cards and panels; one step above the page. */
export const SURFACE_RAISED = 'bg-[#111114]';
/** Inset areas — code blocks, wells, table headers. */
export const SURFACE_SUNKEN = 'bg-[#08080A]';
/** Navigation chrome. */
export const SURFACE_CHROME = 'bg-[#0C0C0F]';
/**
 * Translucent variant for the sticky top bar.
 *
 * Declared whole rather than composed as `${SURFACE_CHROME}/80`: Tailwind
 * scans source files for complete class strings, so a class assembled at
 * runtime is never generated. The bar ended up with no background at all,
 * showing the light body through it.
 */
export const SURFACE_CHROME_BLUR = 'bg-[#0C0C0F]/80';

/** Hairline. Low-opacity white reads better than a fixed grey over any depth. */
export const BORDER = 'border-white/[0.07]';
export const BORDER_STRONG = 'border-white/[0.12]';

/** Card shell used everywhere in the Control Plane. */
export const CARD = `rounded-xl border ${BORDER} ${SURFACE_RAISED}`;

/* -- Type ---------------------------------------------------------------- */

// Mesure sur le fond #0A0A0C : slate-600 tombe a 2,49 et slate-500 a 4,2,
// tous deux sous le seuil AA de 4,5. La rampe est donc decalee d'un cran ;
// rien en dessous de slate-400 ne porte de texte utile.
export const TEXT_PRIMARY = 'text-slate-100';   // ~16:1
export const TEXT_SECONDARY = 'text-slate-300'; // ~13:1
export const TEXT_MUTED = 'text-slate-400';     // ~7,5:1
export const TEXT_FAINT = 'text-slate-500';     // ~4,2:1 — decoratif uniquement

/** Small uppercase caption above a value or a section. */
export const CAPTION =
  'text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400';

/** Metric figures. `tabular-nums` stops numbers jittering as they update. */
export const FIGURE = 'font-mono text-3xl font-semibold tabular-nums text-white';

/* -- Meaningful colour ---------------------------------------------------- */

export type Tone = 'accent' | 'positive' | 'warning' | 'danger' | 'neutral' | 'info';

/** Foreground, tinted background and ring for each tone. */
export const TONE: Record<Tone, { text: string; soft: string; dot: string }> = {
  accent: { text: 'text-cyan-300', soft: 'bg-cyan-500/10 ring-1 ring-cyan-400/20', dot: 'bg-cyan-400' },
  info: { text: 'text-violet-300', soft: 'bg-violet-500/10 ring-1 ring-violet-400/20', dot: 'bg-violet-400' },
  positive: { text: 'text-emerald-300', soft: 'bg-emerald-500/10 ring-1 ring-emerald-400/20', dot: 'bg-emerald-400' },
  warning: { text: 'text-amber-300', soft: 'bg-amber-500/10 ring-1 ring-amber-400/20', dot: 'bg-amber-400' },
  danger: { text: 'text-rose-300', soft: 'bg-rose-500/10 ring-1 ring-rose-400/20', dot: 'bg-rose-400' },
  neutral: { text: 'text-slate-300', soft: 'bg-white/[0.06] ring-1 ring-white/10', dot: 'bg-slate-400' },
};

/** Accent gradient, for the few elements that should lead the eye. */
export const ACCENT_GRADIENT = 'bg-gradient-to-r from-cyan-400 to-violet-400';
export const ACCENT_TEXT_GRADIENT =
  'bg-gradient-to-r from-cyan-300 to-violet-300 bg-clip-text text-transparent';
