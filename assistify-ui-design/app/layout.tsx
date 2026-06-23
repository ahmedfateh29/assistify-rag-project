import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Assistify",
  description: "Assistify AI assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="bg-[#232323]">
      <body>{children}</body>
    </html>
  );
}
