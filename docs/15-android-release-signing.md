# Android Release Signing, Build Metadata & Environment Configuration

## 1. Environment-Based API Configuration (Zero Placeholder Fallbacks)

Configured in `apps/mobile/app/build.gradle.kts`:

| Variant / Build Type | `API_ENV` | `applicationId` | Endpoint Property / Env Var | Policy |
|---|---|---|---|---|
| **`debug`** | `dev` | `com.sitediary.mobile` | `DEV_API_BASE_URL` / `API_BASE_URL` / `local.properties` `api.devBaseUrl` | Defaults to `http://10.0.2.2:8000` (Android emulator host loopback) ONLY in debug |
| **`staging`** | `staging` | `com.sitediary.mobile.staging` (`-staging` versionName) | `STAGING_API_BASE_URL` / `-PSTAGING_API_BASE_URL` / `local.properties` `api.stagingBaseUrl` | **Fails closed** if missing, non-HTTPS, localhost/emulator loopback, or `.example.*` placeholder |
| **`release` (`prod`)** | `prod` | `com.sitediary.mobile` | `PROD_API_BASE_URL` / `-PPROD_API_BASE_URL` / `RELEASE_API_BASE_URL` | **Fails closed** (`GradleException`) if missing, non-HTTPS, localhost/loopback, or `.example.*` placeholder |

There are **zero** hardcoded `.example.com` or fallback production URLs anywhere in Gradle or Kotlin code.

---

## 2. Release Keystore Signing Configuration

Production (`release`) and `staging` tasks **fail closed** if any required signing credential or keystore file is absent (`GradleException: Refusing to emit an unsigned or falsely labelled release artifact`):

| Env Var (CI / Shell) | Gradle Property Alternative | Purpose |
|---|---|---|
| `ANDROID_KEYSTORE_PATH` | `-PRELEASE_STORE_FILE` | Path to PKCS12 / JKS keystore file (decoded in CI runner `RUNNER_TEMP`, never committed to git) |
| `ANDROID_KEYSTORE_PASSWORD` | `-PRELEASE_STORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_ALIAS` | `-PRELEASE_KEY_ALIAS` | Upload key alias |
| `ANDROID_KEY_PASSWORD` | `-PRELEASE_KEY_PASSWORD` | Upload key password |
| `ANDROID_KEYSTORE_BASE64` (CI secret) | — | Base64-encoded keystore stored in GitHub Actions Secrets, decoded to `$RUNNER_TEMP/keystore.jks` at build time and shredded after signing |

### GitHub Repository Variables & Secrets Required for Production Play Release

1. **Repository / Environment Secret `ANDROID_KEYSTORE_BASE64`**: Base64 of production Google Play **upload key** (`base64 -w 0 upload-keystore.jks`).
2. **Secret `ANDROID_KEYSTORE_PASSWORD`**
3. **Secret `ANDROID_KEY_ALIAS`**
4. **Secret `ANDROID_KEY_PASSWORD`**
5. **Variable / Secret `PROD_API_BASE_URL`**: Canonical HTTPS backend domain (e.g., `https://api.<your-production-domain>`).
6. **Variable / Secret `STAGING_API_BASE_URL`**: Canonical HTTPS staging backend domain.

### Generating a Production Upload Keystore (Google Play App Signing Recommended)

```bash
keytool -genkeypair -v \
  -keystore upload-keystore.jks \
  -storetype PKCS12 \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias sitediary-upload
```

Upload the public certificate (`keytool -export -rfc -keystore upload-keystore.jks -alias sitediary-upload -file upload_certificate.pem`) to Google Play Console -> **Release -> Setup -> App signing** so Google manages the final distribution key while CI holds only the upload key.

---

## 3. Build Metadata & Release Artifacts

Running `generateReleaseMetadata` alongside `assembleStaging`/`bundleStaging` or `assembleRelease`/`bundleRelease` emits:

1. **Signed APK**: `apps/mobile/app/build/outputs/apk/<variant>/app-<variant>.apk`
2. **Signed AAB**: `apps/mobile/app/build/outputs/bundle/<variant>/app-<variant>.aab`
3. **Build Metadata JSON**: `apps/mobile/app/build/outputs/release-metadata/<variant>/build-metadata.json` containing `applicationId`, `buildType`, `apiEnvironment`, `apiHost`, `compileSdk`, `targetSdk`, `minSdk`, `versionCode`, `versionName`, `signedWithExternalKeystore`, `productionReady`, `gitSha`, and `generatedAtUtc`.
4. **Version Manifest & Release Notes**: Controlled via `VERSION_CODE` / `VERSION_NAME` and root [RELEASE_NOTES.md](../RELEASE_NOTES.md).

---

## 4. Verification Evidence Recorded

1. **Fail-Closed Check (`./gradlew bundleRelease` without `PROD_API_BASE_URL` or keystore)**:
   - Aborted at configuration time with `GradleException: Production Release builds require an explicit HTTPS API endpoint (PROD_API_BASE_URL / -PPROD_API_BASE_URL (or RELEASE_API_BASE_URL) in secure release configuration). Refusing to fall back to development or placeholder URLs.`
2. **Signed Staging Verification (`assembleStaging bundleStaging generateReleaseMetadata` with ephemeral RSA-2048 PKCS12 keystore & `STAGING_API_BASE_URL=https://staging-api.sitediary.localtest`)**:
   - **APK (`app-staging.apk`, 3,527,762 bytes)**: Verified with `apksigner verify --verbose --print-certs` -> `Verifies`, `Verified using v2 scheme (APK Signature Scheme v2): true`.
   - **AAB (`app-staging.aab`, 7,244,382 bytes)**: Verified with `jarsigner -verify -verbose -certs` -> `jar verified.` (`SHA256withRSA`, 2048-bit RSA key).
   - **Metadata (`outputs/release-metadata/staging/build-metadata.json`)**: `compileSdk: 37`, `targetSdk: 36`, `apiEnvironment: "staging"`, `signedWithExternalKeystore: true`, `productionReady: false`.
   - Ephemeral test keystore was deleted immediately after verification.
   - Real **Production Play AAB signing & live API authentication (`release` / `prod` build)** remains **BLOCKED BY EXTERNAL CREDENTIALS** until `PROD_API_BASE_URL` and Play upload keystore secrets are supplied.
