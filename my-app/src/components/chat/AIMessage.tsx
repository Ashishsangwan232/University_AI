import type { ReactNode } from 'react'

type Props = { text: string }

function inline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|(?<![\w/])_[^_\n]+_|`[^`\n]+`|\[[^\]\n]+\]\((https?:\/\/[^\s)]+)\)|https?:\/\/[^\s<>()"'`]+[^\s<>()"'`.,;:!?])/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index))
    const token = match[0]

    if (token.startsWith('http')) {
      nodes.push(<a key={`u-${match.index}`} href={token} target="_blank" rel="noreferrer">{token}</a>)
    } else if (token.startsWith('**') || token.startsWith('__')) {
      // Formatting can wrap a link ("*Source: https://...*"), so look inside.
      nodes.push(<strong key={`b-${match.index}`}>{inline(token.slice(2, -2))}</strong>)
    } else if (token.startsWith('*') || token.startsWith('_')) {
      nodes.push(<em key={`i-${match.index}`}>{inline(token.slice(1, -1))}</em>)
    } else if (token.startsWith('`')) {
      nodes.push(<code key={`c-${match.index}`}>{token.slice(1, -1)}</code>)
    } else {
      const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/)
      if (link) {
        nodes.push(
          <a key={`a-${match.index}`} href={link[2]} target="_blank" rel="noreferrer">
            {link[1]}
          </a>,
        )
      }
    }
    last = match.index + token.length
  }

  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

export function AIMessage({ text }: Props) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let listType: 'ul' | 'ol' | null = null
  let listItems: ReactNode[] = []
  let codeLines: string[] = []
  let inCode = false
  let tableLines: string[] = []

  const flushTable = () => {
    const cells = (row: string) => row.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim())
    // Drop the |---|:--:| separator row.
    const rows = tableLines.filter(row => !/^\s*\|?[\s:|-]+\|?\s*$/.test(row)).map(cells)
    tableLines = []
    if (!rows.length) return
    const [head, ...body] = rows
    blocks.push(
      <div className="table-wrap" key={`table-${blocks.length}`}>
        <table>
          <thead><tr>{head.map((cell, i) => <th key={i}>{inline(cell)}</th>)}</tr></thead>
          <tbody>{body.map((row, r) => <tr key={r}>{row.map((cell, i) => <td key={i}>{inline(cell)}</td>)}</tr>)}</tbody>
        </table>
      </div>,
    )
  }

  const flushList = () => {
    if (!listType || !listItems.length) return
    const List = listType
    blocks.push(<List key={`list-${blocks.length}`}>{listItems}</List>)
    listItems = []
    listType = null
  }

  const flushCode = () => {
    if (!codeLines.length) return
    blocks.push(
      <pre key={`code-${blocks.length}`}><code>{codeLines.join('\n')}</code></pre>,
    )
    codeLines = []
  }

  lines.forEach((line, index) => {
    if (/^\s*```/.test(line)) {
      if (inCode) flushCode()
      else {
        flushList()
        codeLines = []
      }
      inCode = !inCode
      return
    }

    if (inCode) {
      codeLines.push(line)
      return
    }

    // Markdown table: consecutive lines that start and end with "|".
    if (/^\s*\|.*\|\s*$/.test(line)) {
      flushList()
      tableLines.push(line)
      const next = lines[index + 1]
      if (next === undefined || !/^\s*\|.*\|\s*$/.test(next)) flushTable()
      return
    }

    const bullet = line.match(/^\s*[-*•]\s+(.+)$/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/)

    if (bullet || numbered) {
      const nextType = bullet ? 'ul' : 'ol'
      if (listType && listType !== nextType) flushList()
      listType = nextType
      listItems.push(<li key={`${index}-${listItems.length}`}>{inline((bullet ?? numbered)![1])}</li>)
      return
    }

    flushList()

    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) {
      const Tag = heading[1].length === 1 ? 'h3' : heading[1].length === 2 ? 'h4' : 'h5'
      blocks.push(<Tag key={index}>{inline(heading[2])}</Tag>)
      return
    }

    if (line.trim()) {
      blocks.push(<p key={index}>{inline(line)}</p>)
    }
  })

  flushList()
  if (inCode) flushCode()
  return <div className="ai-message">{blocks}</div>
}
