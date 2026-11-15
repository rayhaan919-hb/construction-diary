import { randomUUID } from "node:crypto";
import { getTodayInTimezone } from "./format";
import type {
  AuditLogItem,
  BillingCheckoutResponse,
  DailyReport,
  ExtractQueueResponse,
  InviteMemberResponse,
  Member,
  Organization,
  OrganizationInvitation,
  OrganizationMember,
  OrganizationUsage,
  Permit,
  PermitHealth,
  PermitInput,
  PermitPatch,
  PermitStatus,
  PlanTier,
  Project,
  ProjectInput,
  ProjectPatch,
  ProjectSummary,
  Role,
  SiteLog,
  TokenPair,
  UploadTicket,
  User,
} from "./types";

const DEMO_PHOTO_SLAB_URI =
  "data:image/jpeg;base64,/9j/2wBDAAsLCwsMCw0ODg0SExETEhoYFhYYGiccHhweHCc8JSslJSslPDVANDA0QDVfSkJCSl9tXFdcbYR2doSnnqfa2v//2wBDAQsLCwsMCw0ODg0SExETEhoYFhYYGiccHhweHCc8JSslJSslPDVANDA0QDVfSkJCSl9tXFdcbYR2doSnnqfa2v//wgARCACgAPADASIAAhEBAxEB/8QAGwABAAIDAQEAAAAAAAAAAAAAAAMEAgUGAQf/xAAaAQEBAAMBAQAAAAAAAAAAAAAAAwECBgQF/9oADAMBAAIQAxAAAAD6EPd84AAAAAAAAAAAAAAAAAAABXsarweu4ovme68oi8ojKorfO93QKL6PhvKIvKI23uGfQfHDbAAAAAAAAAGo1G31HM9D1w6bngAAAAAAAAAAAANRqNvqOZ6Hrh03PAAAOG7nhsbcdJ2W+j6vlFu/9cPgt+h96Y+Ex77Q5fcRbyAAAAajUbfUcz0PXDpueAAAcM0+ta1vTJ2y6PmhW67mhlUss4+0OGbw7lww7lwnuNu6cMzr3Lhh0WooYfB+39AcM+98TuXBSY27lwzOvcuGGsVEPZbVBLLSknS0qqTtKotKos4wZD2OadMPJsqTqrYqLYqLYo5yzTpUW1J1VoBWR5jjOE1bONplfzfSyqMZtqgtqglmo5zpbVFJ21QW1QWsYMjzOOWdMPJsqTrLQqLYq+W4dN/MpVZYZettQzgACGaGaVQrIAACGaGaVQrIABDNDKswrIAAAYkc0ck6BSYAAEM0M0qhWQH/xABGEAAABAEHCAQJCgcBAAAAAAAAAQIDBAURFEFSU5ESExUhMDGhogY0grIQIDNAUXOBg7EWIjI1QkRUYWLCI0NFYHGT0cH/2gAIAQEAAT8A/slUXDpUaTXrI5j1GKZDXnAxTIa84GKZDXnAxTIa84GKZDXnAxTIa84GI2MVmk0Zz5+Vr1Ve0QsZGZ9Gfc/h659Rf+CmQ15wMUyGvOBimQ15wMUyGvOBimQ15wMUyGvOBhJkpJKLcZTlt3IF1bi1EpExqMxo960gaPetIGj3rSBo960gaPetIGj3rSBFMqhWyWsyMjVNqDCyfdS0icjVPvxGj3rSBo960gaPetIGj3rSBo960gaPetIDaTQ2hJ7ySRebS11VHrS+BiS+vM9run57LXVUetL4GJL68z2u6fnstdVR60vgYkvrzPa7p+ey11VHrS+BiS+vM9runsumf3D3v7QxCRUTlZhh13J35CDVNgHZPj2UG47CPoQW9Sm1ERBpp15ZNtNqWs9yUlOZ4DRUqfgIn/UrwaKlT8BE/wCpQdadZWbbrakLLelRTGWO0lrqqPWl8DEl9eZ7XdPZdM/uHvf2joR/UPc/uHSf6jjPd98h0Y+vIP3ncPxOk/15Ge77hbSWuqo9aXwMSX15ntd09l0z+4e9/aJKlqKkrPZhDSs7kz5ZH9kR/SaPj4RyGdaYJC5pzSSp9RziAjXYCLbiWkpNaJ5iVu1lMPlnKlzDYK/74PlnKlzDYK/6I+Ndj4tyJdSklrmnJO7UU20lrqqPWl8DEl9eZ7XdPY6YlK/5UiVXo2PzOWrLyMqyW8UOJu+JChxN3xIUSILejiQokRY4kKHE3fEhQ4m74kKHE3fEhQ4m74kNMSlf8qRpiUr/AJUjTEpX/KkaYlK/5UhUtSilJnn+VIKWZSMiPP8AKkaYlK/5UjTEpX/KkaYlK/5UjTEpX/KkOSlFPpyX3MpJHORZJFrCItbSiW0ZpWW45iGmJSv+VI0xKV/ypCZalM3HCpG6b7CRpiUr/lSNMSlf8qRpiUr/AJUjTEpX/KkaYlK/5U+K99Cb0mRAimLx5yKsZxFtOIedbNtREtJn/kZ9kv5hClMWxS2LXAUxn9R+wUtNTa8BSVVMuYCkO1Q6hnog9zHEZcXdJxCTictcxIytWUJoy02QyIu9TgM1E1v8BmHa4hQoyq33MRSVVMOYCkO1Q6hnoipjiMuLuk4hRxKlJI0oIy1kJoy02QyIu9TgM1EHvf4DMPVxCsBRlVvrxFETW45iKG1Waj9oojFk8RRWLHEw4y0nIyUEU6iIZlm7TgM23YTgMlJVF46PKu9nZI1urP0TFsl63Gi/Mz2E5FWQzjdtOIS42TjhmtMxzVikM3hClMWxS2LXAUxqrKP2Clpqbcw8M5FWDcQX2ixDTjZJM1LSRmZnvFIZvCFKYtilsWuApjP6j9gpaam14CkqqZcwFIdqh1DPRFTHEZcXdJxE8SbhfNQSiLgJoy02QyIu9TgM1E1v8BmHq4hWAoyq314iiJrccxFDarNR+0URiyeIorFjiYQy1nHCyCmKaYZlm7TgM23YTgMlJVF4aImtxzEUNqs1H7RRGLJ4hyHZQgzJGsFDszFOgjMEy1dpwGbbsJwExFUXjp1vOfkRFskeVd7Oxd1qbT6VT4bNrWpw/wBU2GyR5V3s7Etbx/pT8dmx9Cf0mZ7JHlXezsWdeWr0q2SjmSZ/kGSmbT/jZI8q72fG/8QANBEAAQMBAwgIBgMAAAAAAAAAAQACAxESE5EEBRQgUVJTkiExMkFUcqHRECIwNWGyQHGB/9oACAECAQE/AP4uXzZZExhyWESEnpBC03Pngmcp91pufPBM5T7rTc+eCZyn3U2W510tlppY+raRgkNP+VWm588EzlPutNz54JnKfdabnzwTOU+6YXFjS4UJAqPp5b94g88f18t+8QeePVd1KvTRE0RNNfLfvEHnj1SehUVAqfCoVQrbbVnvpVVCqFleTzvznDK2Mlgcyp/oqoTXhwqNpGBoqhVCvo9pwKvm7r+UpslZHusP7h1bFeO4T/RW5OEcQrUvDHMqzbrOYpt8ZXn5OoBUm3mYFWZeIOVWJOKcArt3Ff6KKOrT87+27v8AyVct3n8xVzHsOJ+BIHeonsDAS4C0ScVfRcRuKv4t8K+j2nAq+buv5SmSfNIbDzV2zYFeO4T/AEVuThHEK1LwxzKs26zEqK+smljtu/Yqk28zAqzLxByq4i3ApYoxG6jG1PQOjvPQhHGOpgwVAO7Uh7FdrnH11YewfO/9jqP6Xxt/NcNUmgJUIpEzyjVh7B87/wBj8f/EADURAAEDAQMICAYDAQAAAAAAAAEAAgMRE1GRBAUSICFSU9EUMTJBVHKSoRAiMDWCskBhYnH/2gAIAQMBAT8A/i5JHk0jnCeQsAGyi6LmrxLsRyXRc1eJdiOS6LmrxLsRyUWS5D0Z+jouZR1ZCASF0XNXiXYjkui5q8S7Ecl0XNXiXYjknABxANRXZ9PI/tM3lk+vkf2mbyyarO2FTYgEBXXyP7TN5ZNVrCHAqq2/GzdeFZuvCsX6OlspWis3XhWbrwsmliZm6WJzwHlr6D/oVm68J0LmmhI6gcRVWbrwrN14VhJcMQrF3e5g/IJ0VI2N02d5671Zt4rPdaEfFGBWjDxT6VSDff6RzTrERMHz0JJ7lWDdfiOS0oeGfUtOPhDEq0bwme6llo4fIzsM7v8AIVs7dZ6QreS8YD4AE9QKlY8yEBpIaA3quVjLw3YKwm3CrCS4YhWLu9zB+QT4vljGmwUbfeVZt4rPdaEfFGBWjDxT6VSDef6RzUtjpCun2GXboVYN1+I5LSh4Z9St5t8qKWV0jayOoNp29w2oySHrecVUnvOpN26XNaPbVm7Y8jP1GpHsZI7+qY6oFSApjWWTzHVm7Y8jP1Hx/9k=";

