/**
 * Thin client for the FastAPI backend.
 *
 * Single source of truth for the API base URL and request shapes. UI code
 * never touches `fetch` directly so we can add auth / retries / etc. in one
 * place later.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const fetchInit: RequestInit = { credentials: "include" };

export type DocStatus = "uploaded" | "ingesting" | "indexed" | "failed";

export interface UploadedDocument {
  doc_id: string;
  key: string;
  uri: string;
  size: number;
  content_type: string;
  status: DocStatus;
  syllabus_ready?: boolean;
}

export interface TokenResponse {
  token: string;
  url: string;
  room: string;
  identity: string;
}

async function jsonOrThrow<T>(
  res: Response,
  okStatuses: number[] = [200, 201],
): Promise<T> {
  if (!okStatuses.includes(res.status)) {
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
    ...fetchInit,
  });
  return jsonOrThrow<UploadedDocument>(res);
}

export async function ingestDocument(docId: string): Promise<UploadedDocument> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(docId)}/ingest`,
    { method: "POST", ...fetchInit },
  );
  return jsonOrThrow<UploadedDocument>(res, [200, 202]);
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Poll the library until a document finishes background ingest. */
export async function waitForDocumentReady(
  docId: string,
  opts?: { intervalMs?: number; timeoutMs?: number },
): Promise<UploadedDocument> {
  const intervalMs = opts?.intervalMs ?? 1500;
  const timeoutMs = opts?.timeoutMs ?? 10 * 60_000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const docs = await listDocuments();
    const doc = docs.find((d) => d.doc_id === docId);
    if (doc?.status === "indexed") return doc;
    if (doc?.status === "failed") {
      throw new Error("Document ingestion failed.");
    }
    await sleep(intervalMs);
  }
  throw new Error("Timed out waiting for document ingestion.");
}

export async function listDocuments(): Promise<UploadedDocument[]> {
  const res = await fetch(`${API_BASE}/api/documents`, fetchInit);
  const data = await jsonOrThrow<{ documents: UploadedDocument[] }>(res);
  return data.documents;
}

export function documentFileUrl(docId: string): string {
  return `${API_BASE}/api/documents/${encodeURIComponent(docId)}/file`;
}

/** Fetch PDF bytes with session cookie; use for iframe/embed auth. */
export async function fetchDocumentPdfBlob(docId: string): Promise<string> {
  const res = await fetch(documentFileUrl(docId), fetchInit);
  if (!res.ok) {
    throw new Error(`API ${res.status}: failed to load PDF`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

import type { Syllabus } from "./syllabus";

export async function fetchDocumentSyllabus(docId: string): Promise<Syllabus> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(docId)}/syllabus`,
    fetchInit,
  );
  return jsonOrThrow<Syllabus>(res);
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
    ...fetchInit,
  });
  return jsonOrThrow<TokenResponse>(res);
}
