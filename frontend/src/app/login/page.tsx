"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Lock, Mail } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    setTimeout(() => {
      if (email && password) {
        localStorage.setItem("admin_token", "jwt-mock-admin-token");
        router.push("/agents");
      } else {
        setError("Please enter your admin email and password.");
        setLoading(false);
      }
    }, 400);
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center p-4">
      <Card className="max-w-md w-full shadow-lg border-slate-200">
        <CardHeader className="text-center flex flex-col items-center pb-4 pt-8 border-b-0">
          <div className="w-12 h-12 bg-sky-100 text-sky-700 rounded-2xl flex items-center justify-center mb-3 shadow-2xs">
            <Shield className="w-6 h-6" />
          </div>
          <CardTitle className="text-xl font-bold text-slate-900 justify-center">
            Admin Authentication
          </CardTitle>
          <CardDescription className="text-center max-w-xs mt-1">
            Sign in to access property agent operations, branding, and WhatsApp Cloud controls.
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4 pt-2">
            {error && (
              <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Admin Email Address
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                icon={<Mail className="w-4 h-4" />}
                placeholder="admin@example.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                icon={<Lock className="w-4 h-4" />}
                placeholder="••••••••"
              />
            </div>
          </CardContent>

          <CardFooter className="pt-2 pb-6 px-6 bg-transparent border-t-0 flex flex-col gap-3">
            <Button
              type="submit"
              loading={loading}
              className="w-full"
            >
              Sign In to Console
            </Button>
            <p className="text-[11px] text-slate-400 text-center">
              Internal Enterprise Access Only • Authorized Operator Credentials Required
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
