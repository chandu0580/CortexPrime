"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";

import { loop } from "@/lib/motion-tokens";

function GlowOrb({
  className,
  delay = 0,
}: {
  className: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      animate={{
        y: [-4, 4, -4],
        opacity: [0.6, 1, 0.6],
      }}
      transition={{
        duration: 4,
        repeat: Infinity,
        ease: "easeInOut",
        delay,
      }}
      aria-hidden="true"
    />
  );
}

export function RobotIllustration() {
  return (
    <div className="relative h-[340px] w-[280px] flex flex-col items-center select-none" aria-hidden="true">
      {/* 3D Platform (Stationary/Slow float) */}
      <motion.div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[280px] h-[130px] z-0"
        animate={{
          y: [-2, 2, -2],
        }}
        transition={{
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* Glow beneath the platform */}
        <div className="absolute top-[35%] left-1/2 -translate-x-1/2 w-[220px] h-[60px] rounded-full bg-[#10B981]/25 blur-xl -z-10" />
        
        {/* Platform SVG */}
        <svg viewBox="0 0 300 150" className="w-full h-full drop-shadow-[0_12px_24px_rgba(16,185,129,0.15)]">
          <defs>
            <linearGradient id="leftSideGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#047857" stopOpacity="0.9" />
            </linearGradient>
            <linearGradient id="rightSideGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#047857" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#064E3B" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id="topFaceGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.98" />
              <stop offset="100%" stopColor="#EAFBF4" stopOpacity="0.9" />
            </linearGradient>
            <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Left thickness */}
          <polygon points="10,70 150,125 150,137 10,82" fill="url(#leftSideGrad)" />
          
          {/* Right thickness */}
          <polygon points="150,125 290,70 290,82 150,137" fill="url(#rightSideGrad)" />

          {/* Outer diamond top face */}
          <polygon points="10,70 150,15 290,70 150,125" fill="url(#topFaceGrad)" stroke="#A7F3D0" strokeWidth="1.5" />

          {/* Glowing inner diamond */}
          <polygon points="25,70 150,27 275,70 150,113" fill="none" stroke="#34D399" strokeWidth="1.5" strokeOpacity="0.4" />
          <polygon points="25,70 150,27 275,70 150,113" fill="none" stroke="#10B981" strokeWidth="1" filter="url(#neonGlow)" />

          {/* Center glowing circle (isometric ellipse) */}
          <ellipse cx="150" cy="70" rx="45" ry="20" fill="none" stroke="#34D399" strokeWidth="1" strokeOpacity="0.3" />
          <ellipse cx="150" cy="70" rx="35" ry="15" fill="none" stroke="#10B981" strokeWidth="1.5" filter="url(#neonGlow)" />
          <ellipse cx="150" cy="70" rx="15" ry="6" fill="#10B981" fillOpacity="0.25" stroke="#10B981" strokeWidth="0.5" />
        </svg>
      </motion.div>

      {/* Floating Robot */}
      <motion.div
        className="relative h-[250px] w-[200px] z-10 flex flex-col items-center"
        animate={{
          y: [-8, 8, -8],
        }}
        transition={{
          duration: 4.5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* Antenna */}
        <div className="relative flex flex-col items-center z-0">
          {/* Glowing tip */}
          <motion.div
            className="w-3.5 h-3.5 rounded-full bg-[#10B981] shadow-[0_0_12px_#10B981,0_0_24px_rgba(16,185,129,0.6)]"
            animate={{
              scale: [0.9, 1.15, 0.9],
              opacity: [0.8, 1, 0.8],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
          {/* Antenna stem */}
          <div className="w-[4px] h-[22px] bg-gradient-to-b from-[#E2E8F0] to-[#94A3B8] shadow-sm -mt-0.5" />
        </div>

        {/* Head */}
        <div className="relative w-[136px] h-[106px] rounded-[48px] border border-white/90 bg-gradient-to-br from-white via-[#F8FAFC] to-[#E2E8F0] shadow-[0_12px_32px_rgba(148,163,184,0.22),inset_-2px_-4px_8px_rgba(15,23,42,0.05),inset_2px_4px_6px_rgba(255,255,255,0.9)] z-20 -mt-0.5 flex items-center justify-center">
          
          {/* Ears/Joints */}
          {/* Left ear */}
          <div className="absolute -left-2.5 top-[38px] w-3 h-7 rounded-full bg-gradient-to-l from-slate-200 to-slate-400 border border-slate-300 shadow-[0_2px_4px_rgba(0,0,0,0.05)] flex items-center justify-center">
            <div className="w-1.5 h-3 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]" />
          </div>
          {/* Right ear */}
          <div className="absolute -right-2.5 top-[38px] w-3 h-7 rounded-full bg-gradient-to-r from-slate-200 to-slate-400 border border-slate-300 shadow-[0_2px_4px_rgba(0,0,0,0.05)] flex items-center justify-center">
            <div className="w-1.5 h-3 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]" />
          </div>

          {/* Screen */}
          <div className="relative w-[96px] h-[60px] rounded-[22px] bg-gradient-to-b from-[#1E293B] to-[#0B0F19] border border-slate-700/40 shadow-[inset_0_3px_8px_rgba(0,0,0,0.6),0_1.5px_3px_rgba(255,255,255,0.15)] flex flex-col items-center justify-center overflow-hidden">
            {/* Screen sheen reflection */}
            <div className="absolute top-0 left-0 w-[150px] h-[30px] bg-gradient-to-b from-white/10 to-transparent skew-y-[-15deg] origin-top-left pointer-events-none" />

            {/* Face content */}
            <div className="flex flex-col items-center mt-1">
              {/* Eyes */}
              <div className="flex gap-6">
                {/* Left eye */}
                <motion.div
                  className="w-3.5 h-5 rounded-full bg-[#10B981] shadow-[0_0_8px_#10B981,0_0_15px_rgba(16,185,129,0.5)]"
                  animate={{
                    scaleY: [1, 1, 0.1, 1, 1],
                  }}
                  transition={{
                    duration: 4,
                    repeat: Infinity,
                    times: [0, 0.9, 0.92, 0.94, 1],
                  }}
                />
                {/* Right eye */}
                <motion.div
                  className="w-3.5 h-5 rounded-full bg-[#10B981] shadow-[0_0_8px_#10B981,0_0_15px_rgba(16,185,129,0.5)]"
                  animate={{
                    scaleY: [1, 1, 0.1, 1, 1],
                  }}
                  transition={{
                    duration: 4,
                    repeat: Infinity,
                    times: [0, 0.9, 0.92, 0.94, 1],
                  }}
                />
              </div>

              {/* Smile */}
              <svg viewBox="0 0 24 10" className="w-6 h-3 mt-1 text-[#10B981] drop-shadow-[0_0_4px_#10B981]" fill="none">
                <path d="M4 2C8 7 16 7 20 2" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        </div>

        {/* Neck */}
        <div className="w-8 h-3.5 bg-gradient-to-r from-slate-300 via-slate-200 to-slate-400 rounded-md border-b border-slate-400/50 shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1)] z-10 -mt-1" />

        {/* Torso/Body */}
        <div className="relative w-[92px] h-[98px] rounded-t-[34px] rounded-b-[44px] border border-white/90 bg-gradient-to-b from-white via-[#F8FAFC] to-[#DDE2E8] shadow-[0_16px_36px_rgba(148,163,184,0.22),inset_-2px_-4px_8px_rgba(15,23,42,0.05),inset_2px_4px_6px_rgba(255,255,255,0.9)] z-20 -mt-1.5 flex flex-col items-center">
          
          {/* Logo badge in center */}
          <div className="mt-5 flex h-9.5 w-9.5 items-center justify-center rounded-full border border-emerald-200 bg-white shadow-[0_3px_8px_rgba(56,184,138,0.18)] text-[#38B88A]">
            <svg
              viewBox="0 0 48 48"
              aria-hidden="true"
              className="h-5.5 w-5.5"
              fill="none"
            >
              <path
                d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z"
                stroke="currentColor"
                strokeWidth="3.5"
                strokeLinejoin="round"
              />
              <path
                d="M24 13 31 17v14l-7 4-7-4V17l7-4Z"
                fill="currentColor"
                fillOpacity=".25"
                stroke="currentColor"
                strokeWidth="2.8"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          {/* Hover thruster glow at bottom of body */}
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-6 h-2 rounded-full bg-[#10B981] shadow-[0_0_10px_#10B981]" />
          <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 w-12 h-6 rounded-full bg-gradient-to-b from-[#10B981]/70 to-transparent blur-[2px]" />
        </div>

        {/* Floating Left Arm */}
        <motion.div
          className="absolute left-[-22px] top-[102px] w-8 h-[72px] rotate-[14deg] z-20 flex flex-col items-center"
          animate={{
            y: [-3, 3, -3],
            rotate: [14, 11, 14],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.25,
          }}
        >
          {/* Shoulder cap */}
          <div className="w-6.5 h-6.5 rounded-full bg-gradient-to-br from-[#34D399] to-[#059669] shadow-[0_2px_6px_rgba(16,185,129,0.3)] border border-white/20" />
          {/* Arm body */}
          <div className="w-7 h-[50px] rounded-full border border-white/95 bg-gradient-to-b from-white to-[#E2E8F0] shadow-[0_6px_14px_rgba(148,163,184,0.15),inset_1px_2px_4px_white] -mt-1.5" />
        </motion.div>

        {/* Floating Right Arm */}
        <motion.div
          className="absolute right-[-22px] top-[102px] w-8 h-[72px] -rotate-[14deg] z-20 flex flex-col items-center"
          animate={{
            y: [-3, 3, -3],
            rotate: [-14, -11, -14],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.5,
          }}
        >
          {/* Shoulder cap */}
          <div className="w-6.5 h-6.5 rounded-full bg-gradient-to-br from-[#34D399] to-[#059669] shadow-[0_2px_6px_rgba(16,185,129,0.3)] border border-white/20" />
          {/* Arm body */}
          <div className="w-7 h-[50px] rounded-full border border-white/95 bg-gradient-to-b from-white to-[#E2E8F0] shadow-[0_6px_14px_rgba(148,163,184,0.15),inset_1px_2px_4px_white] -mt-1.5" />
        </motion.div>
      </motion.div>
    </div>
  );
}

export function SecurityIllustration() {
  return (
    <div className="relative h-[240px] w-full max-w-[280px]" aria-hidden="true">
      <div className="absolute inset-x-7 bottom-3 h-6 rounded-full bg-[#8DE8C7]/25 blur-xl" />
      <div className="absolute left-[34px] top-[38px] h-[142px] w-[126px] rounded-[28px] border border-[#E2F3EC] bg-[linear-gradient(180deg,#F8FFFC_0%,#EDF8F2_100%)] shadow-[0_24px_50px_rgba(110,195,160,0.18)]">
        <div className="absolute left-5 top-5 h-[26px] w-[80px] rounded-full bg-[#ECF8F2]" />
        <div className="absolute inset-x-5 top-[62px] h-[18px] rounded-full bg-[#E5F4EE]" />
        <div className="absolute inset-x-5 top-[92px] h-[18px] rounded-full bg-[#E5F4EE]" />
        <div className="absolute inset-x-5 top-[122px] h-[18px] rounded-full bg-[#E5F4EE]" />
      </div>
      <div className="absolute left-[118px] top-[12px] h-[92px] w-[86px] rounded-[24px] border border-[#E2F3EC] bg-[linear-gradient(180deg,#FBFFFD_0%,#F0FAF5_100%)] shadow-[0_18px_40px_rgba(110,195,160,0.12)]">
        <div className="absolute left-1/2 top-6 h-[10px] w-[10px] -translate-x-1/2 rounded-full bg-[#38B88A]" />
        <div className="absolute left-5 top-[40px] h-2 w-2 rounded-full bg-[#8BDDBE]" />
        <div className="absolute left-1/2 top-[44px] h-2 w-2 -translate-x-1/2 rounded-full bg-[#8BDDBE]" />
        <div className="absolute right-5 top-[40px] h-2 w-2 rounded-full bg-[#8BDDBE]" />
      </div>
      <div className="absolute left-0 top-[92px] flex h-[120px] w-[120px] items-center justify-center rounded-[28px] border border-[#D1EFDF] bg-[linear-gradient(180deg,#ECFBF4_0%,#DDF7EA_100%)] shadow-[0_22px_46px_rgba(56,184,138,0.18)]">
        <div className="flex h-[84px] w-[84px] items-center justify-center rounded-[26px] bg-[#38B88A] text-white shadow-[0_16px_30px_rgba(56,184,138,0.24)]">
          <Check className="h-10 w-10" strokeWidth={3} />
        </div>
      </div>
    </div>
  );
}
