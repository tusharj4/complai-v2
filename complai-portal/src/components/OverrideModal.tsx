"use client";

import { useState } from "react";

interface OverrideModalProps {
  documentId: string;
  onSubmit: (newStatus: string, reason: string) => Promise<void>;
  onClose: () => void;
}

export default function OverrideModal({ documentId, onSubmit, onClose }: OverrideModalProps) {
  const [newStatus, setNewStatus] = useState("compliant");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (reason.length < 5) return;
    setLoading(true);
    await onSubmit(newStatus, reason);
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Override Classification</h3>
        <p className="text-sm text-gray-500 mb-4">Document: {documentId.slice(0, 8)}...</p>

        <label className="block text-sm font-medium text-gray-700 mb-1">New Status</label>
        <select
          value={newStatus}
          onChange={(e) => setNewStatus(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4 text-sm"
        >
          <option value="compliant">Compliant</option>
          <option value="non_compliant">Non-Compliant</option>
          <option value="review_required">Review Required</option>
        </select>

        <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Explain why you are overriding this classification..."
          className="w-full border rounded px-3 py-2 mb-4 text-sm h-24 resize-none"
        />

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || reason.length < 5}
            className="px-4 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Saving..." : "Override"}
          </button>
        </div>
      </div>
    </div>
  );
}
