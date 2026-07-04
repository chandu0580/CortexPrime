"use client";

import { motion } from "framer-motion";

import {
  FeatureGrid,
  Footer,
  Hero,
  Navbar,
  SecurityCard,
  StatsSection,
} from "@/components/landing/enterprise/sections";
import { DraggableRobot } from "@/components/landing/enterprise/DraggableRobot";

export default function CortexPrimeLandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#F8FAFC] text-[#111827]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-8%] top-[-12%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(56,184,138,0.12)_0%,rgba(56,184,138,0.03)_42%,transparent_72%)]" />
        <div className="absolute right-[-10%] top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(56,184,138,0.08)_0%,rgba(56,184,138,0.02)_48%,transparent_72%)]" />
        <div className="absolute bottom-[-10%] left-[20%] h-[24rem] w-[24rem] rounded-full bg-[radial-gradient(circle,rgba(110,231,183,0.12)_0%,rgba(110,231,183,0.02)_45%,transparent_72%)]" />
      </div>

      {/* Draggable robot — floats freely over the entire page */}
      <DraggableRobot />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35 }}
        className="relative mx-auto flex w-full max-w-[1560px] flex-col px-4 pb-8 pt-4 sm:px-6 lg:px-8 xl:px-10"
      >
        <Navbar />
        <Hero />

        <div className="mt-8 grid gap-6 lg:mt-10 lg:grid-cols-[1.62fr_0.82fr]">
          <FeatureGrid />
          <SecurityCard />
        </div>

        <div className="mt-6">
          <StatsSection />
        </div>

        <Footer />
      </motion.div>
    </div>
  );
}
