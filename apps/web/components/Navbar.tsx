'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, Shield, Cpu, CheckCircle2, Zap, BarChart3 } from 'lucide-react';

interface NavbarProps {
  currentRole?: string;
  onRoleChange?: (role: string) => void;
}

export default function Navbar({ currentRole = 'ENGINEER', onRoleChange }: NavbarProps) {
  const pathname = usePathname();

  const navItems = [
    { label: 'Grid Overview', href: '/', icon: Zap },
    { label: 'Investigation', href: '/investigate', icon: Cpu },
    { label: 'Config Validation', href: '/validation', icon: CheckCircle2 },
    { label: 'Evaluation & Ablations', href: '/evaluation', icon: BarChart3 },
  ];

  return (
    <nav className="bg-grid-surface border-b border-grid-border sticky top-0 z-50 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded bg-cyan-500/10 border border-grid-cyan/40 flex items-center justify-center text-grid-cyan font-bold text-lg shadow-[0_0_15px_rgba(0,240,255,0.2)]">
            <Activity className="w-5 h-5 text-grid-cyan" />
          </div>
          <div>
            <Link href="/" className="text-xl font-bold tracking-wider text-white flex items-center gap-2">
              GRID<span className="text-grid-cyan">LENS</span>
            </Link>
            <div className="text-[10px] text-grid-muted tracking-widest font-mono uppercase">
              Orion Substation OGS-01
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-grid-cyan/10 text-grid-cyan border border-grid-cyan/30 shadow-[0_0_10px_rgba(0,240,255,0.15)]'
                    : 'text-grid-muted hover:text-white hover:bg-grid-card'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-grid-card px-2.5 py-1 rounded border border-grid-border text-[11px] font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-grid-muted">DATA:</span>
            <span className="text-emerald-400 font-semibold">SEEDED</span>
          </div>

          <div className="flex items-center space-x-2">
            <Shield className="w-3.5 h-3.5 text-grid-amber" />
            <span className="text-xs text-grid-muted font-mono">Role:</span>
            <select
              value={currentRole}
              onChange={(e) => onRoleChange && onRoleChange(e.target.value)}
              className="bg-grid-card border border-grid-border text-white text-xs rounded px-2 py-1 font-mono focus:outline-none focus:border-grid-cyan"
            >
              <option value="VIEWER">VIEWER (Read-Only)</option>
              <option value="ENGINEER">ENGINEER (Investigate/Validate)</option>
              <option value="APPROVER">APPROVER (Simulated Control)</option>
            </select>
          </div>
        </div>
      </div>
    </nav>
  );
}