const DEMO_PHOTO_WALL_URI =
  "data:image/jpeg;base64,/9j/2wBDAAsLCwsMCw0ODg0SExETEhoYFhYYGiccHhweHCc8JSslJSslPDVANDA0QDVfSkJCSl9tXFdcbYR2doSnnqfa2v//2wBDAQsLCwsMCw0ODg0SExETEhoYFhYYGiccHhweHCc8JSslJSslPDVANDA0QDVfSkJCSl9tXFdcbYR2doSnnqfa2v//wgARCACgAPADASIAAhEBAxEB/8QAGwABAAMBAQEBAAAAAAAAAAAAAAMEBQIHBgH/xAAaAQEAAwEBAQAAAAAAAAAAAAAAAwQFAgEG/9oADAMBAAIQAxAAAAD0wWYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGJt/N0retezdKeIJoQAKNKzm5eh9INTPAAUb2bDNW2/m/pIJQu1APwR9+JlGTi9p/PbWfd5q/lKxDeUViC8oi8ojYs5d3I06ai18y8oi8oi9ax7tefUzLmLXmvKN7Qpe2CPsPPfE6lviXivs52pn3KFLSq2Ia6wsQV1gV1gS3ILWRp4aw18yusCusCvditV558bcy681e3x3oU/bBF2B4nRvQS8QbWZr59zOpaVSxDAnWIIE4gTia7XuZGngp2vmQJxAnEF2G3XnsYu9kV5oL0E+hT9sEXYHicE9GXifXwdrPuV6k1KxDOgWIJ0AnQDSuZ13I08xA18ydBLz10u0IbHVvNuuNHI08WvNPPRvaFP2wRdgeJ8dpeONTO08+5Tq3atiHh2sQcOxw7E9qCzkaeS7a+ZxrZl2hpaFWzQxPoM+1Ba+i+Uny9bMrzcdmhT9sEXfwDKQywphDMcdccTOvIUzryFMIUw47IZIUyaOFMIUwh77c+oZnPsKZ3zqsoB56AAAAAAAAAAAAAB//EADYQAAAEAgcHAQcFAQEAAAAAAAACAxMBUQQFERJigrEhMDRDUqHBgQYQFSAxVKI1QURgsjNx/9oACAEBAAE/AP77XFLpFGYZPdvXrdkIirllF6Gkooa00b1sfXcVisohQ1VEzWGhdsj6ip6XSKS+8e9du2bIQ3FYrKIUNVRM1hoXbI+oqel0ikvvHvXbtmyEN37Qfxc/gVR+noZv9R3Fb/p6+X/UB7P/AMrJ53Fb/p6+X/UB7P8A8rJ53dXc3KKZxKnppuKHxKfroKx5WbcUPiU/XQVjys27qfn5fIrHjFcum4q7jEs2grjkZvG4q7jEs2grjkZvG5aPINHkKpKYr9uHyKwIeNLVjCEtA0eQaPINHkGjyDR5Bo8g0eQq8h4UtKMYT0FbFMZizF4DR5Bo8g0eQaPINHkGjyDR5CryHhS0oxhPQVsUxmLMXgNHkGjy+d0kw6SYqwxTPWYRTTkhSlIRjLQOkmHSTDpJh0kw6SYdJMOkmKEckaUnCEZ6CszFKzbiDpJh0kw6SYdJMOkmHSTDpJihHJGlJwhGegrMxSs24g6SYdJPc1Pz8vkVjxiuXTcVdxiWbQVxyM3jcVdxiWbQVxyM3jcsYgxiFVkuPbekU5K9SlI2y0DGIMYgxiDGIMYgxiDGIUFK7Sk42z0FaEvs7eoMYgxiDGIMYgxiDGIMYhQUrtKTjbPQVoS+zt6gxiDGL538Ifwiqz33tnSKcrdpSkLJaB/CH8Ifwh/CH8Ifwh/CKCrepScLJ6CtD3GdnUH8Ifwh/CH8Ifwh/CH8IoKt6lJwsnoK0PcZ2dQfwh/Duan5+XyKx4xXLpuKu4xLNoK45Gbx8iKKixrpID4Yaz/rC3/wLIqImunh7qu4xLNoK45GbxuWiSDRJCrClK9ZhFNISNKUjGEtA0SQaJINEkGiSDRJBokg0SQoRCQpScYQnoKzKUzNuINEkGiSDRJChplIjaWH1j7qYmU6NpofSIaJIUIhIUpOMIT0FZlKZm3EGiSDRJbmrublFM4lT003FD4lP10FY8rN8lFXgWFw0bIftEXoWW2wsFKXgeFwsbYfvH3UPiU/XQVjys3zfG6z+4/Ao+N1n9x+BQwl094hhLp7xDCXT3iEbiN66X6hRNNQ8TxLtiGEunvEMJdPeIYS6e8Qwl094hhLp7xDCXT3iGEunvEJpppngeBdsAtcWu3i/QMJdPeIYS6e8Qwl094hhLp7xDCXT3iGEunvEMJdPeITTTTPA8C7YBa4tdvF+gYS6e8Qwl094hhLp7xHxus/uPwKPjdZ/cfgX+t//8QALBEAAQIDBgYCAgMAAAAAAAAAAQIDAAQ0BRESIFFzEDE1grGyIsIhcUBBUP/aAAgBAgEBPwD/AALSWtEk6pCikjDcQbjziWJVLMEkkltJJP6yOuOC1pdAWoILZJTf+P7yTJKZZ8gkENqII/UWata5JpS1FROK8k3nnxxHhalC92+wiUpZfaR4yPdYlto/bJN0sxtL8RZdCz3ex4YjxtShe7fYRKUsvtI8ZHusS20ftkm6WY2l+IsuhZ7vY5bUoXu32ESlLL7SPGR7rEttH7ZJulmNpfiLLoWe72OW1KF7t9hEpSy+0jxke6xLbR+3BSkoSVKIAHMmGpqXeUUtuAmJulmNpfiLLoWe72OW1KF7t9hEpSy+0jxke6xLbR+3C0m3HJYhAJIUCRqIkWnVzLZSD8VAkxN0sxtL8RZdCz3ex43nWMStTDiA6goXeUnmL4T8EpSkkAAACMStTGJWpjErUwWkKeS8QcaRcDeYxK1MYlamMStTCvmlSVEkEEEQ2gNICEXhI5C+MStTF51/gf/EACsRAAECAwcEAgIDAAAAAAAAAAECAwA0sQQFESBRc4IQEjXBIkEhcTFAUP/aAAgBAwEBPwD/AALClKrU2FAEHH8H9Q+AH3QBgAtVcjaEG7nllI7gsYH7+sjABfaBGIK01i3JSm1OBIAAw/A/XXAdLvm2uVItEw9uKrka8Y/uD1ks8wzuJrF4TbvGnTAdbvm2uVItEw9uKrka8Y/uD1ks8wzuJrF4TbvGmW75trlSLRMPbiq5GvGP7g9ZLPMM7iaxeE27xplu+ba5Ui0TD24quRrxj+4PXRKVLUEpBJP8AQ9Y7SwkKcaIGsWeYZ3E1i8Jt3jTLd821ypFomHtxVcjXjH9weul1OtNWsFwgApIBP0YvF5pFkdCyMVJISNTFnmGdxNYvCbd4064DSO0aCEKLawtGAUIV8lFRAJJxMdo0Edo0Edo0EBxQbU2D8CcSMI7RoI7RoI7RoIT8VBQABBxELUXFla8Cox2jQRgNP6H/9k=";

const DEMO_PHOTO_STEEL_URI =
  "data:image/jpeg;base64,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";

export const DEMO_USER_ID = "00000000-0000-4000-8000-000000000001";
export const DEMO_SUPERVISOR_ONE_ID = "00000000-0000-4000-8000-000000000002";
export const DEMO_SUPERVISOR_TWO_ID = "00000000-0000-4000-8000-000000000003";

export const DEMO_PROJECT_ONE_ID = "11111111-1111-4111-8111-111111111101";
export const DEMO_PROJECT_TWO_ID = "11111111-1111-4111-8111-111111111102";
export const DEMO_PROJECT_THREE_ID = "11111111-1111-4111-8111-111111111103";

export const DEMO_USER: User = {
  id: DEMO_USER_ID,
  email: "owner@sitediary.demo",
  full_name: "Kamran Siddiqui",
  role: "OWNER",
  preferred_locale: "en",
  must_change_password: false,
};

interface DemoPermitRecord {
  id: string;
  project_id: string;
  permit_name: string;
  authority: string;
  permit_number: string | null;
  issue_date: string | null;
  expiry_date: string;
  document_photo_uri: string | null;
  document_photo_url: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  server_version: number;
}

interface DemoStore {
  projects: Project[];
  permits: DemoPermitRecord[];
  members: Member[];
  logs: SiteLog[];
  organization: Organization;
  orgMembers: OrganizationMember[];
  invitations: OrganizationInvitation[];
  auditLogs: AuditLogItem[];
  versionCounter: number;
}

declare global {
  var __siteDiaryDemoStore: DemoStore | undefined;
}

