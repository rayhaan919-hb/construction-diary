/**
 * This file was auto-generated from ../../contracts/api-contract.yaml via openapi-typescript.
 * Do not edit manually; run `npm run generate:types` to regenerate.
 */

export interface paths {
    "/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness + DB connectivity */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** @enum {string} */
                            status: "ok";
                        };
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Email + password login */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        /** Format: email */
                        email: string;
                        password: string;
                        /** @description e.g. 'Pixel 6a' or 'web' */
                        device_label?: string;
                    };
                };
            };
            responses: {
                /** @description Tokens issued */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["TokenPair"];
                    };
                };
                401: components["responses"]["Unauthorized"];
                422: components["responses"]["ValidationError"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Rotate refresh token and issue a new access token
         * @description The presented refresh token is revoked and replaced. Presenting an already-rotated
         *     token revokes the entire chain (theft detection) and returns 401 code=TOKEN_REUSED.
         *     Mobile MUST NOT log the user out on network errors — only on 401.
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        refresh_token: string;
                    };
                };
            };
            responses: {
                /** @description New token pair */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["TokenPair"];
                    };
                };
                401: components["responses"]["Unauthorized"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke a refresh token */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        refresh_token: string;
                    };
                };
            };
            responses: {
                /** @description Revoked */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current user */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["User"];
                    };
                };
                401: components["responses"]["Unauthorized"];
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Change password (required when must_change_password=true) */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        current_password: string;
                        new_password: string;
                    };
                };
            };
            responses: {
                /** @description Changed */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                401: components["responses"]["Unauthorized"];
                422: components["responses"]["ValidationError"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/me/device-tokens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register/refresh an FCM token for push alerts (idempotent upsert) */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        fcm_token: string;
                    };
                };
            };
            responses: {
                /** @description Registered */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Portfolio — projects the caller is a member of, with Bento card stats */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["ProjectSummary"][];
                    };
                };
            };
        };
        put?: never;
        /** Create project (OWNER only; caller becomes OWNER member) */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["ProjectInput"];
                };
            };
            responses: {
                /** @description Created */
                201: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Project"];
                    };
                };
                403: components["responses"]["Forbidden"];
                422: components["responses"]["ValidationError"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
            };
            cookie?: never;
        };
        /** Project detail */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Project"];
                    };
                };
                404: components["responses"]["NotFound"];
            };
        };
        put?: never;
        post?: never;
        /** Soft-delete project (OWNER member only) */
        delete: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description Deleted */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                403: components["responses"]["Forbidden"];
            };
        };
        options?: never;
        head?: never;
        /** Update project (OWNER member only) */
        patch: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["ProjectPatch"];
                };
            };
            responses: {
                /** @description Updated */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Project"];
                    };
                };
                403: components["responses"]["Forbidden"];
                404: components["responses"]["NotFound"];
            };
        };
        trace?: never;
    };
    "/v1/projects/{project_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
            };
            cookie?: never;
        };
        /** List members */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Member"][];
                    };
                };
            };
        };
        put?: never;
        /**
         * Invite a supervisor (OWNER member only)
         * @description If no user with this email exists, one is created with role SUPERVISOR,
         *     must_change_password=true, and a one-time `temporary_password` is returned
         *     (shown once to the owner, who shares it out-of-band). Existing users are simply added.
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        /** Format: email */
                        email: string;
                        full_name: string;
                    };
                };
            };
            responses: {
                /** @description Member added */
                201: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            member: components["schemas"]["Member"];
                            temporary_password?: string | null;
                        };
                    };
                };
                403: components["responses"]["Forbidden"];
                409: components["responses"]["Conflict"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/projects/{project_id}/members/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
                user_id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove member (tombstone; mobile purges that project's local data on next pull) */
        delete: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                    user_id: string;
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description Removed */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                403: components["responses"]["Forbidden"];
            };
        };
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/projects/{project_id}/permits": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
            };
            cookie?: never;
        };
        /** Permits with derived status, ordered by expiry_date ascending */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Permit"][];
                    };
                };
            };
        };
        put?: never;
        /** Create permit (web). Mobile creates permits via /v1/sync/push. */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["PermitInput"];
                };
            };
            responses: {
                /** @description Created */
                201: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Permit"];
                    };
                };
                422: components["responses"]["ValidationError"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/permits/{permit_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                permit_id: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Soft-delete permit */
        delete: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    permit_id: string;
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description Deleted */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                403: components["responses"]["Forbidden"];
            };
        };
        options?: never;
        head?: never;
        /** Update permit (OWNER members: any; SUPERVISOR: only permits they created) */
        patch: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    permit_id: string;
                };
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["PermitPatch"];
                };
            };
            responses: {
                /** @description Updated */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Permit"];
                    };
                };
                403: components["responses"]["Forbidden"];
                404: components["responses"]["NotFound"];
            };
        };
        trace?: never;
    };
    "/v1/projects/{project_id}/timeline": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
            };
            cookie?: never;
        };
        /** Reverse-chronological daily reports (only days that have logs) */
        get: {
            parameters: {
                query?: {
                    /** @description Exclusive upper bound date (project-local). Omit for most recent. */
                    before?: string;
                    days?: number;
                };
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            days: components["schemas"]["DailyReport"][];
                            /**
                             * Format: date
                             * @description Pass as `before` to load older days; null when exhausted.
                             */
                            next_before: string | null;
                        };
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/projects/{project_id}/days/{log_date}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: components["parameters"]["ProjectId"];
                log_date: string;
            };
            cookie?: never;
        };
        /** Aggregated daily report (powers the Today tile and the PDF export) */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    project_id: components["parameters"]["ProjectId"];
                    log_date: string;
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK (logs may be empty) */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["DailyReport"];
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/logs/{log_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                log_id: components["parameters"]["LogId"];
            };
            cookie?: never;
        };
        /** Single log with photos (signed read URLs) */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path: {
                    log_id: components["parameters"]["LogId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["SiteLog"];
                    };
                };
                404: components["responses"]["NotFound"];
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/logs/extract": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * (Re)queue Gemini extraction for a log — async
         * @description Extraction normally starts automatically when the log's audio upload is
         *     confirmed via /v1/media/complete. This endpoint is for manual retries
         *     (e.g. after FAILED). Resets extraction_attempts to 0 and sets status PENDING.
         *     The audio location is resolved server-side from site_logs.audio_uri.
         *     Results reach clients via GET /v1/logs/{log_id} and /v1/sync/pull.
         *     If edited_by_human=true, a re-run updates transcript/detected_language only and
         *     NEVER overwrites structured_summary.
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        /** Format: uuid */
                        log_id: string;
                    };
                };
            };
            responses: {
                /** @description Queued */
                202: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** Format: uuid */
                            log_id: string;
                            extraction_status: components["schemas"]["ExtractionStatus"];
                        };
                    };
                };
                404: components["responses"]["NotFound"];
                /** @description Audio not uploaded yet (code=AUDIO_NOT_UPLOADED) or already PROCESSING (code=EXTRACTION_IN_PROGRESS) */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/problem+json": components["schemas"]["Problem"];
                    };
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/media/upload-url": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get a short-lived signed PUT URL for direct upload
         * @description Object key layout: `projects/{project_id}/{kind_dir}/{object_id}.{ext}` where kind_dir is
         *     audio | photos | permits. The returned storage_uri is what clients store in
         *     site_logs.audio_uri / site_log_photos.storage_uri / permits.document_photo_uri.
         *     GCS backend: V4 signed URL (15 min). Local backend: `{API_BASE}/v1/media/local/{key}?sig=...&exp=...`.
         *     Uploads are idempotent (same key) so WorkManager can safely retry.
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        kind: components["schemas"]["MediaKind"];
                        /** Format: uuid */
                        project_id: string;
                        /**
                         * Format: uuid
                         * @description site_log id (AUDIO), site_log_photo id (PHOTO), or permit id (PERMIT_DOC)
                         */
                        object_id: string;
                        /** @enum {string} */
                        content_type: "audio/mp4" | "image/jpeg";
                        byte_size: number;
                    };
                };
            };
            responses: {
                /** @description Signed URL issued */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["UploadTicket"];
                    };
                };
                403: components["responses"]["Forbidden"];
                422: components["responses"]["ValidationError"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/media/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm an upload finished
         * @description Server verifies the object exists in storage, then marks the owning row UPLOADED
         *     (site_logs.audio_upload_status / site_log_photos.upload_status). For AUDIO it also
         *     sets extraction_status=PENDING and enqueues extraction (unless already DONE).
         *     Idempotent. The owning row must already have been pushed via /v1/sync/push;
         *     otherwise 409 code=ROW_NOT_SYNCED (client retries after push).
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        kind: components["schemas"]["MediaKind"];
                        /** Format: uuid */
                        object_id: string;
                    };
                };
            };
            responses: {
                /** @description Confirmed */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description Object not found in storage (code=OBJECT_MISSING) */
                404: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/problem+json": components["schemas"]["Problem"];
                    };
                };
                409: components["responses"]["Conflict"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/media/local/{key}": {
        parameters: {
            query: {
                sig: string;
                exp: number;
            };
            header?: never;
            path: {
                /** @description URL-encoded object key */
                key: string;
            };
            cookie?: never;
        };
        /** Local-storage stand-in for a signed GET */
        get: {
            parameters: {
                query: {
                    sig: string;
                    exp: number;
                };
                header?: never;
                path: {
                    /** @description URL-encoded object key */
                    key: string;
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description File bytes */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description Bad or expired signature */
                403: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        /** Local-storage stand-in for a signed PUT (STORAGE_BACKEND=local only; 404 otherwise) */
        put: {
            parameters: {
                query: {
                    sig: string;
                    exp: number;
                };
                header?: never;
                path: {
                    /** @description URL-encoded object key */
                    key: string;
                };
                cookie?: never;
            };
            requestBody: {
                content: {
                    "audio/mp4": string;
                    "image/jpeg": string;
                };
            };
            responses: {
                /** @description Stored */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description Bad or expired signature */
                403: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/sync/push": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Idempotent batch upsert of client-originated changes (mobile)
         * @description Each record is applied independently (one bad record never blocks the batch).
         *     Conflict policy: last-write-wins by SERVER RECEIVE ORDER on client-owned fields.
         *     Server-owned fields (see schemas) are ignored if sent.
         *     Apply order within a batch: permits, site_logs, site_log_photos.
         *     Authorization per record: caller must be an active member of the record's project;
         *     site_logs.author_id is forced to the caller on insert; a SUPERVISOR may only update
         *     logs they authored and permits they created.
         *     Re-pushing an identical record is a no-op apart from bumping server_version.
         *     Max 200 records per request.
         */
        post: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": {
                        changes: {
                            permits?: components["schemas"]["PermitPush"][];
                            site_logs?: components["schemas"]["SiteLogPush"][];
                            site_log_photos?: components["schemas"]["SiteLogPhotoPush"][];
                        };
                    };
                };
            };
            responses: {
                /** @description Per-record results */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** Format: date-time */
                            server_time: string;
                            results: {
                                /** @enum {string} */
                                entity: "permits" | "site_logs" | "site_log_photos";
                                /** Format: uuid */
                                id: string;
                                /** @enum {string} */
                                status: "APPLIED" | "REJECTED";
                                /** Format: int64 */
                                server_version?: number | null;
                                /** @description FORBIDDEN | NOT_FOUND | VALIDATION | PROJECT_DELETED */
                                error_code?: string | null;
                                error_detail?: string | null;
                            }[];
                        };
                    };
                };
                /** @description More than 200 records */
                413: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/sync/pull": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Changes since a server cursor, for all projects the caller belongs to
         * @description Returns rows (including tombstones with deleted_at set) whose server_version > since,
         *     ordered by server_version across all entity types, capped at `limit` rows total.
         *     Client loops until has_more=false, persisting next_cursor after each page.
         *
         *     Scoped backfill: when the client sees a project_members row for itself that it did not
         *     have before (newly added to a project), it MUST call pull with `project_id=<id>&since=0`
         *     to backfill that project's history (rows older than its global cursor), using a separate
         *     per-project cursor until has_more=false. When it sees its own membership tombstone, it
         *     purges that project's local data.
         */
        get: {
            parameters: {
                query: {
                    since: number;
                    limit?: number;
                    /** @description Restrict to one project (scoped backfill) */
                    project_id?: string;
                };
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description Change page */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** Format: int64 */
                            next_cursor: number;
                            has_more: boolean;
                            changes: {
                                projects: components["schemas"]["Project"][];
                                project_members: components["schemas"]["Member"][];
                                permits: components["schemas"]["Permit"][];
                                site_logs: components["schemas"]["SiteLog"][];
                                site_log_photos: components["schemas"]["SiteLogPhoto"][];
                            };
                        };
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Problem: {
            /** @default about:blank */
            type: string;
            title: string;
            status: number;
            /** @description Stable machine-readable error code */
            code: string;
            detail?: string;
            /** @description Field-level validation errors */
            errors?: {
                field?: string;
                message?: string;
            }[];
        };
        /** @enum {string} */
        Role: "OWNER" | "SUPERVISOR";
        User: {
            /** Format: uuid */
            id: string;
            /** Format: email */
            email: string;
            full_name: string;
            role: components["schemas"]["Role"];
            /** @enum {string} */
            preferred_locale: "en" | "ur" | "ar";
            must_change_password: boolean;
        };
        TokenPair: {
            access_token: string;
            refresh_token: string;
            /** @description Seconds (900) */
            access_expires_in: number;
            /** Format: date-time */
            refresh_expires_at: string;
            user: components["schemas"]["User"];
        };
        ProjectInput: {
            name: string;
            site_address: string;
            owner_phone?: string | null;
            /**
             * @description IANA timezone
             * @default Asia/Karachi
             */
            timezone: string;
            /** @default false */
            allow_photo_gps: boolean;
        };
        ProjectPatch: {
            name?: string;
            site_address?: string;
            owner_phone?: string | null;
            timezone?: string;
            allow_photo_gps?: boolean;
        };
        Project: {
            /** Format: uuid */
            id: string;
            name: string;
            site_address: string;
            owner_phone?: string | null;
            timezone: string;
            allow_photo_gps: boolean;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            updated_at: string;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: int64 */
            server_version: number;
        };
        /**
         * @description Worst permit status in the project (NONE = no permits)
         * @enum {string}
         */
        PermitHealth: "OK" | "WARN" | "EXPIRED" | "NONE";
        /** @description Portfolio Bento card */
        ProjectSummary: {
            project: components["schemas"]["Project"];
            today: {
                /**
                 * Format: date
                 * @description Today in project timezone
                 */
                log_date: string;
                labor_max: number | null;
                log_count: number;
                /** Format: date-time */
                last_log_at?: string | null;
            };
            permit_health: components["schemas"]["PermitHealth"];
            next_expiring_permit?: components["schemas"]["Permit"] | null;
            /** @description Distinct blockers in today's logs */
            open_blockers_count: number;
        };
        Member: {
            /** Format: uuid */
            project_id: string;
            /** Format: uuid */
            user_id: string;
            role: components["schemas"]["Role"];
            full_name: string;
            /** Format: email */
            email: string;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: int64 */
            server_version: number;
        };
        /**
         * @description Derived from expiry_date vs project-local today; EXPIRING_SOON = within 14 days. Never stored.
         * @enum {string}
         */
        PermitStatus: "ACTIVE" | "EXPIRING_SOON" | "EXPIRED";
        PermitInput: {
            permit_name: string;
            authority: string;
            permit_number?: string | null;
            /** Format: date */
            issue_date?: string | null;
            /** Format: date */
            expiry_date: string;
            document_photo_uri?: string | null;
        };
        PermitPatch: {
            permit_name?: string;
            authority?: string;
            permit_number?: string | null;
            /** Format: date */
            issue_date?: string | null;
            /** Format: date */
            expiry_date?: string;
            document_photo_uri?: string | null;
        };
        Permit: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            project_id: string;
            permit_name: string;
            authority: string;
            permit_number?: string | null;
            /** Format: date */
            issue_date?: string | null;
            /** Format: date */
            expiry_date: string;
            status: components["schemas"]["PermitStatus"];
            /** @description Negative when expired */
            days_to_expiry: number;
            document_photo_uri?: string | null;
            /** @description Signed GET URL (1h) — web convenience; not in sync pull */
            document_photo_url?: string | null;
            /** Format: uuid */
            created_by: string;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            updated_at: string;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: int64 */
            server_version: number;
        };
        /** @description Client-owned permit fields. Mobile re-derives status locally from expiry_date. */
        PermitPush: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            project_id: string;
            permit_name: string;
            authority: string;
            permit_number?: string | null;
            /** Format: date */
            issue_date?: string | null;
            /** Format: date */
            expiry_date: string;
            document_photo_uri?: string | null;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: date-time */
            client_updated_at: string;
        };
        /** @enum {string} */
        ExtractionStatus: "NOT_STARTED" | "PENDING" | "PROCESSING" | "DONE" | "FAILED";
        /** @description English-normalised extraction (also the Gemini response_schema) */
        StructuredSummary: {
            tasks_completed: string[];
            labor_count: number | null;
            material_deliveries: string[];
            blockers: string[];
        };
        /**
         * @description Client-owned site_log fields. Send structured_summary ONLY together with
         *     edited_by_human=true (a human correction); otherwise omit it. audio_upload_status is
         *     set to PENDING by the server whenever a non-null audio_uri arrives for a log that is
         *     not already UPLOADED for that same URI.
         */
        SiteLogPush: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            project_id: string;
            /** Format: date */
            log_date: string;
            /** Format: date-time */
            recorded_at: string;
            notes?: string | null;
            audio_uri?: string | null;
            audio_duration_ms?: number | null;
            structured_summary?: components["schemas"]["StructuredSummary"] | null;
            /** @default false */
            edited_by_human: boolean;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: date-time */
            client_updated_at: string;
        };
        SiteLog: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            project_id: string;
            /** Format: uuid */
            author_id: string;
            author_name?: string | null;
            /** Format: date */
            log_date: string;
            /** Format: date-time */
            recorded_at: string;
            notes?: string | null;
            audio_uri?: string | null;
            audio_duration_ms?: number | null;
            /** @enum {string} */
            audio_upload_status: "NONE" | "PENDING" | "UPLOADED";
            extraction_status: components["schemas"]["ExtractionStatus"];
            extraction_attempts: number;
            extraction_error?: string | null;
            extraction_model?: string | null;
            /** Format: date-time */
            extracted_at?: string | null;
            transcript?: string | null;
            /** @enum {string|null} */
            detected_language?: "ur" | "en" | "ar" | "mixed" | "unknown" | null;
            structured_summary?: components["schemas"]["StructuredSummary"] | null;
            edited_by_human: boolean;
            /** @description Present on REST read endpoints (with signed `url`); omitted in sync pull (photos sync as their own entity) */
            photos?: components["schemas"]["SiteLogPhoto"][];
            /** Format: date-time */
            client_updated_at: string;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            updated_at: string;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: int64 */
            server_version: number;
        };
        SiteLogPhotoPush: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            site_log_id: string;
            storage_uri: string;
            width?: number | null;
            height?: number | null;
            byte_size?: number | null;
            /** Format: date-time */
            taken_at?: string | null;
            /** @default 0 */
            sort_order: number;
            /** Format: date-time */
            deleted_at?: string | null;
        };
        SiteLogPhoto: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            site_log_id: string;
            storage_uri: string;
            /** @enum {string} */
            upload_status: "PENDING" | "UPLOADED";
            /** @description Signed GET URL (1h); REST reads only */
            url?: string | null;
            width?: number | null;
            height?: number | null;
            byte_size?: number | null;
            /** Format: date-time */
            taken_at?: string | null;
            sort_order: number;
            /** Format: date-time */
            deleted_at?: string | null;
            /** Format: int64 */
            server_version: number;
        };
        /**
         * @description Aggregation of all non-deleted logs for (project, log_date).
         *     labor_max = MAX(labor_count) over logs with a non-null count (NOT a sum — avoids
         *     double-counting the same crew across notes). Lists are concatenated in recorded_at
         *     order and de-duplicated case-insensitively after trimming.
         */
        DailyReport: {
            /** Format: uuid */
            project_id: string;
            project_name?: string;
            /** Format: date */
            log_date: string;
            labor_max: number | null;
            log_count: number;
            /** @description Logs not yet DONE (PDF shows a notice when > 0) */
            pending_extraction_count: number;
            tasks_completed: string[];
            material_deliveries: string[];
            blockers: string[];
            /** @description Per-note breakdown in recorded_at order, each including photos with signed URLs */
            logs: components["schemas"]["SiteLog"][];
            /** @description Snapshot of project permits for the report header */
            permits?: components["schemas"]["Permit"][];
        };
        /** @enum {string} */
        MediaKind: "AUDIO" | "PHOTO" | "PERMIT_DOC";
        UploadTicket: {
            upload_url: string;
            /** @enum {string} */
            method: "PUT";
            /** @description Headers the client MUST send with the PUT (e.g. Content-Type) */
            headers: {
                [key: string]: string;
            };
            /** @description gs://bucket/key or local://key */
            storage_uri: string;
            /** Format: date-time */
            expires_at: string;
        };
    };
    responses: {
        /** @description Missing/invalid/expired credentials (codes INVALID_CREDENTIALS, TOKEN_EXPIRED, TOKEN_REUSED) */
        Unauthorized: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/problem+json": components["schemas"]["Problem"];
            };
        };
        /** @description Authenticated but not allowed (code FORBIDDEN) */
        Forbidden: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/problem+json": components["schemas"]["Problem"];
            };
        };
        /** @description Not found or not visible to caller (code NOT_FOUND) */
        NotFound: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/problem+json": components["schemas"]["Problem"];
            };
        };
        /** @description State conflict (see code) */
        Conflict: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/problem+json": components["schemas"]["Problem"];
            };
        };
        /** @description Request validation failed (code VALIDATION) */
        ValidationError: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/problem+json": components["schemas"]["Problem"];
            };
        };
    };
    parameters: {
        ProjectId: string;
        LogId: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
