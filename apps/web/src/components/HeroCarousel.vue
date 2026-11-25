<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import { HERO_IMAGES, resolveHeroImage } from '@/utils/heroImages'

/**
 * 首页大图：读取组委会「首页大图 / 端点内容」发布的 live 条目。
 * 不自动轮播（避免首屏像演示页）；多张时仅手动切换。
 */
type RemoteSlide = {
  id: string
  title?: string
  lead?: string
  meta?: string
  image?: string
  live?: boolean
  jump?: 'page' | 'link'
  link?: string
  pageTitle?: string
  pageBody?: string
  buttonLabel?: string
  primaryTo?: string
  primaryLabel?: string
  secondaryTo?: string
  secondaryLabel?: string
}

type ViewSlide = {
  id: string
  titleHtml: string
  lead: string
  meta: string
  image: string
  primary: { to: string; label: string; external: boolean }
  secondary: { to: string; label: string; external: boolean } | null
}

const fallback: ViewSlide = {
  id: 'intern',
  titleHtml: '华科开源实习',
  lead: '华中科技大学开放原子开源俱乐部组织开源实习：社区发布课题，学生实名申请，导师指导，结项后由社区认定。',
  meta: '',
  image: HERO_IMAGES.intern,
  primary: { to: '/projects?tab=tasks', label: '浏览实习项目', external: false },
  secondary: { to: '/guide', label: '学生申请指南', external: false },
}

const slides = ref<ViewSlide[]>([fallback])
const index = ref(0)

function fromRemote(item: RemoteSlide): ViewSlide {
  const jump = item.jump || (item.pageTitle || item.pageBody ? 'page' : 'link')
  const href = jump === 'page' ? `/banner/${item.id}` : item.link || item.primaryTo || '/projects?tab=tasks'
  const primaryLabel =
    item.buttonLabel || item.primaryLabel || (jump === 'page' ? '了解这次活动' : '浏览实习项目')
  const secondaryTo = (item.secondaryTo || '').trim()
  return {
    id: item.id,
    titleHtml: (item.title || item.pageTitle || '').replace(/\n/g, '<br />'),
    lead: item.lead || '',
    meta: item.meta || '',
    image: resolveHeroImage(item.image, item.id),
    primary: {
      to: href,
      label: primaryLabel,
      external: href.startsWith('http'),
    },
    secondary: secondaryTo
      ? {
          to: secondaryTo,
          label: item.secondaryLabel || '了解更多',
          external: secondaryTo.startsWith('http'),
        }
      : null,
  }
}

function go(i: number) {
  const n = slides.value.length
  if (!n) return
  index.value = ((i % n) + n) % n
}

onMounted(async () => {
  try {
    const { data } = await api.get<RemoteSlide[]>('/site/slides')
    const live = (data || []).filter((item) => item.live !== false)
    if (live.length) {
      slides.value = live.map(fromRemote)
      index.value = 0
    }
  } catch {
    /* 未配置时沿用默认首屏 */
  }
})
</script>

<template>
  <section class="hero-carousel hero-fixed" aria-label="首页首屏">
    <div
      v-for="(s, i) in slides"
      :key="s.id"
      class="hero-slide"
      :class="{ active: i === index }"
      :style="{ backgroundImage: `linear-gradient(105deg, rgba(8,12,20,.72) 0%, rgba(15,23,42,.35) 55%, rgba(15,23,42,.2) 100%), url(${s.image})` }"
    >
      <div class="hero-inner">
        <h1 v-if="s.titleHtml" v-html="s.titleHtml" />
        <p v-if="s.lead" class="hero-lead">{{ s.lead }}</p>
        <div v-if="s.meta" class="hero-meta">{{ s.meta }}</div>
        <div class="hero-cta">
          <a
            v-if="s.primary.external"
            class="btn ghost"
            :href="s.primary.to"
            target="_blank"
            rel="noopener"
          >{{ s.primary.label }}</a>
          <RouterLink v-else class="btn ghost" :to="s.primary.to">{{ s.primary.label }}</RouterLink>
          <template v-if="s.secondary">
            <a
              v-if="s.secondary.external"
              class="btn ghost"
              :href="s.secondary.to"
              target="_blank"
              rel="noopener"
            >{{ s.secondary.label }}</a>
            <RouterLink v-else class="btn ghost" :to="s.secondary.to">{{ s.secondary.label }}</RouterLink>
          </template>
        </div>
      </div>
    </div>

    <template v-if="slides.length > 1">
      <button class="hero-nav prev" type="button" aria-label="上一张" @click="go(index - 1)">‹</button>
      <button class="hero-nav next" type="button" aria-label="下一张" @click="go(index + 1)">›</button>
      <div class="hero-dots" role="tablist">
        <button
          v-for="(s, i) in slides"
          :key="s.id"
          type="button"
          class="hero-dot"
          :class="{ active: i === index }"
          :aria-label="`切换到第 ${i + 1} 张`"
          @click="go(i)"
        />
      </div>
    </template>
  </section>
</template>
