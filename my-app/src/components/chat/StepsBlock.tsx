// Renders a ```steps block: a vertical timeline for step-by-step procedures
// (applying for leave, re-evaluation, fee payment). Cleaner than a flowchart
// when there are no branches.
//
// Spec (JSON):
//   { "title": "How to apply for hostel leave",
//     "steps": [ { "title": "Open UMS", "detail": "Sign in at ums.lpu.in" }, ... ] }
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Check } from 'lucide-react'
import type { StepsSpec } from './stepsSpec'

export function StepsBlock({ spec, renderInline }: { spec: StepsSpec; renderInline: (text: string) => ReactNode }) {
  const last = spec.steps.length - 1
  return (
    <figure className="steps-card">
      {spec.title && <figcaption>{renderInline(spec.title)}</figcaption>}
      <ol className="steps">
        {spec.steps.map((step, i) => (
          <motion.li
            key={i}
            className="step"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.07, duration: 0.25 }}
          >
            <span className="step-rail" aria-hidden="true">
              <span className={`step-dot ${i === last ? 'done' : ''}`}>
                {i === last ? <Check size={13} strokeWidth={3} /> : i + 1}
              </span>
              {i !== last && <span className="step-line" />}
            </span>
            <span className="step-body">
              <span className="step-title">{renderInline(step.title)}</span>
              {step.detail && <span className="step-detail">{renderInline(step.detail)}</span>}
            </span>
          </motion.li>
        ))}
      </ol>
    </figure>
  )
}
