package com.sitediary.mobile.data.remote

import com.sitediary.mobile.data.remote.dto.MediaCompleteRequestDto
import com.sitediary.mobile.data.remote.dto.MediaKind
import com.sitediary.mobile.data.remote.dto.PermitPushDto
import com.sitediary.mobile.data.remote.dto.SiteLogPhotoPushDto
import com.sitediary.mobile.data.remote.dto.SiteLogPushDto
import com.sitediary.mobile.data.remote.dto.StructuredSummaryDto
import com.sitediary.mobile.data.remote.dto.SyncPullResponseDto
import com.sitediary.mobile.data.remote.dto.SyncPushChangesDto
import com.sitediary.mobile.data.remote.dto.SyncPushRequestDto
import com.sitediary.mobile.data.remote.dto.TokenPairDto
import com.sitediary.mobile.data.remote.dto.UploadTicketDto
import com.sitediary.mobile.data.remote.dto.UploadUrlRequestDto
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContractSerializationTest {

    private val json = JsonProvider.json

    @Test
    fun `SiteLogPushDto omits structured_summary when edited_by_human is false`() {
        val dto = SiteLogPushDto(
            id = "11111111-1111-1111-1111-111111111111",
            projectId = "22222222-2222-2222-2222-222222222222",
            logDate = "2026-11-14",
            recordedAt = "2026-11-14T08:00:00Z",
            notes = "Pouring foundation",
            audioUri = "gs://bucket/a.m4a",
            audioDurationMs = 12_000,
            structuredSummary = StructuredSummaryDto(tasksCompleted = listOf("Should not serialize")),
            editedByHuman = false,
            clientUpdatedAt = "2026-11-14T08:01:00Z"
        )

        val serialized = json.encodeToString(SiteLogPushDto.serializer(), dto)
        val obj = json.parseToJsonElement(serialized).jsonObject

        assertFalse(obj.containsKey("structured_summary"))
        assertEquals("false", obj["edited_by_human"]?.jsonPrimitive?.content)
        assertEquals("2026-11-14", obj["log_date"]?.jsonPrimitive?.content)
        assertEquals("2026-11-14T08:00:00Z", obj["recorded_at"]?.jsonPrimitive?.content)
        assertEquals("gs://bucket/a.m4a", obj["audio_uri"]?.jsonPrimitive?.content)
        assertEquals("12000", obj["audio_duration_ms"]?.jsonPrimitive?.content)
    }

    @Test
    fun `SiteLogPushDto includes structured_summary when edited_by_human is true`() {
        val dto = SiteLogPushDto(
            id = "11111111-1111-1111-1111-111111111111",
            projectId = "22222222-2222-2222-2222-222222222222",
            logDate = "2026-11-14",
            recordedAt = "2026-11-14T08:00:00Z",
            structuredSummary = StructuredSummaryDto(
                tasksCompleted = listOf("Column rebar tied"),
                laborCount = 18,
                materialDeliveries = listOf("20 tons steel"),
                blockers = listOf("Crane maintenance")
            ),
            editedByHuman = true,
            clientUpdatedAt = "2026-11-14T08:05:00Z"
        )

        val serialized = json.encodeToString(SiteLogPushDto.serializer(), dto)
        val obj = json.parseToJsonElement(serialized).jsonObject

        assertTrue(obj.containsKey("structured_summary"))
        assertEquals("true", obj["edited_by_human"]?.jsonPrimitive?.content)
        val summaryObj = obj["structured_summary"]!!.jsonObject
        assertEquals("18", summaryObj["labor_count"]?.jsonPrimitive?.content)
        assertEquals(
            "Column rebar tied",
            summaryObj["tasks_completed"]!!.jsonArray[0].jsonPrimitive.content
        )
    }

    @Test
    fun `SyncPushRequestDto uses exact snake_case keys matching api-contract yaml`() {
        val push = SyncPushRequestDto(
            changes = SyncPushChangesDto(
                permits = listOf(
                    PermitPushDto(
                        id = "p1",
                        projectId = "pr1",
                        permitName = "Excavation",
                        authority = "LDA",
                        permitNumber = "LDA-99",
                        issueDate = "2026-01-01",
                        expiryDate = "2026-12-31",
                        documentPhotoUri = "local://projects/pr1/permits/p1.jpg",
                        clientUpdatedAt = "2026-11-14T09:00:00Z"
                    )
                ),
                siteLogs = emptyList(),
                siteLogPhotos = listOf(
                    SiteLogPhotoPushDto(
                        id = "ph1",
                        siteLogId = "l1",
                        storageUri = "local://projects/pr1/photos/ph1.jpg",
                        width = 1600,
                        height = 1200,
                        byteSize = 240000,
                        takenAt = "2026-11-14T09:00:00Z",
                        sortOrder = 0
                    )
                )
            )
        )

        val raw = json.encodeToString(SyncPushRequestDto.serializer(), push)
        val root = json.parseToJsonElement(raw).jsonObject
        val changes = root["changes"]!!.jsonObject
        assertTrue(changes.containsKey("permits"))
        assertTrue(changes.containsKey("site_logs"))
        assertTrue(changes.containsKey("site_log_photos"))

        val permit = changes["permits"]!!.jsonArray[0].jsonObject
        assertEquals("Excavation", permit["permit_name"]?.jsonPrimitive?.content)
        assertEquals("2026-12-31", permit["expiry_date"]?.jsonPrimitive?.content)

        val photo = changes["site_log_photos"]!!.jsonArray[0].jsonObject
        assertEquals("l1", photo["site_log_id"]?.jsonPrimitive?.content)
        assertEquals("local://projects/pr1/photos/ph1.jpg", photo["storage_uri"]?.jsonPrimitive?.content)
        assertEquals("240000", photo["byte_size"]?.jsonPrimitive?.content)
    }

    @Test
    fun `TokenPairDto and SyncPullResponseDto deserialize OpenAPI payloads cleanly`() {
        val tokenJson = """
            {
              "access_token": "jwt.abc.def",
              "refresh_token": "opaque-rt-1",
              "access_expires_in": 900,
              "refresh_expires_at": "2027-01-13T00:00:00Z",
              "user": {
                "id": "u1",
                "email": "sup@site.pk",
                "full_name": "Tariq Mahmood",
                "role": "SUPERVISOR",
                "preferred_locale": "ur",
                "must_change_password": true
              }
            }
        """.trimIndent()

        val pair = json.decodeFromString(TokenPairDto.serializer(), tokenJson)
        assertEquals("jwt.abc.def", pair.accessToken)
        assertEquals("opaque-rt-1", pair.refreshToken)
        assertTrue(pair.user.mustChangePassword)
        assertEquals("ur", pair.user.preferredLocale)

        val pullJson = """
            {
              "next_cursor": 42,
              "has_more": true,
              "changes": {
                "projects": [
                  {
                    "id": "pr1",
                    "name": "Gulberg Tower",
                    "site_address": "Plot 12",
                    "owner_phone": null,
                    "timezone": "Asia/Karachi",
                    "allow_photo_gps": false,
                    "created_at": "2026-11-01T00:00:00Z",
                    "updated_at": "2026-11-14T00:00:00Z",
                    "deleted_at": null,
                    "server_version": 40
                  }
                ],
                "project_members": [
                  {
                    "project_id": "pr1",
                    "user_id": "u1",
                    "role": "SUPERVISOR",
                    "full_name": "Tariq Mahmood",
                    "email": "sup@site.pk",
                    "deleted_at": null,
                    "server_version": 41
                  }
                ],
                "permits": [],
                "site_logs": [],
                "site_log_photos": []
              }
            }
        """.trimIndent()

        val pull = json.decodeFromString(SyncPullResponseDto.serializer(), pullJson)
        assertEquals(42L, pull.nextCursor)
        assertTrue(pull.hasMore)
        assertEquals(1, pull.changes.projects.size)
        assertEquals(false, pull.changes.projects[0].allowPhotoGps)
        assertEquals(1, pull.changes.projectMembers.size)
    }

    @Test
    fun `Media upload ticket and complete DTOs match contract`() {
        val req = UploadUrlRequestDto(
            kind = MediaKind.AUDIO,
            projectId = "pr1",
            objectId = "log1",
            contentType = "audio/mp4",
            byteSize = 4096L
        )
        val reqJson = json.encodeToString(UploadUrlRequestDto.serializer(), req)
        val reqObj = json.parseToJsonElement(reqJson).jsonObject
        assertEquals("AUDIO", reqObj["kind"]?.jsonPrimitive?.content)
        assertEquals("audio/mp4", reqObj["content_type"]?.jsonPrimitive?.content)
        assertEquals("4096", reqObj["byte_size"]?.jsonPrimitive?.content)

        val ticketRaw = """
            {
              "upload_url": "http://localhost:8000/v1/media/local/key?sig=x&exp=999",
              "method": "PUT",
              "headers": {"Content-Type": "audio/mp4"},
              "storage_uri": "local://projects/pr1/audio/log1.m4a",
              "expires_at": "2026-11-14T10:15:00Z"
            }
        """.trimIndent()
        val ticket = json.decodeFromString(UploadTicketDto.serializer(), ticketRaw)
        assertEquals("PUT", ticket.method)
        assertEquals("audio/mp4", ticket.headers["Content-Type"])

        val completeRaw = json.encodeToString(
            MediaCompleteRequestDto.serializer(),
            MediaCompleteRequestDto(kind = MediaKind.PHOTO, objectId = "ph1")
        )
        val completeObj = json.parseToJsonElement(completeRaw).jsonObject
        assertEquals("PHOTO", completeObj["kind"]?.jsonPrimitive?.content)
        assertEquals("ph1", completeObj["object_id"]?.jsonPrimitive?.content)
    }
}
