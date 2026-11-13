import React from "react";
import { redirect } from "next/navigation";
import { serverApiFetch } from "@/lib/server-api";
import { ApiError } from "@/lib/problem";
import type { User } from "@/lib/types";
import { ChangePasswordView } from "@/components/auth/change-password-view";

export const dynamic = "force-dynamic";

export default async function ChangePasswordPage() {
  let user: User | null = null;
  let initialError: string | null = null;

  try {
    user = await serverApiFetch<User>("/v1/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    initialError =
      err instanceof Error ? err.message : "Failed to load user profile";
  }

  return <ChangePasswordView user={user} initialError={initialError} />;
}
