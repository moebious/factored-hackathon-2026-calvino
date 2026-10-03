// Root layout of the minimal demo frontend (TSD-003).

import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Calvino demo",
  description:
    "Project Calvino: calibrated fast decisions, a deterministic policy, humans in the loop.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
