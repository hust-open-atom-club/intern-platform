/** Minimal Markdown → safe HTML for project / news style content. */

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function inlineMd(text: string): string {
  let s = escapeHtml(text)
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  s = s.replace(/_([^_\n]+)_/g, '<em>$1</em>')
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  return s
}

/** True when text looks like Markdown rather than plain prose. */
export function looksLikeMarkdown(text: string): boolean {
  const t = text.trim()
  if (!t) return false
  return (
    /^#{1,6}\s/m.test(t) ||
    /\*\*[^*]+\*\*/.test(t) ||
    /^[-*+]\s+\S/m.test(t) ||
    /^\d+\.\s+\S/m.test(t) ||
    /```/.test(t) ||
    /\[[^\]]+\]\(https?:\/\/[^)]+\)/.test(t)
  )
}

/** Recover newlines lost on paste / escaped \\n from editors. */
export function normalizeMarkdown(src: string): string {
  let s = String(src || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const realBreaks = (s.match(/\n/g) || []).length
  if (realBreaks < 2 && /\\n/.test(s)) {
    s = s.replace(/\\n/g, '\n')
  }
  // 粘贴后整段挤成一行时，尽量在 ATX 标题前恢复换行
  if ((s.match(/\n/g) || []).length < 2 && /#{1,6}\s/.test(s)) {
    s = s.replace(/\s+(#{1,6}\s+)/g, '\n\n$1')
  }
  return s.trim()
}

/**
 * Convert a Markdown string to sanitized HTML (no raw HTML passthrough).
 * Supports headings, paragraphs, lists, fenced code, bold/italic/code/links.
 */
export function renderMarkdown(src: string): string {
  const lines = normalizeMarkdown(src).split('\n')
  const out: string[] = []
  let i = 0
  let inCode = false
  let codeBuf: string[] = []

  const flushPara = (buf: string[]) => {
    if (!buf.length) return
    out.push(`<p>${inlineMd(buf.join('\n')).replace(/\n/g, '<br />')}</p>`)
    buf.length = 0
  }

  let para: string[] = []

  while (i < lines.length) {
    const line = lines[i]

    if (line.trimStart().startsWith('```')) {
      if (inCode) {
        out.push(`<pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`)
        codeBuf = []
        inCode = false
      } else {
        flushPara(para)
        inCode = true
      }
      i += 1
      continue
    }

    if (inCode) {
      codeBuf.push(line)
      i += 1
      continue
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(line)
    if (heading) {
      flushPara(para)
      const level = Math.min(heading[1].length, 4)
      out.push(`<h${level}>${inlineMd(heading[2].trim())}</h${level}>`)
      i += 1
      continue
    }

    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim())) {
      flushPara(para)
      out.push('<hr />')
      i += 1
      continue
    }

    const ul = /^[-*+]\s+(.+)$/.exec(line)
    const ol = /^(\d+)\.\s+(.+)$/.exec(line)
    if (ul || ol) {
      flushPara(para)
      const ordered = !!ol
      const items: string[] = []
      while (i < lines.length) {
        const u = /^[-*+]\s+(.+)$/.exec(lines[i])
        const o = /^(\d+)\.\s+(.+)$/.exec(lines[i])
        if (ordered ? !o : !u) break
        items.push(inlineMd((ordered ? o![2] : u![1]).trim()))
        i += 1
      }
      const tag = ordered ? 'ol' : 'ul'
      out.push(`<${tag}>${items.map((it) => `<li>${it}</li>`).join('')}</${tag}>`)
      continue
    }

    if (!line.trim()) {
      flushPara(para)
      i += 1
      continue
    }

    para.push(line)
    i += 1
  }

  if (inCode) {
    out.push(`<pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre>`)
  }
  flushPara(para)
  return out.join('\n')
}
