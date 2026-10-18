'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Activity, Clock, ZoomIn, ZoomOut, RotateCcw, AlertCircle } from 'lucide-react';

interface WaveformPoint {
  time_ms: number;
  IA?: number;
  IB?: number;
  IC?: number;
  VA?: number;
  '50P_PKP'?: number;
  '51P_TRIP'?: number;
  '52A_BRK'?: number;
  [key: string]: any;
}

interface WaveformViewerProps {
  incidentId: string;
  timeSeries: WaveformPoint[];
  measurements?: any;
  isTruncated?: boolean;
  faultPhase?: string;
  bayLabel?: string;
}

export default function WaveformViewer({
  incidentId,
  timeSeries = [],
  measurements,
  isTruncated,
  faultPhase,
  bayLabel = 'Bay F12',
}: WaveformViewerProps) {
  // Drive channel emphasis from the incident's measured fault phase instead of
  // a hardcoded Phase-C. Explicit prop wins, then the measurements payload
  // (supports both `fault_phase` and `fault_phase_detected` keys), falling
  // back to 'C' only to preserve the Incident A default rendering.
  const rawPhase: unknown =
    faultPhase ?? measurements?.fault_phase ?? measurements?.fault_phase_detected ?? 'C';
  const faultPhaseChar: 'A' | 'B' | 'C' =
    typeof rawPhase === 'string' && /^[ABCabc]$/.test(rawPhase.trim())
      ? (rawPhase.trim().toUpperCase() as 'A' | 'B' | 'C')
      : 'C';
  const emphasizedKey = `I${faultPhaseChar}`;
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [selectedChannels, setSelectedChannels] = useState<{ [key: string]: boolean }>({
    IA: true,
    IB: true,
    IC: true,
    VA: false,
    '50P_PKP': true,
    '51P_TRIP': true,
    '52A_BRK': true,
  });

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const toggleChannel = (ch: string) => {
    setSelectedChannels((prev) => ({ ...prev, [ch]: !prev[ch] }));
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || timeSeries.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#0F172A';
    ctx.fillRect(0, 0, width, height);

    // Draw Grid Lines
    ctx.strokeStyle = '#1E293B';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Zero-axis for Analog signals
    const analogMidY = height * 0.45;
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, analogMidY);
    ctx.lineTo(width, analogMidY);
    ctx.stroke();

    // Analog Channels Definition
    const channelsToDraw = [
      { key: 'IA', color: '#FACC15', label: 'IA (A)' }, // Gold
      { key: 'IB', color: '#38BDF8', label: 'IB (A)' }, // Sky
      { key: 'IC', color: '#F43F5E', label: 'IC (A)' }, // Rose / Fault Phase
      { key: 'VA', color: '#A855F7', label: 'VA (V)' }, // Purple
    ];

    // Dynamic Auto-scale calculation
    let maxVal = 100;
    channelsToDraw.forEach(({ key }) => {
      if (selectedChannels[key]) {
        for (const pt of timeSeries) {
          const v = Math.abs(pt[key] || 0);
          if (v > maxVal) maxVal = v;
        }
      }
    });
    maxVal = Math.ceil(maxVal * 1.15); // 15% headroom for clean peak visualization
    const yScale = (height * 0.38) / maxVal;
    const xScale = width / (timeSeries.length - 1);

    channelsToDraw.forEach(({ key, color }) => {
      if (!selectedChannels[key]) return;

      ctx.strokeStyle = color;
      ctx.lineWidth = key === emphasizedKey ? 2.5 : 1.5;
      ctx.beginPath();

      timeSeries.forEach((pt, i) => {
        const val = pt[key] || 0;
        const x = i * xScale;
        const y = analogMidY - val * yScale;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });

    // Plot Digital Channels in Lower 25% Section
    const digitalBaseY = height * 0.78;
    const digChannels = [
      { key: '50P_PKP', color: '#F59E0B', offset: 0, label: '50P PKP' },
      { key: '51P_TRIP', color: '#EF4444', offset: 22, label: '51P TRIP' },
      { key: '52A_BRK', color: '#10B981', offset: 44, label: '52A BRK' },
    ];

    digChannels.forEach(({ key, color, offset }) => {
      if (!selectedChannels[key]) return;

      const yLow = digitalBaseY + offset + 12;
      const yHigh = digitalBaseY + offset;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      timeSeries.forEach((pt, i) => {
        const bit = pt[key] || 0;
        const x = i * xScale;
        const y = bit === 1 ? yHigh : yLow;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Label
      ctx.fillStyle = color;
      ctx.font = '10px monospace';
      ctx.fillText(key, 8, yHigh - 2);
    });

    // Draw Cursor Line if hovered
    if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < timeSeries.length) {
      const curX = hoverIndex * xScale;
      ctx.strokeStyle = '#00F0FF';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 2]);
      ctx.beginPath();
      ctx.moveTo(curX, 0);
      ctx.lineTo(curX, height);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [timeSeries, selectedChannels, hoverIndex, emphasizedKey]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || timeSeries.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = Math.min(timeSeries.length - 1, Math.max(0, Math.round((x / rect.width) * (timeSeries.length - 1))));
    setHoverIndex(idx);
  };

  const hoveredData = hoverIndex !== null ? timeSeries[hoverIndex] : timeSeries[timeSeries.length - 1];

  return (
    <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-grid-border">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-grid-cyan" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Replay: {incidentId} Disturbance Oscillography (OGS-01 {bayLabel})
          </h2>
          {isTruncated && (
            <span className="flex items-center gap-1 text-[11px] bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded font-mono border border-rose-500/30">
              <AlertCircle className="w-3 h-3" /> TRUNCATED RECORDING
            </span>
          )}
        </div>

        <div className="flex items-center flex-wrap gap-2 text-xs font-mono">
          <button
            onClick={() => toggleChannel('IA')}
            className={`px-2 py-0.5 rounded border text-[11px] transition-colors ${
              emphasizedKey === 'IA' ? 'font-bold ' : ''
            }${
              selectedChannels.IA
                ? emphasizedKey === 'IA'
                  ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50 shadow-[0_0_8px_rgba(250,204,21,0.3)]'
                  : 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50'
                : 'bg-grid-surface text-gray-500 border-grid-border'
            }`}
          >
            {emphasizedKey === 'IA' ? 'Ia (Phase A)' : 'Ia (Yellow)'}
          </button>
          <button
            onClick={() => toggleChannel('IB')}
            className={`px-2 py-0.5 rounded border text-[11px] transition-colors ${
              emphasizedKey === 'IB' ? 'font-bold ' : ''
            }${
              selectedChannels.IB
                ? emphasizedKey === 'IB'
                  ? 'bg-sky-500/20 text-sky-300 border-sky-500/50 shadow-[0_0_8px_rgba(56,189,248,0.3)]'
                  : 'bg-sky-500/20 text-sky-300 border-sky-500/50'
                : 'bg-grid-surface text-gray-500 border-grid-border'
            }`}
          >
            {emphasizedKey === 'IB' ? 'Ib (Phase B)' : 'Ib (Sky)'}
          </button>
          <button
            onClick={() => toggleChannel('IC')}
            className={`px-2 py-0.5 rounded border text-[11px] transition-colors ${
              emphasizedKey === 'IC' ? 'font-bold ' : ''
            }${
              selectedChannels.IC
                ? emphasizedKey === 'IC'
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-[0_0_8px_rgba(244,63,94,0.3)]'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/50'
                : 'bg-grid-surface text-gray-500 border-grid-border'
            }`}
          >
            {emphasizedKey === 'IC' ? 'Ic (Phase C)' : 'Ic (Rose)'}
          </button>
          <button
            onClick={() => toggleChannel('VA')}
            className={`px-2 py-0.5 rounded border text-[11px] transition-colors ${
              selectedChannels.VA ? 'bg-purple-500/20 text-purple-300 border-purple-500/50' : 'bg-grid-surface text-gray-500 border-grid-border'
            }`}
          >
            Va (Voltage)
          </button>
        </div>
      </div>

      <div className="relative w-full bg-slate-950 rounded border border-grid-border overflow-hidden">
        <canvas
          ref={canvasRef}
          width={800}
          height={320}
          className="w-full h-auto cursor-crosshair block"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
        />
      </div>

      {hoveredData && (
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 text-xs font-mono bg-grid-surface p-3 rounded border border-grid-border">
          <div>
            <span className="text-grid-muted block text-[10px]">TIME:</span>
            <span className="text-grid-cyan font-bold">{hoveredData.time_ms ?? 0} ms</span>
          </div>
          <div>
            <span className="text-yellow-400 block text-[10px]">
              {emphasizedKey === 'IA' ? 'IA (PHASE A CURRENT):' : 'IA (CURRENT):'}
            </span>
            <span className={emphasizedKey === 'IA' ? 'text-yellow-300 font-bold' : 'text-white'}>
              {hoveredData.IA ?? 0} A
            </span>
          </div>
          <div>
            <span className="text-sky-400 block text-[10px]">
              {emphasizedKey === 'IB' ? 'IB (PHASE B CURRENT):' : 'IB (CURRENT):'}
            </span>
            <span className={emphasizedKey === 'IB' ? 'text-sky-300 font-bold' : 'text-white'}>
              {hoveredData.IB ?? 0} A
            </span>
          </div>
          <div>
            <span className="text-rose-400 block text-[10px]">
              {emphasizedKey === 'IC' ? 'IC (PHASE C CURRENT):' : 'IC (CURRENT):'}
            </span>
            <span className={emphasizedKey === 'IC' ? 'text-rose-400 font-bold' : 'text-white'}>
              {hoveredData.IC ?? 0} A
            </span>
          </div>
          <div>
            <span className="text-amber-400 block text-[10px]">50P_PKP BIT:</span>
            <span className={hoveredData['50P_PKP'] === 1 ? 'text-amber-400 font-bold' : 'text-gray-500'}>
              {hoveredData['50P_PKP'] ?? 0}
            </span>
          </div>
          <div>
            <span className="text-emerald-400 block text-[10px]">52A (BREAKER):</span>
            <span className={hoveredData['52A_BRK'] === 1 ? 'text-emerald-400' : 'text-rose-400 font-bold'}>
              {hoveredData['52A_BRK'] === 1 ? 'CLOSED (1)' : 'OPENED (0)'}
            </span>
          </div>
        </div>
      )}

      {measurements && measurements.analog_measurements && (
        <div className="mt-3 pt-3 border-t border-grid-border flex flex-wrap items-center justify-between text-xs text-grid-muted font-mono">
          <div>
            Fault Phase Detected:{' '}
            <span className="text-rose-400 font-bold">
              {measurements.fault_phase ?? measurements.fault_phase_detected ?? faultPhaseChar ?? 'N/A'}
            </span>
          </div>
          <div>
            Peak Current:{' '}
            <span className="text-white font-bold">
              {measurements.analog_measurements?.[emphasizedKey]?.peak_value ||
                measurements.analog_measurements?.IC?.peak_value ||
                measurements.analog_measurements?.IB?.peak_value ||
                measurements.analog_measurements?.IA?.peak_value ||
                'N/A'}{' '}
              A
            </span>
          </div>
          <div>
            Clearing Duration ($\Delta t$):{' '}
            <span className="text-grid-cyan font-bold">{measurements.total_clearing_time_ms || 'N/A'} ms</span>
          </div>
        </div>
      )}
    </div>
  );
}
