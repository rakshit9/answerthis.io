import type {
  EditProposal, Health, Paper, RenderedDoc, ReviewRun, StyleInfo,
} from "./types";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const body = await r.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* keep status */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then((r) => j<Health>(r)),
  styles: () => fetch("/api/styles").then((r) => j<StyleInfo[]>(r)),

  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/papers", { method: "POST", body: fd })
      .then((r) => j<{ id: string; title: string }>(r));
  },
  papers: () => fetch("/api/papers").then((r) => j<{ id: string; title: string; filename: string; n_references: number; version: number }[]>(r)),
  paper: (id: string) => fetch(`/api/papers/${id}`).then((r) => j<Paper>(r)),
  rendered: (id: string, style?: string) =>
    fetch(`/api/papers/${id}/rendered${style ? `?style=${style}` : ""}`).then((r) => j<RenderedDoc>(r)),
  setStyle: (id: string, style: string) =>
    fetch(`/api/papers/${id}/style`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style }),
    }).then((r) => j<{ ok: boolean }>(r)),

  startResolve: (id: string) =>
    fetch(`/api/papers/${id}/resolve`, { method: "POST" }).then((r) => j<{ started: boolean; todo: number }>(r)),
  resolveStatus: (id: string) =>
    fetch(`/api/papers/${id}/resolve/status`).then((r) => j<{ counts: Record<string, number>; total: number; done: boolean }>(r)),

  startReview: (id: string, scope: Record<string, unknown>) =>
    fetch(`/api/papers/${id}/review`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scope),
    }).then((r) => j<{ run_id: string }>(r)),
  review: (id: string, runId: string) =>
    fetch(`/api/papers/${id}/review/${runId}`).then((r) => j<ReviewRun>(r)),
  reviews: (id: string) => fetch(`/api/papers/${id}/reviews`).then((r) => j<ReviewRun[]>(r)),

  startEdit: (id: string, command: string) =>
    fetch(`/api/papers/${id}/edit`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    }).then((r) => j<{ proposal_id: string }>(r)),
  proposal: (id: string, propId: string) =>
    fetch(`/api/papers/${id}/proposals/${propId}`).then((r) => j<EditProposal>(r)),
  proposals: (id: string) =>
    fetch(`/api/papers/${id}/proposals`).then((r) => j<EditProposal[]>(r)),
  applyProposal: (id: string, propId: string, approvedChangeIds: string[]) =>
    fetch(`/api/papers/${id}/proposals/${propId}/apply`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_change_ids: approvedChangeIds }),
    }).then((r) => j<{ status: string; version: number }>(r)),
  rejectProposal: (id: string, propId: string) =>
    fetch(`/api/papers/${id}/proposals/${propId}/reject`, { method: "POST" }).then((r) => j<{ status: string }>(r)),

  exportZipUrl: (id: string, style?: string) =>
    `/api/papers/${id}/export.zip${style ? `?style=${style}` : ""}`,
  exportTex: (id: string, style?: string) =>
    fetch(`/api/papers/${id}/export/main.tex${style ? `?style=${style}` : ""}`).then((r) => r.text()),
};
