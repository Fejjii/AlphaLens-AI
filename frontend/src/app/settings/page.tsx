"use client";

import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/PageHeader";
import { Separator } from "@/components/ui/separator";

const MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet", "llama-3.1-70b"];
const PROVIDERS = [
  { name: "OpenAI", status: "available" },
  { name: "Anthropic", status: "limited" },
  { name: "Bedrock", status: "standby" },
];
const TOOLS = [
  { key: "market_data", label: "Market data" },
  { key: "portfolio", label: "Portfolio" },
  { key: "risk", label: "Risk" },
  { key: "rag", label: "Retrieval" },
];

export default function SettingsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const [model, setModel] = useState(MODELS[0]);
  const [temperature, setTemperature] = useState(0.2);
  const [topP, setTopP] = useState(0.9);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [enabledTools, setEnabledTools] = useState<Record<string, boolean>>({
    market_data: true,
    portfolio: true,
    risk: true,
    rag: true,
  });

  const enabledToolCount = useMemo(
    () => Object.values(enabledTools).filter(Boolean).length,
    [enabledTools],
  );

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Local model, tool, and provider controls for demos and experimentation."
      />

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Model and generation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SettingRow label="Primary model" hint="Local demo selector only">
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
                className="h-11 rounded-[0.875rem] border border-border bg-background px-3 text-sm"
              >
                {MODELS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </SettingRow>
            <SettingRow label="Temperature" hint="Balancing consistency and creativity">
              <Input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(event) => setTemperature(Number(event.target.value))}
                className="max-w-32"
              />
            </SettingRow>
            <SettingRow label="Top-p" hint="Nucleus sampling">
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={topP}
                onChange={(event) => setTopP(Number(event.target.value))}
                className="max-w-32"
              />
            </SettingRow>
            <SettingRow label="Max tokens" hint="Upper output bound">
              <Input
                type="number"
                min={128}
                max={8192}
                step={64}
                value={maxTokens}
                onChange={(event) => setMaxTokens(Number(event.target.value))}
                className="max-w-40"
              />
            </SettingRow>

            <div className="rounded-[0.875rem] border border-border/60 bg-card/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Current profile</div>
                  <div className="text-xs text-muted-foreground">
                    {model} · temp {temperature.toFixed(1)} · top-p {topP.toFixed(2)} · {maxTokens} tokens
                  </div>
                </div>
                <Badge variant="muted">{enabledToolCount} tools enabled</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Provider status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {PROVIDERS.map((provider) => (
                <div key={provider.name} className="flex items-center justify-between rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5">
                  <span className="text-sm font-medium">{provider.name}</span>
                  <Badge variant={provider.status === "available" ? "success" : provider.status === "limited" ? "warning" : "muted"} className="capitalize">
                    {provider.status}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tool toggles</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {TOOLS.map((tool) => (
                <label
                  key={tool.key}
                  className="flex cursor-pointer items-center justify-between rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5 text-sm"
                >
                  <div>
                    <div className="font-medium">{tool.label}</div>
                    <div className="text-xs text-muted-foreground">{tool.key}</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={enabledTools[tool.key]}
                    onChange={(event) =>
                      setEnabledTools((prev) => ({
                        ...prev,
                        [tool.key]: event.target.checked,
                      }))
                    }
                    className="h-4 w-4 rounded border-border"
                  />
                </label>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Runtime endpoint</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <code className="block rounded-[0.875rem] border border-border/60 bg-muted/70 px-3 py-2 text-xs">
                {apiUrl}
              </code>
              <Separator />
              <div className="text-xs text-muted-foreground">
                Settings stay local for now so chat and approvals remain stable while the backend contract stays unchanged.
              </div>
              <div className="flex gap-2">
                <Button variant="subtle" type="button">
                  Reset local state
                </Button>
                <Button variant="outline" type="button">
                  Save snapshot
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-[0.875rem] border border-border/60 bg-card/60 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{hint}</div>
      </div>
      <div className="w-full sm:max-w-[240px]">{children}</div>
    </div>
  );
}
