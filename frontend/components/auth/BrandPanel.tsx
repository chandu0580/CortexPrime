"use client";

import { motion } from "framer-motion";
import { Database, Mic, ShieldCheck, Users } from "lucide-react";

import LandingLogo from "@/components/landing/enterprise/LandingLogo";
import { RobotIllustration } from "@/components/landing/enterprise/illustrations";
import { stagger, variants } from "@/lib/motion-tokens";

const features = [
  { icon: Users,       label: "Multi-Agent Orchestration" },
  { icon: Mic,         label: "Real-time Voice & Decisions" },
  { icon: Database,    label: "Memory & Knowledge Engine" },
  { icon: ShieldCheck, label: "Governance & Security by Default" },
];

function Sparkline() {
  const points = "0,18 14,14 28,16 42,10 56,13 70,8 84,11";
  return (
    <svg viewBox="0 0 84 28" className="h-5 w-[64px] shrink-0" fill="none" aria-hidden>
      <path
        d={`M0 27 L${points.split(" ").join(" L")} L84 27 Z`}
        fill="rgba(56,184,138,0.07)"
      />
      <polyline
        points={points}
        stroke="#38B88A"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FloatingMetricCard({
  title,
  value,
  delta,
  className,
  delay = 0,
  dir = 1,
}: {
  title: string;
  value: string;
  delta?: string;
  className: string;
  delay?: number;
  dir?: 1 | -1;
}) {
  return (
    <motion.div
      animate={{ y: [dir * -4, dir * 4, dir * -4] }}
      transition={{ duration: 4 + delay * 0.4, repeat: Infinity, ease: "easeInOut", delay }}
      className={`absolute hidden rounded-[18px] border border-[#E5E7EB] bg-white/92 px-3.5 py-3 shadow-[0_12px_28px_rgba(148,163,184,0.13)] backdrop-blur md:block ${className}`}
      aria-hidden="true"
    >
      <p className="text-[0.65rem] font-medium text-[#6B7280]">{title}</p>
      <div className="mt-1.5 flex items-end justify-between gap-2">
        <div className="flex items-end gap-1">
          <span className="text-[1.45rem] font-bold leading-none tracking-[-0.05em] text-[#111827]">
            {value}
          </span>
          {delta && (
            <span className="pb-0.5 text-[0.65rem] font-semibold text-[#22C55E]">{delta}</span>
          )}
        </div>
        <Sparkline />
      </div>
    </motion.div>
  );
}

export default function BrandPanel() {
  return (
    <section className="relative overflow-hidden border-b border-[#E8EDF2] bg-[#F4F8F6] px-8 py-8 sm:px-10 lg:min-h-screen lg:border-b-0 lg:border-r lg:px-12 lg:py-10 xl:px-14">
      {/* Background glows */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-14%] top-[-10%] h-[24rem] w-[24rem] rounded-full bg-[radial-gradient(circle,rgba(56,184,138,0.13)_0%,rgba(56,184,138,0.03)_48%,transparent_75%)]" />
        <div className="absolute bottom-[-12%] right-[-10%] h-[22rem] w-[22rem] rounded-full bg-[radial-gradient(circle,rgba(110,231,183,0.11)_0%,rgba(110,231,183,0.02)_45%,transparent_74%)]" />
      </div>

      <motion.div
        initial="hidden"
        animate="visible"
        variants={stagger(0.07, 0.04)}
        className="relative z-10 flex h-full flex-col"
      >
        {/* Logo */}
        <motion.div variants={variants.fadeUp}>
          <LandingLogo />
        </motion.div>

        {/* Headline — exactly as reference */}
        <motion.div variants={variants.fadeUp} className="mt-10 lg:mt-14">
          <h1
            className="text-[2.5rem] font-bold leading-[1.12] tracking-[-0.04em] sm:text-[2.8rem]"
            style={{ fontWeight: 700 }}
          >
            <span style={{ color: "#38B88A" }}>AI Operating System</span>
            <br />
            <span style={{ color: "#111827" }}>for Enterprise</span>
            <br />
            <span style={{ color: "#111827" }}>Intelligence</span>
          </h1>
        </motion.div>

        {/* Subtitle */}
        <motion.p
          variants={variants.fadeUp}
          className="mt-5 max-w-[28rem] text-[0.98rem] leading-[1.75] text-[#6B7280]"
        >
          Orchestrate autonomous AI agents, govern with confidence, and unlock
          enterprise-wide value from one unified platform.
        </motion.p>

        {/* Feature bullets */}
        <motion.ul variants={variants.fadeUp} className="mt-8 space-y-3.5">
          {features.map(({ icon: Icon, label }) => (
            <li key={label} className="flex items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#38B88A] text-white shadow-[0_3px_8px_rgba(56,184,138,0.22)]">
                <Icon className="h-4.5 w-4.5" />
              </span>
              <span className="text-[0.96rem] font-medium text-[#374151]">{label}</span>
            </li>
          ))}
        </motion.ul>

        {/* Illustration area */}
        <motion.div
          variants={variants.fadeUp}
          className="relative mt-10 flex flex-1 items-end justify-center pb-4 lg:mt-6 lg:pb-6"
          aria-hidden="true"
        >
          {/* Glow under robot */}
          <div className="absolute inset-x-0 bottom-0 mx-auto h-[100px] max-w-[400px] rounded-full bg-[radial-gradient(circle,rgba(56,184,138,0.14)_0%,rgba(56,184,138,0.03)_55%,transparent_78%)] blur-2xl" />

          {/* Robot + platform */}
          <div className="relative flex items-center justify-center">
            {/* Floating KPI cards */}
            <FloatingMetricCard
              title="Active Agents"
              value="24"
              delta="+4"
              className="-left-[105px] top-[10px] z-30"
              delay={0}
              dir={-1}
            />
            <FloatingMetricCard
              title="System Health"
              value="98.7%"
              className="-right-[100px] top-[30px] z-30"
              delay={0.5}
              dir={1}
            />
            <FloatingMetricCard
              title="Missions Running"
              value="7"
              delta="+2"
              className="-left-[90px] bottom-[90px] z-30"
              delay={0.9}
              dir={-1}
            />

            {/* Shield badge */}
            <div className="absolute bottom-[20px] right-[-14px] z-30 flex h-12 w-12 items-center justify-center rounded-[16px] border border-[#C8EDD9] bg-[#38B88A] p-2.5 shadow-[0_8px_20px_rgba(56,184,138,0.35)]">
              <ShieldCheck className="h-5.5 w-5.5 text-white" />
            </div>

            <RobotIllustration />
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
}
