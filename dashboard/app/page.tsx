"use client";

import { useEffect, useState } from "react";
import { 
  Activity, Database, Server, RefreshCw, CheckCircle, XCircle, 
  Clock, AlertTriangle, ShieldCheck, ListOrdered, Loader2
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

const API_BASE = "http://localhost:8000/dashboard";

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, paymentsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/recent-payments`),
        fetch(`${API_BASE}/recent-logs`)
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (paymentsRes.ok) setPayments(await paymentsRes.json());
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

  const StatusBadge = ({ status }: { status: string }) => {
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

  return (
    <main className="min-h-screen p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-10 animate-fade-in">
        <div>
          <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
            JakRif Sentinel
          </h1>
          <p className="text-slate-400 mt-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Fault-Tolerant Payment Platform Monitoring
          </p>
        </div>
        
        <div className="flex gap-4">
          <div className="glass px-4 py-2 rounded-xl flex items-center gap-3">
            <div className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${stats?.health_status === "healthy" ? "bg-emerald-400" : "bg-red-400"}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${stats?.health_status === "healthy" ? "bg-emerald-500" : "bg-red-500"}`}></span>
            </div>
            <span className="text-sm font-medium">Live Sync</span>
          </div>
        </div>
      </div>

      {loading && !stats ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="space-y-8">
          
          {/* Main Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Total Payments</p>
                  <h3 className="text-3xl font-bold text-white mt-2">{stats?.total_payments || 0}</h3>
                </div>
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                  <Activity className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Successful</p>
                  <h3 className="text-3xl font-bold text-emerald-400 mt-2">{stats?.successful_payments || 0}</h3>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-xl text-emerald-400">
                  <CheckCircle className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Failed / Dead</p>
                  <h3 className="text-3xl font-bold text-red-400 mt-2">
                    {stats?.failed_payments || 0} <span className="text-sm font-normal text-slate-500">({stats?.dead_letter_queue_count || 0} DLQ)</span>
                  </h3>
                </div>
                <div className="p-3 bg-red-500/10 rounded-xl text-red-400">
                  <XCircle className="w-6 h-6" />
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl glass-card transition-all duration-300">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-slate-400 text-sm font-medium">Processing / Retry</p>
                  <h3 className="text-3xl font-bold text-yellow-400 mt-2">
                    {stats?.processing_payments || 0} <span className="text-sm font-normal text-slate-500">({stats?.retry_queue_count || 0} Retry)</span>
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
            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">RabbitMQ</h4>
                  <p className="text-xs text-slate-400">Message Broker</p>
                </div>
              </div>
              <StatusBadge status={stats?.rabbitmq_status || "unknown"} />
            </div>

            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-red-500/10 rounded-xl text-red-400">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">Redis</h4>
                  <p className="text-xs text-slate-400">Cache & Idempotency</p>
                </div>
              </div>
              <StatusBadge status={stats?.redis_status || "unknown"} />
            </div>

            <div className="glass-panel p-5 rounded-2xl flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-blue-500/10 rounded-xl text-blue-400">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-white">PostgreSQL</h4>
                  <p className="text-xs text-slate-400">Primary Database</p>
                </div>
              </div>
              <StatusBadge status={stats?.postgresql_status || "unknown"} />
            </div>
          </div>

          {/* Data Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-fade-in" style={{ animationDelay: '0.3s' }}>
            
            {/* Recent Payments */}
            <div className="glass-panel rounded-2xl overflow-hidden flex flex-col">
              <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <ListOrdered className="w-4 h-4 text-blue-400" />
                  Recent Payments
                </h3>
              </div>
              <div className="p-0 overflow-x-auto flex-1">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="text-xs text-slate-400 bg-white/[0.02]">
                    <tr>
                      <th className="px-5 py-3 font-medium">ID</th>
                      <th className="px-5 py-3 font-medium">Amount</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {payments.map((p) => (
                      <tr key={p.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-5 py-3 font-mono text-xs">{p.payment_id.split('-')[0]}...</td>
                        <td className="px-5 py-3 font-medium text-white">{p.amount} {p.currency}</td>
                        <td className="px-5 py-3">
                          <span className={`px-2 py-1 rounded text-[10px] font-bold tracking-wider uppercase ${
                            p.status === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400' :
                            p.status === 'FAILED' ? 'bg-red-500/20 text-red-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {p.status}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-500">
                          {new Date(p.created_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))}
                    {payments.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-5 py-8 text-center text-slate-500">No payments yet</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Recent Logs */}
            <div className="glass-panel rounded-2xl overflow-hidden flex flex-col">
              <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-purple-400" />
                  Recent Request Logs
                </h3>
              </div>
              <div className="p-0 overflow-x-auto flex-1">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="text-xs text-slate-400 bg-white/[0.02]">
                    <tr>
                      <th className="px-5 py-3 font-medium">Request ID</th>
                      <th className="px-5 py-3 font-medium">Method</th>
                      <th className="px-5 py-3 font-medium">Path</th>
                      <th className="px-5 py-3 font-medium">Status</th>
                      <th className="px-5 py-3 font-medium">Latency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {logs.map((l) => (
                      <tr key={l.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-5 py-3 font-mono text-xs">{l.request_id.split('-')[0]}...</td>
                        <td className="px-5 py-3 font-bold text-xs">
                          <span className={`px-1.5 py-0.5 rounded ${
                            l.method === 'GET' ? 'bg-blue-500/20 text-blue-400' :
                            l.method === 'POST' ? 'bg-emerald-500/20 text-emerald-400' :
                            'bg-slate-500/20 text-slate-400'
                          }`}>
                            {l.method}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs">{l.path}</td>
                        <td className="px-5 py-3 text-xs">
                          <span className={l.status_code >= 400 ? 'text-red-400' : 'text-emerald-400'}>
                            {l.status_code}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-xs">{l.latency_ms}ms</td>
                      </tr>
                    ))}
                    {logs.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-5 py-8 text-center text-slate-500">No logs yet</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      )}
    </main>
  );
}
