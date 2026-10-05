// Root layout of the customer app (TSD-010).

import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Calvino · Tu espacio de decisión",
  description:
    "Calvino convierte tus decisiones bancarias en pasos claros, verificables y humanos.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
