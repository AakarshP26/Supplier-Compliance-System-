import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { CopilotSidebar } from "@/components/CopilotSidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Supplier Compliance System",
  description: "AI-Powered Supplier Risk Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.className} bg-[#0A0A0A] text-foreground min-h-screen flex flex-col`}>
        <div className="flex flex-1 h-screen overflow-hidden">
          {/* Sidebar Nav */}
          <div className="w-64 border-r border-white/5 bg-[#050505] p-6 flex flex-col z-20">
            <h1 className="text-xl font-bold bg-gradient-to-br from-white to-white/40 bg-clip-text text-transparent mb-12">
              Risk Center
            </h1>
            <nav className="space-y-1 flex-1">
              <div className="text-xs font-semibold text-white/30 uppercase tracking-wider mb-4 px-2">Dashboards</div>
              <Link href="/" className="block px-4 py-2.5 rounded-lg hover:bg-white/5 text-sm font-medium text-white/70 hover:text-white transition-colors">Overview</Link>
              <Link href="/suppliers" className="block px-4 py-2.5 rounded-lg hover:bg-white/5 text-sm font-medium text-white/70 hover:text-white transition-colors">Suppliers</Link>
              <div className="mt-8 mb-4 px-2 text-xs font-semibold text-white/30 uppercase tracking-wider">Analysis</div>
              <Link href="/lab" className="block px-4 py-2.5 rounded-lg hover:bg-white/5 text-sm font-medium text-white/70 hover:text-white transition-colors">Adversarial Lab</Link>
            </nav>
          </div>
          
          {/* Main Content Area */}
          <main className="flex-1 overflow-y-auto relative bg-[#0A0A0A]">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#0A0A0A] to-[#0A0A0A] pointer-events-none" />
            <div className="relative z-10 h-full">
              {children}
            </div>
          </main>

          {/* Global Copilot Sidebar */}
          <div className="h-full z-20">
            <CopilotSidebar />
          </div>
        </div>
      </body>
    </html>
  );
}
