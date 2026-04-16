"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getCompany,
  getComplianceStatus,
  getAuditLog,
  overrideClassification,
  retryDocument,
  triggerScrape,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import OverrideModal from "@/components/OverrideModal";

export default function CompanyDetailsPage() {
  const params = useParams();
  const companyId = params.id as string;
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [overrideDocId, setOverrideDocId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"compliance" | "audit">("compliance");

  const { data: company } = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => getCompany(companyId),
    enabled: isAuthenticated,
  });

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["compliance", companyId],
    queryFn: () => getComplianceStatus(companyId),
    enabled: isAuthenticated,
    refetchInterval: 10000,
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["audit", companyId],
    queryFn: () => getAuditLog(companyId),
    enabled: isAuthenticated && activeTab === "audit",
  });

  const retryMutation = useMutation({
    mutationFn: retryDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance", companyId] });
    },
  });

  const scrapeMutation = useMutation({
    mutationFn: () => triggerScrape(companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance", companyId] });
    },
  });

  const handleOverride = async (newStatus: string, reason: string) => {
    if (!overrideDocId) return;
    await overrideClassification(overrideDocId, newStatus, reason);
    queryClient.invalidateQueries({ queryKey: ["compliance", companyId] });
    queryClient.invalidateQueries({ queryKey: ["audit", companyId] });
    setOverrideDocId(null);
  };

  if (!isAuthenticated) return null;

  const compliantCount = status?.documents?.filter((d: any) => d.status === "compliant").length || 0;
  const nonCompliantCount = status?.documents?.filter((d: any) => d.status === "non_compliant").length || 0;
  const reviewCount = status?.documents?.filter((d: any) => d.status === "review_required").length || 0;
  const pendingCount = status?.documents?.filter((d: any) => d.status === "pending").length || 0;

  return (
    <div className="min-h-screen">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Company Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{company?.name || "Loading..."}</h1>
            <p className="text-gray-500 mt-1 font-mono">{company?.gst_id}</p>
          </div>
          <div className="flex gap-3">
            <StatusBadge status={status?.overall_status || "pending"} />
            <button
              onClick={() => scrapeMutation.mutate()}
              disabled={scrapeMutation.isPending}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            >
              {scrapeMutation.isPending ? "Scraping..." : "Run Scrape"}
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-sm text-green-600 font-medium">Compliant</p>
            <p className="text-3xl font-bold text-green-700">{compliantCount}</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-600 font-medium">Non-Compliant</p>
            <p className="text-3xl font-bold text-red-700">{nonCompliantCount}</p>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-600 font-medium">Review Required</p>
            <p className="text-3xl font-bold text-yellow-700">{reviewCount}</p>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 font-medium">Pending</p>
            <p className="text-3xl font-bold text-gray-700">{pendingCount}</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <div className="flex gap-8">
            <button
              onClick={() => setActiveTab("compliance")}
              className={`pb-3 text-sm font-medium border-b-2 transition ${
                activeTab === "compliance"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Documents ({status?.total_documents || 0})
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              className={`pb-3 text-sm font-medium border-b-2 transition ${
                activeTab === "audit"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Audit Log
            </button>
          </div>
        </div>

        {/* Compliance Tab */}
        {activeTab === "compliance" && (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            {statusLoading ? (
              <div className="p-8 text-center text-gray-400">Loading documents...</div>
            ) : status?.documents?.length === 0 ? (
              <div className="p-8 text-center text-gray-400">No documents yet.</div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Flags</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Checked</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {status?.documents?.map((doc: any) => (
                    <tr key={doc.document_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="text-sm font-medium text-gray-900">{doc.document_type}</span>
                        <p className="text-xs text-gray-400 font-mono">{doc.document_id.slice(0, 8)}...</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={doc.status} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {doc.confidence > 0 ? `${(doc.confidence * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {doc.flags?.map((flag: string) => (
                            <span key={flag} className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                              {flag}
                            </span>
                          ))}
                          {(!doc.flags || doc.flags.length === 0) && <span className="text-xs text-gray-400">None</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {doc.last_checked ? new Date(doc.last_checked).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => retryMutation.mutate(doc.document_id)}
                          disabled={retryMutation.isPending}
                          className="text-xs text-blue-600 hover:text-blue-800 mr-3"
                        >
                          Retry
                        </button>
                        <button
                          onClick={() => setOverrideDocId(doc.document_id)}
                          className="text-xs text-purple-600 hover:text-purple-800"
                        >
                          Override
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Audit Log Tab */}
        {activeTab === "audit" && (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            {!auditLogs ? (
              <div className="p-8 text-center text-gray-400">Loading audit log...</div>
            ) : auditLogs.length === 0 ? (
              <div className="p-8 text-center text-gray-400">No audit events yet.</div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Event</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {auditLogs.map((log: any) => (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm font-medium text-gray-900">{log.event_type}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 font-mono">
                        {log.document_id ? `${log.document_id.slice(0, 8)}...` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <details className="text-xs text-gray-500">
                          <summary className="cursor-pointer hover:text-gray-700">View details</summary>
                          <pre className="mt-2 bg-gray-50 p-2 rounded text-xs overflow-auto max-w-md">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </main>

      {/* Override Modal */}
      {overrideDocId && (
        <OverrideModal
          documentId={overrideDocId}
          onSubmit={handleOverride}
          onClose={() => setOverrideDocId(null)}
        />
      )}
    </div>
  );
}
