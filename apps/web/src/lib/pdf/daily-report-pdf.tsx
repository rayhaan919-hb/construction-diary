import React from "react";
import {
  Document,
  Image,
  Page,
  StyleSheet,
  Text,
  View,
  renderToBuffer,
} from "@react-pdf/renderer";
import type { DailyReport, Permit, Project, SiteLog } from "@/lib/types";
import {
  formatCountdown,
  formatDateShort,
  formatDurationMs,
  formatTimeInZone,
  getLanguageLabel,
  getTextDirection,
} from "@/lib/format";
import { ensurePdfFontsRegistered } from "./fonts";

export interface DailyReportPdfProps {
  project: Project;
  report: DailyReport;
  permits: Permit[];
  photoDataUris: Map<string, string>;
  generatedAtIso: string;
}

const styles = StyleSheet.create({
  page: {
    fontFamily: "Inter",
    fontSize: 9.5,
    color: "#0F172A",
    backgroundColor: "#FFFFFF",
    paddingTop: 28,
    paddingBottom: 34,
    paddingHorizontal: 28,
  },
  accentBar: {
    height: 4,
    backgroundColor: "#D97706",
    marginBottom: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingBottom: 10,
    marginBottom: 14,
  },
  titleGroup: {
    maxWidth: "65%",
  },
  eyebrow: {
    fontFamily: "JetBrainsMono",
    fontSize: 7.5,
    fontWeight: 700,
    color: "#D97706",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: 3,
  },
  projectTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "#0F172A",
    marginBottom: 3,
  },
  subtitle: {
    fontSize: 8.5,
    color: "#475569",
    lineHeight: 1.35,
  },
  metaBox: {
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#F8FAFC",
    borderRadius: 4,
    padding: 8,
    minWidth: 155,
  },
  metaLabel: {
    fontSize: 7.5,
    color: "#64748B",
    textTransform: "uppercase",
    marginBottom: 2,
  },
  metaValueMono: {
    fontFamily: "JetBrainsMono",
    fontSize: 10,
    fontWeight: 700,
    color: "#0F172A",
    marginBottom: 4,
  },
  metaSubMono: {
    fontFamily: "JetBrainsMono",
    fontSize: 7.5,
    color: "#475569",
  },
  sectionHeading: {
    fontSize: 10,
    fontWeight: 700,
    color: "#0F172A",
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: 6,
    marginTop: 10,
  },
  warningBanner: {
    borderWidth: 1,
    borderColor: "#F59E0B",
    backgroundColor: "#FFFBEB",
    borderRadius: 4,
    padding: 8,
    marginBottom: 10,
  },
  warningTitle: {
    fontSize: 8.5,
    fontWeight: 700,
    color: "#92400E",
    marginBottom: 2,
  },
  warningBody: {
    fontSize: 8,
    color: "#78350F",
  },
  table: {
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 4,
    marginBottom: 12,
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#F8FAFC",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingVertical: 5,
    paddingHorizontal: 8,
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingVertical: 5,
    paddingHorizontal: 8,
    alignItems: "center",
  },
  tableRowLast: {
    borderBottomWidth: 0,
  },
  th: {
    fontSize: 7.5,
    fontWeight: 700,
    color: "#475569",
    textTransform: "uppercase",
  },
  td: {
    fontSize: 8.5,
    color: "#0F172A",
  },
  tdMono: {
    fontFamily: "JetBrainsMono",
    fontSize: 8,
    color: "#334155",
  },
  colName: { width: "28%", paddingRight: 6 },
  colAuth: { width: "22%", paddingRight: 6 },
  colNum: { width: "16%", paddingRight: 6 },
  colExp: { width: "16%", paddingRight: 6 },
  colStatus: { width: "18%" },
  kpiGrid: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 10,
  },
  kpiBox: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#F8FAFC",
    borderRadius: 4,
    padding: 8,
  },
  kpiLabel: {
    fontSize: 7.5,
    fontWeight: 600,
    color: "#64748B",
    textTransform: "uppercase",
    marginBottom: 3,
  },
  kpiValue: {
    fontFamily: "JetBrainsMono",
    fontSize: 15,
    fontWeight: 700,
    color: "#0F172A",
  },
  summaryCols: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  summaryCard: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 4,
    padding: 8,
    backgroundColor: "#FFFFFF",
  },
  summaryCardTitle: {
    fontSize: 8,
    fontWeight: 700,
    color: "#334155",
    textTransform: "uppercase",
    marginBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingBottom: 3,
  },
  bulletItem: {
    fontSize: 8.5,
    color: "#0F172A",
    lineHeight: 1.35,
    marginBottom: 2,
  },
  mutedText: {
    fontSize: 8,
    color: "#64748B",
  },
  logCard: {
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 4,
    padding: 8,
    marginBottom: 8,
    backgroundColor: "#FFFFFF",
  },
  logHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingBottom: 4,
    marginBottom: 6,
  },
  logMetaLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  monoPill: {
    fontFamily: "JetBrainsMono",
    fontSize: 8,
    fontWeight: 700,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 3,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  authorText: {
    fontSize: 9,
    fontWeight: 600,
    color: "#0F172A",
  },
  transcriptBox: {
    marginTop: 5,
    padding: 6,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#F8FAFC",
    borderRadius: 3,
  },
  transcriptLabel: {
    fontSize: 7.5,
    fontWeight: 600,
    color: "#64748B",
    marginBottom: 2,
  },
  transcriptText: {
    fontSize: 8.5,
    color: "#0F172A",
    lineHeight: 1.4,
  },
  transcriptRtl: {
    fontFamily: "NotoNaskhArabic",
    fontSize: 9.5,
    color: "#0F172A",
    textAlign: "right",
    lineHeight: 1.5,
  },
  photoRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 6,
  },
  photoThumb: {
    width: 96,
    height: 72,
    objectFit: "cover",
    borderRadius: 3,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  footer: {
    position: "absolute",
    bottom: 14,
    left: 28,
    right: 28,
    flexDirection: "row",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: "#E2E8F0",
    paddingTop: 5,
    fontSize: 7.5,
    color: "#64748B",
  },
});

