import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach token to every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// Auth
export async function getToken(partnerId: string, userId: string) {
  const res = await api.post("/token", { partner_id: partnerId, user_id: userId });
  return res.data;
}

// Companies
export async function getCompanies() {
  const res = await api.get("/api/v1/companies");
  return res.data;
}

export async function getCompany(id: string) {
  const res = await api.get(`/api/v1/companies/${id}`);
  return res.data;
}

export async function createCompany(name: string, gstId: string) {
  const res = await api.post("/api/v1/companies", { name, gst_id: gstId });
  return res.data;
}

// Compliance
export async function getComplianceStatus(companyId: string) {
  const res = await api.get(`/api/v1/companies/${companyId}/compliance-status`);
  return res.data;
}

// Audit Log
export async function getAuditLog(companyId: string, limit = 100, offset = 0) {
  const res = await api.get(`/api/v1/companies/${companyId}/audit-log`, {
    params: { limit, offset },
  });
  return res.data;
}

// Documents
export async function createDocument(companyId: string, documentType: string) {
  const res = await api.post("/api/v1/documents", {
    company_id: companyId,
    document_type: documentType,
  });
  return res.data;
}

// Override
export async function overrideClassification(
  documentId: string,
  newStatus: string,
  reason: string
) {
  const res = await api.post(`/api/v1/documents/${documentId}/override`, {
    new_status: newStatus,
    reason,
  });
  return res.data;
}

// Retry
export async function retryDocument(documentId: string) {
  const res = await api.post(`/api/v1/documents/${documentId}/retry`);
  return res.data;
}

// Scrape
export async function triggerScrape(companyId: string) {
  const res = await api.post(`/api/v1/companies/${companyId}/scrape`);
  return res.data;
}

export default api;