export function shiftIsoDate(isoDate: string, deltaDays: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
  if (!match) return isoDate;
  const dt = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + deltaDays)
  );
  return dt.toISOString().slice(0, 10);
}

function daysBetweenIso(fromDate: string, toDate: string): number {
  const parse = (val: string): number => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(val.trim());
    if (!m) return 0;
    return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  };
  return Math.round((parse(toDate) - parse(fromDate)) / (1000 * 60 * 60 * 24));
}

export function derivePermit(record: DemoPermitRecord, timezone: string): Permit {
  const localToday = getTodayInTimezone(timezone);
  const daysToExpiry = daysBetweenIso(localToday, record.expiry_date);
  let status: PermitStatus = "ACTIVE";
  if (daysToExpiry < 0) {
    status = "EXPIRED";
  } else if (daysToExpiry <= 14) {
    status = "EXPIRING_SOON";
  }
  return {
    ...record,
    status,
    days_to_expiry: daysToExpiry,
  };
}

function buildDemoJwt(user: User, ttlSeconds: number): string {
  const encodePart = (obj: object): string =>
    Buffer.from(JSON.stringify(obj)).toString("base64url");
  const header = encodePart({ alg: "none", typ: "JWT" });
  const nowSec = Math.floor(Date.now() / 1000);
  const payload = encodePart({
    sub: user.id,
    email: user.email,
    role: user.role,
    must_change_password: user.must_change_password,
    iat: nowSec,
    exp: nowSec + ttlSeconds,
  });
  return `${header}.${payload}.demo`;
}

export function createDemoTokenPair(emailOverride?: string): TokenPair {
  const user: User = emailOverride
    ? { ...DEMO_USER, email: emailOverride.trim() || DEMO_USER.email }
    : { ...DEMO_USER };
  const refreshExpires = new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString();
  return {
    access_token: buildDemoJwt(user, 900),
    refresh_token: `demo-rt-${randomUUID()}`,
    access_expires_in: 900,
    refresh_expires_at: refreshExpires,
    user,
  };
}

function makeIsoTimestamp(logDate: string, utcHourMinute: string): string {
  return `${logDate}T${utcHourMinute}:00Z`;
}

