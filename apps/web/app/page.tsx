'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowRight, Cpu, RefreshCw } from 'lucide-react';
import SingleLineDiagram from '@/components/SingleLineDiagram';
import { fetchIncidents } from '@/lib/api';

export default function GridOverviewPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadIncidents = async () => {
    setLoading(true);
    try {
      const data = await fetchIncidents();
      setIncidents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-grid-card via-grid-surface to-cyan-950/20 p-6 rounded-xl border border-grid-border shadow-2xl">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-grid-cyan uppercase tracking-widest mb-1">
            <span className="w-2 h-2 rounded-full bg-grid-cyan"></span>
            <span>Seeded OGS-01 Substation Dataset</span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">
            Orion Grid Substation <span className="text-grid-cyan">OGS-01</span>
          </h1>
          <p className="text-sm text-grid-muted mt-1 max-w-2xl">
            Protection event analysis using COMTRADE records, equipment topology,
            validation rules, and source-linked findings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/investigate?incidentId=INC-2026-001"
            className="flex items-center gap-2 bg-grid-cyan text-slate-950 font-bold px-4 py-2.5 rounded-lg hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(0,240,255,0.3)] text-xs font-mono"
          >
            <Cpu className="w-4 h-4" />
            INVESTIGATE F12 TRIP
          </Link>
        </div>
      </div>

      <div className="space-y-1">
        <div className="text-[10px] font-mono text-grid-muted uppercase tracking-wider px-1">
          Reference values from the seeded dataset — not live telemetry
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono">
          <div className="bg-grid-card border border-grid-border p-4 rounded-lg shadow">
            <div className="text-[11px] text-grid-muted uppercase">Grid Frequency</div>
            <div className="text-xl font-bold text-emerald-400 mt-1">50.02 Hz</div>
            <div className="text-[10px] text-grid-muted mt-1">Seeded nominal value (±0.05 Hz)</div>
          </div>

          <div className="bg-grid-card border border-grid-border p-4 rounded-lg shadow">
            <div className="text-[11px] text-grid-muted uppercase">33 kV Bus A Voltage</div>
            <div className="text-xl font-bold text-grid-cyan mt-1">33.12 kV</div>
            <div className="text-[10px] text-grid-muted mt-1">Seeded nominal value (Primary)</div>
          </div>

          <div className="bg-grid-card border border-grid-border p-4 rounded-lg shadow">
            <div className="text-[11px] text-grid-muted uppercase">11 kV Bus B Voltage</div>
            <div className="text-xl font-bold text-grid-amber mt-1">10.94 kV</div>
            <div className="text-[10px] text-grid-muted mt-1">Seeded nominal value (Secondary)</div>
          </div>

          <div className="bg-grid-card border border-grid-border p-4 rounded-lg shadow">
            <div className="text-[11px] text-grid-muted uppercase">Substation Active Load</div>
            <div className="text-xl font-bold text-white mt-1">18.45 MW</div>
            <div className="text-[10px] text-emerald-400 mt-1">Seeded nominal value (73.8%)</div>
          </div>
        </div>
      </div>

      <SingleLineDiagram activeFeeder="F12" />

      <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-grid-border">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-grid-amber" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
              Protection Incidents
            </h2>
          </div>
          <button
            onClick={loadIncidents}
            className="flex items-center gap-1.5 text-xs text-grid-cyan font-mono hover:underline"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>

        {loading ? (
          <div className="py-8 text-center text-xs font-mono text-grid-muted animate-pulse">
            Loading incident database...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-grid-surface text-grid-muted uppercase text-[10px] border-b border-grid-border">
                <tr>
                  <th className="py-2.5 px-3">Incident ID</th>
                  <th className="py-2.5 px-3">Title & Feeder</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Apparent Cause</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-grid-border">
                {incidents.map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-grid-surface transition-colors">
                    <td className="py-3 px-3 font-bold text-grid-cyan">
                      {inc.incident_id}
                    </td>
                    <td className="py-3 px-3 text-white font-sans font-semibold">
                      {inc.title}
                      <span className="block font-mono text-[10px] text-grid-muted font-normal">
                        Bay: {inc.bay_id} • Feeder: {inc.feeder_id}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-grid-muted">
                      {inc.timestamp}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          inc.severity === 'HIGH'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        {inc.severity}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-gray-300 max-w-xs truncate">
                      {inc.apparent_cause_text}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <Link
                        href={`/incidents/${inc.incident_id}`}
                        className="inline-block px-2.5 py-1 rounded bg-grid-surface hover:bg-slate-800 text-gray-300 border border-grid-border text-[11px] transition-colors"
                      >
                        Waveform & SOE
                      </Link>
                      <Link
                        href={`/investigate?incidentId=${inc.incident_id}`}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-grid-cyan border border-cyan-500/40 font-bold text-[11px] transition-all"
                      >
                        Investigate <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
