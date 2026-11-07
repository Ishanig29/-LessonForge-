import { Children, isValidElement, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Renders lesson markdown and turns claim markers like [C3] into small
 * clickable references, so readers can jump to the claim's evidence.
 */
export function LessonMarkdown({ children, onClaimClick }: { children: string; onClaimClick?: (claimId: string) => void }) {
  const decorate = (nodes: ReactNode): ReactNode =>
    Children.map(nodes, (node) => {
      if (typeof node !== 'string') return isValidElement(node) ? node : node
      const parts = node.split(/(\[C\d+\])/g)
      if (parts.length === 1) return node
      return parts.map((part, i) => {
        const m = /^\[(C\d+)\]$/.exec(part)
        if (!m) return part
        return onClaimClick ? (
          <button
            key={i}
            type="button"
            onClick={() => onClaimClick(m[1])}
            className="mx-0.5 rounded bg-accent-soft px-1 align-super text-[10px] font-semibold text-accent-2 no-underline hover:bg-accent/20"
            aria-label={`View evidence for claim ${m[1]}`}
          >
            {m[1]}
          </button>
        ) : (
          <sup key={i} className="mx-0.5 text-[10px] font-semibold text-accent-2">{m[1]}</sup>
        )
      })
    })

  return (
    <div className="prose prose-sm prose-lesson max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{decorate(children)}</p>,
          li: ({ children }) => <li>{decorate(children)}</li>,
          td: ({ children }) => <td>{decorate(children)}</td>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
