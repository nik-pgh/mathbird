/**
 * Thin client for the FastAPI backend.
 *
 * Single source of truth for the API base URL and request shapes. UI code
 * never touches `fetch` directly so we can add auth / retries / etc. in one
 * place later.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type DocStatus = "uploaded" | "indexed" | "failed";

export interface UploadedDocument {
  doc_id: string;
  key: string;
  uri: string;
  size: number;
  content_type: string;
  status: DocStatus;
}

export interface TokenResponse {
  token: string;
  url: string;
  room: string;
  identity: string;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadPdf(file: File): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/documents`, {
    method: "POST",
    body: form,
  });
  return jsonOrThrow<UploadedDocument>(res);
}

export async function ingestDocument(docId: string): Promise<UploadedDocument> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(docId)}/ingest`,
    { method: "POST" },
  );
  return jsonOrThrow<UploadedDocument>(res);
}

export async function listDocuments(): Promise<UploadedDocument[]> {
  const res = await fetch(`${API_BASE}/api/documents`);
  const data = await jsonOrThrow<{ documents: UploadedDocument[] }>(res);
  return data.documents;
}

export function documentFileUrl(docId: string): string {
  return `${API_BASE}/api/documents/${encodeURIComponent(docId)}/file`;
}

export async function requestToken(opts?: {
  identity?: string;
  room?: string;
  name?: string;
  doc_id?: string;
}): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/api/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts ?? {}),
  });
  return jsonOrThrow<TokenResponse>(res);
}