function permitStatusColor(status: Permit["status"]): string {
  switch (status) {
    case "ACTIVE":
      return "#059669";
    case "EXPIRING_SOON":
      return "#EA580C";
    case "EXPIRED":
      return "#DC2626";
  }
}

function LogBreakdownItem({
  log,
  timezone,
  photoDataUris,
}: {
  log: SiteLog;
  timezone: string;
  photoDataUris: Map<string, string>;
}) {
  const timeStr = formatTimeInZone(log.recorded_at, timezone);
  const summary = log.structured_summary;
  const isRtl =
    getTextDirection(log.detected_language, log.transcript) === "rtl";
  const photos = (log.photos ?? [])
    .map((p) => ({ id: p.id, uri: photoDataUris.get(p.id) }))
    .filter((p): p is { id: string; uri: string } => Boolean(p.uri));

  return (
    <View style={styles.logCard}>
      <View style={styles.logHeader} wrap={false}>
        <View style={styles.logMetaLeft}>
          <Text style={styles.monoPill}>{timeStr}</Text>
          <Text style={styles.authorText}>
            {log.author_name ?? "Site Supervisor"}
          </Text>
          <Text style={styles.monoPill}>{log.extraction_status}</Text>
          {log.edited_by_human && <Text style={styles.monoPill}>EDITED</Text>}
          {log.audio_duration_ms !== null &&
            log.audio_duration_ms !== undefined && (
              <Text style={styles.tdMono}>
                {formatDurationMs(log.audio_duration_ms)}
              </Text>
            )}
        </View>
        {summary?.labor_count !== null && summary?.labor_count !== undefined && (
          <Text style={styles.monoPill}>{summary.labor_count} workers</Text>
        )}
      </View>

      {summary ? (
        <View style={{ gap: 2 }}>
          {summary.tasks_completed.length > 0 && (
            <Text style={styles.bulletItem}>
              <Text style={{ fontWeight: 700 }}>Tasks: </Text>
              {summary.tasks_completed.join("; ")}
            </Text>
          )}
          {summary.material_deliveries.length > 0 && (
            <Text style={styles.bulletItem}>
              <Text style={{ fontWeight: 700 }}>Deliveries: </Text>
              {summary.material_deliveries.join("; ")}
            </Text>
          )}
          {summary.blockers.length > 0 && (
            <Text style={[styles.bulletItem, { color: "#9A3412" }]}>
              <Text style={{ fontWeight: 700 }}>Blockers: </Text>
              {summary.blockers.join("; ")}
            </Text>
          )}
        </View>
      ) : (
        <Text style={styles.mutedText}>
          No structured extraction available ({log.extraction_status}).
        </Text>
      )}

      {log.notes && (
        <Text style={[styles.bulletItem, { marginTop: 3 }]}>
          <Text style={{ fontWeight: 700 }}>Note: </Text>
          {log.notes}
        </Text>
      )}

      {log.transcript && (
        <View style={styles.transcriptBox}>
          <Text style={styles.transcriptLabel}>
            Original Transcript ({getLanguageLabel(log.detected_language)})
          </Text>
          <Text style={isRtl ? styles.transcriptRtl : styles.transcriptText}>
            {log.transcript}
          </Text>
        </View>
      )}

      {photos.length > 0 && (
        <View style={styles.photoRow}>
          {photos.map((photo) => (
            // eslint-disable-next-line jsx-a11y/alt-text
            <Image
              key={photo.id}
              src={photo.uri}
              style={styles.photoThumb}
            />
          ))}
        </View>
      )}
    </View>
  );
}

