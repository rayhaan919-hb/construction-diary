package com.sitediary.mobile.ui.screens.diary

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material.icons.outlined.Sync
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.sitediary.mobile.R
import com.sitediary.mobile.data.local.dao.SiteLogWithPhotos
import com.sitediary.mobile.ui.components.ActionableEmptyState
import com.sitediary.mobile.ui.components.CardSkeletonList
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.PermitExpiryBanner
import com.sitediary.mobile.ui.components.PrimaryOutdoorButton
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.components.StatusChip
import com.sitediary.mobile.ui.theme.SiteColors
import com.sitediary.mobile.ui.theme.SiteTextStyles
import java.io.File

@Composable
fun ProjectDiaryScreen(
    onBack: () -> Unit,
    onRecordNote: (String) -> Unit,
    onOpenLogDetail: (String) -> Unit,
    onOpenPermits: (String) -> Unit,
    viewModel: DiaryViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SiteColors.BgCanvas)
            .safeDrawingPadding()
    ) {
        // Header bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(SiteColors.BgSurface)
                .padding(horizontal = 8.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            IconButton(
                onClick = onBack,
                modifier = Modifier.size(48.dp)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = stringResource(R.string.back),
                    tint = SiteColors.TextPrimary
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = state.project?.name ?: stringResource(R.string.diary_title),
                    style = MaterialTheme.typography.titleLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                state.project?.siteAddress?.let { addr ->
                    Text(
                        text = addr,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            SecondaryOutdoorButton(
                text = stringResource(R.string.permits_button),
                icon = Icons.Outlined.VerifiedUser,
                onClick = { onOpenPermits(viewModel.projectId) }
            )
            IconButton(
                onClick = viewModel::syncNow,
                enabled = !state.isSyncing,
                modifier = Modifier.size(48.dp)
            ) {
                Icon(
                    imageVector = Icons.Outlined.Sync,
                    contentDescription = stringResource(R.string.sync_now),
                    tint = SiteColors.TextPrimary
                )
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            state.bannerSummary?.let { banner ->
                item {
                    PermitExpiryBanner(
                        summary = banner,
                        onViewPermits = { onOpenPermits(viewModel.projectId) }
                    )
                }
            }

            state.lastSyncError?.let { error ->
                item {
                    InlineErrorRetryBanner(
                        message = stringResource(R.string.sync_error_prefix, error),
                        onRetry = viewModel::syncNow
                    )
                }
            }

            // Primary 64dp outdoor CTA
            item {
                PrimaryOutdoorButton(
                    text = stringResource(R.string.record_site_note_cta),
                    icon = Icons.Outlined.Mic,
                    minHeight = 64.dp,
                    onClick = { onRecordNote(viewModel.projectId) }
                )
            }

            // Today summary card
            item {
                FlatCard {
                    Text(
                        text = stringResource(R.string.today_summary_header, state.todayDate),
                        style = SiteTextStyles.MonoLabel.copy(
                            color = SiteColors.TextPrimary,
                            fontWeight = FontWeight.Bold
                        )
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        MetricTile(
                            label = stringResource(R.string.today_logs_count, state.todayLogCount),
                            value = state.todayLogCount.toString(),
                            modifier = Modifier.weight(1f)
                        )
                        MetricTile(
                            label = if (state.todayLaborMax != null) {
                                stringResource(R.string.today_labor_count, state.todayLaborMax!!)
                            } else {
                                stringResource(R.string.today_labor_none)
                            },
                            value = state.todayLaborMax?.toString() ?: "--",
                            modifier = Modifier.weight(1f)
                        )
                        MetricTile(
                            label = "Blockers",
                            value = state.todayBlockersCount.toString(),
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
            }

            if (state.isInitialLoading) {
                item {
                    CardSkeletonList(count = 3, cardHeight = 132.dp)
                }
            } else if (state.logs.isEmpty()) {
                item {
                    ActionableEmptyState(
                        icon = Icons.Outlined.Mic,
                        title = stringResource(R.string.diary_empty_title),
                        description = stringResource(R.string.diary_empty_desc),
                        ctaText = stringResource(R.string.record_site_note_cta),
                        onCtaClick = { onRecordNote(viewModel.projectId) }
                    )
                }
            } else {
                items(state.logs, key = { it.log.id }) { item ->
                    SiteLogCard(
                        item = item,
                        onClick = { onOpenLogDetail(item.log.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun MetricTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(SiteColors.BgTonalMuted)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Text(
            text = value,
            style = SiteTextStyles.MonoMetric
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
private fun SiteLogCard(
    item: SiteLogWithPhotos,
    onClick: () -> Unit
) {
    val log = item.log
    FlatCard(onClick = onClick) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${log.logDate} • ${log.recordedAt.take(19).replace('T', ' ')}",
                style = SiteTextStyles.MonoLabel
            )
            StatusChip(
                label = if (log.syncDirty) {
                    stringResource(R.string.status_pending_push)
                } else {
                    stringResource(R.string.status_synced)
                },
                textColor = if (log.syncDirty) SiteColors.StatusWarn else SiteColors.StatusOk,
                backgroundColor = if (log.syncDirty) SiteColors.StatusWarnBg else SiteColors.StatusOkBg
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        val previewText = log.transcript?.takeIf { it.isNotBlank() }
            ?: log.notes?.takeIf { it.isNotBlank() }
            ?: log.structuredSummary?.tasksCompleted?.firstOrNull()
            ?: "Voice / photo log (${log.id.take(8)})"

        Text(
            text = previewText,
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis
        )

        Spacer(modifier = Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            ExtractionBadge(status = log.extractionStatus)

            if (log.editedByHuman) {
                StatusChip(
                    label = stringResource(R.string.edited_by_human_badge),
                    textColor = SiteColors.AccentPrimaryDark,
                    backgroundColor = SiteColors.AccentTint
                )
            }

            if (item.photos.isNotEmpty()) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Icon(
                        imageVector = Icons.Outlined.PhotoLibrary,
                        contentDescription = null,
                        tint = SiteColors.TextSecondary,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = item.photos.size.toString(),
                        style = SiteTextStyles.MonoLabel
                    )
                }
            }
        }

        if (item.photos.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                item.photos.take(3).forEach { photo ->
                    val model: Any? = photo.localPath?.let { File(it) }?.takeIf { it.exists() }
                        ?: photo.remoteUrl
                    if (model != null) {
                        AsyncImage(
                            model = model,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .size(64.dp)
                                .clip(RoundedCornerShape(6.dp))
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ExtractionBadge(status: String) {
    val (label, color, bg) = when (status) {
        "DONE" -> Triple(
            stringResource(R.string.extraction_done),
            SiteColors.StatusOk,
            SiteColors.StatusOkBg
        )
        "PROCESSING" -> Triple(
            stringResource(R.string.extraction_processing),
            SiteColors.AccentPrimaryDark,
            SiteColors.AccentTint
        )
        "PENDING" -> Triple(
            stringResource(R.string.extraction_pending),
            SiteColors.StatusWarn,
            SiteColors.StatusWarnBg
        )
        "FAILED" -> Triple(
            stringResource(R.string.extraction_failed),
            SiteColors.StatusExpired,
            SiteColors.StatusExpiredBg
        )
        else -> Triple(
            stringResource(R.string.extraction_not_started),
            SiteColors.TextSecondary,
            SiteColors.BgTonalMuted
        )
    }
    StatusChip(label = label, textColor = color, backgroundColor = bg)
}
