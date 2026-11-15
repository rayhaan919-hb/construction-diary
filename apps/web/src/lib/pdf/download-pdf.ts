import { parseErrorResponse, getErrorMessage } from "@/lib/problem";

export async function downloadDailyReportPdf(
  projectId: string,
  date: string
): Promise<void> {
  const res = await fetch(`/api/reports/${projectId}/${date}/pdf`, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });

  if (res.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login");
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const err = await parseErrorResponse(res);
    throw new Error(getErrorMessage(err, `Failed to export PDF (${res.status})`));
  }

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/i.exec(disposition);
  const filename = match?.[1] ?? `site-diary-${date}.pdf`;

  const objectUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
