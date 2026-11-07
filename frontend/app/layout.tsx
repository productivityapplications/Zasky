import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Zasky · Owner Dashboard",
  description:
    "A private owner dashboard for today's plan, the task pool and reconciliation history.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
