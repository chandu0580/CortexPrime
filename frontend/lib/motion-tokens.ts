/**
 * CortexPrime — Global Motion Token System
 *
 * Single source of truth for ALL animation timing.
 * Use these everywhere — no more random durations.
 *
 * Usage:
 *   import { dur, ease, spring, variants } from "@/lib/motion-tokens"
 *   transition={{ duration: dur.fast, ease: ease.out }}
 */

// ─── Duration tokens (seconds, for Framer Motion) ──────────────────────────

export const dur = {
  /** 100ms — instant feedback, active states */
  instant:  0.10,
  /** 150ms — button press, icon swap */
  snap:     0.15,
  /** 200ms — hover lift, color change */
  fast:     0.20,
  /** 300ms — panel reveal, tooltip */
  base:     0.30,
  /** 400ms — modal, drawer, card expand */
  medium:   0.40,
  /** 600ms — page section entrance */
  slow:     0.60,
  /** 800ms — hero elements, landing page */
  xslow:    0.80,
} as const

/** CSS var equivalents for use outside Framer Motion */
export const durMs = {
  instant:  100,
  snap:     150,
  fast:     200,
  base:     300,
  medium:   400,
  slow:     600,
  xslow:    800,
} as const

// ─── Easing tokens ─────────────────────────────────────────────────────────

export const ease = {
  /** Spring-like snap — feels snappy, most UI */
  out:      [0.16, 1, 0.3, 1] as const,
  /** Material-style — smooth entry and exit */
  inOut:    [0.4, 0, 0.2, 1] as const,
  /** Overshoot — draws attention */
  back:     [0.34, 1.56, 0.64, 1] as const,
  /** Linear — loading bars, progress */
  linear:   [0, 0, 1, 1] as const,
  /** Quick out — hover reveals */
  quickOut: [0, 0, 0.2, 1] as const,
} as const

// ─── Spring presets ────────────────────────────────────────────────────────

export const spring = {
  /** Snappy — button press, toggle */
  snappy: { type: "spring", stiffness: 500, damping: 30, mass: 0.8 } as const,
  /** Bouncy — tooltip, badge pop */
  bouncy: { type: "spring", stiffness: 400, damping: 20, mass: 0.6 } as const,
  /** Smooth — card, panel */
  smooth: { type: "spring", stiffness: 300, damping: 35, mass: 1.0 } as const,
  /** Gentle — page elements */
  gentle: { type: "spring", stiffness: 180, damping: 28, mass: 1.2 } as const,
} as const

// ─── Reusable Framer Motion transition presets ─────────────────────────────

export const transition = {
  fast:   { duration: dur.fast,   ease: ease.out   },
  base:   { duration: dur.base,   ease: ease.out   },
  medium: { duration: dur.medium, ease: ease.inOut },
  slow:   { duration: dur.slow,   ease: ease.inOut },
} as const

interface StaggerType {
  (children?: number, delayStart?: number): {
    hidden: Record<string, any>;
    visible: {
      transition: {
        staggerChildren: number;
        delayChildren: number;
      };
    };
  };
  container: {
    hidden: Record<string, any>;
    show: {
      transition: {
        staggerChildren: number;
      };
    };
  };
}

export const stagger: StaggerType = (() => {
  const fn = (children = 0.06, delayStart = 0) => ({
    hidden:  {},
    visible: {
      transition: {
        staggerChildren: children,
        delayChildren:   delayStart,
      },
    },
  });

  (fn as any).container = {
    hidden: {},
    show: {
      transition: {
        staggerChildren: 0.05,
      },
    },
  };

  return fn as unknown as StaggerType;
})();

// ─── Common variant sets ───────────────────────────────────────────────────

export const variants = {

  /** Generic fade in */
  fadeIn: {
    hidden:  { opacity: 0 },
    visible: { opacity: 1, transition: transition.base },
    exit:    { opacity: 0, transition: { duration: dur.fast, ease: ease.quickOut } },
  },

  /** Fade up (most used for list items, cards) */
  fadeUp: {
    hidden:  { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: dur.base, ease: ease.out } },
    exit:    { opacity: 0, y: -8, transition: { duration: dur.fast } },
  },

  /** Fade down (dropdowns, tooltips) */
  fadeDown: {
    hidden:  { opacity: 0, y: -10 },
    visible: { opacity: 1, y: 0, transition: { duration: dur.base, ease: ease.out } },
    exit:    { opacity: 0, y: -6, transition: { duration: dur.fast } },
  },

  /** Scale pop (badges, chips, indicators) */
  scalePop: {
    hidden:  { opacity: 0, scale: 0.75 },
    visible: { opacity: 1, scale: 1, transition: spring.bouncy },
    exit:    { opacity: 0, scale: 0.8, transition: { duration: dur.snap } },
  },

  /** Slide in from left */
  slideLeft: {
    hidden:  { opacity: 0, x: -24 },
    visible: { opacity: 1, x: 0, transition: { duration: dur.base, ease: ease.out } },
    exit:    { opacity: 0, x: -16, transition: { duration: dur.fast } },
  },

  /** Slide in from right */
  slideRight: {
    hidden:  { opacity: 0, x: 24 },
    visible: { opacity: 1, x: 0, transition: { duration: dur.base, ease: ease.out } },
    exit:    { opacity: 0, x: 16, transition: { duration: dur.fast } },
  },

  /** Page section — for landing page sections */
  section: {
    hidden:  { opacity: 0, y: 40 },
    visible: { opacity: 1, y: 0, transition: { duration: dur.slow, ease: ease.out } },
  },

  /** Card hover lift — applied via whileHover */
  cardHover: {
    scale: 1.015,
    y:     -3,
    transition: transition.fast,
  },

  /** Button press */
  buttonTap: {
    scale: 0.96,
    transition: { duration: dur.snap, ease: ease.inOut },
  },
} as const

// ─── Infinite loop presets (for animate prop, not variants) ───────────────

export const loop = {
  /** Heartbeat — status dots, active indicators */
  pulse: {
    scale:   [1, 1.18, 1] as number[],
    opacity: [1, 0.6, 1] as number[],
    transition: {
      repeat:   Infinity,
      duration: 2,
      ease:     "easeInOut" as const,
    },
  },

  /** Slow glow — accent elements */
  glow: {
    opacity: [0.5, 1, 0.5] as number[],
    transition: {
      repeat:   Infinity,
      duration: 3,
      ease:     "easeInOut" as const,
    },
  },

  /** Rotation — loading spinners, orbit rings */
  spin: (seconds = 4) => ({
    rotate: 360,
    transition: { repeat: Infinity, duration: seconds, ease: "linear" as const },
  }),

  /** Shimmer wave — skeleton loaders */
  shimmer: {
    x: ["-100%", "100%"] as string[],
    transition: {
      repeat:   Infinity,
      duration: 1.4,
      ease:     "easeInOut" as const,
    },
  },

  /** Float — ambient elements */
  float: {
    y: [-6, 6, -6] as number[],
    transition: {
      repeat:   Infinity,
      duration: 4,
      ease:     "easeInOut" as const,
    },
  },
}

// ─── CSS variable aliases (for use in style={} props) ─────────────────────

export const cssMotion = {
  fast:   "var(--duration-fast, 200ms)",
  base:   "var(--duration-base, 300ms)",
  medium: "var(--duration-medium, 400ms)",
  slow:   "var(--duration-slow, 600ms)",
  xslow:  "var(--duration-xslow, 800ms)",
  ease:   "var(--ease-out, cubic-bezier(0.16, 1, 0.3, 1))",
} as const
