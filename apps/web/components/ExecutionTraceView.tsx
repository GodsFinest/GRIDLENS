'use client';

import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronRight, Cpu, Clock, CheckCircle } from 'lucide-react';

interface TraceEntry {
  step_index: number;
  timestamp: string;
  stage: string;
  tool_invoked?: string;
  inputs?: any;
  outputs_summary: string;
  duration_ms: number;
}

interface ExecutionTraceViewProps {
  trace: TraceEntry[];
  totalDurationMs?: number;
}

export default function ExecutionTraceView({ trace = [], totalDurationMs }: ExecutionTraceViewProps) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const toggleExpand = (idx: number) => {
    setExpandedStep(expandedStep === idx ? null : idx);
  };

  return (
    <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-grid-border">
        <div className="flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-grid-cyan" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Auditable Agent Execution Trace ({trace.length} Steps)
          </h2>
        </div>
        {totalDurationMs && (
          <span className="text-xs text-grid-cyan font-mono bg-grid-surface px-2.5 py-1 rounded border border-grid-border">
            Total Execution: {totalDurationMs.toFixed(1)} ms
          </span>
        )}
      </div>

      <div className="space-y-2">
        {trace.map((step) => {
          const isExpanded = expandedStep === step.step_index;

          return (
            <div
              key={step.step_index}
              className="bg-grid-surface border border-grid-border rounded overflow-hidden transition-colors hover:border-grid-cyan/40"
            >
              <div
                onClick={() => toggleExpand(step.step_index)}
                className="p-3 flex items-center justify-between cursor-pointer select-none"
              >
                <div className="flex items-center space-x-2.5">
                  <span className="font-mono text-xs text-grid-muted w-6">
                    #{step.step_index}
                  </span>

                  {step.tool_invoked ? (
                    <span className="text-xs font-mono font-bold text-grid-cyan bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/40">
                      {step.tool_invoked}
                    </span>
                  ) : (
                    <span className="text-xs font-mono text-grid-amber bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
                      {step.stage}
                    </span>
                  )}

                  <span className="text-xs text-white truncate max-w-md hidden sm:inline">
                    {step.outputs_summary}
                  </span>
                </div>

                <div className="flex items-center space-x-3 text-xs font-mono">
                  <span className="text-grid-muted">
                    {step.duration_ms.toFixed(1)} ms
                  </span>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-grid-muted" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-grid-muted" />
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="p-3.5 bg-slate-950/70 border-t border-grid-border text-xs font-mono space-y-2">
                  <div>
                    <span className="text-grid-muted block text-[10px]">STAGE:</span>
                    <span className="text-grid-cyan font-bold">{step.stage}</span>
                  </div>

                  {step.inputs && Object.keys(step.inputs).length > 0 && (
                    <div>
                      <span className="text-grid-muted block text-[10px]">INPUT ARGUMENTS:</span>
                      <pre className="text-gray-300 bg-grid-card p-2 rounded text-[11px] overflow-x-auto border border-grid-border">
                        {JSON.stringify(step.inputs, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div>
                    <span className="text-grid-muted block text-[10px]">OUTPUT SUMMARY:</span>
                    <p className="text-emerald-400 bg-grid-card p-2 rounded text-[11px] border border-grid-border">
                      {step.outputs_summary}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
