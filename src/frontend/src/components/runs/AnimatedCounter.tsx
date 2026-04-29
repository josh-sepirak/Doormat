'use client'

import { useEffect, useRef, useState } from 'react'

type Props = {
  value: number
  decimals?: number
  className?: string
}

/**
 * Smoothly rolls a numeric counter toward `value` over ~400ms using
 * requestAnimationFrame. Restarts from the last interpolated position if
 * `value` changes mid-animation. Uses tabular-nums to limit layout shift.
 */
export function AnimatedCounter({ value, decimals = 0, className }: Props) {
  const [displayed, setDisplayed] = useState(value)
  const animValueRef = useRef(value)
  const rafRef = useRef(0)

  useEffect(() => {
    const from = animValueRef.current
    const to = value
    if (from === to) return

    const duration = 400
    const start = performance.now()

    const tick = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - (1 - progress) ** 2
      const v = from + (to - from) * eased
      animValueRef.current = v
      setDisplayed(v)
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        animValueRef.current = to
        setDisplayed(to)
      }
    }

    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value])

  const formatted =
    decimals > 0
      ? displayed.toFixed(decimals)
      : Math.round(displayed).toLocaleString()

  return (
    <span className={className} style={{ fontVariantNumeric: 'tabular-nums' }}>
      {formatted}
    </span>
  )
}
