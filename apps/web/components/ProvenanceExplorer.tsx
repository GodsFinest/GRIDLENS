'use client';

import React, { useState, useEffect } from 'react';
import { GitBranch, ShieldCheck, CheckCircle2, XCircle, FileText, Activity, Database, ArrowRight, Layers, Cpu } from 'lucide-react';
import { fetchProvenance } from '@/lib/api';

interface ProvenanceChain {
  claim_id: string;
  claim_statement: string;
  claim_type: string;
  status: string;
  verification_notes?: string;
  evidence_ids: string[];
  premise_claim_ids?: string[];
  inference_rule_id?: string;
  evidence_items: Array<{
    evidence_id: string;
    kind?: string;
    source_type?: string;
    source_id: string;
    tool_name?: string;
    fact: string;
    structured_value?: any;
    unit?: string;
    provenance?: string;
    metadata?: Record<string, any>;
  }>;
}

interface ProvenanceData {
  investigation_id: string;
  incident_id?: string;
  diagnosis: string;
  diagnosis_summary: string;
  conflict_lifecycle: string;
  conflict_explanation?: string;
  conflict_transitions: any[];
  chains: ProvenanceChain[];
}

interface ProvenanceExplorerProps {
  investigationId: string;
  initialData?: ProvenanceData | null;
}

export default function ProvenanceExplorer({ investigationId, initialData }: ProvenanceExplorerProps) {
  const [data, setData] = useState<ProvenanceData | null>(initialData || null);
  const [loading, setLoading] = useState(!initialData);
  const [selectedClaim, setSelectedClaim] = useState<ProvenanceChain | null>(null);

  useEffect(() => {
    if (initialData) {
      setData(initialData);
      if (initialData.chains?.length > 0 && !selectedClaim) {
        setSelectedClaim(initialData.chains[0]);
      }
      return;
    }

    async function loadProvenance() {
      setLoading(true);
      try {
        const res = await fetchProvenance(investigationId);
        setData(res);
        if (res.chains?.length > 0) {
          setSelectedClaim(res.chains[0]);
        }
      } catch (err) {
        console.error('Failed to load provenance chain', err);
      } finally {
        setLoading(false);
      }
    }

    if (investigationId) {
      loadProvenance();
    }
  }, [investigationId, initialData]);

  if (loading) {
    return (
      <div className="p-8 text-center text-xs font-mono text-grid-cyan animate-pulse">
        Tracing deterministic evidence DAG and reconstructed provenance chains...
      </div>
    );
  }

  if (!data || !data.chains || data.chains.length === 0) {
    return (
      <div className="p-6 text-center text-xs font-mono text-grid-muted">
        No provenance DAG records available for this investigation.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-grid-card border border-grid-border rounded-xl p-5 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-3 border-b border-grid-border">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-grid-cyan" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-white">
              End-to-End Lineage DAG ({data.chains.length} Chains)
            </h3>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-grid-muted">LIFECYCLE:</span>
            <span className="text-purple-300 bg-purple-950/40 border border-purple-800/40 px-2 py-0.5 rounded">
              {data.conflict_lifecycle}
            </span>
          </div>
        </div>

        <div className="bg-grid-surface/80 p-4 rounded-lg border border-grid-border">
          <div className="text-[10px] font-mono uppercase text-grid-cyan mb-1">Authoritative Root Finding</div>
          <div className="text-base font-bold text-white">{data.diagnosis}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 space-y-2 max-h-[600px] overflow-y-auto pr-2">
          {data.chains.map((chain) => {
            const isSelected = selectedClaim?.claim_id === chain.claim_id;
            return (
              <div
                key={chain.claim_id}
                onClick={() => setSelectedClaim(chain)}
                className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-cyan-950/30 border-grid-cyan shadow-[0_0_12px_rgba(0,240,255,0.2)]'
                    : 'bg-grid-card border-grid-border hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                  <span className="font-bold text-grid-cyan">
                    [{chain.claim_id}] {chain.claim_type}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      chain.status === 'VERIFIED'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    {chain.status}
                  </span>
                </div>
                <p className="text-xs text-gray-200 line-clamp-2">{chain.claim_statement}</p>
                <div className="mt-2 flex items-center gap-2 text-[10px] font-mono text-grid-muted">
                  <span>Cited Evidence: {chain.evidence_ids.length}</span>
                  {chain.inference_rule_id && <span>Rule: {chain.inference_rule_id}</span>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="lg:col-span-7">
          {selectedClaim ? (
            <div className="bg-grid-card border border-grid-border rounded-xl p-6 shadow-xl space-y-5">
              <div className="pb-3 border-b border-grid-border">
                <div className="text-[10px] font-mono text-grid-muted uppercase">Selected Assertion</div>
                <h4 className="text-base font-bold text-white mt-1">
                  [{selectedClaim.claim_id}] {selectedClaim.claim_statement}
                </h4>
                {selectedClaim.verification_notes && (
                  <div className="mt-2 text-xs font-mono text-emerald-300 bg-emerald-950/30 p-2.5 rounded border border-emerald-800/40">
                    Verification Audit: {selectedClaim.verification_notes}
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-2 text-xs font-mono text-grid-cyan uppercase tracking-wider">
                  <Database className="w-3.5 h-3.5" />
                  <span>Authoritative Physical Evidence Trace</span>
                </div>

                {selectedClaim.evidence_items.length === 0 ? (
                  <div className="text-xs font-mono text-grid-muted p-4 bg-grid-surface rounded border border-grid-border">
                    No physical evidence attachments for this assertion.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selectedClaim.evidence_items.map((ev, idx) => (
                      <div
                        key={idx}
                        className="bg-grid-surface p-4 rounded-lg border border-grid-border space-y-2 text-xs font-mono"
                      >
                        <div className="flex items-center justify-between text-[11px] pb-2 border-b border-slate-800">
                          <span className="font-bold text-yellow-400">{ev.evidence_id}</span>
                          <span className="text-grid-muted">Tool: {ev.tool_name || 'Workflow'}</span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px] text-grid-muted">
                          <div>
                            <span className="block text-[10px] text-slate-400">SOURCE TYPE:</span>
                            <span className="text-white">{ev.source_type || 'SYSTEM'}</span>
                          </div>
                          <div>
                            <span className="block text-[10px] text-slate-400">SOURCE ID:</span>
                            <span className="text-white">{ev.source_id}</span>
                          </div>
                        </div>

                        <div>
                          <span className="block text-[10px] text-slate-400">PHYSICAL FACT:</span>
                          <span className="text-gray-100 font-sans">{ev.fact}</span>
                        </div>

                        {ev.provenance && (
                          <div>
                            <span className="block text-[10px] text-slate-400">PROVENANCE METHOD:</span>
                            <span className="text-grid-cyan">{ev.provenance}</span>
                          </div>
                        )}

                        {ev.structured_value !== null && ev.structured_value !== undefined && (
                          <div>
                            <span className="block text-[10px] text-slate-400">STRUCTURED VALUE:</span>
                            <span className="text-emerald-400 font-bold">
                              {JSON.stringify(ev.structured_value)} {ev.unit || ''}
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-12 text-center text-xs font-mono text-grid-muted bg-grid-card border border-grid-border rounded-xl">
              Select a claim on the left to reconstruct its physical provenance DAG.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
