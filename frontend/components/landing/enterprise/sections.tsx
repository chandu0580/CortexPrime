"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Menu,
  Shield,
} from "lucide-react";

import DashboardPreview from "@/components/landing/enterprise/DashboardPreview";
import LandingLogo from "@/components/landing/enterprise/LandingLogo";
import {
  featureItems,
  navItems,
  statItems,
  trustItems,
} from "@/components/landing/enterprise/data";
import {
  SecurityIllustration,
} from "@/components/landing/enterprise/illustrations";
import {
  LandingBadge,
  LandingButton,
  LandingCard,
} from "@/components/landing/enterprise/primitives";
import { dur, ease, stagger, variants } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

export function Navbar() {
  return (
    <motion.header
      initial="hidden"
      animate="visible"
      variants={variants.fadeDown}
      className="sticky top-4 z-50"
    >
      <div className="rounded-[30px] border border-[#E5E7EB] bg-white/95 px-6 py-5 shadow-[0_18px_44px_rgba(148,163,184,0.14)] backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <LandingLogo />

          <nav
            aria-label="Primary navigation"
            className="hidden items-center gap-10 lg:flex"
          >
            {navItems.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="text-[0.96rem] font-medium tracking-[-0.02em] text-[#111827] transition-colors hover:text-[#2F9F77]"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            <LandingButton href="/login" variant="secondary">
              Sign In
            </LandingButton>
            <LandingButton href="/command" icon>
              Launch Console
            </LandingButton>
          </div>

          <button
            type="button"
            aria-label="Open navigation"
            className="flex h-11 w-11 items-center justify-center rounded-[16px] border border-[#E5E7EB] bg-white text-[#111827] md:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>
    </motion.header>
  );
}

export function Hero() {
  return (
    <section className="relative pt-8 lg:pt-10">
      <div className="grid items-start gap-10 lg:grid-cols-[0.92fr_1.22fr] lg:gap-8 xl:gap-10">
        {/* ── Left column: copy only, no robot in flow ── */}
        <motion.div
          initial="hidden"
          animate="visible"
          variants={stagger(0.08, 0.1)}
          className="relative z-10 flex flex-col pt-6 lg:pt-12"
        >
          <motion.div variants={variants.fadeUp}>
            <LandingBadge>AI Operating System for Enterprise</LandingBadge>
          </motion.div>

          <motion.div variants={variants.fadeUp} className="mt-6">
            <h1
              className="max-w-[13ch] text-[2.6rem] font-semibold leading-[1.0] tracking-[-0.05em] text-[#111827] sm:text-[3.2rem] xl:text-[4rem]"
              style={{ color: "#111827" }}
            >
              Run Autonomous{" "}
              <span className="text-[#38B88A]">AI&nbsp;Workforces</span>{" "}
              at Enterprise Scale
            </h1>
          </motion.div>

          <motion.p
            variants={variants.fadeUp}
            className="mt-6 max-w-[38rem] text-[1.08rem] leading-[1.72] tracking-[-0.01em] text-[#6B7280]"
          >
            Build, orchestrate, govern, and observe intelligent agents across
            your organization from one unified platform.
          </motion.p>

          <motion.div
            variants={variants.fadeUp}
            className="mt-8 flex flex-wrap gap-4"
          >
            <LandingButton href="/command" size="lg" icon>
              Launch Command Center
            </LandingButton>
            <LandingButton href="#enterprise" size="lg" variant="secondary">
              Book Enterprise Demo
            </LandingButton>
          </motion.div>

          {/* Trust badges — single horizontal row */}
          <motion.div
            variants={variants.fadeUp}
            className="mt-10 flex flex-row flex-wrap items-center gap-x-6 gap-y-3"
          >
            {trustItems.map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-2 text-[0.86rem] font-medium text-[#4B5563]"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white shadow-[0_4px_12px_rgba(148,163,184,0.12)] ring-1 ring-[#E5E7EB]">
                  <item.icon className="h-3.5 w-3.5 text-[#38B88A]" />
                </div>
                <span className="whitespace-nowrap">{item.label}</span>
              </div>
            ))}
          </motion.div>
        </motion.div>

        {/* ── Right column: robot floats at left edge of dashboard ── */}
        <motion.div
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: dur.slow, ease: ease.out, delay: 0.18 }}
          className="relative"
        >
          <DashboardPreview />
        </motion.div>
      </div>
    </section>
  );
}

