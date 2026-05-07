"use client";

import { Library, Loader2, RefreshCw, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { KnowledgeDocument, KnowledgeSearchResult, KnowledgeStats } from "@/types/api";

export default function KnowledgeBasePage() {
  const searchParams = useSearchParams();
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [uploading, setUploading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    setRefreshing(true);
    setMessage(null);
    setSearchResults([]);
    try {
      const [statsData, docs] = await Promise.all([api.fetchKnowledgeStats(), api.fetchKnowledgeDocuments()]);
      setStats(statsData);
      setDocuments(docs);
      setRefreshedAt(new Date().toISOString());
    } catch {
      setMessage("Knowledge base could not be loaded.");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const presetQuery = searchParams.get("q");
    if (presetQuery && presetQuery.trim()) {
      setQuery(presetQuery);
    }
  }, [searchParams]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setMessage(null);
    try {
      const result = await api.uploadKnowledgeDocument(file);
      setMessage(
        `Indexed ${result.document.document_title} · ${result.document.chunk_count} chunks · ${result.document.collection}`,
      );
      await refresh();
    } catch {
      setMessage("Upload failed. Supported formats are .md and .txt.");
    } finally {
      setUploading(false);
    }
  };

  const runSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setSearching(true);
    setMessage(null);
    try {
      const response = await api.searchKnowledge({ query: trimmed, k: 6 });
      setSearchResults(response.results);
      if (response.results.length === 0) {
        setMessage("No matching chunks found.");
      }
    } catch {
      setMessage("Search failed.");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        description="Documents indexed for retrieval-augmented generation."
      />
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Indexed corpus</CardTitle>
            <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={refreshing}>
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-[0.875rem] border border-primary/25 bg-primary/10 p-3 text-sm">
              <div className="font-semibold text-foreground">What is inside the knowledge base?</div>
              <p className="mt-1 text-muted-foreground">
                AlphaLens indexes seeded policy/research documents and your uploaded notes for retrieval-augmented answers.
              </p>
              <div className="mt-2 text-xs text-muted-foreground">
                Retrieval mode:{" "}
                <span className="text-foreground">
                  {stats?.vector_mode === "qdrant" ? "Qdrant vector search" : "deterministic lexical fallback"}
                </span>
              </div>
            </div>
            <div className="rounded-[0.875rem] border border-border/70 bg-card/60 p-3 text-sm text-muted-foreground">
              Accepted formats: <span className="text-foreground">.md, .txt</span> · Max file size:{" "}
              <span className="text-foreground">5 MB</span>
            </div>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-[0.875rem] border border-dashed border-border/80 bg-background/40 px-4 py-5 text-sm">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {uploading ? "Uploading..." : "Upload markdown or text document"}
              <input
                type="file"
                accept=".md,.txt,text/plain,text/markdown"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleUpload(file);
                  event.target.value = "";
                }}
              />
            </label>
            {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
            {refreshedAt ? (
              <div className="text-xs text-muted-foreground">
                Refreshed: {new Date(refreshedAt).toLocaleTimeString()}
              </div>
            ) : null}
            <div className="overflow-x-auto rounded-[0.875rem] border border-border/70">
              <table className="table-base">
                <thead>
                  <tr className="table-head-row">
                    <th className="table-head-cell">Document</th>
                    <th className="table-head-cell">Type</th>
                    <th className="table-head-cell">Chunks</th>
                    <th className="table-head-cell">Indexed at</th>
                    <th className="table-head-cell">Source</th>
                    <th className="table-head-cell">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.document_id} className="table-row">
                      <td className="table-cell">{doc.document_title}</td>
                      <td className="table-cell uppercase text-muted-foreground">{doc.file_type}</td>
                      <td className="table-cell tabular">{doc.chunk_count}</td>
                      <td className="table-cell text-muted-foreground">
                        {new Date(doc.indexed_at).toLocaleString()}
                      </td>
                      <td className="table-cell text-muted-foreground">{doc.source}</td>
                      <td className="table-cell capitalize">{doc.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Corpus stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Stat label="Total docs" value={String(stats?.document_count ?? 0)} />
              <Stat label="Total chunks" value={String(stats?.chunk_count ?? 0)} />
              <Stat label="Seeded docs" value={String(stats?.seeded_documents ?? 0)} />
              <Stat label="Uploaded docs" value={String(stats?.uploaded_documents ?? 0)} />
              <Stat label="Collection" value={stats?.collection ?? "—"} />
              <Stat label="Retrieval mode" value={stats?.vector_mode ?? "—"} />
              <StatList
                label="Seeded sources"
                values={stats?.seeded_source_titles ?? []}
                fallback={[
                  "Investment Policy Statement",
                  "Risk Playbook",
                  "AI Infrastructure Thesis",
                  "Portfolio Committee Notes",
                  "Readme",
                ]}
              />
              <StatList
                label="Uploaded sources"
                values={stats?.uploaded_source_titles ?? []}
                fallback={["No uploaded sources yet"]}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Search retrieval test</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search internal policy, risk playbook, committee notes..."
              />
              <Button onClick={() => void runSearch()} disabled={searching || !query.trim()}>
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Library className="h-4 w-4" />}
                Retrieve chunks
              </Button>
              <div className="space-y-2">
                {searchResults.map((result) => (
                  <div key={result.chunk_id} className="rounded-[0.875rem] border border-border/70 bg-background/40 p-3">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-medium">{result.document_title}</span>
                      <span className="tabular text-muted-foreground">{result.score.toFixed(2)}</span>
                    </div>
                    {result.section ? <div className="mt-1 text-xs text-muted-foreground">{result.section}</div> : null}
                    <p className="mt-2 text-sm text-muted-foreground">{result.snippet}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] items-start gap-3 rounded-[0.875rem] border border-border/60 bg-background/40 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  );
}

function StatList({
  label,
  values,
  fallback,
}: {
  label: string;
  values: string[];
  fallback: string[];
}) {
  const items = values.length > 0 ? values : fallback;
  return (
    <div className="grid grid-cols-[9rem_1fr] items-start gap-3 rounded-[0.875rem] border border-border/60 bg-background/40 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-full border border-border/60 bg-card px-2 py-0.5 text-xs text-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
