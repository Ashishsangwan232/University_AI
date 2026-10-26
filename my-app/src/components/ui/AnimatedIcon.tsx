// Library icons (lucide-react / react-icons) with small motion effects.
// Put an <AnimatedIcon> inside a <motion.button initial="rest" whileHover="hover"
// whileTap="tap">: the button's hover/tap state drives the icon.
import { motion, type Variants } from 'framer-motion'
import type { ComponentType } from 'react'

export type IconMotion = 'spin' | 'lift' | 'wiggle' | 'shake' | 'pop' | 'nudge' | 'none'

const VARIANTS: Record<IconMotion, Variants> = {
  spin: { rest: { rotate: 0 }, hover: { rotate: 180, transition: { duration: 0.45 } }, tap: { rotate: 360, transition: { duration: 0.35 } } },
  lift: { rest: { y: 0 }, hover: { y: -2, transition: { type: 'spring', stiffness: 400, damping: 12 } }, tap: { y: -4, scale: 0.9 } },
  wiggle: { rest: { rotate: 0 }, hover: { rotate: [0, -12, 10, -6, 0], transition: { duration: 0.5 } }, tap: { scale: 0.85 } },
  shake: { rest: { x: 0 }, hover: { x: [0, -2, 2, -1, 1, 0], transition: { duration: 0.4 } }, tap: { scale: 0.85 } },
  pop: { rest: { scale: 1 }, hover: { scale: 1.15, transition: { type: 'spring', stiffness: 400, damping: 10 } }, tap: { scale: 0.85 } },
  nudge: { rest: { x: 0 }, hover: { x: 2, transition: { type: 'spring', stiffness: 400, damping: 12 } }, tap: { scale: 0.9 } },
  none: {},
}

type IconLike = ComponentType<{ size?: number; className?: string; strokeWidth?: number }>

export function AnimatedIcon({
  icon: Icon, size = 18, motion: kind = 'pop', className = '', strokeWidth,
}: { icon: IconLike; size?: number; motion?: IconMotion; className?: string; strokeWidth?: number }) {
  return (
    <motion.span variants={VARIANTS[kind]} className="inline-flex items-center justify-center" style={{ lineHeight: 0 }}>
      <Icon size={size} className={className} {...(strokeWidth ? { strokeWidth } : {})} />
    </motion.span>
  )
}