export function DailyReportDocument({
  project,
  report,
  permits,
  photoDataUris,
  generatedAtIso,
}: DailyReportPdfProps) {
  const generatedLabel = formatTimeInZone(generatedAtIso, project.timezone);

  return (
    <Document
      title={`Site Diary - ${project.name} - ${report.log_date}`}
      author="Site Diary Owner Portal"
    >
      <Page size="A4" style={styles.page}>
        <View style={styles.accentBar} />

        {/* Project Header */}
        <View style={styles.headerRow}>
          <View style={styles.titleGroup}>
            <Text style={styles.eyebrow}>Daily Site Diary &amp; Permit Report</Text>
            <Text style={styles.projectTitle}>{project.name}</Text>
            <Text style={styles.subtitle}>{project.site_address}</Text>
            {project.owner_phone && (
              <Text style={[styles.subtitle, { fontFamily: "JetBrainsMono" }]}>
                Owner Phone: {project.owner_phone}
              </Text>
            )}
          </View>

          <View style={styles.metaBox}>
            <Text style={styles.metaLabel}>Report Date (Project Local)</Text>
            <Text style={styles.metaValueMono}>
              {report.log_date} ({formatDateShort(report.log_date)})
            </Text>
            <Text style={styles.metaSubMono}>TZ: {project.timezone}</Text>
            <Text style={styles.metaSubMono}>
              Generated: {generatedLabel}
            </Text>
          </View>
        </View>

        {/* Pending Extraction Notice */}
        {report.pending_extraction_count > 0 && (
          <View style={styles.warningBanner}>
            <Text style={styles.warningTitle}>
              Pending Voice Extractions ({report.pending_extraction_count})
            </Text>
            <Text style={styles.warningBody}>
              {report.pending_extraction_count} site log(s) for this date have not completed AI extraction yet. Daily totals may update once processing finishes.
            </Text>
          </View>
        )}

        {/* Permit Snapshot Table */}
        <Text style={styles.sectionHeading}>Permit Compliance Snapshot</Text>
        {permits.length === 0 ? (
          <View style={[styles.table, { padding: 8 }]}>
            <Text style={styles.mutedText}>
              No permits registered for this project.
            </Text>
          </View>
        ) : (
          <View style={styles.table}>
            <View style={styles.tableHeader}>
              <Text style={[styles.th, styles.colName]}>Permit</Text>
              <Text style={[styles.th, styles.colAuth]}>Authority</Text>
              <Text style={[styles.th, styles.colNum]}>Permit #</Text>
              <Text style={[styles.th, styles.colExp]}>Expiry</Text>
              <Text style={[styles.th, styles.colStatus]}>Status</Text>
            </View>
            {permits.map((permit, idx) => (
              <View
                key={permit.id}
                style={[
                  styles.tableRow,
                  idx === permits.length - 1 ? styles.tableRowLast : {},
                ]}
              >
                <Text style={[styles.td, styles.colName]}>
                  {permit.permit_name}
                </Text>
                <Text style={[styles.td, styles.colAuth]}>
                  {permit.authority}
                </Text>
                <Text style={[styles.tdMono, styles.colNum]}>
                  {permit.permit_number || "—"}
                </Text>
                <Text style={[styles.tdMono, styles.colExp]}>
                  {permit.expiry_date}
                </Text>
                <Text
                  style={[
                    styles.tdMono,
                    styles.colStatus,
                    { color: permitStatusColor(permit.status), fontWeight: 700 },
                  ]}
                >
                  {permit.status} ({formatCountdown(permit.days_to_expiry)})
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Daily Summary Rollup */}
        <Text style={styles.sectionHeading}>Daily Operational Summary</Text>
        <View style={styles.kpiGrid}>
          <View style={styles.kpiBox}>
            <Text style={styles.kpiLabel}>Peak Crew (labor_max)</Text>
            <Text style={styles.kpiValue}>
              {report.labor_max !== null && report.labor_max !== undefined
                ? String(report.labor_max)
                : "—"}
            </Text>
          </View>
          <View style={styles.kpiBox}>
            <Text style={styles.kpiLabel}>Total Site Logs</Text>
            <Text style={styles.kpiValue}>{String(report.log_count)}</Text>
          </View>
          <View style={styles.kpiBox}>
            <Text style={styles.kpiLabel}>Open Blockers</Text>
            <Text
              style={[
                styles.kpiValue,
                { color: report.blockers.length > 0 ? "#EA580C" : "#059669" },
              ]}
            >
              {String(report.blockers.length)}
            </Text>
          </View>
        </View>

        <View style={styles.summaryCols}>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryCardTitle}>Tasks Completed</Text>
            {report.tasks_completed.length === 0 ? (
              <Text style={styles.mutedText}>No tasks recorded.</Text>
            ) : (
              report.tasks_completed.map((task, idx) => (
                <Text key={idx} style={styles.bulletItem}>
                  • {task}
                </Text>
              ))
            )}
          </View>

          <View style={styles.summaryCard}>
            <Text style={styles.summaryCardTitle}>Material Deliveries</Text>
            {report.material_deliveries.length === 0 ? (
              <Text style={styles.mutedText}>No deliveries recorded.</Text>
            ) : (
              report.material_deliveries.map((mat, idx) => (
                <Text key={idx} style={styles.bulletItem}>
                  • {mat}
                </Text>
              ))
            )}
          </View>

          <View style={styles.summaryCard}>
            <Text style={styles.summaryCardTitle}>Blockers</Text>
            {report.blockers.length === 0 ? (
              <Text style={styles.mutedText}>No blockers flagged.</Text>
            ) : (
              report.blockers.map((blocker, idx) => (
                <Text
                  key={idx}
                  style={[styles.bulletItem, { color: "#9A3412" }]}
                >
                  • {blocker}
                </Text>
              ))
            )}
          </View>
        </View>

        {/* Per-note Breakdown */}
        <Text style={styles.sectionHeading}>
          Per-Note Field Breakdown ({report.logs.length})
        </Text>
        {report.logs.length === 0 ? (
          <View style={styles.logCard}>
            <Text style={styles.mutedText}>
              No supervisor logs were recorded for {report.log_date}.
            </Text>
          </View>
        ) : (
          report.logs.map((log) => (
            <LogBreakdownItem
              key={log.id}
              log={log}
              timezone={project.timezone}
              photoDataUris={photoDataUris}
            />
          ))
        )}

        <View style={styles.footer} fixed>
          <Text>
            Site Diary Owner Portal · Project {project.id}
          </Text>
          <Text
            render={({ pageNumber, totalPages }) =>
              `Page ${pageNumber} / ${totalPages}`
            }
          />
        </View>
      </Page>
    </Document>
  );
}

export async function renderDailyReportPdfBuffer(
  props: DailyReportPdfProps
): Promise<Buffer> {
  ensurePdfFontsRegistered();
  return renderToBuffer(<DailyReportDocument {...props} />);
}
