import React from "react";
import { redirect } from "next/navigation";
import { serverApiFetch } from "@/lib/server-api";
import { ApiError, getErrorMessage } from "@/lib/problem";
import { getTodayInTimezone } from "@/lib/format";
import type {
  DailyReport,
  Member,
  Permit,
  Project,
  TimelineResponse,
  User,
} from "@/lib/types";
import { ProjectDashboardView } from "@/components/project/project-dashboard-view";

export const dynamic = "force-dynamic";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let user: User | null = null;
  try {
    user = await serverApiFetch<User>("/v1/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
  }

  if (user?.must_change_password) {
    redirect("/change-password");
  }

  let project: Project | null = null;
  let projectError: string | null = null;

  try {
    project = await serverApiFetch<Project>(`/v1/projects/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    projectError = getErrorMessage(err, "Failed to load project");
  }

  const todayDate = getTodayInTimezone(project?.timezone ?? "Asia/Karachi");

  let permits: Permit[] | null = null;
  let permitsError: string | null = null;
  let todayReport: DailyReport | null = null;
  let todayError: string | null = null;
  let timeline: TimelineResponse | null = null;
  let timelineError: string | null = null;
  let members: Member[] | null = null;
  let membersError: string | null = null;

  if (project) {
    const [permitsRes, todayRes, timelineRes, membersRes] =
      await Promise.allSettled([
        serverApiFetch<Permit[]>(`/v1/projects/${id}/permits`),
        serverApiFetch<DailyReport>(`/v1/projects/${id}/days/${todayDate}`),
        serverApiFetch<TimelineResponse>(`/v1/projects/${id}/timeline?days=7`),
        serverApiFetch<Member[]>(`/v1/projects/${id}/members`),
      ]);

    if (permitsRes.status === "fulfilled") {
      permits = permitsRes.value;
    } else {
      permitsError = getErrorMessage(
        permitsRes.reason,
        "Failed to load permits"
      );
    }

    if (todayRes.status === "fulfilled") {
      todayReport = todayRes.value;
    } else {
      todayError = getErrorMessage(
        todayRes.reason,
        "Failed to load today's rollup"
      );
    }

    if (timelineRes.status === "fulfilled") {
      timeline = timelineRes.value;
    } else {
      timelineError = getErrorMessage(
        timelineRes.reason,
        "Failed to load timeline"
      );
    }

    if (membersRes.status === "fulfilled") {
      members = membersRes.value;
    } else {
      membersError = getErrorMessage(
        membersRes.reason,
        "Failed to load team members"
      );
    }
  }

  return (
    <ProjectDashboardView
      projectId={id}
      user={user}
      initialProject={project}
      initialProjectError={projectError}
      initialTodayDate={todayDate}
      initialPermits={permits}
      initialPermitsError={permitsError}
      initialTodayReport={todayReport}
      initialTodayError={todayError}
      initialTimeline={timeline}
      initialTimelineError={timelineError}
      initialMembers={members}
      initialMembersError={membersError}
    />
  );
}