function buildInitialDemoStore(): DemoStore {
  const tz = "Asia/Karachi";
  const today = getTodayInTimezone(tz);
  const y1 = shiftIsoDate(today, -1);
  const y2 = shiftIsoDate(today, -2);
  const y4 = shiftIsoDate(today, -4);
  const y6 = shiftIsoDate(today, -6);
  const y7 = shiftIsoDate(today, -7);
  const y9 = shiftIsoDate(today, -9);
  const y11 = shiftIsoDate(today, -11);

  const projects: Project[] = [
    {
      id: DEMO_PROJECT_ONE_ID,
      name: "Margalla Heights Mixed-Use Tower",
      site_address: "Plot 14-B, F-8 Markaz, Islamabad",
      owner_phone: "+92 300 5550148",
      timezone: tz,
      allow_photo_gps: true,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -65), "05:00"),
      updated_at: makeIsoTimestamp(today, "10:15"),
      deleted_at: null,
      server_version: 24,
    },
    {
      id: DEMO_PROJECT_TWO_ID,
      name: "Clifton Coastal Residences",
      site_address: "Block 4, Marine Promenade, Clifton, Karachi",
      owner_phone: "+92 321 5550192",
      timezone: tz,
      allow_photo_gps: false,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -42), "06:30"),
      updated_at: makeIsoTimestamp(today, "08:40"),
      deleted_at: null,
      server_version: 18,
    },
    {
      id: DEMO_PROJECT_THREE_ID,
      name: "Lahore Cold-Chain Logistics Hub",
      site_address: "Plot 88-C, Sundar Industrial Estate, Lahore",
      owner_phone: "+92 333 5550174",
      timezone: tz,
      allow_photo_gps: true,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -30), "07:00"),
      updated_at: makeIsoTimestamp(today, "09:05"),
      deleted_at: null,
      server_version: 15,
    },
  ];

  const permits: DemoPermitRecord[] = [
    {
      id: "22222222-2222-4222-8222-222222222101",
      project_id: DEMO_PROJECT_ONE_ID,
      permit_name: "CDA Deep Excavation & Shoring Permit",
      authority: "Capital Development Authority (CDA)",
      permit_number: "CDA-BLD-2026-0419",
      issue_date: shiftIsoDate(today, -85),
      expiry_date: shiftIsoDate(today, 5),
      document_photo_uri: "local://demo/permits/cda-shoring.jpg",
      document_photo_url: DEMO_PHOTO_WALL_URI,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -85), "06:00"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -12), "09:00"),
      deleted_at: null,
      server_version: 3,
    },
    {
      id: "22222222-2222-4222-8222-222222222102",
      project_id: DEMO_PROJECT_ONE_ID,
      permit_name: "IESCO Temporary Transformer & Site Power",
      authority: "IESCO",
      permit_number: "IESCO-TMP-8812",
      issue_date: shiftIsoDate(today, -40),
      expiry_date: shiftIsoDate(today, 48),
      document_photo_uri: null,
      document_photo_url: null,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -40), "07:15"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -40), "07:15"),
      deleted_at: null,
      server_version: 1,
    },
    {
      id: "22222222-2222-4222-8222-222222222201",
      project_id: DEMO_PROJECT_TWO_ID,
      permit_name: "SBCA High-Rise Structural Approval",
      authority: "Sindh Building Control Authority (SBCA)",
      permit_number: "SBCA-KHI-2026-994",
      issue_date: shiftIsoDate(today, -50),
      expiry_date: shiftIsoDate(today, 62),
      document_photo_uri: "local://demo/permits/sbca-approval.jpg",
      document_photo_url: DEMO_PHOTO_SLAB_URI,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -50), "05:30"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -15), "08:00"),
      deleted_at: null,
      server_version: 2,
    },
    {
      id: "22222222-2222-4222-8222-222222222202",
      project_id: DEMO_PROJECT_TWO_ID,
      permit_name: "SEPA Coastal Dewatering Clearance",
      authority: "Sindh EPA",
      permit_number: "SEPA-DEV-3310",
      issue_date: shiftIsoDate(today, -35),
      expiry_date: shiftIsoDate(today, 29),
      document_photo_uri: null,
      document_photo_url: null,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -35), "08:00"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -35), "08:00"),
      deleted_at: null,
      server_version: 1,
    },
    {
      id: "22222222-2222-4222-8222-222222222301",
      project_id: DEMO_PROJECT_THREE_ID,
      permit_name: "PIEDMC Industrial Shed Fire & Egress NOC",
      authority: "Punjab Industrial Estates (PIEDMC)",
      permit_number: "PIEDMC-SIE-1182",
      issue_date: shiftIsoDate(today, -94),
      expiry_date: shiftIsoDate(today, -4),
      document_photo_uri: "local://demo/permits/piedmc-noc.jpg",
      document_photo_url: DEMO_PHOTO_STEEL_URI,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -94), "06:00"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -10), "11:00"),
      deleted_at: null,
      server_version: 4,
    },
    {
      id: "22222222-2222-4222-8222-222222222302",
      project_id: DEMO_PROJECT_THREE_ID,
      permit_name: "Rescue 1122 Hydrant Compliance Certificate",
      authority: "Punjab Emergency Service",
      permit_number: "R1122-LHR-502",
      issue_date: shiftIsoDate(today, -50),
      expiry_date: shiftIsoDate(today, 9),
      document_photo_uri: null,
      document_photo_url: null,
      created_by: DEMO_USER_ID,
      created_at: makeIsoTimestamp(shiftIsoDate(today, -50), "09:00"),
      updated_at: makeIsoTimestamp(shiftIsoDate(today, -50), "09:00"),
      deleted_at: null,
      server_version: 1,
    },
  ];

  const members: Member[] = [
    {
      project_id: DEMO_PROJECT_ONE_ID,
      user_id: DEMO_USER_ID,
      role: "OWNER",
      full_name: DEMO_USER.full_name,
      email: DEMO_USER.email,
      deleted_at: null,
      server_version: 1,
    },
    {
      project_id: DEMO_PROJECT_ONE_ID,
      user_id: DEMO_SUPERVISOR_ONE_ID,
      role: "SUPERVISOR",
      full_name: "Tariq Mahmood",
      email: "tariq.mahmood@sitediary.demo",
      deleted_at: null,
      server_version: 2,
    },
    {
      project_id: DEMO_PROJECT_ONE_ID,
      user_id: DEMO_SUPERVISOR_TWO_ID,
      role: "SUPERVISOR",
      full_name: "Bilal Ahmed",
      email: "bilal.ahmed@sitediary.demo",
      deleted_at: null,
      server_version: 3,
    },
    {
      project_id: DEMO_PROJECT_TWO_ID,
      user_id: DEMO_USER_ID,
      role: "OWNER",
      full_name: DEMO_USER.full_name,
      email: DEMO_USER.email,
      deleted_at: null,
      server_version: 4,
    },
    {
      project_id: DEMO_PROJECT_TWO_ID,
      user_id: DEMO_SUPERVISOR_TWO_ID,
      role: "SUPERVISOR",
      full_name: "Bilal Ahmed",
      email: "bilal.ahmed@sitediary.demo",
      deleted_at: null,
      server_version: 5,
    },
    {
      project_id: DEMO_PROJECT_THREE_ID,
      user_id: DEMO_USER_ID,
      role: "OWNER",
      full_name: DEMO_USER.full_name,
      email: DEMO_USER.email,
      deleted_at: null,
      server_version: 6,
    },
    {
      project_id: DEMO_PROJECT_THREE_ID,
      user_id: DEMO_SUPERVISOR_ONE_ID,
      role: "SUPERVISOR",
      full_name: "Tariq Mahmood",
      email: "tariq.mahmood@sitediary.demo",
      deleted_at: null,
      server_version: 7,
    },
  ];

  const logs: SiteLog[] = [
    // ---- Project 1: Today (EN voice + UR voice + typed afternoon update)
    {
      id: "33333333-3333-4333-8333-333333333101",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: today,
      recorded_at: makeIsoTimestamp(today, "04:15"),
      notes: "Weather: Clear & Mild (24°C, light NW breeze) · Slump test 95mm verified",
      audio_uri: "local://demo/audio/margalla-morning.m4a",
      audio_duration_ms: 78000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(today, "04:17"),
      transcript:
        "Morning crew mobilized on Tower B podium slab. Completed rebar stirrup tying for grid lines B3 through B7 and verified cover blocks with the structural resident engineer. Received 40 bags of Maple Leaf OPC cement and 3 tons of Grade-60 deformed steel bars. Tower crane slewing brake alarm tripped twice before lunch; electrician inspecting limit switch.",
      detected_language: "en",
      structured_summary: {
        tasks_completed: [
          "Completed rebar stirrup tying on Tower B podium slab (grids B3-B7)",
          "Resident engineer signed off 40mm cover blocks and MEP sleeves",
        ],
        labor_count: 28,
        material_deliveries: [
          "40 bags Maple Leaf OPC cement",
          "3.0 tons Grade-60 deformed steel bars (16mm / 20mm)",
        ],
        blockers: [
          "Tower crane slewing brake limit switch fault under electrical inspection",
        ],
      },
      edited_by_human: false,
      photos: [
        {
          id: "44444444-4444-4444-8444-444444444101",
          site_log_id: "33333333-3333-4333-8333-333333333101",
          storage_uri: "local://demo/photos/margalla-slab-rebar.jpg",
          upload_status: "UPLOADED",
          url: DEMO_PHOTO_SLAB_URI,
          width: 240,
          height: 160,
          byte_size: 2786,
          taken_at: makeIsoTimestamp(today, "04:12"),
          sort_order: 0,
          deleted_at: null,
          server_version: 10,
        },
      ],
      client_updated_at: makeIsoTimestamp(today, "04:15"),
      created_at: makeIsoTimestamp(today, "04:15"),
      updated_at: makeIsoTimestamp(today, "04:17"),
      deleted_at: null,
      server_version: 10,
    },
    {
      id: "33333333-3333-4333-8333-333333333102",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: today,
      recorded_at: makeIsoTimestamp(today, "06:45"),
      notes: "Weather: Sunny (26°C, low humidity) · Basement B2 north retaining wall",
      audio_uri: "local://demo/audio/margalla-urdu-retaining.m4a",
      audio_duration_ms: 54000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(today, "06:46"),
      transcript:
        "آج بیسمنٹ بی ٹو کی شمالی دیوار پر شٹرنگ اور واٹر اسٹاپر کی تنصیب مکمل کر لی گئی ہے۔ چونتیس مزدور اور مستری موقع پر کام کر رہے ہیں، لارنس پور ریت کے دو ڈمپر اور کرش بجری پہنچ چکی ہے۔ مغربی حصے میں ڈی واٹرنگ پمپ کا پریشر کم ہونے کی وجہ سے کھدائی عارضی طور پر رکی ہوئی ہے۔",
      detected_language: "ur",
      structured_summary: {
        tasks_completed: [
          "Installed shuttering and PVC water-stopper along Basement B2 north retaining wall",
        ],
        labor_count: 34,
        material_deliveries: [
          "2 dumpers washed Lawrencepur sand",
          "18 cu. yd. Margalla crush aggregate (1/2 in)",
        ],
        blockers: [
          "Dewatering pump pressure drop pausing west-wing trench excavation",
        ],
      },
      edited_by_human: false,
      photos: [
        {
          id: "44444444-4444-4444-8444-444444444102",
          site_log_id: "33333333-3333-4333-8333-333333333102",
          storage_uri: "local://demo/photos/margalla-retaining-wall.jpg",
          upload_status: "UPLOADED",
          url: DEMO_PHOTO_WALL_URI,
          width: 240,
          height: 160,
          byte_size: 2396,
          taken_at: makeIsoTimestamp(today, "06:43"),
          sort_order: 0,
          deleted_at: null,
          server_version: 11,
        },
      ],
      client_updated_at: makeIsoTimestamp(today, "06:45"),
      created_at: makeIsoTimestamp(today, "06:45"),
      updated_at: makeIsoTimestamp(today, "06:46"),
      deleted_at: null,
      server_version: 11,
    },
    {
      id: "33333333-3333-4333-8333-333333333103",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: today,
      recorded_at: makeIsoTimestamp(today, "10:15"),
      notes: "Weather: Clear evening (22°C) · Afternoon crane load check & shift handoff",
      audio_uri: null,
      audio_duration_ms: null,
      audio_upload_status: "NONE",
      extraction_status: "DONE",
      extraction_attempts: 0,
      extraction_error: null,
      extraction_model: null,
      extracted_at: null,
      transcript: null,
      detected_language: null,
      structured_summary: {
        tasks_completed: [
          "Replaced crane slewing limit switch and verified dry-run load test",
        ],
        labor_count: 34,
        material_deliveries: [],
        blockers: [],
      },
      edited_by_human: true,
      photos: [],
      client_updated_at: makeIsoTimestamp(today, "10:15"),
      created_at: makeIsoTimestamp(today, "10:15"),
      updated_at: makeIsoTimestamp(today, "10:15"),
      deleted_at: null,
      server_version: 12,
    },
    // ---- Project 1: Yesterday & prior days (for timeline & pagination)
    {
      id: "33333333-3333-4333-8333-333333333104",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: y1,
      recorded_at: makeIsoTimestamp(y1, "11:20"),
      notes: "Weather: Partly cloudy (23°C) · Podium waterproofing membrane test",
      audio_uri: "local://demo/audio/margalla-y1.m4a",
      audio_duration_ms: 46000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(y1, "11:21"),
      transcript:
        "بیسمنٹ کی بیرونی دیوار پر بٹومین واٹر پروفنگ کی پہلی تہہ مکمل ہو گئی ہے اور سریا باندھنے کا کام جاری ہے۔",
      detected_language: "ur",
      structured_summary: {
        tasks_completed: [
          "Applied first bitumen waterproofing coat on Basement B2 perimeter",
          "Continued column starter-bar alignment across grid B",
        ],
        labor_count: 31,
        material_deliveries: ["12 drums elastomeric bitumen primer"],
        blockers: [],
      },
      edited_by_human: false,
      photos: [],
      client_updated_at: makeIsoTimestamp(y1, "11:20"),
      created_at: makeIsoTimestamp(y1, "11:20"),
      updated_at: makeIsoTimestamp(y1, "11:21"),
      deleted_at: null,
      server_version: 9,
    },
    {
      id: "33333333-3333-4333-8333-333333333105",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: y2,
      recorded_at: makeIsoTimestamp(y2, "12:00"),
      notes: "Weather: Windy (21°C, gusts 24 km/h) · Ready-mix slump & cube sampling",
      audio_uri: "local://demo/audio/margalla-y2.m4a",
      audio_duration_ms: 61000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(y2, "12:02"),
      transcript:
        "Poured 42 cubic meters of 4000 PSI concrete for lift core foundation cap. Cast 6 compression test cubes for 7-day and 28-day lab testing.",
      detected_language: "en",
      structured_summary: {
        tasks_completed: [
          "Poured 42 m³ 4000 PSI ready-mix concrete for lift core footing",
          "Sampled 6 compression cubes for lab testing",
        ],
        labor_count: 29,
        material_deliveries: ["42 m³ 4000 PSI RMC transit mixers (6 loads)"],
        blockers: [],
      },
      edited_by_human: false,
      photos: [
        {
          id: "44444444-4444-4444-8444-444444444103",
          site_log_id: "33333333-3333-4333-8333-333333333105",
          storage_uri: "local://demo/photos/margalla-y2.jpg",
          upload_status: "UPLOADED",
          url: DEMO_PHOTO_SLAB_URI,
          width: 240,
          height: 160,
          byte_size: 2786,
          taken_at: makeIsoTimestamp(y2, "11:55"),
          sort_order: 0,
          deleted_at: null,
          server_version: 8,
        },
      ],
      client_updated_at: makeIsoTimestamp(y2, "12:00"),
      created_at: makeIsoTimestamp(y2, "12:00"),
      updated_at: makeIsoTimestamp(y2, "12:02"),
      deleted_at: null,
      server_version: 8,
    },
    {
      id: "33333333-3333-4333-8333-333333333106",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: y4,
      recorded_at: makeIsoTimestamp(y4, "10:10"),
      notes: "Weather: Light rain (19°C) · Audio uploaded while compressor ran nearby",
      audio_uri: "local://demo/audio/margalla-y4-noisy.m4a",
      audio_duration_ms: 33000,
      audio_upload_status: "UPLOADED",
      extraction_status: "FAILED",
      extraction_attempts: 2,
      extraction_error:
        "Background generator noise obscured speech segments; retry extraction or edit manually.",
      extraction_model: "gemini-2.5-flash",
      extracted_at: null,
      transcript: null,
      detected_language: null,
      structured_summary: null,
      edited_by_human: false,
      photos: [],
      client_updated_at: makeIsoTimestamp(y4, "10:10"),
      created_at: makeIsoTimestamp(y4, "10:10"),
      updated_at: makeIsoTimestamp(y4, "10:12"),
      deleted_at: null,
      server_version: 7,
    },
    {
      id: "33333333-3333-4333-8333-333333333107",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: y6,
      recorded_at: makeIsoTimestamp(y6, "09:30"),
      notes: "Weather: Clear (25°C) · Perimeter hoarding & safety signage audit",
      audio_uri: "local://demo/audio/margalla-y6.m4a",
      audio_duration_ms: 42000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(y6, "09:31"),
      transcript:
        "Completed perimeter hoarding inspection and installed reflective PPE warning boards at Gate 1 and Gate 2.",
      detected_language: "en",
      structured_summary: {
        tasks_completed: [
          "Inspected perimeter safety hoarding and installed PPE signage",
        ],
        labor_count: 24,
        material_deliveries: ["18 galvanized scaffolding ledger tubes"],
        blockers: [],
      },
      edited_by_human: false,
      photos: [],
      client_updated_at: makeIsoTimestamp(y6, "09:30"),
      created_at: makeIsoTimestamp(y6, "09:30"),
      updated_at: makeIsoTimestamp(y6, "09:31"),
      deleted_at: null,
      server_version: 6,
    },
    {
      id: "33333333-3333-4333-8333-333333333108",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: y9,
      recorded_at: makeIsoTimestamp(y9, "08:50"),
      notes: "Weather: Sunny (26°C) · Soil bearing plate load verification",
      audio_uri: "local://demo/audio/margalla-y9.m4a",
      audio_duration_ms: 49000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(y9, "08:52"),
      transcript:
        "Geotech team completed plate load test at 220 kN/m² with settlement within allowable limit. Cleared lean concrete blinding pour.",
      detected_language: "mixed",
      structured_summary: {
        tasks_completed: [
          "Passed geotech plate load bearing test at 220 kN/m²",
          "Poured lean PCC blinding layer on Sector A",
        ],
        labor_count: 21,
        material_deliveries: ["25 tons crushed limestone sub-base"],
        blockers: [],
      },
      edited_by_human: false,
      photos: [],
      client_updated_at: makeIsoTimestamp(y9, "08:50"),
      created_at: makeIsoTimestamp(y9, "08:50"),
      updated_at: makeIsoTimestamp(y9, "08:52"),
      deleted_at: null,
      server_version: 5,
    },
    {
      id: "33333333-3333-4333-8333-333333333109",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: y7,
      recorded_at: makeIsoTimestamp(y7, "08:30"),
      notes: "Weather: Clear (24°C) · Pile cap rebar inspection",
      audio_uri: null,
      audio_duration_ms: null,
      audio_upload_status: "NONE",
      extraction_status: "DONE",
      extraction_attempts: 0,
      extraction_error: null,
      extraction_model: null,
      extracted_at: null,
      transcript: null,
      detected_language: null,
      structured_summary: {
        tasks_completed: ["Inspected North-Wing pile cap starter bars"],
        labor_count: 23,
        material_deliveries: [],
        blockers: [],
      },
      edited_by_human: true,
      photos: [],
      client_updated_at: makeIsoTimestamp(y7, "08:30"),
      created_at: makeIsoTimestamp(y7, "08:30"),
      updated_at: makeIsoTimestamp(y7, "08:30"),
      deleted_at: null,
      server_version: 4,
    },
    {
      id: "33333333-3333-4333-8333-333333333110",
      project_id: DEMO_PROJECT_ONE_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: y11,
      recorded_at: makeIsoTimestamp(y11, "08:15"),
      notes: "Weather: Mild (25°C) · Site benchmark & total-station survey",
      audio_uri: "local://demo/audio/margalla-y11.m4a",
      audio_duration_ms: 39000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(y11, "08:17"),
      transcript:
        "Surveyors pinned permanent elevation benchmarks around Sector A and verified plot boundary setbacks.",
      detected_language: "en",
      structured_summary: {
        tasks_completed: [
          "Pinned permanent TBM elevation benchmarks & boundary setbacks",
        ],
        labor_count: 18,
        material_deliveries: ["Timber survey stakes and reflective targets"],
        blockers: [],
      },
      edited_by_human: false,
      photos: [],
      client_updated_at: makeIsoTimestamp(y11, "08:15"),
      created_at: makeIsoTimestamp(y11, "08:15"),
      updated_at: makeIsoTimestamp(y11, "08:17"),
      deleted_at: null,
      server_version: 3,
    },

    // ---- Project 2: Clifton Coastal Residences (OK, clean bilingual log)
    {
      id: "33333333-3333-4333-8333-333333333201",
      project_id: DEMO_PROJECT_TWO_ID,
      author_id: DEMO_SUPERVISOR_TWO_ID,
      author_name: "Bilal Ahmed",
      log_date: today,
      recorded_at: makeIsoTimestamp(today, "08:40"),
      notes: "Weather: Humid sea breeze (31°C, 68% RH) · Sulphate-resistant concrete cure check",
      audio_uri: "local://demo/audio/clifton-today.m4a",
      audio_duration_ms: 51000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(today, "08:42"),
      transcript:
        "Clifton Tower B fourth-floor block masonry completed up to lintel level. ساحلی نمی سے بچاؤ کے لیے سلفیٹ ریزسٹنٹ سیمنٹ کی کیورنگ جاری ہے۔ All 22 workers active; received 1,200 hollow concrete blocks.",
      detected_language: "mixed",
      structured_summary: {
        tasks_completed: [
          "Completed 4th-floor hollow block masonry up to lintel beam elevation",
          "Maintained wet burlap curing on sulphate-resistant shear walls",
        ],
        labor_count: 22,
        material_deliveries: [
          "1,200 hollow concrete masonry blocks",
          "30 bags Falcon SRC (sulphate-resistant) cement",
        ],
        blockers: [],
      },
      edited_by_human: false,
      photos: [
        {
          id: "44444444-4444-4444-8444-444444444201",
          site_log_id: "33333333-3333-4333-8333-333333333201",
          storage_uri: "local://demo/photos/clifton-masonry.jpg",
          upload_status: "UPLOADED",
          url: DEMO_PHOTO_WALL_URI,
          width: 240,
          height: 160,
          byte_size: 2396,
          taken_at: makeIsoTimestamp(today, "08:38"),
          sort_order: 0,
          deleted_at: null,
          server_version: 14,
        },
      ],
      client_updated_at: makeIsoTimestamp(today, "08:40"),
      created_at: makeIsoTimestamp(today, "08:40"),
      updated_at: makeIsoTimestamp(today, "08:42"),
      deleted_at: null,
      server_version: 14,
    },

    // ---- Project 3: Lahore Cold-Chain Logistics Hub (EXPIRED permit alert)
    {
      id: "33333333-3333-4333-8333-333333333301",
      project_id: DEMO_PROJECT_THREE_ID,
      author_id: DEMO_SUPERVISOR_ONE_ID,
      author_name: "Tariq Mahmood",
      log_date: today,
      recorded_at: makeIsoTimestamp(today, "09:05"),
      notes: "Weather: Overcast / Hazy (23°C) · PEB portal steel frame bay 4-7",
      audio_uri: "local://demo/audio/lahore-peb.m4a",
      audio_duration_ms: 47000,
      audio_upload_status: "UPLOADED",
      extraction_status: "DONE",
      extraction_attempts: 1,
      extraction_error: null,
      extraction_model: "gemini-2.5-flash",
      extracted_at: makeIsoTimestamp(today, "09:06"),
      transcript:
        "Erected three pre-engineered steel portal rafters along warehouse bays 4 through 7 and torqued anchor bolts to spec. Waiting on renewed PIEDMC fire & egress NOC before energizing insulated cold-room panels.",
      detected_language: "en",
      structured_summary: {
        tasks_completed: [
          "Erected PEB steel portal rafters along warehouse bays 4-7",
          "Applied non-shrink epoxy grout beneath column baseplates",
        ],
        labor_count: 19,
        material_deliveries: ["6 tons pre-fabricated H-section rafters & purlins"],
        blockers: [
          "Cold-room panel energization held pending renewed PIEDMC fire & egress NOC",
        ],
      },
      edited_by_human: false,
      photos: [
        {
          id: "44444444-4444-4444-8444-444444444301",
          site_log_id: "33333333-3333-4333-8333-333333333301",
          storage_uri: "local://demo/photos/lahore-warehouse-peb.jpg",
          upload_status: "UPLOADED",
          url: DEMO_PHOTO_STEEL_URI,
          width: 240,
          height: 160,
          byte_size: 2576,
          taken_at: makeIsoTimestamp(today, "09:01"),
          sort_order: 0,
          deleted_at: null,
          server_version: 15,
        },
      ],
      client_updated_at: makeIsoTimestamp(today, "09:05"),
      created_at: makeIsoTimestamp(today, "09:05"),
      updated_at: makeIsoTimestamp(today, "09:06"),
      deleted_at: null,
      server_version: 15,
    },
  ];

  const nowIso = new Date().toISOString();
  const billingMonth = nowIso.slice(0, 7);
  const organization: Organization = {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    name: "Siddiqui Builders & Developers",
    slug: "siddiqui-builders",
    status: "ACTIVE",
    plan_tier: "PRO",
    subscription_status: "ACTIVE",
    billing_provider: "stripe",
    trial_ends_at: null,
    current_period_end: new Date(Date.now() + 28 * 24 * 60 * 60 * 1000).toISOString(),
    max_projects: 25,
    max_seats: 50,
    max_storage_bytes: 50 * 1024 * 1024 * 1024,
    max_ai_extractions_monthly: 2000,
    ai_extractions_this_month: 142,
    storage_bytes_used: 384 * 1024 * 1024,
    billing_month: billingMonth,
    created_at: makeIsoTimestamp(y11, "08:00"),
    updated_at: nowIso,
  };

  const orgMembers: OrganizationMember[] = [
    {
      organization_id: organization.id,
      user_id: DEMO_USER_ID,
      email: DEMO_USER.email,
      full_name: DEMO_USER.full_name,
      role: "OWNER",
      status: "ACTIVE",
      created_at: makeIsoTimestamp(y11, "08:00"),
    },
    {
      organization_id: organization.id,
      user_id: DEMO_SUPERVISOR_ONE_ID,
      email: "tariq@sitediary.demo",
      full_name: "Tariq Mahmood",
      role: "SUPERVISOR",
      status: "ACTIVE",
      created_at: makeIsoTimestamp(y9, "09:00"),
    },
    {
      organization_id: organization.id,
      user_id: DEMO_SUPERVISOR_TWO_ID,
      email: "bilal@sitediary.demo",
      full_name: "Bilal Ahmed",
      role: "SUPERVISOR",
      status: "ACTIVE",
      created_at: makeIsoTimestamp(y7, "10:00"),
    },
  ];

  const invitations: OrganizationInvitation[] = [
    {
      id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
      organization_id: organization.id,
      project_id: DEMO_PROJECT_ONE_ID,
      email: "inspector.asad@sitediary.demo",
      full_name: "Asadullah Khan",
      role: "SUPERVISOR",
      expires_at: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
      accepted_at: null,
      revoked_at: null,
      created_at: makeIsoTimestamp(y1, "11:00"),
      invite_token: "demo-invite-token-asad",
    },
  ];

  const auditLogs: AuditLogItem[] = [
    {
      id: "cccccccc-cccc-4ccc-8ccc-ccccccccccc3",
      sequence_num: 3,
      actor_email: DEMO_USER.email,
      action: "PROJECT_CREATED",
      resource_type: "project",
      resource_id: DEMO_PROJECT_ONE_ID,
      ip_address: "127.0.0.1",
      details: { name: "Margalla Heights Mixed-Use Tower" },
      created_at: makeIsoTimestamp(y1, "14:10"),
    },
    {
      id: "cccccccc-cccc-4ccc-8ccc-ccccccccccc2",
      sequence_num: 2,
      actor_email: DEMO_USER.email,
      action: "INVITATION_CREATED",
      resource_type: "invitation",
      resource_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
      ip_address: "127.0.0.1",
      details: { email: "inspector.asad@sitediary.demo", role: "SUPERVISOR" },
      created_at: makeIsoTimestamp(y1, "11:00"),
    },
    {
      id: "cccccccc-cccc-4ccc-8ccc-ccccccccccc1",
      sequence_num: 1,
      actor_email: DEMO_USER.email,
      action: "ORGANIZATION_CREATED",
      resource_type: "organization",
      resource_id: organization.id,
      ip_address: "127.0.0.1",
      details: { plan_tier: "PRO" },
      created_at: makeIsoTimestamp(y11, "08:00"),
    },
  ];

  return {
    projects,
    permits,
    members,
    logs,
    organization,
    orgMembers,
    invitations,
    auditLogs,
    versionCounter: 100,
  };
}

