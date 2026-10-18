'use client';

import React, { useState, useEffect } from 'react';
import { BarChart3, ShieldCheck, CheckCircle2, XCircle, AlertCircle, RefreshCw, Cpu, Layers } from 'lucide-react';
import { fetchEvaluationResults, triggerEvaluationRun } from '@/lib/api';

export default function EvaluationDashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [runningEval, setRunningEval] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchEvaluationResults();
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async () => {
    setRunningEval(true);
    try {
      await triggerEvaluationRun();
      await loadData();
    } catch (e) {
      console.error(e);
    } finally {
      setRunningEval(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const metrics = data?.full_gridlens?.metrics;

  return (
    <div className="space-y-6">
      <div className="bg-grid-card border border-grid-border p-6 rounded-xl shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-grid-cyan uppercase tracking-widest mb-1">
            <BarChart3 className="w-4 h-4 text-grid-cyan" />
            <span>Empirical Benchmarking & Ablation Suite</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            System Evaluation & Comparative Ablations
          </h1>
          <p className="text-xs text-grid-muted mt-1 max-w-2xl font-mono">
            Comparing a scripted heuristic negative control (no LLM) with GridLens and 6 subsystem ablations across {metrics?.total_test_cases || 26} curated regression cases. This is not field accuracy or a real-model comparison.
          </p>
        </div>

        <button
          onClick={handleRunEvaluation}
          disabled={runningEval}
          className="flex items-center gap-2 bg-grid-cyan text-slate-950 font-bold px-4 py-2.5 rounded-lg hover:bg-cyan-300 transition-all shadow-[0_0_15px_rgba(0,240,255,0.3)] text-xs font-mono disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${runningEval ? 'animate-spin' : ''}`} />
          {runningEval ? 'RUNNING BENCHMARKS...' : 'EXECUTE GOLDEN TEST SUITE'}
        </button>
      </div>

      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Diagnosis Accuracy</span>
            <span className="text-xl font-bold text-emerald-400 mt-1 block">
              {metrics.diagnosis_accuracy_percent}%
            </span>
            <span className="text-[9px] text-grid-muted">Root-cause identification</span>
          </div>

          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Tool Selection</span>
            <span className="text-xl font-bold text-grid-cyan mt-1 block">
              {metrics.tool_selection_accuracy_percent}%
            </span>
            <span className="text-[9px] text-grid-muted">Minimal tool set invocation</span>
          </div>

          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Contradiction Handling</span>
            <span className="text-xl font-bold text-purple-400 mt-1 block">
              {metrics.contradiction_detection_percent}%
            </span>
            <span className="text-[9px] text-grid-muted">A/C mapping anomaly</span>
          </div>

          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Abstention Accuracy</span>
            <span className="text-xl font-bold text-amber-400 mt-1 block">
              {metrics.abstention_accuracy_percent}%
            </span>
            <span className="text-[9px] text-grid-muted">Refuses under missing data</span>
          </div>

          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Unsupported Claims</span>
            <span className="text-xl font-bold text-emerald-400 mt-1 block">
              {metrics.unsupported_claim_rate_percent}%
            </span>
            <span className="text-[9px] text-grid-muted">Rejected candidate claims</span>
          </div>

          <div className="bg-grid-card border border-grid-border p-3.5 rounded-lg shadow">
            <span className="text-grid-muted block text-[10px] uppercase">Average Latency</span>
            <span className="text-xl font-bold text-white mt-1 block">
              {metrics.avg_latency_ms} ms
            </span>
            <span className="text-[9px] text-grid-muted">Per full investigation</span>
          </div>
        </div>
      )}

      <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
        <div className="flex items-center space-x-2 mb-4 pb-3 border-b border-grid-border">
          <Layers className="w-4 h-4 text-grid-cyan" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Benchmark comparison
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-grid-surface text-grid-muted uppercase text-[10px] border-b border-grid-border">
              <tr>
                <th className="py-3 px-3">System Architecture</th>
                <th className="py-3 px-3 text-center">Diagnosis Acc (%)</th>
                <th className="py-3 px-3 text-center">Contradiction (%)</th>
                <th className="py-3 px-3 text-center">Abstention (%)</th>
                <th className="py-3 px-3 text-center">Unsupported Claims (%)</th>
                <th className="py-3 px-3 text-center">Avg Latency</th>
                <th className="py-3 px-3">Primary Engineering Limitation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-grid-border">
              {data?.comparison_matrix?.map((row: any, idx: number) => {
                const isGridLens = row.system === 'Full GridLens';
                const isBaseline = row.system.includes('Baseline');

                return (
                  <tr
                    key={idx}
                    className={`transition-colors ${
                      isGridLens
                        ? 'bg-cyan-950/20 font-bold text-white border-l-2 border-l-grid-cyan'
                        : isBaseline
                        ? 'bg-rose-950/10 text-gray-300'
                        : 'hover:bg-grid-surface text-gray-300'
                    }`}
                  >
                    <td className="py-3 px-3 flex items-center gap-1.5">
                      {isGridLens && <CheckCircle2 className="w-3.5 h-3.5 text-grid-cyan shrink-0" />}
                      <span className={isGridLens ? 'text-grid-cyan font-bold' : ''}>{row.system}</span>
                    </td>
                    <td className="py-3 px-3 text-center font-bold">
                      <span className={row.diagnosis_accuracy > 85 ? 'text-emerald-400' : 'text-amber-400'}>
                        {row.diagnosis_accuracy}%
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className={row.contradiction_detection > 80 ? 'text-purple-400' : 'text-gray-500'}>
                        {row.contradiction_detection}%
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className={row.abstention_accuracy > 80 ? 'text-amber-400' : 'text-gray-500'}>
                        {row.abstention_accuracy}%
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center font-bold">
                      <span className={row.unsupported_claim_rate === 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {row.unsupported_claim_rate}%
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center text-grid-muted">
                      {row.avg_latency_ms} ms
                    </td>
                    <td className="py-3 px-3 text-[11px] text-gray-400 font-sans">
                      {row.key_limitation}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-4 font-mono text-xs">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-white pb-2 border-b border-grid-border">
          Subsystem responsibilities
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300">
          <div className="bg-grid-surface p-3.5 rounded border border-grid-border space-y-1">
            <strong className="text-grid-cyan block text-[11px]">1. Seeded Directed Graph</strong>
            <p className="text-[11px] font-sans">
              Resolves breaker, relay, CT, IED, bay, and feeder relationships.
            </p>
          </div>

          <div className="bg-grid-surface p-3.5 rounded border border-grid-border space-y-1">
            <strong className="text-grid-cyan block text-[11px]">2. COMTRADE IEEE C37.111 Analyzer</strong>
            <p className="text-[11px] font-sans">
              Calculates RMS values, peaks, event timing, and phase identification from oscillography.
            </p>
          </div>

          <div className="bg-grid-surface p-3.5 rounded border border-grid-border space-y-1">
            <strong className="text-grid-cyan block text-[11px]">3. Deterministic Configuration Validator</strong>
            <p className="text-[11px] font-sans">
              Detects secondary CT channel mapping conflicts before report generation.
            </p>
          </div>

          <div className="bg-grid-surface p-3.5 rounded border border-grid-border space-y-1">
            <strong className="text-grid-cyan block text-[11px]">4. Claim Verification & Sufficiency Gate</strong>
            <p className="text-[11px] font-sans">
              Rejects unsupported claims and returns an insufficient-evidence result when required data is missing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
