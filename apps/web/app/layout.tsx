import type { Metadata } from 'next';
import './globals.css';
import Navbar from '@/components/Navbar';

export const metadata: Metadata = {
  title: 'GridLens — Power-System Event Investigation',
  description: 'Source-linked analysis of substation protection events.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col bg-grid-bg text-grid-text selection:bg-grid-cyan selection:text-slate-900">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto p-6">
          {children}
        </main>
        <footer className="border-t border-grid-border py-4 px-6 text-center text-xs text-grid-muted font-mono bg-grid-surface">
          GridLens • Orion Grid Substation OGS-01 • Seeded local dataset
        </footer>
      </body>
    </html>
  );
}