function getStore(): DemoStore {
  if (!globalThis.__siteDiaryDemoStore) {
    globalThis.__siteDiaryDemoStore = buildInitialDemoStore();
  }
  return globalThis.__siteDiaryDemoStore;
}

export function resetDemoStore(): void {
  globalThis.__siteDiaryDemoStore = buildInitialDemoStore();
}

function dedupeStringsCaseInsensitive(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of items) {
    const cleaned = raw.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      out.push(cleaned);
    }
  }
  return out;
}

function deriveProjectPermits(store: DemoStore, project: Project): Permit[] {
  return store.permits
    .filter((p) => p.project_id === project.id && p.deleted_at === null)
    .map((p) => derivePermit(p, project.timezone))
    .sort((a, b) => a.days_to_expiry - b.days_to_expiry);
}

function buildDailyReportForDate(
  store: DemoStore,
  project: Project,
  dateStr: string
): DailyReport {
  const logs = store.logs
    .filter(
      (l) =>
        l.project_id === project.id &&
        l.deleted_at === null &&
        l.log_date === dateStr
    )
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));

  let laborMax: number | null = null;
  let pendingExtractionCount = 0;
  const tasks: string[] = [];
  const materials: string[] = [];
  const blockers: string[] = [];

  for (const log of logs) {
    if (log.extraction_status !== "DONE") {
      pendingExtractionCount += 1;
    }
    const summary = log.structured_summary;
    if (summary) {
      if (
        summary.labor_count !== null &&
        summary.labor_count !== undefined &&
        (laborMax === null || summary.labor_count > laborMax)
      ) {
        laborMax = summary.labor_count;
      }
      tasks.push(...summary.tasks_completed);
      materials.push(...summary.material_deliveries);
      blockers.push(...summary.blockers);
    }
  }

  return {
    project_id: project.id,
    project_name: project.name,
    log_date: dateStr,
    labor_max: laborMax,
    log_count: logs.length,
    pending_extraction_count: pendingExtractionCount,
    tasks_completed: dedupeStringsCaseInsensitive(tasks),
    material_deliveries: dedupeStringsCaseInsensitive(materials),
    blockers: dedupeStringsCaseInsensitive(blockers),
    logs,
    permits: deriveProjectPermits(store, project),
  };
}

