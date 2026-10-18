'use client';

import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck, RefreshCw, Wrench, ArrowRight } from 'lucide-react';
import { runValidation } from '@/lib/api';

export default function ConfigurationValidationPage() {
  const [bayId, setBayId] = useState('BAY_F12');
  const [simulateInversion, setSimulateInversion] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const executeValidation = async (inverted: boolean = simulateInversion) => {
    setLoading(true);
    setError(null);
    try {
      const mapping = inverted ? { CH1: 'CT12C', CH2: 'CT12B', CH3: 'CT12A' } : undefined;
      const data = await runValidation(bayId, mapping);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Validation execution failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    executeValidation(false);
  }, [bayId]);

  const handleToggleInversion = () => {
    const nextVal = !simulateInversion;
    setSimulateInversion(nextVal);
    executeValidation(nextVal);
  };

  return (
    <div className="space-y-6">
      <div className="bg-grid-card border border-grid-border p-6 rounded-xl shadow-xl">
        <div className="flex items-center space-x-2 mb-1">
          <ShieldCheck className="w-5 h-5 text-grid-cyan" />
          <h1 className="text-xl font-bold text-white tracking-tight">
            Deterministic Substation Configuration & Wiring Validator
          </h1>
        </div>
        <p className="text-xs text-grid-muted max-w-3xl">
          Executes deterministic engineering rule checks on bay parameters, relay-to-breaker trip routing,
          CT/VT secondary terminal polarity, and overcurrent pickup thresholds. Zero probabilistic LLM guessing.
        </p>
      </div>

      <div className="bg-grid-card border border-grid-border p-5 rounded-lg shadow-xl flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
        <div className="flex items-center space-x-4">
          <div>
            <span className="text-grid-muted block text-[10px] uppercase">Select Bay:</span>
            <select
              value={bayId}
              onChange={(e) => setBayId(e.target.value)}
              className="bg-grid-surface border border-grid-border text-white px-3 py-1.5 rounded focus:outline-none focus:border-grid-cyan"
            >
              <option value="BAY_F12">BAY_F12 (Feeder F12)</option>
              <option value="BAY_F13">BAY_F13 (Feeder F13)</option>
            </select>
          </div>

          <div>
            <span className="text-grid-muted block text-[10px] uppercase">Fault Injection Test:</span>
            <button
              onClick={handleToggleInversion}
              className={`px-3 py-1.5 rounded border transition-all ${
                simulateInversion
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 font-bold shadow-[0_0_10px_rgba(244,63,94,0.3)]'
                  : 'bg-grid-surface text-gray-300 border-grid-border hover:border-grid-cyan'
              }`}
            >
              {simulateInversion ? 'SIMULATING PHASE A/C INVERSION' : 'NORMAL WIRING TABLE'}
            </button>
          </div>
        </div>

        <button
          onClick={() => executeValidation()}
          disabled={loading}
          className="flex items-center gap-1.5 bg-grid-cyan text-slate-950 font-bold px-4 py-2 rounded hover:bg-cyan-300 transition-all shadow-[0_0_10px_rgba(0,240,255,0.2)] disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          RE-RUN VALIDATION
        </button>
      </div>

      {error && (
        <div className="bg-rose-950/40 border border-rose-800 p-4 rounded-lg text-rose-300 text-xs font-mono">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div
            className={`p-6 rounded-xl border shadow-xl flex flex-wrap items-center justify-between gap-4 ${
              result.valid
                ? 'bg-emerald-950/20 border-emerald-500/40'
                : 'bg-rose-950/20 border-rose-500/50'
            }`}
          >
            <div className="flex items-center space-x-3">
              {result.valid ? (
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              ) : (
                <XCircle className="w-8 h-8 text-rose-400" />
              )}
              <div>
                <h2 className="text-lg font-bold text-white">
                  {result.valid ? 'Configuration Valid — 0 Violations' : `Configuration Invalid — ${result.violations?.length} Violation(s) Found`}
                </h2>
                <p className="text-xs text-grid-muted font-mono mt-0.5">
                  Target: {result.target_entity_id} • Evaluated against {result.checks_performed?.length} explicit engineering rules
                </p>
              </div>
            </div>

            <span
              className={`font-mono text-xs font-bold px-3 py-1 rounded border ${
                result.valid
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-rose-500/20 text-rose-300 border-rose-500/50'
              }`}
            >
              {result.valid ? 'PASSED' : 'VIOLATION DETECTED'}
            </span>
          </div>

          {result.violations && result.violations.length > 0 && (
            <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
              <div className="flex items-center space-x-2 pb-2 border-b border-grid-border">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
                  Detected Rule Violations
                </h3>
              </div>

              <div className="space-y-3">
                {result.violations.map((v: any, idx: number) => (
                  <div key={idx} className="bg-grid-surface p-4 rounded-lg border border-rose-900/50 space-y-2">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="font-bold text-rose-400 bg-rose-950/50 px-2 py-0.5 rounded border border-rose-800">
                        {v.rule_id} • {v.rule_name}
                      </span>
                      <span className="text-grid-muted">
                        Entity: <strong className="text-white">{v.entity_id}</strong> ({v.entity_type})
                      </span>
                    </div>

                    <p className="text-xs text-white font-mono">
                      {v.message}
                    </p>

                    <div className="text-[11px] font-mono text-amber-300 bg-amber-950/20 p-2.5 rounded border border-amber-900/40">
                      <strong>Remediation Advice:</strong> {v.remediation_advice}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-white pb-2 border-b border-grid-border">
              Standard Checks Executed
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono">
              {result.checks_performed?.map((chk: string, idx: number) => (
                <div key={idx} className="flex items-center space-x-2 bg-grid-surface p-2.5 rounded border border-grid-border">
                  <CheckCircle2 className="w-3.5 h-3.5 text-grid-cyan" />
                  <span className="text-gray-300">{chk}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
