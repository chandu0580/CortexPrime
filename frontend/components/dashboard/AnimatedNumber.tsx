"use client"

import { useEffect } from "react"
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"

export function AnimatedNum({ value }: { value: string }) {
  const num = Number(value.replace(/[^0-9.]/g, ""));
  const count = useMotionValue(0);
  const spring = useSpring(count, { stiffness: 80, damping: 22 });
  const display = useTransform(spring, (v) => {
    if (!Number.isFinite(num) || num === 0) return value;
    const n = num >= 100 ? Math.round(v) : Math.round(v * 10) / 10;
    return value.replace(/[0-9.]+/, String(n));
  });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (Number.isFinite(num) && num > 0) count.set(num); }, [count, num]);
  if (!Number.isFinite(num) || num === 0) return <span>{value}</span>;
  return <motion.span>{display}</motion.span>;
}
