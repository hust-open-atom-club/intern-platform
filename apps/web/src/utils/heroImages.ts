/** 站内托管的原首页大图（自 Unsplash 镜像），避免外链缓存失败。 */
export const HERO_IMAGES = {
  intern: '/heroes/hero-intern.jpg',
  process: '/heroes/hero-process.jpg',
  club: '/heroes/hero-club.jpg',
} as const

const FALLBACK = HERO_IMAGES.intern

function isUnsplash(url: string): boolean {
  const u = url.trim().toLowerCase()
  return u.includes('unsplash.com') || u.includes('images.unsplash')
}

function isPlaceholderSvg(url: string): boolean {
  const u = url.trim().toLowerCase()
  return u.includes('/heroes/hero-') && u.endsWith('.svg')
}

/** 空地址、历史 Unsplash、临时 SVG 占位 → 本地实景图；其它自定义图保留 */
export function resolveHeroImage(image?: string | null, slideId?: string | null): string {
  const id = String(slideId || '')
  const local =
    id in HERO_IMAGES ? HERO_IMAGES[id as keyof typeof HERO_IMAGES] : FALLBACK
  const raw = (image || '').trim()
  if (!raw || isUnsplash(raw) || isPlaceholderSvg(raw)) return local
  return raw
}
