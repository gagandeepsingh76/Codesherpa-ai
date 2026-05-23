import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeSherpa AI",
  description: "Understand any repository in minutes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
