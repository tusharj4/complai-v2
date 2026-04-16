"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCompanies, createCompany } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import Header from "@/components/Header";
import CompanyCard from "@/components/CompanyCard";

export default function CompaniesPage() {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [gstId, setGstId] = useState("");
  const [formError, setFormError] = useState("");

  const { data: companies, isLoading, error } = useQuery({
    queryKey: ["companies"],
    queryFn: getCompanies,
    enabled: isAuthenticated,
  });

  const createMutation = useMutation({
    mutationFn: () => createCompany(name, gstId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      setShowForm(false);
      setName("");
      setGstId("");
      setFormError("");
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || "Failed to create company");
    },
  });

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Companies</h1>
            <p className="text-gray-500 mt-1">
              {companies?.length || 0} companies managed
            </p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
          >
            + Add Company
          </button>
        </div>

        {showForm && (
          <div className="bg-white border border-gray-200 rounded-lg p-6 mb-8">
            <h2 className="text-lg font-semibold mb-4">Add New Company</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                <input
                  type="text"
                  name="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Acme Pvt Ltd"
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">GST ID</label>
                <input
                  type="text"
                  name="gst_id"
                  value={gstId}
                  onChange={(e) => setGstId(e.target.value.toUpperCase())}
                  placeholder="27AABAA0000A1Z5"
                  maxLength={15}
                  className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                />
              </div>
            </div>
            {formError && <p className="text-red-500 text-sm mt-2">{formError}</p>}
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || !name || !gstId}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="text-gray-600 px-4 py-2 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border rounded-lg p-5 animate-pulse">
                <div className="h-5 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-4 bg-gray-100 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg">
            Failed to load companies. Please try again.
          </div>
        )}

        {companies && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {companies.map((company: any) => (
              <CompanyCard key={company.id} company={company} />
            ))}
            {companies.length === 0 && !showForm && (
              <div className="col-span-full text-center py-16 text-gray-400">
                No companies yet. Click &quot;Add Company&quot; to get started.
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
