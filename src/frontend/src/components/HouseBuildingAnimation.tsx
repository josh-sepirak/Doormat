'use client'

import { useState, useEffect } from 'react'

const STATUS_MESSAGES = [
  'Searching for property managers…',
  'Analyzing listings…',
  'Scoring against your preferences…',
  'Building your results…',
]

export function HouseBuildingAnimation({ message }: { message?: string }) {
  const [messageIndex, setMessageIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (message) return

    let fadeTimeout: ReturnType<typeof setTimeout> | null = null
    const interval = setInterval(() => {
      setVisible(false)
      fadeTimeout = setTimeout(() => {
        setMessageIndex((i) => (i + 1) % STATUS_MESSAGES.length)
        setVisible(true)
      }, 400)
    }, 3000)

    return () => {
      clearInterval(interval)
      if (fadeTimeout) clearTimeout(fadeTimeout)
    }
  }, [message])

  const displayMessage = message ?? STATUS_MESSAGES[messageIndex]

  return (
    <div className="flex flex-col items-center gap-y-4 py-2">
      <style>{`
        /* ── Phase 1: Foundation (0–3s) ── */
        @keyframes foundation-grow {
          0%   { transform: scaleX(0); opacity: 0; }
          10%  { opacity: 1; }
          30%  { transform: scaleX(1); }
          100% { transform: scaleX(1); }
        }

        /* ── Phase 2: Walls grow upward (3–6s) ── */
        @keyframes wall-grow {
          0%   { transform: scaleY(0); opacity: 0; }
          25%  { transform: scaleY(0); opacity: 0; }
          26%  { opacity: 1; }
          55%  { transform: scaleY(1); }
          100% { transform: scaleY(1); }
        }

        /* ── Phase 3: Roof drops in (6–9s) ── */
        @keyframes roof-drop {
          0%   { transform: translateY(-30px); opacity: 0; }
          50%  { transform: translateY(-30px); opacity: 0; }
          65%  { opacity: 1; transform: translateY(4px); }
          72%  { transform: translateY(-2px); }
          78%  { transform: translateY(0); }
          100% { transform: translateY(0); }
        }

        /* ── Phase 4a: Door appears (9–10s) ── */
        @keyframes door-appear {
          0%   { opacity: 0; transform: scaleY(0); }
          75%  { opacity: 0; transform: scaleY(0); }
          82%  { opacity: 1; transform: scaleY(1); }
          100% { opacity: 1; transform: scaleY(1); }
        }

        /* ── Phase 4b: Window appears (10–11s) ── */
        @keyframes window-appear {
          0%   { opacity: 0; transform: scale(0); }
          83%  { opacity: 0; transform: scale(0); }
          92%  { opacity: 1; transform: scale(1.1); }
          96%  { transform: scale(0.95); }
          100% { opacity: 1; transform: scale(1); }
        }

        /* ── Chimney puff ── */
        @keyframes smoke-puff {
          0%   { opacity: 0; transform: translateY(0) scale(0.3); }
          88%  { opacity: 0; transform: translateY(0) scale(0.3); }
          92%  { opacity: 0.6; transform: translateY(-4px) scale(0.6); }
          96%  { opacity: 0.3; transform: translateY(-10px) scale(0.9); }
          100% { opacity: 0; transform: translateY(-16px) scale(1.1); }
        }

        /* ── Worker A: walks left-right during building ── */
        @keyframes worker-a-move {
          0%   { transform: translateX(0); }
          15%  { transform: translateX(-18px); }
          30%  { transform: translateX(0); }
          45%  { transform: translateX(14px); }
          60%  { transform: translateX(0); }
          80%  { transform: translateX(-8px); }
          90%  { transform: translateX(-8px); }
          /* Step back to admire */
          100% { transform: translateX(-28px); }
        }

        /* ── Worker A arm: swings while working ── */
        @keyframes worker-a-arm {
          0%   { transform-origin: 50% 0%; transform: rotate(0deg); }
          12%  { transform-origin: 50% 0%; transform: rotate(-30deg); }
          24%  { transform-origin: 50% 0%; transform: rotate(20deg); }
          36%  { transform-origin: 50% 0%; transform: rotate(-25deg); }
          48%  { transform-origin: 50% 0%; transform: rotate(15deg); }
          75%  { transform-origin: 50% 0%; transform: rotate(0deg); }
          /* Arm raises in admiration */
          88%  { transform-origin: 50% 0%; transform: rotate(-50deg); }
          100% { transform-origin: 50% 0%; transform: rotate(-50deg); }
        }

        /* ── Worker B: carries bricks left to right ── */
        @keyframes worker-b-move {
          0%   { transform: translateX(-30px); opacity: 0; }
          8%   { opacity: 1; transform: translateX(-30px); }
          35%  { transform: translateX(22px); }
          50%  { transform: translateX(22px); }
          65%  { transform: translateX(-10px); }
          78%  { transform: translateX(10px); }
          90%  { transform: translateX(-20px); }
          100% { transform: translateX(-20px); }
        }

        /* ── Brick carried by worker B ── */
        @keyframes brick-carry {
          0%   { opacity: 0; }
          8%   { opacity: 1; }
          30%  { opacity: 1; }
          35%  { opacity: 0; }
          65%  { opacity: 0; }
          66%  { opacity: 1; }
          89%  { opacity: 1; }
          90%  { opacity: 0; }
          100% { opacity: 0; }
        }

        /* ── Ground sparkle on completion ── */
        @keyframes sparkle {
          0%   { opacity: 0; transform: scale(0) rotate(0deg); }
          92%  { opacity: 0; transform: scale(0) rotate(0deg); }
          96%  { opacity: 1; transform: scale(1.2) rotate(15deg); }
          98%  { opacity: 0.8; transform: scale(0.9) rotate(-5deg); }
          100% { opacity: 0; transform: scale(0) rotate(0deg); }
        }

        .house-anim {
          animation-duration: 12s;
          animation-timing-function: ease-in-out;
          animation-iteration-count: infinite;
        }

        .anim-foundation { animation-name: foundation-grow; transform-origin: left center; }
        .anim-wall       { animation-name: wall-grow;       transform-origin: center bottom; }
        .anim-roof       { animation-name: roof-drop; }
        .anim-door       { animation-name: door-appear;     transform-origin: center bottom; }
        .anim-window     { animation-name: window-appear;   transform-origin: center center; }
        .anim-smoke      { animation-name: smoke-puff; }
        .anim-worker-a   { animation-name: worker-a-move; }
        .anim-worker-a-arm { animation-name: worker-a-arm; }
        .anim-worker-b   { animation-name: worker-b-move; }
        .anim-brick      { animation-name: brick-carry; }
        .anim-sparkle    { animation-name: sparkle; }

        @media (prefers-reduced-motion: reduce) {
          .house-anim {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
          }
        }
      `}</style>

      {/* SVG scene */}
      <svg
        viewBox="0 0 320 200"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full max-w-xs"
        aria-label="House being built animation"
        role="img"
      >
        {/* ── Sky background ── */}
        <rect
          width="320"
          height="200"
          fill="none"
          className="[.dark_&]:fill-[#0f172a] fill-[#f8fafc]"
        />

        {/* ── Distant hills (static atmosphere) ── */}
        <ellipse cx="60"  cy="168" rx="55" ry="18" className="[.dark_&]:fill-[#1e293b] fill-[#e2e8f0]" />
        <ellipse cx="260" cy="170" rx="48" ry="15" className="[.dark_&]:fill-[#1e293b] fill-[#e2e8f0]" />

        {/* ── Ground line ── */}
        <line
          x1="0" y1="174" x2="320" y2="174"
          className="[.dark_&]:stroke-[#334155] stroke-[#cbd5e1]"
          strokeWidth="2"
        />

        {/* ── Tree (static, left side) ── */}
        <rect x="36" y="148" width="5" height="24"
          className="[.dark_&]:fill-[#334155] fill-[#94a3b8]" rx="1" />
        <ellipse cx="38" cy="142" rx="12" ry="14"
          className="[.dark_&]:fill-[#1e3a2f] fill-[#86efac]" />

        {/* ── Tree (static, right side) ── */}
        <rect x="272" y="153" width="4" height="19"
          className="[.dark_&]:fill-[#334155] fill-[#94a3b8]" rx="1" />
        <ellipse cx="274" cy="148" rx="10" ry="11"
          className="[.dark_&]:fill-[#1e3a2f] fill-[#86efac]" />

        {/* ══════════════════════════════════════
            HOUSE — built up in animation phases
            ══════════════════════════════════════ */}

        {/* ── Foundation (Phase 1: 0–3s) ── */}
        <rect
          x="110" y="166" width="100" height="8"
          rx="2"
          className="house-anim anim-foundation [.dark_&]:fill-[#334155] [.dark_&]:stroke-[#475569] fill-[#cbd5e1] stroke-[#94a3b8]"
          strokeWidth="1"
        />

        {/* ── Walls (Phase 2: 3–6s) ── */}
        <rect
          x="114" y="120" width="92" height="46"
          rx="1"
          className="house-anim anim-wall [.dark_&]:fill-[#1e293b] [.dark_&]:stroke-[#475569] fill-[#f1f5f9] stroke-[#94a3b8]"
          strokeWidth="1.5"
        />

        {/* ── Chimney (appears with walls) ── */}
        <rect
          x="183" y="105" width="12" height="22"
          rx="1"
          className="house-anim anim-wall [.dark_&]:fill-[#334155] [.dark_&]:stroke-[#475569] fill-[#cbd5e1] stroke-[#94a3b8]"
          strokeWidth="1"
        />

        {/* ── Smoke puff from chimney (Phase 4) ── */}
        <circle
          cx="189" cy="104" r="5"
          className="house-anim anim-smoke [.dark_&]:fill-[#334155] fill-[#e2e8f0]"
          opacity="0"
        />
        <circle
          cx="186" cy="97" r="4"
          className="house-anim anim-smoke [.dark_&]:fill-[#334155] fill-[#e2e8f0]"
          opacity="0"
          style={{ animationDelay: '0.4s' }}
        />

        {/* ── Roof / triangle (Phase 3: 6–9s) ── */}
        <polygon
          points="104,122 160,88 216,122"
          className="house-anim anim-roof [.dark_&]:fill-[#334155] [.dark_&]:stroke-[#475569] fill-[#64748b] stroke-[#475569]"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* ── Door (Phase 4a: 9–10s) ── */}
        <rect
          x="149" y="138" width="22" height="28"
          rx="2"
          className="house-anim anim-door [.dark_&]:fill-[#0f172a] [.dark_&]:stroke-[#3b82f6] fill-[#e2e8f0] stroke-[#2563EB]"
          strokeWidth="1.5"
          opacity="0"
        />
        {/* Door knob */}
        <circle
          cx="167" cy="153" r="2"
          className="house-anim anim-door [.dark_&]:fill-[#3b82f6] fill-[#2563EB]"
          opacity="0"
        />

        {/* ── Window (Phase 4b: 10–11s) ── */}
        <rect
          x="125" y="130" width="18" height="16"
          rx="2"
          className="house-anim anim-window [.dark_&]:fill-[#1e3a5f] [.dark_&]:stroke-[#3b82f6] fill-[#bfdbfe] stroke-[#2563EB]"
          strokeWidth="1.5"
          opacity="0"
        />
        {/* Window cross */}
        <line x1="134" y1="130" x2="134" y2="146"
          className="house-anim anim-window [.dark_&]:stroke-[#3b82f6] stroke-[#2563EB]"
          strokeWidth="1" opacity="0" />
        <line x1="125" y1="138" x2="143" y2="138"
          className="house-anim anim-window [.dark_&]:stroke-[#3b82f6] stroke-[#2563EB]"
          strokeWidth="1" opacity="0" />

        {/* ── Second window (right side) ── */}
        <rect
          x="177" y="130" width="18" height="16"
          rx="2"
          className="house-anim anim-window [.dark_&]:fill-[#1e3a5f] [.dark_&]:stroke-[#3b82f6] fill-[#bfdbfe] stroke-[#2563EB]"
          strokeWidth="1.5"
          opacity="0"
          style={{ animationDelay: '0.3s' }}
        />
        <line x1="186" y1="130" x2="186" y2="146"
          className="house-anim anim-window [.dark_&]:stroke-[#3b82f6] stroke-[#2563EB]"
          strokeWidth="1" opacity="0"
          style={{ animationDelay: '0.3s' }} />
        <line x1="177" y1="138" x2="195" y2="138"
          className="house-anim anim-window [.dark_&]:stroke-[#3b82f6] stroke-[#2563EB]"
          strokeWidth="1" opacity="0"
          style={{ animationDelay: '0.3s' }} />

        {/* ── Completion sparkles ── */}
        <text x="108" y="170" fontSize="10" className="house-anim anim-sparkle" opacity="0">✦</text>
        <text x="208" y="168" fontSize="8"  className="house-anim anim-sparkle" opacity="0" style={{ animationDelay: '0.2s' }}>✦</text>
        <text x="156" y="84"  fontSize="7"  className="house-anim anim-sparkle" opacity="0" style={{ animationDelay: '0.5s' }}>✦</text>

        {/* ══════════════════════════════════════
            WORKER A — primary builder, right of house
            ══════════════════════════════════════ */}
        <g className="house-anim anim-worker-a" style={{ transformOrigin: '245px 174px' }}>
          {/* Head */}
          <circle cx="245" cy="151" r="6"
            className="[.dark_&]:fill-[#f8d7a0] [.dark_&]:stroke-[#475569] fill-[#fde68a] stroke-[#94a3b8]"
            strokeWidth="1" />
          {/* Hard hat */}
          <rect x="239" y="145" width="12" height="4" rx="2"
            className="[.dark_&]:fill-[#3b82f6] fill-[#2563EB]" />
          {/* Body */}
          <line x1="245" y1="157" x2="245" y2="170"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2.5" strokeLinecap="round" />
          {/* Right arm (swings) */}
          <line x1="245" y1="160" x2="254" y2="165"
            className="house-anim anim-worker-a-arm [.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round"
            style={{ transformOrigin: '245px 160px' }} />
          {/* Left arm */}
          <line x1="245" y1="160" x2="237" y2="165"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
          {/* Legs */}
          <line x1="245" y1="170" x2="241" y2="174"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
          <line x1="245" y1="170" x2="249" y2="174"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
        </g>

        {/* ══════════════════════════════════════
            WORKER B — carries bricks, left of house
            ══════════════════════════════════════ */}
        <g className="house-anim anim-worker-b" style={{ transformOrigin: '88px 174px' }}>
          {/* Head */}
          <circle cx="88" cy="151" r="5.5"
            className="[.dark_&]:fill-[#f8d7a0] [.dark_&]:stroke-[#475569] fill-[#fde68a] stroke-[#94a3b8]"
            strokeWidth="1" />
          {/* Hard hat (orange for contrast) */}
          <rect x="83" y="146" width="11" height="3.5" rx="1.5"
            className="[.dark_&]:fill-[#f97316] fill-[#fb923c]" />
          {/* Body */}
          <line x1="88" y1="157" x2="88" y2="169"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2.5" strokeLinecap="round" />
          {/* Arms (outstretched, carrying) */}
          <line x1="88" y1="160" x2="98" y2="158"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
          <line x1="88" y1="160" x2="78" y2="158"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
          {/* Brick being carried */}
          <rect x="77" y="154" width="22" height="7" rx="1"
            className="house-anim anim-brick [.dark_&]:fill-[#dc2626] [.dark_&]:stroke-[#991b1b] fill-[#fca5a5] stroke-[#ef4444]"
            strokeWidth="1" opacity="0" />
          {/* Legs */}
          <line x1="88" y1="169" x2="84" y2="174"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
          <line x1="88" y1="169" x2="92" y2="174"
            className="[.dark_&]:stroke-[#94a3b8] stroke-[#64748b]"
            strokeWidth="2" strokeLinecap="round" />
        </g>
      </svg>

      {/* Status message */}
      <p
        className="text-sm text-slate-500 dark:text-slate-400 transition-opacity duration-300 text-center"
        style={{ opacity: visible ? 1 : 0 }}
      >
        {displayMessage}
      </p>
    </div>
  )
}
