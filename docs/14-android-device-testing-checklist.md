# Android Device & OS Compatibility Verification Checklist

## SDK & Play Policy Target

- **`compileSdk`**: `37` (Android 17 preview/latest SDK platform installed locally: `platforms/android-37.0`)
- **`targetSdk`**: `36` (Android 16 — satisfies Google Play's August 2025+ target API 35 minimum and August 2026+ API 36 requirement for new apps and app updates on phones/general devices)
- **`minSdk`**: `26` (Android 8.0 Oreo)
- **Automated Verification Status**:
  - `:app:testDebugUnitTest` (Gradle + Room + MockK + MockWebServer): **VERIFIED**
  - `:app:lintDebug` (Android Lint at `targetSdk = 36` / `compileSdk = 37`): **VERIFIED**
  - `:app:assembleStaging`, `:app:bundleStaging`, `apksigner verify`, `jarsigner -verify`: **VERIFIED** (see [15-android-release-signing.md](15-android-release-signing.md))
  - Physical device / Android Emulator interactive QA across Android 13, 14, 15, and 16: **NOT TESTED** in this environment (zero attached `adb` devices and zero installed AVD system images).

---

## Android 13–16 Behavior Change Review (Static Audit in Source Code)

| Android Version / Area | Requirement / Behavior Change | Implementation Status in Codebase |
|---|---|---|
| **Android 13 (API 33) — Notifications** | Runtime `POST_NOTIFICATIONS` permission required before posting alerts/FCM notifications | Manifest declares `POST_NOTIFICATIONS`. Runtime `ActivityResultContracts.RequestPermission()` gated behind `Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU` |
| **Android 13–14 (API 33–34) — Media & Storage** | Granular media permissions (`READ_MEDIA_*`) and Selected Photos Access; no `WRITE_EXTERNAL_STORAGE` / `READ_EXTERNAL_STORAGE` needed for private app capture | App captures photos via CameraX and audio via `MediaRecorder` directly into app-private `filesDir` (`LocalMediaFileManager`); declares only `CAMERA` and `RECORD_AUDIO`, avoiding broad external media storage permissions |
| **Android 14 (API 34) — Foreground Services** | Apps targeting SDK 34+ must declare `foregroundServiceType` if starting foreground services | App uses `WorkManager` (`SyncWorker`, `MediaUploadWorker`, `MediaRetentionWorker`) with constraints (`NetworkType.CONNECTED`) and does not declare or start any `<service>` foreground service; `AndroidManifest.xml` defines no custom `FOREGROUND_SERVICE` |
| **Android 15 (API 35) — Edge-to-Edge Enforcement** | Edge-to-edge UI is enforced by default when `targetSdk >= 35`; system bars may overlap content without insets | `MainActivity` calls `enableEdgeToEdge()`, and Compose screens/scaffolds apply `.safeDrawingPadding()` / Material3 `Scaffold` `paddingValues` |
| **Android 15 (API 35) — Private Space / Background Limits** | Doze / App Standby Buckets / WorkManager quota compliance | Periodic & triggered sync uses WorkManager `OneTimeWorkRequest` / `PeriodicWorkRequest` (`ExistingWorkPolicy.KEEP` / `APPEND_OR_REPLACE`) with exponential backoff, no exact alarms or wake-locks |
| **Android 16 (API 36) — Predictive Back / Large Screen & Resizability / Edge-to-Edge Opt-out Removed** | `targetSdk = 36` removes the manifest opt-out for edge-to-edge and adapts to adaptive layouts / orientation | Single-activity Jetpack Compose UI respects insets cleanly; no `android:windowOptOutEdgeToEdgeEnforcement` relied upon; Lint passes cleanly with `targetSdk = 36` |
| **Location Privacy** | Avoid unnecessary background/fine location permissions | App declares zero `ACCESS_FINE_LOCATION` or `ACCESS_COARSE_LOCATION` permissions; EXIF GPS metadata is stripped during `PhotoProcessor` compression when `allow_photo_gps` is false |
| **Network Connectivity & Cleartext Policy** | Release builds must enforce HTTPS; connectivity changes must be observed safely | `res/xml/network_security_config.xml` restricts cleartext traffic cleanly; release/staging variants require HTTPS API URLs at Gradle configuration time; `ConnectivityObserver` uses `ConnectivityManager.registerDefaultNetworkCallback` |
| **Offline-First Auth & Sync Safety** | Reserve media before upload URL issuance so offline sync cannot orphan objects or bypass ownership | `MediaUploader` calls `POST /v1/media/reservations` before `POST /v1/media/upload-url`, pushes Room dirty rows to `/v1/sync/push`, uploads bytes via pre-signed `PUT`, and completes via `POST /v1/media/complete` with SHA-256 |

---

## Pre-Launch Manual Device Matrix (Required Before Play Store Production Rollout)

All items below are currently **NOT TESTED** on real hardware or emulators in this repository environment and MUST be executed before promoting a production AAB from Google Play Internal Testing to Production:

- [ ] **Android 13 (API 33)**: Clean install APK/AAB -> Sign in -> Grant/Deny `POST_NOTIFICATIONS` -> Capture offline photo + audio note -> Toggle Airplane Mode OFF -> Verify WorkManager upload + reservation/sync/completion end-to-end.
- [ ] **Android 14 (API 34)**: Verify background `MediaUploadWorker` resumes after app backgrounding and network recovery without `ForegroundService` crashes; verify FCM token registration & permit alert notification tap routing.
- [ ] **Android 15 (API 35)**: Inspect top status bar and bottom 3-button / gesture navigation insets on `LoginScreen`, `ProjectsScreen`, `ProjectDiaryScreen`, `RecordNoteScreen`, `LogDetailScreen`, `PermitsScreen`, and `ChangePasswordScreen`.
- [ ] **Android 16 (API 36)**: Verify predictive back gesture behavior across `SiteDiaryNavHost` routes, adaptive window/foldable resizing, dark/light contrast readability, CameraX preview orientation, and `MediaRecorder` interruption handling on incoming phone call.
- [ ] **Production API Authentication**: Install signed `release` (`prod`) APK/AAB configured with production `PROD_API_BASE_URL` -> Confirm successful TLS login (`POST /v1/auth/login`), token refresh (`TokenRefreshAuthenticator`), and diary sync against live Cloud Run API.