export function FeatureGrid() {
  return (
    <motion.section
      id="platform"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.15 }}
      variants={variants.section}
    >
      <LandingCard className="h-full px-6 py-8 sm:px-8">
        <h2
          className="text-[1.9rem] font-semibold tracking-[-0.05em]"
          style={{ color: "#111827" }}
        >
          Everything you need to operate enterprise AI
        </h2>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {featureItems.map((feature) => (
            <motion.article
              key={feature.title}
              whileHover={{ y: -4 }}
              transition={{ duration: 0.2, ease: ease.out }}
              className="rounded-[24px] border border-[#EEF2F7] bg-[#FCFDFC] px-5 py-5 shadow-[0_8px_22px_rgba(148,163,184,0.05)]"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-[16px] border border-[#D9F1E7] bg-white text-[#38B88A] shadow-[0_8px_18px_rgba(56,184,138,0.1)]">
                <feature.icon className="h-5 w-5" />
              </div>
              {/* Title — inline style ensures visibility regardless of global CSS variable */}
              <h3
                className="mt-4 text-[0.98rem] font-semibold leading-snug tracking-[-0.02em]"
                style={{ color: "#111827", fontWeight: 600 }}
              >
                {feature.title}
              </h3>
              <p className="mt-2 text-[0.88rem] leading-[1.65] text-[#6B7280]">
                {feature.description}
              </p>
            </motion.article>
          ))}
        </div>
      </LandingCard>
    </motion.section>
  );
}

export function SecurityCard() {
  return (
    <motion.section
      id="enterprise"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.25 }}
      variants={variants.section}
    >
      <LandingCard className="h-full overflow-hidden px-6 py-8 sm:px-8">
        <div className="flex h-full flex-col justify-between gap-8 xl:grid xl:grid-cols-[1fr_0.98fr] xl:items-center">
          <div className="flex justify-center xl:justify-start">
            <SecurityIllustration />
          </div>

          <div className="xl:max-w-[270px]">
            <div className="inline-flex items-center gap-2 rounded-full bg-[#F0FBF6] px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.12em] text-[#2F9F77]">
              <Shield className="h-3.5 w-3.5" />
              Compliance
            </div>
            <h2 className="mt-5 text-[2rem] font-semibold leading-[1.02] tracking-[-0.05em] text-[#111827]">
              Enterprise Security <span className="text-[#38B88A]">by Default</span>
            </h2>
            <p className="mt-4 text-[1rem] leading-8 text-[#6B7280]">
              Built with security, compliance, and governance at every layer.
            </p>
            <div className="mt-7">
              <LandingButton href="#docs" variant="secondary" icon>
                Learn More
              </LandingButton>
            </div>
          </div>
        </div>
      </LandingCard>
    </motion.section>
  );
}

export function StatsSection() {
  return (
    <motion.section
      id="solutions"
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.25 }}
      variants={variants.section}
    >
      <LandingCard className="px-5 py-5 sm:px-7 sm:py-7">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6 xl:gap-0">
          {statItems.map((item, index) => (
            <div
              key={item.label}
              className={cn(
                "flex flex-col items-center justify-center rounded-[22px] px-4 py-4 text-center xl:rounded-none",
                index !== 0 && "xl:border-l xl:border-[#EEF2F7]",
              )}
            >
              <p className="text-[2.3rem] font-semibold leading-none tracking-[-0.06em] text-[#38B88A]">
                {item.value}
              </p>
              <p className="mt-3 text-[0.96rem] font-medium text-[#111827]">
                {item.label}
              </p>
            </div>
          ))}
        </div>
      </LandingCard>
    </motion.section>
  );
}

export function Footer() {
  return (
    <footer id="resources" className="pb-8 pt-8">
      <div className="flex flex-col gap-6 rounded-[28px] border border-[#E5E7EB] bg-white/80 px-6 py-6 shadow-[0_10px_30px_rgba(148,163,184,0.08)] backdrop-blur md:flex-row md:items-center md:justify-between">
        <div>
          <LandingLogo className="gap-3" />
          <p className="mt-3 max-w-[34rem] text-[0.95rem] text-[#6B7280]">
            Autonomous AI infrastructure for secure enterprise execution,
            observability, and governance.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-[0.92rem] font-medium text-[#6B7280]">
          <Link href="#platform" className="transition hover:text-[#111827]">
            Platform
          </Link>
          <Link href="#solutions" className="transition hover:text-[#111827]">
            Solutions
          </Link>
          <Link href="#docs" className="transition hover:text-[#111827]">
            Docs
          </Link>
          <Link href="/login" className="transition hover:text-[#111827]">
            Sign In
          </Link>
          <span className="hidden text-[#CBD5E1] md:inline">|</span>
          <div className="inline-flex items-center gap-2 text-[#2F9F77]">
            <CheckCircle2 className="h-4 w-4" />
            <span>Enterprise ready</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
