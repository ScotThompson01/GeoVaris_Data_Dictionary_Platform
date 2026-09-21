
import "./globals.css";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "GeoVaris Data Dictionary Platform",
  description: "Clean data. Confident results.",
  icons: {
    icon: "/branding/data-dictionary-icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}