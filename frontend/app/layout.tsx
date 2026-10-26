import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "XAI-CVD | Cardiovascular Intelligence",
  description: "An explainable academic prototype for 10-year cardiovascular risk assessment and decision support.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f8fafb" };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
