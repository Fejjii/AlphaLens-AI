"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Create your AlphaLens AI account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Input
              placeholder="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
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
            disabled={submitting || !fullName || !email || password.length < 8}
            onClick={async () => {
              setSubmitting(true);
              setError(null);
              try {
                await register({ full_name: fullName, email, password });
                router.replace("/");
              } catch {
                setError("Unable to create the account. Try a different email.");
              } finally {
                setSubmitting(false);
              }
            }}
          >
            {submitting ? "Creating account..." : "Create account"}
          </Button>
          <Button variant="ghost" className="w-full" onClick={() => router.push("/login")}>
            Already have an account
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
