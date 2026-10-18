'use client';

import React from 'react';
import { GitCompare, CheckCircle2, XCircle, AlertCircle, Award } from 'lucide-react';

interface Assessment {
  assessment_id: string;
  evidence_id: string;
  relationship: string;
  weight: number;
  explanation: string;
}

interface HypothesisItem {
  hypothesis_id: string;
  code: string;
  title: string;
  description: string;
  deterministic_score: number;
  confidence_normalized: number;
  is_primary_diagnosis: boolean;
  supporting_assessments?: Assessment[];
  contradicting_assessments?: Assessment[];
  missing_evidence_descriptions?: string[];
}

interface HypothesesMatrixProps {
  hypotheses: HypothesisItem[];
}

export default function HypothesesMatrix({ hypotheses = [] }: HypothesesMatrixProps) {
  return (
    <div className="bg-grid-card border border-grid-border rounded-lg p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-grid-border">
        <div className="flex items-center space-x-2">
          <GitCompare className="w-4 h-4 text-grid-cyan" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white">
            Competing Hypotheses Evaluation Matrix
          </h2>
        </div>
        <span className="text-xs text-grid-muted font-mono">
          Evidence weights — not calibrated probabilities
        </span>
      </div>

      <div className="space-y-3">
        {hypotheses.map((hyp) => {
          const isWinner = hyp.is_primary_diagnosis;
          const score = hyp.deterministic_score;
          const conf = Math.round(hyp.confidence_normalized * 100);

          return (
            <div
              key={hyp.code || hyp.hypothesis_id}
              className={`p-4 rounded-lg border transition-all ${
                isWinner
                  ? 'bg-gradient-to-r from-grid-surface to-cyan-950/30 border-grid-cyan shadow-[0_0_15px_rgba(0,240,255,0.15)]'
                  : 'bg-grid-surface border-grid-border opacity-85 hover:opacity-100'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="flex items-center space-x-2">
                  <span
                    className={`font-mono text-xs px-2 py-0.5 rounded font-bold ${
                      isWinner ? 'bg-grid-cyan text-slate-900 font-extrabold' : 'bg-grid-card text-grid-muted border border-grid-border'
                    }`}
                  >
                    {hyp.code}
                  </span>
                  <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                    {hyp.title}
                    {isWinner && (
                      <span className="text-[10px] bg-cyan-500/20 text-grid-cyan px-2 py-0.5 rounded font-mono font-normal border border-cyan-500/40">
                        LEADING HYPOTHESIS
                      </span>
                    )}
                  </h3>
                </div>

                <div className="flex items-center space-x-3 text-xs font-mono">
                  <span className="text-grid-muted">
                    Evidence Score: <strong className={score > 0 ? 'text-emerald-400' : 'text-rose-400'}>{score > 0 ? `+${score.toFixed(1)}` : score.toFixed(1)}</strong>
                  </span>
                  <span className="text-grid-cyan font-bold bg-grid-card px-2 py-0.5 rounded border border-grid-border">
                    {conf}% normalized score
                  </span>
                </div>
              </div>

              <p className="text-xs text-grid-muted mb-3">
                {hyp.description}
              </p>

              {hyp.supporting_assessments && hyp.supporting_assessments.length > 0 && (
                <div className="mb-2">
                  <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider block mb-1">
                    Supporting Evidence ({hyp.supporting_assessments.length}):
                  </span>
                  <div className="space-y-1">
                    {hyp.supporting_assessments.map((ast, idx) => (
                      <div key={idx} className="flex items-start space-x-1.5 text-xs text-emerald-300 bg-emerald-950/20 px-2 py-1 rounded border border-emerald-900/40">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{ast.explanation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {hyp.contradicting_assessments && hyp.contradicting_assessments.length > 0 && (
                <div className="mb-2">
                  <span className="text-[10px] font-mono text-rose-400 uppercase tracking-wider block mb-1">
                    Refuting / Contradicting Evidence ({hyp.contradicting_assessments.length}):
                  </span>
                  <div className="space-y-1">
                    {hyp.contradicting_assessments.map((ast, idx) => (
                      <div key={idx} className="flex items-start space-x-1.5 text-xs text-rose-300 bg-rose-950/20 px-2 py-1 rounded border border-rose-900/40">
                        <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                        <span>{ast.explanation}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {hyp.missing_evidence_descriptions && hyp.missing_evidence_descriptions.length > 0 && (
                <div>
                  <span className="text-[10px] font-mono text-amber-400 uppercase tracking-wider block mb-1">
                    Missing Evidence Required:
                  </span>
                  <div className="space-y-1">
                    {hyp.missing_evidence_descriptions.map((m, idx) => (
                      <div key={idx} className="flex items-start space-x-1.5 text-xs text-amber-300 bg-amber-950/20 px-2 py-1 rounded border border-amber-900/40">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                        <span>{m}</span>
                      </div>
                    ))}
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
