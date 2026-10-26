// The robot mascot from the reference input component (kept as-is).
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

export type Emotion = 'reading' | 'thinking'

function EyeLED({ emotion, isBlinking, offsetX }: { emotion: Emotion; isBlinking: boolean; offsetX: number }) {
  if (emotion === 'thinking') {
    return (
      <motion.div
        className="w-2.5 h-3.5 rounded-xs bg-amber-300 shadow-[0_0_10px_#facc15,0_0_18px_rgba(250,204,21,0.4)]"
        animate={{ y: [-1, -3, -1] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
      />
    )
  }
  if (isBlinking) return <div className="w-2.5 h-1 rounded-xs bg-emerald-400 shadow-[0_0_6px_#10b981]" />
  return (
    <motion.div
      className="w-2.5 h-4.5 rounded-xs bg-emerald-400 shadow-[0_0_12px_#34d399,0_0_20px_rgba(52,211,153,0.45)]"
      animate={{ x: offsetX }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    />
  )
}

export function RobotMascot({ emotion, textLength = 0, isListening = false }: { emotion: Emotion; textLength?: number; isListening?: boolean }) {
  const [isBlinking, setIsBlinking] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      if (emotion !== 'thinking') {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 140)
      }
    }, 2800 + Math.random() * 2200)
    return () => clearInterval(interval)
  }, [emotion])

  // The eyes follow the text as it grows.
  const eyeOffset = Math.sin(textLength * 0.45) * 6
  const ear = isListening
    ? 'bg-red-500 shadow-[0_0_10px_#ef4444,0_0_18px_rgba(239,68,68,0.7)] animate-pulse'
    : emotion === 'thinking'
      ? 'bg-amber-400 shadow-[0_0_8px_#facc15]'
      : 'bg-emerald-400 shadow-[0_0_8px_#10b981]'

  return (
    <motion.div
      className="relative flex flex-col items-center justify-center select-none px-2.5 pt-2"
      animate={{ y: emotion === 'thinking' ? [0, -5, 0] : [0, -2, 0] }}
      transition={{ y: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' } }}
    >
      <div className="relative w-20 flex justify-between px-2 -mb-2 z-0">
        <div className="w-3.5 h-4 bg-zinc-300 dark:bg-zinc-700 border-2 border-black/10 dark:border-white/10 rounded-tl-xl" />
        <div className="w-3.5 h-4 bg-zinc-300 dark:bg-zinc-700 border-2 border-black/10 dark:border-white/10 rounded-tr-xl" />
      </div>
      <div className="relative flex items-center justify-center">
        <div className={`absolute -left-1.5 w-1 h-5 rounded-l-xs transition-all duration-300 ${ear}`} />
        <div className={`absolute -right-1.5 w-1 h-5 rounded-r-xs transition-all duration-300 ${ear}`} />
        <div className="z-10 w-22 h-15 rounded-xl bg-zinc-100 dark:bg-zinc-800 border-2 border-black/10 dark:border-white/20 flex items-center justify-center p-1.5 shadow-[0_3px_10px_rgba(0,0,0,0.05)] dark:shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
          <div className="relative w-full h-full bg-[#050505] rounded-lg flex items-center justify-center gap-3.5 overflow-hidden shadow-[inset_0_2px_5px_rgba(0,0,0,0.95)]">
            <div className="relative z-10 flex items-center justify-center gap-3.5">
              <EyeLED emotion={emotion} isBlinking={isBlinking} offsetX={eyeOffset} />
              <EyeLED emotion={emotion} isBlinking={isBlinking} offsetX={eyeOffset} />
            </div>
            <div
              className="absolute inset-0 pointer-events-none z-20"
              style={{ backgroundImage: 'linear-gradient(rgba(0,0,0,0) 50%, rgba(0,0,0,0.72) 50%)', backgroundSize: '100% 4px' }}
            />
            <div className="absolute inset-0 pointer-events-none z-20 shadow-[inset_0_0_8px_rgba(0,0,0,0.9)]" />
          </div>
        </div>
      </div>
    </motion.div>
  )
}

