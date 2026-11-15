import crypto from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8000";

// Minimal valid JPEG image bytes with SOI, APP0/JFIF, SOF0 (1x1) & EOI markers for pillow/Content-Type checks.
const VALID_1X1_JPEG = Buffer.from([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01,
  0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43, 0x00, 0x03,
  0x02, 0x02, 0x03, 0x02, 0x02, 0x03, 0x03, 0x03, 0x03, 0x04, 0x03, 0x03, 0x04,
  0x05, 0x08, 0x05, 0x05, 0x04, 0x04, 0x05, 0x0a, 0x07, 0x07, 0x06, 0x08, 0x0c,
  0x0a, 0x0c, 0x0c, 0x0b, 0x0a, 0x0b, 0x0b, 0x0d, 0x0e, 0x12, 0x10, 0x0d, 0x0e,
  0x11, 0x0e, 0x0b, 0x0b, 0x10, 0x16, 0x10, 0x11, 0x13, 0x14, 0x15, 0x15, 0x15,
  0x0c, 0x0f, 0x17, 0x18, 0x16, 0x14, 0x18, 0x12, 0x14, 0x15, 0x14, 0xff, 0xc0,
  0x00, 0x0b, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4,
  0x00, 0x1f, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
  0x07, 0x08, 0x09, 0x0a, 0x0b, 0xff, 0xc4, 0x00, 0xb5, 0x10, 0x00, 0x02, 0x01,
  0x03, 0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d,
  0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13,
  0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08, 0x23, 0x42,
  0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0a,
  0x16, 0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x34, 0x35,
  0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a,
  0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x63, 0x64, 0x65, 0x66, 0x67,
  0x68, 0x69, 0x6a, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x83, 0x84,
  0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98,
  0x99, 0x9a, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2, 0xb3,
  0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7,
  0xc8, 0xc9, 0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1,
  0xe2, 0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf1, 0xf2, 0xf3, 0xf4,
  0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa, 0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00,
  0x00, 0x3f, 0x00, 0xfb, 0xd5, 0x00, 0x00, 0x00, 0x00, 0xff, 0xd9,
]);

