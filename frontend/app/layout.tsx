// Root layout of the customer app (TSD-010).

import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Calvino",
  description:
    "Project Calvino: verified banking support. Calibrated fast decisions, a deterministic policy, cards from a fixed catalog, humans in the loop.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
