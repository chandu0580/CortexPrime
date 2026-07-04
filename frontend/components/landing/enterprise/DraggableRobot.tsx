"use client";

import { useState } from "react";
import { motion } from "framer-motion";

import { RobotIllustration } from "@/components/landing/enterprise/illustrations";

export function DraggableRobot() {
  const [isDragging, setIsDragging] = useState(false);
  const [hasEverDragged, setHasEverDragged] = useState(false);

  return (
    <motion.div
      drag
      dragMomentum={false}
      dragElastic={0}
      onDragStart={() => {
        setIsDragging(true);
        setHasEverDragged(true);
      }}
      onDragEnd={() => setIsDragging(false)}
      /* Slightly bounce when dropped */
      whileDrag={{ scale: 1.08, rotate: 3, zIndex: 999 }}
      whileTap={{ scale: 1.04 }}
      className="fixed bottom-[80px] right-[48px] z-50 hidden select-none xl:block"
      style={{
        cursor: isDragging ? "grabbing" : "grab",
        touchAction: "none",
      }}
    >
      <div className="relative">

        {/* "Drag me" tooltip — shown until user drags once */}
        {!hasEverDragged && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 1.8, duration: 0.4, ease: "easeOut" }}
            className="pointer-events-none absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-[#111827]/85 px-3 py-1.5 text-[0.65rem] font-semibold tracking-wide text-white shadow-lg backdrop-blur-sm"
          >
            ✦ Drag me anywhere
            {/* Small arrow pointing down */}
            <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#111827]/85" />
          </motion.div>
        )}

        {/* Glow ring when dragging */}
        {isDragging && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute inset-0 -z-10 rounded-full bg-[#38B88A]/20 blur-2xl"
          />
        )}

        <RobotIllustration />
      </div>
    </motion.div>
  );
}
