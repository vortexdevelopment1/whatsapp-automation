import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/shared/Navbar";

export const metadata: Metadata = {
  title: "Rental Operations — Admin Console",
  description: "Authorized Agent Profile, Branding & WhatsApp Setup",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
