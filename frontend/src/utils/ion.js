// Ion symbol helpers (frontend).
//
// The backend stores ions in the canonical form <formula><sign><magnitude>,
// e.g. "SO4-2", "Na+1", "Mg+2" (the magnitude digit is always present). These
// helpers turn a canonical symbol into (formula, charge) and into HTML with
// proper subscripts and an IUPAC superscript charge (magnitude-then-sign; a
// unit charge omits the "1", so Na+1 renders as Na with a superscript "+").

/**
 * Split a canonical ion symbol into { formula, charge }.
 * @param {string} symbol e.g. "SO4-2"
 * @returns {{ formula: string, charge: number }}
 */
export function parseIon(symbol) {
  const s = String(symbol ?? '').replace(/\s+/g, '')
  const i = Math.max(s.lastIndexOf('+'), s.lastIndexOf('-'))
  if (i <= 0) return { formula: s, charge: 0 }
  const sign = s[i]
  const magnitude = parseInt(s.slice(i + 1), 10) || 1
  return { formula: s.slice(0, i), charge: sign === '+' ? magnitude : -magnitude }
}

/** Escape a string for safe interpolation into an HTML attribute/body. */
function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/**
 * Render an ion symbol as HTML with subscripts for the formula digits and an
 * IUPAC superscript charge (magnitude-then-sign).
 * @param {string} symbol canonical ion symbol, e.g. "SO4-2"
 * @returns {string} e.g. `SO<sub>4</sub><sup>2&#8722;</sup>`
 */
export function ionToHtml(symbol) {
  const { formula, charge } = parseIon(symbol)
  // Wrap runs of digits (subscripts) in the formula.
  const f = esc(formula).replace(/(\d+)/g, '<sub>$1</sub>')
  if (charge === 0) return f
  const magnitude = Math.abs(charge)
  // IUPAC: number before the sign; the "1" is omitted for a unit charge.
  const num = magnitude > 1 ? String(magnitude) : ''
  const sign = charge > 0 ? '+' : '\u2212'
  return `${f}<sup>${num}${sign}</sup>`
}
