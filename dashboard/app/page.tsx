"use client";

import { useEffect, useState } from "react";
import { 
  Activity, Database, Server, RefreshCw, CheckCircle, XCircle, 
  AlertTriangle, ShieldCheck, ListOrdered, Loader2, GitCommit, Copy, Fingerprint
} from "lucide-react";

type Stats = {
  total_payments: number;
  successful_payments: number;
  failed_payments: number;
  processing_payments: number;
  retry_queue_count: number;
  dead_letter_queue_count: number;
  rabbitmq_status: string;
  postgresql_status: string;
  redis_status: string;
  health_status: string;
};

type Payment = {
  id: number;
  payment_id: string;
  amount: number;
  currency: string;
  status: string;
  merchant_reference: string | null;
  created_at: string;
};

type Log = {
  id: number;
  request_id: string;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  created_at: string;
};

type RetryAttempt = {
  id: number;
  request_id: string;
  attempt_number: number;
  status: string;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
};

const API_BASE = "http://localhost:8000/dashboard";

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [failedPayments, setFailedPayments] = useState<Payment[]>([]);
  const [retries, setRetries] = useState<RetryAttempt[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, paymentsRes, failedRes, retriesRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/recent-payments`),
        fetch(`${API_BASE}/failed-payments`),
        fetch(`${API_BASE}/recent-retries`),
        fetch(`${API_BASE}/recent-logs`)
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (paymentsRes.ok) setPayments(await paymentsRes.json());
      if (failedRes.ok) setFailedPayments(await failedRes.json());
      if (retriesRes.ok) setRetries(await retriesRes.json());
      if (logsRes.ok) setLogs(await logsRes.json());
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const HealthBadge = ({ status }: { status: string }) => {
    const isHealthy = status === "healthy";
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        isHealthy ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
      }`}>
        {isHealthy ? "Healthy" : "Degraded"}
      </span>
    );
  };

  const StatusPill = ({ status }: { status: string }) => {
    const s = status.toUpperCase();
    if (s === 'SUCCESS') return <span className="bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-[10px] font-bold tracking-wider">SUCCESS</span>;
    if (s === 'FAILED') return <span className="bg-red-500/20 text-red-400 px-2 py-1 rounded text-[10px] font-bold tracking-wider">FAILED</span>;
    if (s === 'PROCESSING' || s === 'ENQUEUED') return <span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded text-[10px] font-bold tracking-wider">{s}</span>;
    return <span className="bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded text-[10px] font-bold tracking-wider">{s}</span>;
  };

  const CorrelationId = ({ id }: { id: string }) => (
    <div 
      onClick={() => copyToClipboard(id)}
      className="inline-flex items-center gap-1.5 px-2 py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-md cursor-pointer transition-colors group"
      title="Click to copy Trace ID"
    >
      <Fingerprint className="w-3 h-3 text-blue-400" />
      <span className="font-mono text-[10px] text-slate-300 group-hover:text-white">
        {id.split('-')[0]}...{id.split('-')[4] || ''}
      </span>
      <Copy className="w-3 h-3 text-slate-500 group-hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );

  return (
    <main className="min-h-screen p-8 max-w-[90rem] mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-10 animate-fade-in gap-4">
        <div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
            JakRif Sentinel
          </h1>
          <p className="text-slate-400 mt-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Observability & Fault-Tolerant Platform Monitoring
          </p>
        </div>
        
        <div className="flex gap-4">
          <div className="glass px-4 py-2 rounded-xl flex items-center gap-3">
            <div className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${stats?.health_status === "healthy" ? "bg-emerald-400" : "bg-red-400"}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${stats?.health_status === "healthy" ? "bg-emerald-500" : "bg-red-500"}`}></span>
            </div>
            <span className="text-sm font-medium">System {stats?.health_status === "healthy" ? "Online" : "Degraded"}</span>
          </div>
        </div>
      </div>

      {loading && !stats ? (
        <div className="flex justify-center items-center h-64">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            <span className="text-slate-400 text-sm animate-pulse">Establishing secure connection...</span>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          
          {/* Main Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              <div className="flex justify-between items-start relative z-10">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Total Payments</p>
                  <h3 className="text-4xl font-bold text-white mt-2">{stats?.total_payments || 0}</h3>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                  <Activity className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              <div className="flex justify-between items-start relative z-10">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Successful</p>
                  <h3 className="text-4xl font-bold text-emerald-400 mt-2">{stats?.successful_payments || 0}</h3>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400">
                  <CheckCircle className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              <div className="flex justify-between items-start relative z-10">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Failed / Dead</p>
                  <h3 className="text-4xl font-bold text-red-400 mt-2">
                    {stats?.failed_payments || 0} <span className="text-sm font-normal text-slate-500">({stats?.dead_letter_queue_count || 0} DLQ)</span>
                  </h3>
                </div>
                <div className="p-3 bg-red-500/10 rounded-xl text-red-400">
                  <XCircle className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-yellow-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              <div className="flex justify-between items-start relative z-10">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Processing / Retry</p>
                  <h3 className="text-4xl font-bold text-yellow-400 mt-2">
                    {stats?.processing_payments || 0} <span className="text-sm font-normal text-slate-500">({stats?.retry_queue_count || 0} Wait)</span>
                  </h3>
                </div>
                <div className="p-3 bg-yellow-500/10 rounded-xl text-yellow-400">
                  <RefreshCw className="w-6 h-6" />
                </div>
              </div>
            </div>
          </div>

          {/* Infrastructure Health */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in" style={{ animationDelay: '0.2s' }}>
            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between border-t-4 border-t-purple-500/50">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">RabbitMQ</h4>
                  <p className="text-xs text-slate-400">Message Broker</p>
                </div>
              </div>
              <HealthBadge status={stats?.rabbitmq_status || "unknown"} />
            </div>

            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between border-t-4 border-t-red-500/50">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-red-500/10 rounded-xl text-red-400">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">Redis</h4>
                  <p className="text-xs text-slate-400">Cache & Idempotency</p>
                </div>
              </div>
              <HealthBadge status={stats?.redis_status || "unknown"} />
            </div>

            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between border-t-4 border-t-blue-500/50">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">PostgreSQL</h4>
                  <p className="text-xs text-slate-400">Primary Database</p>
                </div>
              </div>
              <HealthBadge status={stats?.postgresql_status || "unknown"} />
            </div>
          </div>

          {/* Timelines and Data Views */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-fade-in" style={{ animationDelay: '0.3s' }}>
            
            {/* Payment Timeline */}
            <div className="glass-panel rounded-2xl overflow-hidden flex flex-col h-[600px]">
              <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5 sticky top-0 z-20">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <ListOrdered className="w-4 h-4 text-blue-400" />
                  Payment Timeline
                </h3>
              </div>
              <div className="p-5 overflow-y-auto flex-1 custom-scrollbar">
                <div className="relative border-l-2 border-white/10 ml-3 space-y-6">
                  {payments.map((p, idx) => (
                    <div key={p.id} className="relative pl-6 group">
                      <div className={`absolute w-3 h-3 rounded-full -left-[7px] top-1.5 ring-4 ring-[#0b0c10] ${
                        p.status === 'SUCCESS' ? 'bg-emerald-500' :
                        p.status === 'FAILED' ? 'bg-red-500' :
                        'bg-blue-500'
                      }`} />
                      <div className="glass p-4 rounded-xl flex flex-col gap-2 hover:bg-white/5 transition-colors">
                        <div className="flex justify-between items-start">
                          <StatusPill status={p.status} />
                          <span className="text-xs text-slate-500">{new Date(p.created_at).toLocaleTimeString()}</span>
                        </div>
                        <div className="flex justify-between items-end mt-1">
                          <span className="font-medium text-white">{p.amount} {p.currency}</span>
                          <CorrelationId id={p.payment_id} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {payments.length === 0 && <p className="text-slate-500 text-sm ml-6">No recent payments.</p>}
                </div>
              </div>
            </div>

            {/* Failed & Retry Events */}
            <div className="glass-panel rounded-2xl overflow-hidden flex flex-col h-[600px]">
              <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5 sticky top-0 z-20">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                  Faults & Retries
                </h3>
              </div>
              <div className="p-5 overflow-y-auto flex-1 custom-scrollbar space-y-8">
                
                {/* Retries */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 ml-4">Retry Attempts</h4>
                  <div className="relative border-l-2 border-yellow-500/30 ml-3 space-y-4">
                    {retries.map((r) => (
                      <div key={r.id} className="relative pl-6">
                        <div className="absolute w-2.5 h-2.5 bg-yellow-500 rounded-full -left-[6px] top-2 ring-4 ring-[#0b0c10]" />
                        <div className="glass px-4 py-3 rounded-xl hover:border-yellow-500/30 transition-colors">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-xs font-semibold text-yellow-400">Attempt #{r.attempt_number}</span>
                            <span className="text-[10px] text-slate-500">{new Date(r.created_at).toLocaleTimeString()}</span>
                          </div>
                          <CorrelationId id={r.request_id} />
                          {r.error_message && (
                            <p className="text-xs text-red-400/80 mt-2 font-mono bg-red-500/5 p-2 rounded">{r.error_message}</p>
                          )}
                        </div>
                      </div>
                    ))}
                    {retries.length === 0 && <p className="text-slate-500 text-sm ml-6">No retries recorded.</p>}
                  </div>
                </div>

                {/* Failed */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4 ml-4">Terminal Failures</h4>
                  <div className="relative border-l-2 border-red-500/30 ml-3 space-y-4">
                    {failedPayments.map((p) => (
                      <div key={p.id} className="relative pl-6">
                        <div className="absolute w-2.5 h-2.5 bg-red-500 rounded-full -left-[6px] top-2 ring-4 ring-[#0b0c10]" />
                        <div className="glass px-4 py-3 rounded-xl border border-red-500/10 hover:border-red-500/30 transition-colors">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-white font-medium">{p.amount} {p.currency}</span>
                            <span className="text-[10px] text-slate-500">{new Date(p.created_at).toLocaleTimeString()}</span>
                          </div>
                          <CorrelationId id={p.payment_id} />
                        </div>
                      </div>
                    ))}
                    {failedPayments.length === 0 && <p className="text-slate-500 text-sm ml-6">No failed payments.</p>}
                  </div>
                </div>

              </div>
            </div>

            {/* Recent Events (Logs) */}
            <div className="glass-panel rounded-2xl overflow-hidden flex flex-col h-[600px]">
              <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5 sticky top-0 z-20">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-purple-400" />
                  Recent System Logs
                </h3>
              </div>
              <div className="p-0 overflow-y-auto flex-1 custom-scrollbar">
                <div className="divide-y divide-white/5">
                  {logs.map((l) => (
                    <div key={l.id} className="p-4 hover:bg-white/[0.02] transition-colors flex flex-col gap-3">
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            l.method === 'GET' ? 'bg-blue-500/20 text-blue-400' :
                            l.method === 'POST' ? 'bg-emerald-500/20 text-emerald-400' :
                            'bg-slate-500/20 text-slate-400'
                          }`}>
                            {l.method}
                          </span>
                          <span className="text-xs font-mono text-slate-300 truncate max-w-[150px]" title={l.path}>{l.path}</span>
                        </div>
                        <span className="text-[10px] text-slate-500">{new Date(l.created_at).toLocaleTimeString()}</span>
                      </div>
                      
                      <div className="flex justify-between items-center">
                        <CorrelationId id={l.request_id} />
                        <div className="flex items-center gap-3">
                          <span className={`text-xs font-medium ${l.status_code >= 400 ? 'text-red-400' : 'text-emerald-400'}`}>
                            {l.status_code}
                          </span>
                          <span className="text-xs text-slate-500">{l.latency_ms}ms</span>
                        </div>
                      </div>
                    </div>
                  ))}
                  {logs.length === 0 && <div className="p-8 text-center text-slate-500">No recent logs.</div>}
                </div>
              </div>
            </div>

          </div>
        </div>
      )}
      
      {/* Scrollbar styling injected directly for convenience */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.02);
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.2);
        }
      `}} />
    </main>
  );
}
