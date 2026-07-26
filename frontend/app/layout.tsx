import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar, Header } from "@/components/LayoutComponents";
import { BackgroundCarousel } from "@/components/BackgroundCarousel";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "StarkX QuantEdge",
  description: "AI Crypto & Forex Confluence Engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} dark`}>
      <body className="font-sans antialiased text-white selection:bg-[#00d4ff]/30 selection:text-white bg-transparent">
        <BackgroundCarousel />
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col ml-64 overflow-hidden relative">
            <Header />
            <main className="flex-1 overflow-y-auto overflow-x-hidden p-8 pb-20">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
