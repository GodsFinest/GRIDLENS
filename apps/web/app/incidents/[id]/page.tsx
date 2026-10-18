'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Activity, Clock, ShieldAlert, Cpu, ArrowLeft, CheckCircle2, FileText, Wrench } from 'lucide-react';
import WaveformViewer from '@/components/WaveformViewer';
import EventTimeline from '@/components/EventTimeline';
import { fetchIncident, fetchComtrade } from '@/lib/api';

const FEEDER_NAME_MAP: Record<string, string> = {
  F12: '(11 kV North Industrial Feeder)',
  F13: '(11 kV South Commercial Feeder)',
};

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const incidentId = (params?.id as string) || 'INC-2026-001';

  const [incident, setIncident] = useState<any>(null);
  const [comtrade, setComtrade] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const incData = await fetchIncident(incidentId);
        setIncident(incData);

        const cData = await fetchComtrade(incidentId);
        setComtrade(cData);
      } catch (err: any) {
        setError(err.message || 'Failed to load incident oscillography.');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [incidentId]);

  if (loading) {
    return (
      <div className="py-20 text-center text-sm font-mono text-grid-cyan animate-pulse">
        Fetching COMTRADE oscillography waveforms and SOE logs for {incidentId}...
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="bg-rose-950/30 border border-rose-800/40 p-6 rounded-lg text-center space-y-3">
        <div className="text-rose-400 font-bold font-mono">Failed to load incident record: {error}</div>
        <Link href="/" className="inline-block text-xs font-mono text-grid-cyan hover:underline">
          &larr; Return to Grid Overview
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="text-xs font-mono text-grid-muted hover:text-grid-cyan flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Grid Overview
        </Link>
        <div className="text-xs font-mono text-grid-muted">
          Substation: <span className="text-white font-bold">OGS-01</span> • Bay: <span className="text-grid-cyan font-bold">{incident.bay_id}</span>
        </div>
      </div>

      <div className="bg-grid-card border border-grid-border p-6 rounded-xl shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
              {incident.severity} SEVERITY
            </span>
            <span className="font-mono text-xs text-grid-muted">
              {incident.incident_id}
            </span>
            <span className="font-mono text-xs text-grid-muted">
              • {incident.timestamp}
            </span>
          </div>

          <h1 className="text-xl font-bold text-white mt-1.5">
            {incident.title}
          </h1>

          <p className="text-xs text-grid-muted font-mono mt-1">
            Apparent SCADA Text: <span className="text-amber-300">{incident.apparent_cause_text}</span>
          </p>
        </div>

        <Link
          href={`/investigate?incidentId=${incident.incident_id}`}
          className="flex items-center gap-2 bg-grid-cyan text-slate-950 font-bold px-4 py-2.5 rounded-lg hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(0,240,255,0.3)] text-xs font-mono"
        >
          <Cpu className="w-4 h-4" />
          START AGENT INVESTIGATION &rarr;
        </Link>
      </div>

      {comtrade && (
        <WaveformViewer
          incidentId={incident.incident_id}
          timeSeries={comtrade.time_series}
          measurements={comtrade.measurements}
          isTruncated={comtrade.is_truncated}
          bayLabel={`Bay ${incident.feeder_id}`}
          faultPhase={
            comtrade?.measurements?.fault_phase ?? comtrade?.measurements?.fault_phase_detected
          }
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <EventTimeline
            events={incident.events}
            synchronizationStatus={comtrade?.measurements?.synchronization_status || 'SYNCHRONIZED'}
          />
        </div>

        <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 pb-3 border-b border-grid-border">
            <Wrench className="w-4 h-4 text-grid-cyan" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
              Bay Protection Apparatus
            </h2>
          </div>

          <div className="space-y-3 text-xs font-mono">
            <div className="bg-grid-surface p-3 rounded border border-grid-border">
              <span className="text-grid-muted block text-[10px]">PROTECTED FEEDER</span>
              <span className="text-white font-bold">{incident.feeder_id}</span>{' '}
              {FEEDER_NAME_MAP[incident.feeder_id] ?? ''}
            </div>

            <div className="bg-grid-surface p-3 rounded border border-grid-border">
              <span className="text-grid-muted block text-[10px]">PRIMARY PROTECTION RELAY</span>
              <span className="text-grid-cyan font-bold">{incident.involved_relay_id}</span> (SIPROTEC 5 7SJ85)
            </div>

            <div className="bg-grid-surface p-3 rounded border border-grid-border">
              <span className="text-grid-muted block text-[10px]">CONTROLLED BREAKER</span>
              <span className="text-emerald-400 font-bold">{incident.involved_breaker_id}</span> (Vacuum Breaker 2000A)
            </div>

            <div className="bg-grid-surface p-3 rounded border border-grid-border">
              <span className="text-grid-muted block text-[10px]">BAY CONTROLLER IED</span>
              <span className="text-white font-bold">{incident.involved_ied_id}</span>
            </div>

            <div className="pt-2">
              <Link
                href="/validation"
                className="block text-center py-2 rounded bg-grid-surface hover:bg-slate-800 text-grid-cyan border border-grid-border text-xs transition-colors font-sans"
              >
                Inspect Secondary Wiring Configuration &rarr;
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
