import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Local Workspace | Firm AI",
  description: "Local business agent workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}