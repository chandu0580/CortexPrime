import { Inter } from "next/font/google";

import CortexPrimeLandingPage from "@/components/landing/enterprise/CortexPrimeLandingPage";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export default function LandingPage() {
  return (
    <main className={inter.className}>
      <CortexPrimeLandingPage />
    </main>
  );
}
