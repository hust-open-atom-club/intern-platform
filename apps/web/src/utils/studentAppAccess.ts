import type { ApplicationOut } from '@/api/types'

function httpStatus(e: unknown): number | undefined {
  if (e && typeof e === 'object' && 'response' in e) {
    const status = (e as { response?: { status?: number } }).response?.status
    return typeof status === 'number' ? status : undefined
  }
  return undefined
}

/** 学生进度相关页：无权时强制回首页（软路由在部分情况下会失败并留下白屏） */
export function bounceHome(reason: string): void {
  try {
    sessionStorage.setItem('intern_platform_flash', reason)
  } catch {
    /* ignore */
  }
  const target = `${window.location.origin}/`
  if (window.location.href !== target && window.location.pathname !== '/') {
    window.location.replace(target)
  }
}

/** 加载成功后校验是否本人申请；非本人则跳转并返回 true。userId 未知时不拦截。 */
export function rejectIfNotOwner(
  app: ApplicationOut,
  userId: number | undefined,
): boolean {
  if (userId == null) return false
  if (app.student_id === userId) return false
  bounceHome('这不是你的任务进度，已返回首页')
  return true
}

/**
 * 处理加载失败。
 * - 403/404：跳转首页，返回用于本地展示的文案（跳转前短暂可见）
 * - 其它：返回错误文案
 */
export function handleStudentAppLoadError(e: unknown): string {
  const status = httpStatus(e)
  const msg = e instanceof Error ? e.message : '加载失败'
  if (status === 403 || msg.includes('无权查看')) {
    bounceHome('无权查看该任务进度，已返回首页')
    return '无权查看该任务进度，正在返回首页…'
  }
  if (status === 404 || msg.includes('不存在')) {
    bounceHome('申请不存在，已返回首页')
    return '申请不存在，正在返回首页…'
  }
  return msg
}
