// Greeting preloader (from the reference snippet). The overlay's slide-up is
// done with framer-motion instead of GSAP, so no extra library is needed.
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { GREETINGS, type Greeting } from './greetings'

const textVariants = {
  hidden: { y: 20, opacity: 0 },
  visible: { y: 0, opacity: 1 },
  exit: { y: -100, opacity: 0 },
}

/** Greetings flicking past. Plays once (then onComplete) or loops forever. */
export function DynamicText({
  greetings = GREETINGS, intervalMs = 300, loop = false, onComplete, className = '',
}: { greetings?: Greeting[]; intervalMs?: number; loop?: boolean; onComplete?: () => void; className?: string }) {
  const [index, setIndex] = useState(0)
  const [running, setRunning] = useState(true)

  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => {
      setIndex(previous => {
        const next = previous + 1
        if (next < greetings.length) return next
        if (loop) return 0
        clearInterval(timer)
        setRunning(false)
        onComplete?.()
        return previous
      })
    }, intervalMs)
    return () => clearInterval(timer)
  }, [running, greetings, intervalMs, loop, onComplete])

  return (
    <div className={`relative h-16 w-72 flex items-center justify-center overflow-visible ${className}`} aria-label="Greetings in different languages">
      <AnimatePresence mode="popLayout">
        <motion.div
          key={index}
          className="absolute flex items-center gap-2 text-2xl xl:text-3xl font-medium"
          style={{ color: 'var(--ink)' }}
          aria-live="off"
          initial={textVariants.hidden}
          animate={textVariants.visible}
          exit={textVariants.exit}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <span className="h-2 w-2 rounded-full" style={{ background: 'var(--ink)' }} aria-hidden="true" />
          {greetings[index].text}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/**
 * Full-screen (or panel) cover that flicks through greetings, then slides up.
 * - `active` false + no `loop`: plays the greetings once, then leaves (app start).
 * - `loop`: keeps going while `active` is true, leaves when it turns false (UMS connecting).
 */
export function GreetingPreloader({
  active = true, loop = false, fullPage = true, intervalMs = 300, caption,
}: { active?: boolean; loop?: boolean; fullPage?: boolean; intervalMs?: number; caption?: ReactNode }) {
  const [finished, setFinished] = useState(false)
  const visible = loop ? active : active && !finished

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="preloader"
          className={`${fullPage ? 'fixed z-[11000]' : 'absolute z-20'} inset-0 flex items-center justify-center`}
          style={{ background: 'var(--bg)' }}
          initial={{ y: 0 }}
          exit={{ y: '-110%', transition: { duration: 1, ease: [0.33, 1, 0.68, 1] } }}
        >
          <div className="flex flex-col items-center gap-3 text-center px-6">
            <DynamicText intervalMs={intervalMs} loop={loop} onComplete={() => setFinished(true)} />
            {caption && <div className="text-sm" style={{ color: 'var(--muted)' }}>{caption}</div>}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default GreetingPreloader
