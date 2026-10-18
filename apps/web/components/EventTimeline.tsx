'use client';

import React from 'react';
import { Clock, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react';

interface SOEEventItem {
  event_id: string;
  timestamp: string;
  offset_ms: number;
  source_device: string;
  event_type: string;
  channel_or_function: string;
  description: string;
  value?: any;
}

interface EventTimelineProps {
  events: SOEEventItem[];
  synchronizationStatus?: string;
  totalDurationMs?: number;
}

export default function EventTimeline({ events = [], synchronizationStatus = 'SYNCHRONIZED', totalDurationMs }: EventTimelineProps) {
  return (
    <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-grid-border">
        <div className="flex items-center space-x-2">
          <Clock className="w-4 h-4 text-grid-amber" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Deterministic Sequence of Events (SOE) Timeline
          </h2>
        </div>
        <div className="flex items-center space-x-3 text-xs font-mono">
          <span className="text-grid-muted">Sync Status:</span>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              synchronizationStatus === 'SYNCHRONIZED'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
            }`}
          >
            {synchronizationStatus}
          </span>
        </div>
      </div>

      <div className="space-y-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-grid-border">
        {events.length === 0 ? (
          <div className="text-center py-6 text-sm text-grid-muted font-mono">
            No sequence-of-events records available.
          </div>
        ) : (
          events.map((ev, i) => {
            const isTrip = ev.event_type.includes('TRIP') || ev.event_type.includes('OPEN');
            const isPickup = ev.event_type.includes('PICKUP');

            return (
              <div key={ev.event_id || i} className="relative pl-8 group">
                <span
                  className={`absolute left-1.5 top-1.5 w-3.5 h-3.5 rounded-full border-2 transform -translate-x-1/2 transition-transform group-hover:scale-125 ${
                    isTrip
                      ? 'bg-rose-500 border-rose-300 shadow-[0_0_8px_rgba(244,63,94,0.6)]'
                      : isPickup
                      ? 'bg-amber-400 border-amber-200 shadow-[0_0_8px_rgba(251,191,36,0.5)]'
                      : 'bg-grid-surface border-cyan-400'
                  }`}
                />

                <div className="bg-grid-surface border border-grid-border rounded p-3 hover:border-grid-cyan/40 transition-colors">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs text-grid-cyan font-bold">
                        {ev.timestamp}
                      </span>
                      <span className="text-[10px] font-mono bg-grid-card px-1.5 py-0.5 rounded text-grid-muted border border-grid-border">
                        +{ev.offset_ms.toFixed(1)} ms
                      </span>
                      <span className="text-xs font-semibold text-white">
                        [{ev.source_device}]
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                        isTrip
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : isPickup
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/20'
                      }`}
                    >
                      {ev.event_type}
                    </span>
                  </div>

                  <p className="text-xs text-grid-text mt-1.5">
                    {ev.description}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