function buildProjectSummary(store: DemoStore, project: Project): ProjectSummary {
  const today = getTodayInTimezone(project.timezone);
  const todayReport = buildDailyReportForDate(store, project, today);
  const permits = deriveProjectPermits(store, project);

  let permitHealth: PermitHealth = "NONE";
  if (permits.some((p) => p.status === "EXPIRED")) {
    permitHealth = "EXPIRED";
  } else if (permits.some((p) => p.status === "EXPIRING_SOON")) {
    permitHealth = "WARN";
  } else if (permits.length > 0) {
    permitHealth = "OK";
  }

  const lastLogAt =
    todayReport.logs.length > 0
      ? todayReport.logs[todayReport.logs.length - 1]?.recorded_at ?? null
      : null;

  return {
    project,
    today: {
      log_date: today,
      labor_max: todayReport.labor_max,
      log_count: todayReport.log_count,
      last_log_at: lastLogAt,
    },
    permit_health: permitHealth,
    next_expiring_permit: permits[0] ?? null,
    open_blockers_count: todayReport.blockers.length,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function problemResponse(
  status: number,
  code: string,
  title: string,
  detail: string
): Response {
  return new Response(
    JSON.stringify({
      type: "about:blank",
      title,
      status,
      code,
      detail,
    }),
    {
      status,
      headers: { "Content-Type": "application/problem+json" },
    }
  );
}

async function parseJsonBody<T>(init?: RequestInit): Promise<T | null> {
  if (!init?.body) return null;
  try {
    if (typeof init.body === "string") {
      return JSON.parse(init.body) as T;
    }
    if (init.body instanceof ArrayBuffer) {
      return JSON.parse(Buffer.from(init.body).toString("utf-8")) as T;
    }
    if (ArrayBuffer.isView(init.body)) {
      return JSON.parse(
        Buffer.from(
          init.body.buffer,
          init.body.byteOffset,
          init.body.byteLength
        ).toString("utf-8")
      ) as T;
    }
    return JSON.parse(await new Response(init.body).text()) as T;
  } catch {
    return null;
  }
}

/**
 * In-process seeded API router used exclusively when NEXT_PUBLIC_DEMO_MODE=true.
 * Allows previewing the portfolio, bilingual EN/UR logs, permits, and PDF export
 * without running FastAPI or PostgreSQL.
 */
export async function handleDemoBackendRequest(
  pathWithQuery: string,
  init: RequestInit = {}
): Promise<Response> {
  const store = getStore();
  const method = (init.method ?? "GET").toUpperCase();
  const url = new URL(pathWithQuery, "http://demo.local");
  const pathname = url.pathname;

  if (pathname === "/v1/me" && method === "GET") {
    return jsonResponse(DEMO_USER);
  }

  if (pathname === "/v1/me/password" && method === "POST") {
    return new Response(null, { status: 204 });
  }

  if (pathname === "/v1/auth/login" && method === "POST") {
    const body = await parseJsonBody<{ email?: string }>(init);
    return jsonResponse(createDemoTokenPair(body?.email));
  }

  if (pathname === "/v1/auth/refresh" && method === "POST") {
    return jsonResponse(createDemoTokenPair());
  }

  if (pathname === "/v1/auth/logout" && method === "POST") {
    return new Response(null, { status: 204 });
  }

  if (pathname === "/v1/projects" && method === "GET") {
    const summaries = store.projects
      .filter((p) => p.deleted_at === null)
      .map((p) => buildProjectSummary(store, p));
    return jsonResponse(summaries);
  }

  if (pathname === "/v1/projects" && method === "POST") {
    const input = await parseJsonBody<ProjectInput>(init);
    if (!input?.name?.trim() || !input.site_address?.trim()) {
      return problemResponse(
        422,
        "VALIDATION",
        "Validation failed",
        "Project name and site_address are required."
      );
    }
    const nowIso = new Date().toISOString();
    store.versionCounter += 1;
    const project: Project = {
      id: randomUUID(),
      name: input.name.trim(),
      site_address: input.site_address.trim(),
      owner_phone: input.owner_phone ?? null,
      timezone: input.timezone?.trim() || "Asia/Karachi",
      allow_photo_gps: Boolean(input.allow_photo_gps),
      created_at: nowIso,
      updated_at: nowIso,
      deleted_at: null,
      server_version: store.versionCounter,
    };
    store.projects.unshift(project);
    store.members.push({
      project_id: project.id,
      user_id: DEMO_USER_ID,
      role: "OWNER",
      full_name: DEMO_USER.full_name,
      email: DEMO_USER.email,
      deleted_at: null,
      server_version: store.versionCounter,
    });
    return jsonResponse(project, 201);
  }

  const projectMatch = /^\/v1\/projects\/([^/]+)$/.exec(pathname);
  if (projectMatch?.[1]) {
    const projectId = projectMatch[1];
    const project = store.projects.find(
      (p) => p.id === projectId && p.deleted_at === null
    );
    if (!project) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Project not found");
    }

    if (method === "GET") {
      return jsonResponse(project);
    }
    if (method === "PATCH") {
      const patch = (await parseJsonBody<ProjectPatch>(init)) ?? {};
      store.versionCounter += 1;
      if (typeof patch.name === "string" && patch.name.trim()) {
        project.name = patch.name.trim();
      }
      if (typeof patch.site_address === "string" && patch.site_address.trim()) {
        project.site_address = patch.site_address.trim();
      }
      if (patch.owner_phone !== undefined) {
        project.owner_phone = patch.owner_phone;
      }
      if (typeof patch.timezone === "string" && patch.timezone.trim()) {
        project.timezone = patch.timezone.trim();
      }
      if (typeof patch.allow_photo_gps === "boolean") {
        project.allow_photo_gps = patch.allow_photo_gps;
      }
      project.updated_at = new Date().toISOString();
      project.server_version = store.versionCounter;
      return jsonResponse(project);
    }
    if (method === "DELETE") {
      store.versionCounter += 1;
      project.deleted_at = new Date().toISOString();
      project.server_version = store.versionCounter;
      return new Response(null, { status: 204 });
    }
  }

  const projectPermitsMatch = /^\/v1\/projects\/([^/]+)\/permits$/.exec(pathname);
  if (projectPermitsMatch?.[1]) {
    const projectId = projectPermitsMatch[1];
    const project = store.projects.find(
      (p) => p.id === projectId && p.deleted_at === null
    );
    if (!project) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Project not found");
    }

    if (method === "GET") {
      return jsonResponse(deriveProjectPermits(store, project));
    }

    if (method === "POST") {
      const input = await parseJsonBody<PermitInput>(init);
      if (
        !input?.permit_name?.trim() ||
        !input.authority?.trim() ||
        !input.expiry_date
      ) {
        return problemResponse(
          422,
          "VALIDATION",
          "Validation failed",
          "permit_name, authority, and expiry_date are required."
        );
      }
      const nowIso = new Date().toISOString();
      store.versionCounter += 1;
      const record: DemoPermitRecord = {
        id: randomUUID(),
        project_id: project.id,
        permit_name: input.permit_name.trim(),
        authority: input.authority.trim(),
        permit_number: input.permit_number ?? null,
        issue_date: input.issue_date ?? null,
        expiry_date: input.expiry_date,
        document_photo_uri: input.document_photo_uri ?? null,
        document_photo_url: null,
        created_by: DEMO_USER_ID,
        created_at: nowIso,
        updated_at: nowIso,
        deleted_at: null,
        server_version: store.versionCounter,
      };
      store.permits.push(record);
      return jsonResponse(derivePermit(record, project.timezone), 201);
    }
  }

  const permitMatch = /^\/v1\/permits\/([^/]+)$/.exec(pathname);
  if (permitMatch?.[1]) {
    const permitId = permitMatch[1];
    const record = store.permits.find(
      (p) => p.id === permitId && p.deleted_at === null
    );
    if (!record) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Permit not found");
    }
    const project = store.projects.find((p) => p.id === record.project_id);
    const tz = project?.timezone ?? "Asia/Karachi";

    if (method === "PATCH") {
      const patch = (await parseJsonBody<PermitPatch>(init)) ?? {};
      store.versionCounter += 1;
      if (typeof patch.permit_name === "string" && patch.permit_name.trim()) {
        record.permit_name = patch.permit_name.trim();
      }
      if (typeof patch.authority === "string" && patch.authority.trim()) {
        record.authority = patch.authority.trim();
      }
      if (patch.permit_number !== undefined) {
        record.permit_number = patch.permit_number;
      }
      if (patch.issue_date !== undefined) {
        record.issue_date = patch.issue_date;
      }
      if (typeof patch.expiry_date === "string" && patch.expiry_date) {
        record.expiry_date = patch.expiry_date;
      }
      record.updated_at = new Date().toISOString();
      record.server_version = store.versionCounter;
      return jsonResponse(derivePermit(record, tz));
    }

    if (method === "DELETE") {
      store.versionCounter += 1;
      record.deleted_at = new Date().toISOString();
      record.server_version = store.versionCounter;
      return new Response(null, { status: 204 });
    }
  }

  const membersMatch = /^\/v1\/projects\/([^/]+)\/members$/.exec(pathname);
  if (membersMatch?.[1]) {
    const projectId = membersMatch[1];
    const project = store.projects.find(
      (p) => p.id === projectId && p.deleted_at === null
    );
    if (!project) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Project not found");
    }

    if (method === "GET") {
      const list = store.members.filter(
        (m) => m.project_id === projectId && m.deleted_at === null
      );
      return jsonResponse(list);
    }

    if (method === "POST") {
      const body = await parseJsonBody<{ email?: string; full_name?: string }>(init);
      if (!body?.email?.trim() || !body.full_name?.trim()) {
        return problemResponse(
          422,
          "VALIDATION",
          "Validation failed",
          "email and full_name are required."
        );
      }
      store.versionCounter += 1;
      const member: Member = {
        project_id: projectId,
        user_id: randomUUID(),
        role: "SUPERVISOR",
        full_name: body.full_name.trim(),
        email: body.email.trim(),
        deleted_at: null,
        server_version: store.versionCounter,
      };
      store.members.push(member);
      const response: InviteMemberResponse = {
        member,
        temporary_password: `Demo-${Math.random().toString(36).slice(2, 8)}`,
      };
      return jsonResponse(response, 201);
    }
  }

  const removeMemberMatch = /^\/v1\/projects\/([^/]+)\/members\/([^/]+)$/.exec(
    pathname
  );
  if (removeMemberMatch?.[1] && removeMemberMatch[2] && method === "DELETE") {
    const projectId = removeMemberMatch[1];
    const userId = removeMemberMatch[2];
    const member = store.members.find(
      (m) =>
        m.project_id === projectId &&
        m.user_id === userId &&
        m.deleted_at === null
    );
    if (!member) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Member not found");
    }
    store.versionCounter += 1;
    member.deleted_at = new Date().toISOString();
    member.server_version = store.versionCounter;
    return new Response(null, { status: 204 });
  }

  const dayMatch = /^\/v1\/projects\/([^/]+)\/days\/(\d{4}-\d{2}-\d{2})$/.exec(
    pathname
  );
  if (dayMatch?.[1] && dayMatch[2] && method === "GET") {
    const projectId = dayMatch[1];
    const dateStr = dayMatch[2];
    const project = store.projects.find(
      (p) => p.id === projectId && p.deleted_at === null
    );
    if (!project) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Project not found");
    }
    return jsonResponse(buildDailyReportForDate(store, project, dateStr));
  }

  const timelineMatch = /^\/v1\/projects\/([^/]+)\/timeline$/.exec(pathname);
  if (timelineMatch?.[1] && method === "GET") {
    const projectId = timelineMatch[1];
    const project = store.projects.find(
      (p) => p.id === projectId && p.deleted_at === null
    );
    if (!project) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Project not found");
    }

    const beforeParam = url.searchParams.get("before");
    const daysParam = Number(url.searchParams.get("days") ?? "7");
    const limit =
      Number.isFinite(daysParam) && daysParam > 0 ? Math.min(daysParam, 30) : 7;

    const allDates = Array.from(
      new Set(
        store.logs
          .filter((l) => l.project_id === projectId && l.deleted_at === null)
          .map((l) => l.log_date)
      )
    )
      .filter((d) => !beforeParam || d < beforeParam)
      .sort((a, b) => b.localeCompare(a));

    const pageDates = allDates.slice(0, limit);
    const hasMore = allDates.length > limit;
    const lastPageDate = pageDates[pageDates.length - 1];

    return jsonResponse({
      days: pageDates.map((d) => buildDailyReportForDate(store, project, d)),
      next_before: hasMore && lastPageDate ? lastPageDate : null,
    });
  }

  if (pathname === "/v1/logs/extract" && method === "POST") {
    const body = await parseJsonBody<{ log_id?: string }>(init);
    if (!body?.log_id) {
      return problemResponse(
        422,
        "VALIDATION",
        "Validation failed",
        "log_id is required"
      );
    }
    const log = store.logs.find(
      (l) => l.id === body.log_id && l.deleted_at === null
    );
    if (!log) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Log not found");
    }
    store.versionCounter += 1;
    log.extraction_status = "DONE";
    log.extraction_attempts += 1;
    log.extraction_error = null;
    log.extracted_at = new Date().toISOString();
    log.transcript =
      "Generator servicing complete. Cleared storm drainage channel and checked perimeter sump pump.";
    log.detected_language = "en";
    log.structured_summary = {
      tasks_completed: [
        "Cleared storm drainage channel after light rain",
        "Verified perimeter sump pump operation",
      ],
      labor_count: 26,
      material_deliveries: [],
      blockers: [],
    };
    log.server_version = store.versionCounter;

    const queued: ExtractQueueResponse = {
      log_id: log.id,
      extraction_status: "DONE",
    };
    return jsonResponse(queued, 202);
  }

  const logMatch = /^\/v1\/logs\/([^/]+)$/.exec(pathname);
  if (logMatch?.[1]) {
    const logId = logMatch[1];
    const log = store.logs.find((l) => l.id === logId && l.deleted_at === null);
    if (!log) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Site log not found");
    }
    if (method === "PATCH") {
      const body = (await parseJsonBody<{ notes?: string }>(init)) ?? {};
      if (typeof body.notes === "string") {
        store.versionCounter += 1;
        log.notes = body.notes;
        log.edited_by_human = true;
        log.updated_at = new Date().toISOString();
        log.server_version = store.versionCounter;
      }
      return jsonResponse(log);
    }
    if (method === "DELETE") {
      store.versionCounter += 1;
      log.deleted_at = new Date().toISOString();
      log.server_version = store.versionCounter;
      return new Response(null, { status: 204 });
    }
  }

  if (pathname === "/v1/media/upload-url" && method === "POST") {
    const ticket: UploadTicket = {
      ticket_id: `demo-ticket-${randomUUID()}`,
      upload_url: "data:text/plain;base64,ZGVtbw==",
      method: "PUT",
      headers: { "Content-Type": "application/octet-stream" },
      storage_uri: `demo://uploads/${randomUUID()}`,
      expires_at: new Date(Date.now() + 900 * 1000).toISOString(),
    };
    return jsonResponse(ticket);
  }

  if (pathname === "/v1/media/complete" && method === "POST") {
    return jsonResponse({ status: "ok", upload_status: "UPLOADED" });
  }

  if (pathname === "/v1/organization") {
    if (method === "GET") {
      return jsonResponse(store.organization);
    }
    if (method === "PATCH") {
      const body = (await parseJsonBody<{ name?: string; slug?: string }>(init)) ?? {};
      if (typeof body.name === "string" && body.name.trim()) {
        store.organization.name = body.name.trim();
      }
      if (typeof body.slug === "string" && body.slug.trim()) {
        store.organization.slug = body.slug.trim().toLowerCase();
      }
      store.organization.updated_at = new Date().toISOString();
      return jsonResponse(store.organization);
    }
  }

  if (pathname === "/v1/organization/usage" && method === "GET") {
    const usage: OrganizationUsage = {
      organization_id: store.organization.id,
      active_projects: store.projects.filter((p) => p.deleted_at === null).length,
      max_projects: store.organization.max_projects,
      active_seats: store.orgMembers.filter((m) => m.status === "ACTIVE").length,
      max_seats: store.organization.max_seats,
      storage_bytes_used: store.organization.storage_bytes_used,
      max_storage_bytes: store.organization.max_storage_bytes,
      ai_extractions_this_month: store.organization.ai_extractions_this_month,
      max_ai_extractions_monthly: store.organization.max_ai_extractions_monthly,
    };
    return jsonResponse(usage);
  }

  if (pathname === "/v1/organization/members" && method === "GET") {
    return jsonResponse(store.orgMembers);
  }

  const orgMemberMatch = /^\/v1\/organization\/members\/([^/]+)$/.exec(pathname);
  if (orgMemberMatch?.[1]) {
    const userId = orgMemberMatch[1];
    const member = store.orgMembers.find((m) => m.user_id === userId);
    if (!member) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Member not found");
    }
    if (method === "PATCH") {
      const body = await parseJsonBody<{ role?: Role }>(init);
      if (body?.role === "OWNER" || body?.role === "SUPERVISOR") {
        member.role = body.role;
      }
      return jsonResponse(member);
    }
    if (method === "DELETE") {
      store.orgMembers = store.orgMembers.filter((m) => m.user_id !== userId);
      return new Response(null, { status: 204 });
    }
  }

  if (pathname === "/v1/organization/invitations") {
    if (method === "GET") {
      return jsonResponse(store.invitations);
    }
    if (method === "POST") {
      const body = await parseJsonBody<{
        email?: string;
        full_name?: string;
        role?: Role;
        project_id?: string | null;
      }>(init);
      if (!body?.email?.trim() || !body.full_name?.trim()) {
        return problemResponse(422, "VALIDATION", "Validation failed", "email and full_name are required.");
      }
      const inv: OrganizationInvitation = {
        id: randomUUID(),
        organization_id: store.organization.id,
        project_id: body.project_id ?? null,
        email: body.email.trim(),
        full_name: body.full_name.trim(),
        role: body.role === "OWNER" ? "OWNER" : "SUPERVISOR",
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        accepted_at: null,
        revoked_at: null,
        created_at: new Date().toISOString(),
        invite_token: `demo-inv-${randomUUID().slice(0, 8)}`,
      };
      store.invitations.unshift(inv);
      return jsonResponse(inv, 201);
    }
  }

  const orgInviteMatch = /^\/v1\/organization\/invitations\/([^/]+)$/.exec(pathname);
  if (orgInviteMatch?.[1] && method === "DELETE") {
    const inviteId = orgInviteMatch[1];
    const inv = store.invitations.find((i) => i.id === inviteId);
    if (!inv) {
      return problemResponse(404, "NOT_FOUND", "Not found", "Invitation not found");
    }
    inv.revoked_at = new Date().toISOString();
    return new Response(null, { status: 204 });
  }

  if (pathname === "/v1/organization/subscription" && method === "POST") {
    const body = await parseJsonBody<{ plan_tier?: PlanTier }>(init);
    if (body?.plan_tier) {
      store.organization.plan_tier = body.plan_tier;
      store.organization.max_projects =
        body.plan_tier === "ENTERPRISE" ? 1000 : body.plan_tier === "PRO" ? 25 : 3;
      store.organization.max_seats =
        body.plan_tier === "ENTERPRISE" ? 500 : body.plan_tier === "PRO" ? 50 : 5;
      store.organization.updated_at = new Date().toISOString();
    }
    return jsonResponse(store.organization);
  }

  if (pathname === "/v1/billing/checkout" && method === "POST") {
    const checkout: BillingCheckoutResponse = {
      provider: "stripe",
      configured: false,
      checkout_url: null,
      message: "Demo mode: billing checkout preview active (Stripe disabled in offline demo).",
    };
    return jsonResponse(checkout);
  }

  if (pathname === "/v1/organization/suspend" && method === "POST") {
    store.organization.status = "SUSPENDED";
    store.organization.updated_at = new Date().toISOString();
    return jsonResponse(store.organization);
  }

  if (pathname === "/v1/organization/unsuspend" && method === "POST") {
    store.organization.status = "ACTIVE";
    store.organization.updated_at = new Date().toISOString();
    return jsonResponse(store.organization);
  }

  if (pathname === "/v1/organization/delete" && method === "POST") {
    const body = await parseJsonBody<{ confirm_slug?: string }>(init);
    if (body?.confirm_slug !== store.organization.slug) {
      return problemResponse(422, "SLUG_MISMATCH", "Validation failed", "Confirmation slug does not match.");
    }
    return jsonResponse({ accepted: true, status: "PENDING_DELETION" }, 202);
  }

  if (pathname === "/v1/organization/export" && method === "GET") {
    return jsonResponse({
      exported_at: new Date().toISOString(),
      organization: store.organization,
      projects: store.projects.filter((p) => p.deleted_at === null),
      permits: store.permits.filter((p) => p.deleted_at === null),
      members: store.orgMembers,
    });
  }

  if (pathname === "/v1/organization/audit-logs" && method === "GET") {
    const limit = Math.min(Number(url.searchParams.get("limit") ?? "25") || 25, 100);
    const offset = Math.max(Number(url.searchParams.get("offset") ?? "0") || 0, 0);
    return jsonResponse({
      items: store.auditLogs.slice(offset, offset + limit),
      total: store.auditLogs.length,
      limit,
      offset,
    });
  }

  return problemResponse(
    404,
    "NOT_FOUND",
    "Not found",
    `Demo backend has no handler for ${method} ${pathname}`
  );
}
