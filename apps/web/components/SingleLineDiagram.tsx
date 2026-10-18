'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, CheckCircle, Info, Zap } from 'lucide-react';

interface SingleLineDiagramProps {
  activeFeeder?: string;
  onSelectEquipment?: (equipmentId: string) => void;
}

export default function SingleLineDiagram({ activeFeeder = 'F12', onSelectEquipment }: SingleLineDiagramProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(activeFeeder);

  const handleNodeClick = (nodeId: string) => {
    setSelectedNode(nodeId);
    if (onSelectEquipment) onSelectEquipment(nodeId);
  };

  return (
    <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between mb-4 border-b border-grid-border pb-3">
        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-grid-cyan" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Substation OGS-01 • Single-Line Topology Diagram
          </h2>
        </div>
        <div className="flex items-center space-x-4 text-xs font-mono">
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-1 bg-cyan-400 rounded-full inline-block"></span>
            <span className="text-grid-muted">33 kV Bus A</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-1 bg-amber-400 rounded-full inline-block"></span>
            <span className="text-grid-muted">11 kV Bus B</span>
          </div>
        </div>
      </div>

      <div className="w-full flex justify-center py-2">
        <svg viewBox="0 0 740 380" className="w-full max-w-3xl h-auto select-none">
          <defs>
            <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="glow-rose" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          <line x1="370" y1="20" x2="370" y2="50" stroke="#00F0FF" strokeWidth="2.5" />
          <text x="370" y="15" fill="#00F0FF" fontSize="11" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
            GRID INFEED (33 kV)
          </text>

          <line x1="180" y1="50" x2="560" y2="50" stroke="#00F0FF" strokeWidth="4" filter="url(#glow-cyan)" />
          <text x="575" y="54" fill="#00F0FF" fontSize="11" fontFamily="monospace">
            BUS A (33 kV)
          </text>

          <line x1="370" y1="50" x2="370" y2="100" stroke="#00F0FF" strokeWidth="2" />

          <g
            className="cursor-pointer transition-transform hover:scale-105"
            onClick={() => handleNodeClick('T1')}
          >
            <circle cx="370" cy="115" r="18" fill="#111827" stroke="#00F0FF" strokeWidth="2.5" />
            <circle cx="370" cy="135" r="18" fill="#111827" stroke="#FFB800" strokeWidth="2.5" />
            <text x="405" y="130" fill="#F3F4F6" fontSize="11" fontFamily="monospace" fontWeight="bold">
              T1 (25 MVA)
            </text>
            <text x="405" y="145" fill="#9CA3AF" fontSize="9" fontFamily="monospace">
              Dyn11 • 8.5% Z
            </text>
          </g>

          <line x1="370" y1="153" x2="370" y2="190" stroke="#FFB800" strokeWidth="2.5" />

          <line x1="100" y1="190" x2="640" y2="190" stroke="#FFB800" strokeWidth="4" />
          <text x="655" y="194" fill="#FFB800" fontSize="11" fontFamily="monospace">
            BUS B (11 kV)
          </text>

          <g className="cursor-pointer" onClick={() => handleNodeClick('F12')}>
            <line x1="220" y1="190" x2="220" y2="230" stroke="#FFB800" strokeWidth="2" />

            <rect
              x="205"
              y="230"
              width="30"
              height="30"
              fill={activeFeeder === 'F12' ? '#3B1D28' : '#111827'}
              stroke={activeFeeder === 'F12' ? '#F43F5E' : '#10B981'}
              strokeWidth="2.5"
              rx="4"
              filter={activeFeeder === 'F12' ? 'url(#glow-rose)' : undefined}
            />
            <text x="220" y="250" fill="#FFF" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              CB12
            </text>

            <line x1="220" y1="260" x2="220" y2="285" stroke="#9CA3AF" strokeWidth="2" strokeDasharray="3 2" />
            <circle cx="220" cy="285" r="7" fill="#111827" stroke="#00F0FF" strokeWidth="1.5" />
            <text x="175" y="289" fill="#00F0FF" fontSize="9" fontFamily="monospace">
              CT12(A,B,C)
            </text>

            <line x1="220" y1="292" x2="220" y2="340" stroke="#F43F5E" strokeWidth="3" />
            <polygon points="215,340 225,340 220,352" fill="#F43F5E" />

            <rect x="145" y="325" width="60" height="20" fill="#1F2937" rx="3" stroke="#374151" />
            <text x="175" y="339" fill="#FFF" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              BAY F12
            </text>
            <text x="175" y="362" fill="#F43F5E" fontSize="9" textAnchor="middle" fontFamily="monospace">
              TRIPPED (14:32)
            </text>
          </g>

          <g
            className="cursor-pointer"
            onClick={() => handleNodeClick('RELAY_12')}
          >
            <rect x="70" y="235" width="105" height="42" fill="#111827" stroke="#00F0FF" strokeWidth="1.5" rx="4" />
            <text x="122" y="252" fill="#00F0FF" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              RELAY_12 (7SJ85)
            </text>
            <text x="122" y="267" fill="#9CA3AF" fontSize="7" textAnchor="middle" fontFamily="monospace">
              ANSI 50/51/50N/51N/27/59
            </text>
            <line x1="175" y1="245" x2="205" y2="245" stroke="#F43F5E" strokeWidth="1.5" strokeDasharray="2 2" />
          </g>

          <g className="cursor-pointer" onClick={() => handleNodeClick('F13')}>
            <line x1="520" y1="190" x2="520" y2="230" stroke="#FFB800" strokeWidth="2" />

            <rect
              x="505"
              y="230"
              width="30"
              height="30"
              fill="#111827"
              stroke="#10B981"
              strokeWidth="2.5"
              rx="4"
            />
            <text x="520" y="250" fill="#FFF" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              CB13
            </text>

            <line x1="520" y1="260" x2="520" y2="285" stroke="#9CA3AF" strokeWidth="2" strokeDasharray="3 2" />
            <circle cx="520" cy="285" r="7" fill="#111827" stroke="#00F0FF" strokeWidth="1.5" />
            <text x="535" y="289" fill="#00F0FF" fontSize="9" fontFamily="monospace">
              CT13(A,B,C)
            </text>

            <line x1="520" y1="292" x2="520" y2="340" stroke="#10B981" strokeWidth="2.5" />
            <polygon points="515,340 525,340 520,352" fill="#10B981" />

            <rect x="535" y="325" width="60" height="20" fill="#1F2937" rx="3" stroke="#374151" />
            <text x="565" y="339" fill="#FFF" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              BAY F13
            </text>
            <text x="565" y="362" fill="#10B981" fontSize="9" textAnchor="middle" fontFamily="monospace">
              NORMAL LOAD
            </text>
          </g>

          <g className="cursor-pointer" onClick={() => handleNodeClick('RELAY_13')}>
            <rect x="565" y="235" width="105" height="42" fill="#111827" stroke="#374151" strokeWidth="1.5" rx="4" />
            <text x="617" y="252" fill="#E5E7EB" fontSize="10" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
              RELAY_13 (7SJ85)
            </text>
            <text x="617" y="267" fill="#9CA3AF" fontSize="8" textAnchor="middle" fontFamily="monospace">
              ANSI 50/51/50N/51N
            </text>
            <line x1="535" y1="245" x2="565" y2="245" stroke="#10B981" strokeWidth="1.5" strokeDasharray="2 2" />
          </g>
        </svg>
      </div>

      <div className="mt-2 pt-3 border-t border-grid-border flex items-center justify-between text-xs text-grid-muted font-mono">
        <div>
          Selected Entity: <span className="text-grid-cyan font-bold">{selectedNode || 'Feeder F12'}</span>
        </div>
        <Link
          href={`/investigate?feeder=${selectedNode || 'F12'}`}
          className="text-grid-cyan hover:underline flex items-center gap-1 font-sans"
        >
          Launch Agent Investigation &rarr;
        </Link>
      </div>
    </div>
  );
}
