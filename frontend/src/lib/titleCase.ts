/** Title-case procedure names; keep mixed-case brands (e.g. SpaceOAR). */
const SMALL_WORDS = new Set([
  'a',
  'an',
  'and',
  'as',
  'at',
  'but',
  'by',
  'for',
  'in',
  'of',
  'on',
  'or',
  'the',
  'to',
])

export function titleCase(text: string): string {
  if (!text) return text
  return text
    .split(/\s+/)
    .map((word, i) => {
      const hasInternalCaps = [...word.slice(1)].some((c) => c >= 'A' && c <= 'Z')
      const isAllCaps = word === word.toUpperCase() && /[A-Z]/.test(word)
      if (hasInternalCaps && !isAllCaps) return word
      if (i > 0 && SMALL_WORDS.has(word.toLowerCase())) return word.toLowerCase()
      const base = isAllCaps ? word.toLowerCase() : word
      return base.charAt(0).toUpperCase() + base.slice(1)
    })
    .join(' ')
}
