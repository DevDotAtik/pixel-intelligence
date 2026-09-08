import type { Metadata } from "next";
import type { ReactNode } from "react";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";

const grotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-grotesk",
});

const jbmono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jbmono",
});

export const metadata: Metadata = {
  title: "Pixel Intelligence — AI Video Analytics Command Platform · SIH 187",
  description:
    "AI-based intelligent video analytics for border surveillance: real-time YOLO detection, tracking, counting and analytics over existing CCTV infrastructure. Smart India Hackathon problem statement 187 prototype.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${grotesk.variable} ${jbmono.variable}`}>
      <body className="bg-ink text-pale font-display min-h-screen">
        <SiteNav />
        {children}
        <div className="noise-layer" aria-hidden />
      </body>
    </html>
  );
}
