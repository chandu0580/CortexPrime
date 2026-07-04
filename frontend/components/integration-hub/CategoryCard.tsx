"use client";

import { motion } from "framer-motion";
import { integrationCategories } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { Layers, MessageSquare, Cloud, Cpu, Code, ShieldCheck, Database, HardDrive, BookOpen, Key } from "lucide-react";

export default function CategoryCard() {
  const getIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case "communication":
        return MessageSquare;
      case "cloud services":
        return Cloud;
      case "ai providers":
        return Cpu;
      case "development tools":
        return Code;
      case "databases":
        return Database;
      case "storage providers":
        return HardDrive;
      case "knowledge hubs":
        return BookOpen;
      case "identity & sso":
        return Key;
      default:
        return Layers;
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
      {integrationCategories.map((cat, index) => {
        const Icon = getIcon(cat.name);
        const isDegraded = cat.health < 80;

        return (
          <motion.div
            key={cat.name}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.04 }}
            whileHover={variants.cardHover}
            className="flex flex-col justify-between rounded-[20px] border border-[#E5E7EB] bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200"
          >
            {/* Header */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#F8FAFC] border border-[#E5E7EB] text-[#6B7280]">
                <Icon className="h-4 w-4" />
              </div>
              <span className="text-xs font-extrabold text-[#111827] truncate pr-1">
                {cat.name}
              </span>
            </div>

            {/* Stat Row */}
            <div className="mt-4 flex items-center justify-between text-xs">
              <span className="font-semibold text-[#6B7280]">Connected</span>
              <span className="font-extrabold text-[#111827]">{cat.connectedServices} services</span>
            </div>

            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="font-semibold text-[#6B7280]">Health Score</span>
              <span className={`font-bold ${isDegraded ? "text-amber-600" : "text-[#2F9F77]"}`}>
                {cat.health}%
              </span>
            </div>

            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="font-semibold text-[#6B7280]">Traffic</span>
              <span className="font-bold text-[#111827]">{cat.traffic}</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
