'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Cpu,
  ShieldCheck,
  AlertCircle,
  FileCheck2,
  BookOpen,
  Send,
  Loader2,
  AlertTriangle,
  Lightbulb,
  GitBranch,
} from 'lucide-react';
import HypothesesMatrix from '@/components/HypothesesMatrix';
import ExecutionTraceView from '@/components/ExecutionTraceView';
import ProvenanceExplorer from '@/components/ProvenanceExplorer';
import { runInvestigation } from '@/lib/api';

function InvestigationContent() {
  const searchParams = useSearchParams();
  const initialIncident = searchParams.get('incidentId') || 'INC-2026-001';

  const [query, setQuery] = useState('Why did feeder F12 trip at 14:32?');
  const [selectedIncident, setSelectedIncident] = useState(initialIncident);
  const [role, setRole] = useState('ENGINEER');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const presetQueries = [
    {
      label: 'Incident A: F12 Genuine Trip',
      query: 'Why did feeder F12 trip at 14:32?',
      incidentId: 'INC-2026-001',
    },
    {
      label: 'Incident B: Deceptive CT Inversion',
      query: 'Investigate deceptive phase trip in incident B with conflicting relay flag and waveform.',
      incidentId: 'INC-2026-002',
    },
    {
      label: 'Incident C: Insufficient Evidence',
      query: 'Why did feeder F13 trip in incident INC-2026-003?',
      incidentId: 'INC-2026-003',
    },
    {
      label: 'Topology Lookup (Graph Only)',
      query: 'Which relay protects feeder F12?',
      incidentId: 'INC-2026-001',
    },
    {
      label: 'Protection QA (RAG Only)',
      query: 'What does ANSI 51 time overcurrent protection mean?',
      incidentId: 'INC-2026-001',
    },
  ];

  const handleSelectPreset = (preset: typeof presetQueries[0]) => {
    setQuery(preset.query);
    setSelectedIncident(preset.incidentId);
    handleExecuteInvestigation(preset.query, preset.incidentId);
  };

  const handleExecuteInvestigation = async (qText?: string, incId?: string) => {
    const activeQuery = qText || query;
    const activeInc = incId || selectedIncident;
    if (!activeQuery.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await runInvestigation(activeQuery, activeInc, role);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Investigation execution failed.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleExecuteInvestigation('Why did feeder F12 trip at 14:32?', initialIncident);
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-grid-card border border-grid-border p-6 rounded-xl shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-grid-cyan" />
            <h1 className="text-xl font-bold tracking-tight text-white">
              Protection Event Investigation
            </h1>
          </div>
          <div className="flex items-center space-x-2 font-mono text-xs">
            <span className="text-grid-muted">Active Substation:</span>
            <span className="text-grid-cyan font-bold">OGS-01</span>
          </div>
        </div>

        <p className="text-xs text-grid-muted max-w-3xl">
          Correlates COMTRADE records, topology, validation results, event timing,
          and local technical references.
        </p>

        <div className="mt-4 pt-3 border-t border-grid-border flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-mono text-grid-muted">Saved queries:</span>
          {presetQueries.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => handleSelectPreset(preset)}
              className="text-xs font-mono px-2.5 py-1 rounded bg-grid-surface hover:bg-slate-800 text-gray-300 border border-grid-border hover:border-grid-cyan transition-all"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-grid-card border border-grid-border p-4 rounded-lg shadow-xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleExecuteInvestigation();
          }}
          className="flex items-center gap-3"
        >
          <div className="relative flex-1">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask an investigation question (e.g., Why did feeder F12 trip at 14:32?)..."
              className="w-full bg-grid-surface border border-grid-border text-white text-sm rounded-lg px-4 py-3 focus:outline-none focus:border-grid-cyan font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 bg-grid-cyan text-slate-950 font-bold px-6 py-3 rounded-lg hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(0,240,255,0.3)] text-xs font-mono disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                INVESTIGATING...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                INVESTIGATE
              </>
            )}
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 p-4 rounded-lg text-rose-300 text-xs font-mono">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div
            className={`p-6 rounded-xl border shadow-2xl transition-all ${
              !result.is_sufficient
                ? 'bg-amber-950/20 border-amber-500/50'
                : result.conflict_lifecycle === 'CONFLICT_RESOLVED'
                ? 'bg-purple-950/20 border-purple-500/50'
                : 'bg-gradient-to-r from-grid-card via-grid-surface to-cyan-950/30 border-grid-cyan'
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3 pb-3 border-b border-grid-border/60">
              <div className="flex items-center space-x-2.5">
                {!result.is_sufficient ? (
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                ) : (
                  <ShieldCheck className="w-5 h-5 text-grid-cyan" />
                )}
                <span className="font-mono text-xs uppercase tracking-widest text-grid-muted">
                  Diagnostic Conclusion • {result.investigation_type}
                </span>
              </div>

              <div className="flex items-center space-x-3 text-xs font-mono">
                <span
                  className={`px-2.5 py-1 rounded text-xs font-bold border ${
                    result.is_sufficient
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  }`}
                >
                  {result.is_sufficient ? 'EVIDENCE SUFFICIENT' : 'INSUFFICIENT EVIDENCE (ABSTAINED)'}
                </span>

                {result.conflict_lifecycle !== 'NO_CONFLICT' && (
                  <span className="px-2.5 py-1 rounded text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">
                    {result.conflict_lifecycle}
                  </span>
                )}

                <span className="bg-grid-surface px-3 py-1 rounded text-grid-cyan font-bold border border-grid-border">
                  Evidence score (uncalibrated): {Math.round(result.confidence_score * 100)}%
                </span>
              </div>
            </div>

            <h2 className="text-xl font-black tracking-tight text-white mb-2">
              {result.diagnosis_title}
            </h2>

            <div className="text-xs text-grid-text font-mono leading-relaxed bg-grid-surface/60 p-4 rounded-lg border border-grid-border whitespace-pre-line">
              {result.diagnosis_summary}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-grid-border">
                <FileCheck2 className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                  Verified Facts ({result.verified_facts?.length || 0})
                </h3>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {result.verified_facts?.map((f: any) => (
                  <div key={f.claim_id} className="bg-grid-surface p-2.5 rounded border border-grid-border text-xs">
                    <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400 mb-1">
                      <span className="font-bold">[{f.claim_id}] VERIFIED FACT</span>
                      <span className="text-grid-muted">{f.verification_source}</span>
                    </div>
                    <p className="text-gray-200">{f.statement}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-grid-border">
                <GitBranch className="w-4 h-4 text-grid-cyan" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                  Supported Inferences ({result.supported_inferences?.length || 0})
                </h3>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {result.supported_inferences?.map((inf: any) => (
                  <div key={inf.claim_id} className="bg-grid-surface p-2.5 rounded border border-cyan-900/40 text-xs">
                    <div className="flex items-center justify-between text-[10px] font-mono text-grid-cyan mb-1">
                      <span className="font-bold">[{inf.claim_id}] INFERENCE</span>
                      <span className="text-grid-muted">{inf.inference_rule_id || 'Premise Derived'}</span>
                    </div>
                    <p className="text-gray-200">{inf.statement}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-grid-border">
                <Lightbulb className="w-4 h-4 text-grid-amber" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                  Actionable Next Steps ({result.recommendations?.length || 0})
                </h3>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {result.recommendations?.map((rec: any) => (
                  <div key={rec.claim_id} className="bg-grid-surface p-2.5 rounded border border-amber-900/40 text-xs">
                    <div className="flex items-center justify-between text-[10px] font-mono text-amber-400 mb-1">
                      <span className="font-bold">[{rec.claim_id}] RECOMMENDED STEP</span>
                      <span className="text-grid-muted">{rec.verification_source}</span>
                    </div>
                    <p className="text-gray-200">{rec.statement}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {result.hypotheses && (
            <HypothesesMatrix hypotheses={result.hypotheses} />
          )}

          {result.citations && result.citations.length > 0 && (
            <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-grid-border">
                <BookOpen className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
                  Technical Literature Citations ({result.citations.length})
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {result.citations.map((c: any) => (
                  <div key={c.chunk_id} className="bg-grid-surface p-3 rounded border border-grid-border text-xs font-mono space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] text-purple-400">
                      <span className="font-bold">{c.doc_id}</span>
                      <span className="text-grid-muted">{c.section}</span>
                    </div>
                    <h4 className="text-white font-bold">{c.title}</h4>
                    <p className="text-gray-300 text-[11px] font-sans line-clamp-3">
                      {c.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.execution_trace && (
            <ExecutionTraceView
              trace={result.execution_trace}
              totalDurationMs={result.duration_ms}
            />
          )}

          {result && (
            <ProvenanceExplorer investigationId={result.investigation_id} />
          )}
        </div>
      )}
    </div>
  );
}

export default function InvestigationPage() {
  return (
    <Suspense fallback={<div className="text-xs font-mono text-grid-cyan p-8">Loading investigation...</div>}>
      <InvestigationContent />
    </Suspense>
  );
}
