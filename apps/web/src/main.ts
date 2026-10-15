import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'

// 热更后旧入口还会去拉已失效的 hashed chunk；只自动整页刷新一次
if (typeof window !== 'undefined') {
  const reloadOnce = () => {
    const key = 'spa-chunk-reload'
    if (sessionStorage.getItem(key)) return
    sessionStorage.setItem(key, '1')
    window.location.reload()
  }
  window.addEventListener('vite:preloadError', (event) => {
    event.preventDefault()
    reloadOnce()
  })
  router.onError((err) => {
    const msg = err instanceof Error ? err.message : String(err)
    if (/Failed to fetch dynamically imported module|Unable to preload CSS/i.test(msg)) {
      reloadOnce()
    }
  })
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// 空闲时预取常用路由分包，减少点导航后「干等」
const prefetch = () => {
  void import('@/views/HomeView.vue')
  void import('@/views/ProjectsView.vue')
  void import('@/views/LoginView.vue')
  void import('@/views/GuideView.vue')
  void import('@/views/ProfileCenterView.vue')
}
if (typeof window !== 'undefined') {
  const ric = (
    window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => void
    }
  ).requestIdleCallback
  if (ric) ric(prefetch, { timeout: 2500 })
  else window.setTimeout(prefetch, 800)
}
