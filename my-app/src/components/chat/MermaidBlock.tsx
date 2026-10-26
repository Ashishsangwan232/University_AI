// Renders a ```mermaid block (flowchart, timeline, ...) from an answer.
// Mermaid is loaded only when an answer contains a diagram.
import { useEffect, useId, useState } from 'react'
import { LoaderGooeyBlobs } from '../ui/LoaderGooeyBlobs'

let mermaidPromise: Promise<typeof import('mermaid').default> | null = null

function loadMermaid(dark: boolean) {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then(module => {
      const mermaid = module.default
      // Styled to match the app instead of Mermaid's stock grey boxes:
      // soft dark/light nodes with a green border, curved thin arrows.
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict', // no scripts or click handlers from the model's text
        theme: 'base',
        fontFamily: "'DM Sans', system-ui, sans-serif",
        themeVariables: dark
          ? {
              darkMode: true,
              background: 'transparent',
              primaryColor: '#16241f',
              primaryTextColor: '#ececec',
              primaryBorderColor: '#34d399',
              secondaryColor: '#1f1f1f',
              tertiaryColor: '#141414',
              lineColor: '#5b6b66',
              textColor: '#ececec',
              edgeLabelBackground: '#0b0b0b',
              fontSize: '14px',
            }
          : {
              background: 'transparent',
              primaryColor: '#ecfdf5',
              primaryTextColor: '#0d0d0d',
              primaryBorderColor: '#10b981',
              secondaryColor: '#f4f4f5',
              tertiaryColor: '#fafafa',
              lineColor: '#a1a1aa',
              textColor: '#0d0d0d',
              edgeLabelBackground: '#ffffff',
              fontSize: '14px',
            },
        flowchart: { curve: 'basis', nodeSpacing: 28, rankSpacing: 34, padding: 10, useMaxWidth: true },
      })
      return mermaid
    })
  }
  return mermaidPromise
}

export function MermaidBlock({ code }: { code: string }) {
  const id = `mmd-${useId().replace(/:/g, '')}`
  const [svg, setSvg] = useState('')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
    loadMermaid(dark)
      .then(mermaid => mermaid.render(id, code))
      .then(result => { if (active) setSvg(result.svg) })
      .catch(() => { if (active) setFailed(true) })
    return () => { active = false }
  }, [code, id])

  if (failed) {
    // Show the source rather than nothing if the diagram does not parse.
    return <pre><code>{code}</code></pre>
  }
  if (!svg) {
    return <div className="diagram-card loading"><LoaderGooeyBlobs size={8} color="var(--muted)" /></div>
  }
  // Mermaid's own output with securityLevel "strict" (sanitised SVG).
  return <div className="diagram-card" dangerouslySetInnerHTML={{ __html: svg }} />
}
