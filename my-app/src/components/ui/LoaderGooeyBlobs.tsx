// Gooey blobs loader (from the reference snippet). Uses framer-motion, which
// this project already has, and a unique filter id so several can coexist.
import { useId } from 'react'
import { motion } from 'framer-motion'

export interface LoaderGooeyBlobsProps {
  className?: string
  size?: number
  color?: string
  duration?: number
}

export function LoaderGooeyBlobs({ className = '', size = 20, color = 'currentColor', duration = 1.5 }: LoaderGooeyBlobsProps) {
  const filterId = `gooey-${useId().replace(/:/g, '')}`
  return (
    <div className={`flex items-center gap-2 ${className}`} role="status" aria-label="Loading">
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
        <defs>
          <filter id={filterId}>
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="gooey" />
            <feBlend in="SourceGraphic" in2="gooey" />
          </filter>
        </defs>
      </svg>
      <div style={{ filter: `url(#${filterId})` }} className="flex gap-1">
        {[0, 1, 2].map(index => (
          <motion.div
            key={index}
            className="rounded-full"
            style={{ width: size, height: size, backgroundColor: color }}
            animate={{ x: [0, 15, 0, -15, 0], scale: [1, 1.2, 1, 1.2, 1] }}
            transition={{ duration, ease: 'easeInOut', repeat: Infinity, delay: index * 0.2 }}
          />
        ))}
      </div>
    </div>
  )
}

export default LoaderGooeyBlobs
