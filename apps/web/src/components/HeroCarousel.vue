<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { HERO_IMAGES } from '@/utils/heroImages'

/** 首页固定首屏：不轮播，主 CTA 始终可见。镜像/代码仓等放在下方「核心服务」。 */
const slide = {
  id: 'intern',
  titleHtml: '华科开源实习',
  lead: '华中科技大学开放原子开源俱乐部组织开源实习：社区发布课题，学生实名申请，导师指导，结项后由社区认定。',
  image: HERO_IMAGES.intern,
  primary: { to: '/projects?tab=tasks', label: '浏览实习项目' },
  secondary: { to: '/guide', label: '学生申请指南' },
}
</script>

<template>
  <section class="hero-carousel hero-fixed" aria-label="首页首屏">
    <div
      class="hero-slide active"
      :style="{ backgroundImage: `linear-gradient(105deg, rgba(8,12,20,.72) 0%, rgba(15,23,42,.35) 55%, rgba(15,23,42,.2) 100%), url(${slide.image})` }"
    >
      <div class="hero-inner">
        <h1 v-html="slide.titleHtml" />
        <p class="hero-lead">{{ slide.lead }}</p>
        <div class="hero-cta">
          <RouterLink class="btn ghost" :to="slide.primary.to">{{ slide.primary.label }}</RouterLink>
          <RouterLink class="btn ghost" :to="slide.secondary.to">{{ slide.secondary.label }}</RouterLink>
        </div>
      </div>
    </div>
  </section>
</template>
