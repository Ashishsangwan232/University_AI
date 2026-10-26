import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

/** The CampusAI mark: a library sparkles icon that twinkles now and then. */
export function BrandMark({ size = 15 }: { size?: number }) {
  return (
    <span className="brand-mark">
      <motion.span
        style={{ display: 'inline-flex', lineHeight: 0 }}
        animate={{ rotate: [0, 0, 18, 0], scale: [1, 1, 1.18, 1] }}
        transition={{ duration: 4, repeat: Infinity, times: [0, 0.7, 0.85, 1], ease: 'easeInOut' }}
      >
        <Sparkles size={size} strokeWidth={2.2} />
      </motion.span>
    </span>
  )
}
