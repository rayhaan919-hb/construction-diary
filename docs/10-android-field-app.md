# 10 — Android Field App (`apps/mobile`)

Built with Kotlin, Jetpack Compose Material 3, Hilt DI, Room SQLite, Retrofit/OkHttp, WorkManager, and Media3/MediaRecorder.

---

## Core Screens & Workflows

- **Authentication (`LoginScreen`, `ChangePasswordScreen`):** Email/password login, forced first-login password change flow, and token auto-refresh (`TokenRefreshAuthenticator`).
- **Projects & Diary Timeline (`ProjectsScreen`, `ProjectDiaryScreen`):** Instant offline browsing backed by Room `Flow` streams, live `OfflineStatusBanner` connectivity indicator, and pull-to-refresh sync.
- **Multilingual Capture (`RecordNoteScreen`, `LanguageToggleChip`):** Supports **English (`en`)**, **Urdu (`ur`, `values-ur/`)**, and **Arabic (`ar`, `values-ar/`)** with runtime locale switching, AAC/M4A voice recording (`AudioRecorderController`), compressed multi-photo capture (`PhotoProcessor` + EXIF stripping/GPS gating per project policy), and offline notes.
- **Log Detail & Permits (`LogDetailScreen`, `PermitsScreen`):** Edit notes/structured summaries offline, play local *or* signed remote `audioUrl` recordings (`AudioRecorderController.togglePlayback`), soft-delete logs/permits with tombstone sync, and inspect/edit compliance permits with deadline status badges (`PermitStatusCalculator`).

---

## Firebase Cloud Messaging (Optional Build & Runtime Safety)

- `apps/mobile/app/build.gradle.kts` checks `file("google-services.json").exists()` before applying `com.google.gms.google-services`.
- When `google-services.json` is absent, debug/release compilation and all unit tests succeed without errors, and `FcmTokenManager` logs a warning and returns cleanly instead of throwing `IllegalStateException`.
- When configured with a valid Firebase project, `SiteDiaryFirebaseMessagingService` handles token rotation (`POST /v1/auth/device-tokens`) and renders permit expiry push notifications safely even when notification permission (`POST_NOTIFICATIONS` on Android 13+) was declined (`NotificationPermissionRequester`).
