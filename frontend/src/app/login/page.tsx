"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const nextPath = searchParams.get("next") || "/";

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Sign in to AlphaLens AI</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Input
              placeholder="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button
            className="w-full"
            disabled={submitting || !email || !password}
            onClick={async () => {
              setSubmitting(true);
              setError(null);
              try {
                await login({ email, password });
                router.replace(nextPath);
              } catch {
                setError("Unable to sign in with those credentials.");
              } finally {
                setSubmitting(false);
              }
            }}
          >
            {submitting ? "Signing in..." : "Sign in"}
          </Button>
          <Button variant="ghost" className="w-full" onClick={() => router.push("/register")}>
            Create account
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
