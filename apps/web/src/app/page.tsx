import React from "react";
import { redirect } from "next/navigation";
import { serverApiFetch } from "@/lib/server-api";
import { ApiError } from "@/lib/problem";
import type { ProjectSummary, User } from "@/lib/types";
import { PortfolioView } from "@/components/portfolio/portfolio-view";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let user: User | null = null;
  let initialProjects: ProjectSummary[] | null = null;
  let initialError: string | null = null;

  try {
    const [me, projects] = await Promise.all([
      serverApiFetch<User>("/v1/me"),
      serverApiFetch<ProjectSummary[]>("/v1/projects"),
    ]);
    user = me;
    initialProjects = projects;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    initialError =
      err instanceof Error ? err.message : "Failed to load portfolio from API";
  }

  if (user?.must_change_password) {
    redirect("/change-password");
  }

  return (
    <PortfolioView
      user={user}
      initialProjects={initialProjects}
      initialError={initialError}
    />
  );
}