function karachiDateToday(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Karachi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

async function seedOfflineSyncedLogWithPhoto(
  ownerEmail: string,
  ownerPassword: string,
  projectId: string,
  logDate: string
): Promise<{ logId: string; photoId: string }> {
  const loginRes = await fetch(`${API_URL}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ownerEmail, password: ownerPassword }),
  });
  expect(loginRes.status).toBe(200);
  const { access_token: token } = (await loginRes.json()) as {
    access_token: string;
  };
  const authHdr = { Authorization: `Bearer ${token}` };

  const logId = crypto.randomUUID();
  const photoId = crypto.randomUUID();

  const resResp = await fetch(`${API_URL}/v1/media/reservations`, {
    method: "POST",
    headers: { ...authHdr, "Content-Type": "application/json" },
    body: JSON.stringify({
      kind: "PHOTO",
      project_id: projectId,
      object_id: photoId,
    }),
  });
  expect(resResp.status).toBe(201);

  const ticketResp = await fetch(`${API_URL}/v1/media/upload-url`, {
    method: "POST",
    headers: { ...authHdr, "Content-Type": "application/json" },
    body: JSON.stringify({
      kind: "PHOTO",
      project_id: projectId,
      object_id: photoId,
      content_type: "image/jpeg",
      byte_size: VALID_1X1_JPEG.length,
    }),
  });
  expect(ticketResp.status).toBe(200);
  const ticket = (await ticketResp.json()) as {
    ticket_id: string;
    upload_url: string;
    storage_uri: string;
  };

  const putUrl = ticket.upload_url.startsWith("http")
    ? ticket.upload_url
    : `${API_URL}${ticket.upload_url}`;
  const putResp = await fetch(putUrl, {
    method: "PUT",
    headers: { "Content-Type": "image/jpeg" },
    body: VALID_1X1_JPEG,
  });
  expect(putResp.status).toBe(200);

  const nowIso = new Date().toISOString();
  const pushResp = await fetch(`${API_URL}/v1/sync/push`, {
    method: "POST",
    headers: { ...authHdr, "Content-Type": "application/json" },
    body: JSON.stringify({
      changes: {
        site_logs: [
          {
            id: logId,
            project_id: projectId,
            log_date: logDate,
            recorded_at: nowIso,
            notes: "Batching plant slab concrete pour complete",
            client_updated_at: nowIso,
          },
        ],
        site_log_photos: [
          {
            id: photoId,
            site_log_id: logId,
            storage_uri: ticket.storage_uri,
            sort_order: 0,
          },
        ],
      },
    }),
  });
  expect(pushResp.status).toBe(200);

  const completeResp = await fetch(`${API_URL}/v1/media/complete`, {
    method: "POST",
    headers: { ...authHdr, "Content-Type": "application/json" },
    body: JSON.stringify({
      kind: "PHOTO",
      object_id: photoId,
      ticket_id: ticket.ticket_id,
    }),
  });
  expect(completeResp.status).toBe(204);

  return { logId, photoId };
}

function attachConsoleAndServerErrorListeners(page: Page, errors: string[]) {
  page.on("pageerror", (err) => {
    errors.push(`pageerror: ${err.message}`);
  });
  page.on("response", (res) => {
    if (res.status() >= 500) {
      errors.push(`HTTP ${res.status()} on ${res.url()}`);
    }
  });
}

test.describe("Commercial readiness full-stack E2E workflows", () => {
  test("signup, invitations, RBAC, projects, offline log/photo, notes, lightbox, permits, PDF, billing usage, session expiration, and auth guards", async ({
    browser,
  }) => {
    const unique = `${Date.now()}-${Math.floor(Math.random() * 10000)}`;
    const ownerEmail = `owner-${unique}@sitediary.pk`;
    const supervisorEmail = `supervisor-${unique}@sitediary.pk`;
    const ownerPass = "OwnerStrong!2026";
    const supervisorPass = "SupervisorStrong!2026";
    const runtimeErrors: string[] = [];

    // 1. Company signup through /register UI
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    attachConsoleAndServerErrorListeners(ownerPage, runtimeErrors);

    await ownerPage.goto("/register");
    await ownerPage.fill("#companyName", `Indus Builders ${unique}`);
    await ownerPage.fill("#fullName", "Kamran Siddiqui");
    await ownerPage.selectOption("#planTier", "PRO");
    await ownerPage.fill("#email", ownerEmail);
    await ownerPage.fill("#password", ownerPass);
    await ownerPage.getByRole("button", { name: "Create Organization & Sign In" }).click();
    await expect(ownerPage).toHaveURL(/\/$/);

    // 2. Organization usage & subscription view (/organization) + seat invitation
    await ownerPage.goto("/organization");
    await expect(ownerPage.getByText("Plan & Quota Usage (PRO)")).toBeVisible();
    await expect(ownerPage.getByText("Active Projects")).toBeVisible();
    await expect(ownerPage.getByText("Active Seats")).toBeVisible();
    await expect(ownerPage.getByText("Media Storage")).toBeVisible();

    // Invite SUPERVISOR user
    await ownerPage.getByPlaceholder("Full name").fill("Tariq Supervisor");
    await ownerPage.getByPlaceholder("email@company.com").fill(supervisorEmail);
    const inviteResponsePromise = ownerPage.waitForResponse(
      (res) =>
        res.url().includes("/api/bff/v1/organization/invitations") &&
        res.request().method() === "POST"
    );
    await ownerPage.getByRole("button", { name: "Invite", exact: true }).click();
    const inviteRes = await inviteResponsePromise;
    expect(inviteRes.status()).toBe(201);
    const inviteJson = (await inviteRes.json()) as {
      invite_token?: string;
      email: string;
    };
    const inviteToken = inviteJson.invite_token;
    expect(inviteToken).toBeTruthy();

    // 3. Project creation via portfolio UI
    await ownerPage.goto("/");
    await ownerPage.getByRole("button", { name: /New Project/i }).first().click();
    await ownerPage.fill("#project-name", "Margalla Steel Frame");
    await ownerPage.fill("#project-address", "Plot 14-B, F-8 Markaz, Islamabad");
    await ownerPage.fill("#project-timezone", "Asia/Karachi");
    await ownerPage.getByRole("button", { name: "Create Project" }).click();
    await expect(ownerPage).toHaveURL(/\/projects\/[0-9a-f-]+$/);
    const projectUrl = ownerPage.url();
    const projectId = projectUrl.split("/projects/")[1]!;

    // 4. Supervisor invite acceptance & RBAC enforcement in isolated context
    const supContext = await browser.newContext();
    const supPage = await supContext.newPage();
    attachConsoleAndServerErrorListeners(supPage, runtimeErrors);

    await supPage.goto(`/invite?token=${encodeURIComponent(inviteToken!)}`);
    await supPage.fill("#invitePassword", supervisorPass);
    await supPage.fill("#confirmInvitePassword", supervisorPass);
    await supPage.getByRole("button", { name: /Accept Invitation/i }).click();
    await expect(supPage).toHaveURL(/\/$/);

    // Supervisor must be blocked from Owner-only /organization page (server redirects to /)
    await supPage.goto("/organization");
    await expect(supPage).toHaveURL(/\/$/);
    expect(supPage.url()).not.toContain("/organization");
    await expect(supPage.getByRole("button", { name: /New Project/i })).toHaveCount(0);
    await expect(supPage.getByRole("link", { name: /Organization/i })).toHaveCount(0);

    // Direct API calls to admin-only organization audit-logs and export endpoints as supervisor must return 403
    const supAdminStatuses = await supPage.evaluate(async () => {
      const [auditResp, exportResp] = await Promise.all([
        fetch("/api/bff/v1/organization/audit-logs"),
        fetch("/api/bff/v1/organization/export"),
      ]);
      return [auditResp.status, exportResp.status];
    });
    expect(supAdminStatuses).toEqual([403, 403]);

    // 5. Sign out + Invalid login error feedback
    await supPage.getByRole("button", { name: /Sign out/i }).click();
    await expect(supPage).toHaveURL(/\/login/);
    await supPage.fill("#email", ownerEmail);
    await supPage.fill("#password", "WrongPassword999");
    await supPage.getByRole("button", { name: "Sign in to Portal" }).click();
    await expect(supPage.getByRole("alert")).toBeVisible();
    await supContext.close();

    // 6. Seed offline-synced diary entry + reserved & completed photo via real API, then verify in owner UI
    const todayKarachi = karachiDateToday();
    await seedOfflineSyncedLogWithPhoto(
      ownerEmail,
      ownerPass,
      projectId,
      todayKarachi
    );
    await ownerPage.goto(`/projects/${projectId}`);
    await expect(
      ownerPage.getByText("Batching plant slab concrete pour complete")
    ).toBeVisible();

    const thumbImg = ownerPage.locator('img[alt^="Log photo"]').first();
    await expect(thumbImg).toBeVisible();
    await expect
      .poll(async () =>
        thumbImg.evaluate((el) => (el as HTMLImageElement).naturalWidth)
      )
      .toBeGreaterThan(0);

    // 7. Lightbox modal inspection
    await thumbImg.click();
    const lightboxImg = ownerPage.locator('div[role="dialog"] img, [aria-modal="true"] img').first();
    await expect(lightboxImg).toBeVisible();
    await ownerPage.keyboard.press("Escape");

    // 8. Edit diary note & verify persistence across reload
    await ownerPage.getByRole("button", { name: "Edit site note" }).first().click();
    await ownerPage
      .getByPlaceholder("Update typed supervisor field notes...")
      .fill("Updated field note: slab curing verified after inspection");
    await ownerPage.getByRole("button", { name: "Save Note" }).click();
    await expect(
      ownerPage.getByText("Updated field note: slab curing verified after inspection")
    ).toBeVisible();
    await ownerPage.reload();
    await expect(
      ownerPage.getByText("Updated field note: slab curing verified after inspection")
    ).toBeVisible();
    await expect(ownerPage.getByText("Edited").first()).toBeVisible();

    // 9. Permit CRUD (Create, Edit, Delete, Keep second permit for PDF export)
    await ownerPage
      .getByRole("button", { name: /Add( First)? Permit/i })
      .first()
      .click();
    await ownerPage.fill("#permit-name", "Tower Crane Permit");
    await ownerPage.fill("#permit-authority", "CDA");
    await ownerPage.fill("#permit-number", "CDA-CRANE-101");
    await ownerPage.fill("#expiry-date", "2027-08-15");
    await ownerPage
      .getByRole("dialog")
      .getByRole("button", { name: "Add Permit" })
      .click();
    await expect(ownerPage.getByText("Tower Crane Permit")).toBeVisible();

    await ownerPage.getByRole("button", { name: "Edit Tower Crane Permit" }).click();
    await ownerPage.fill("#permit-authority", "CDA South Zone");
    await ownerPage
      .getByRole("dialog")
      .getByRole("button", { name: "Save Changes" })
      .click();
    await expect(ownerPage.getByText("CDA South Zone")).toBeVisible();

    await ownerPage.getByRole("button", { name: /Add Permit/i }).first().click();
    await ownerPage.fill("#permit-name", "Hot Work Safety Certificate");
    await ownerPage.fill("#permit-authority", "Labor Dept");
    await ownerPage.fill("#expiry-date", "2027-09-01");
    await ownerPage
      .getByRole("dialog")
      .getByRole("button", { name: "Add Permit" })
      .click();
    await expect(ownerPage.getByText("Hot Work Safety Certificate")).toBeVisible();

    await ownerPage.getByRole("button", { name: "Delete Tower Crane Permit" }).click();
    await ownerPage.getByRole("button", { name: "Confirm" }).click();
    await expect(ownerPage.getByText("Tower Crane Permit")).toHaveCount(0);
    await expect(ownerPage.getByText("Hot Work Safety Certificate")).toBeVisible();

    // 10. Export PDF & verify real PDF binary header
    const pdfResponse = await ownerPage.request.get(
      `/api/reports/${projectId}/${todayKarachi}/pdf`
    );
    expect(pdfResponse.status()).toBe(200);
    expect(pdfResponse.headers()["content-type"]).toContain("application/pdf");
    const pdfBytes = await pdfResponse.body();
    expect(pdfBytes.byteLength).toBeGreaterThan(1000);
    expect(pdfBytes.subarray(0, 5).toString("ascii")).toBe("%PDF-");

    // 11. Project Team Settings tab & assignment
    await ownerPage.getByRole("tab", { name: /Team/i }).click();
    await expect(ownerPage.getByText("Invite Site Supervisor")).toBeVisible();
    await ownerPage.fill("#invite-name", "Bilal Junior Engineer");
    await ownerPage.fill("#invite-email", `bilal-${unique}@sitediary.pk`);
    await ownerPage.getByRole("button", { name: "Add Supervisor" }).click();
    await expect(
      ownerPage.getByText(/One-Time Temporary Password Generated/i)
    ).toBeVisible();

    // 12. Session expiration / cleared cookie handling
    await ownerContext.clearCookies();
    await ownerPage.goto(`/projects/${projectId}`);
    await expect(ownerPage).toHaveURL(/\/login/);
    await ownerPage.goto("/organization");
    await expect(ownerPage).toHaveURL(/\/login\?next=%2Forganization/);

    // 13. Valid login flow back into portal as owner (restores ?next= then loads portfolio)
    await ownerPage.fill("#email", ownerEmail);
    await ownerPage.fill("#password", ownerPass);
    await ownerPage.getByRole("button", { name: "Sign in to Portal" }).click();
    await expect(ownerPage).toHaveURL(/\/organization/);
    await ownerPage.goto("/");
    await expect(ownerPage.getByText("Margalla Steel Frame")).toBeVisible();

    await ownerContext.close();
    expect(runtimeErrors).toEqual([]);
  });
});
