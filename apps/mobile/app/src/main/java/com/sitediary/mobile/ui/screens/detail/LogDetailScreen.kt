package com.sitediary.mobile.ui.screens.detail

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.sitediary.mobile.R
import com.sitediary.mobile.ui.components.CardSkeletonList
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.PrimaryOutdoorButton
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.components.StatusChip
import com.sitediary.mobile.ui.screens.diary.ExtractionBadge
import com.sitediary.mobile.ui.screens.record.formatDurationMs
import com.sitediary.mobile.ui.theme.SiteColors
import com.sitediary.mobile.ui.theme.SiteTextStyles
import java.io.File

@Composable
fun LogDetailScreen(
    onBack: () -> Unit,
    viewModel: LogDetailViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val logWithPhotos = state.logWithPhotos

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SiteColors.BgCanvas)
            .safeDrawingPadding()
    ) {
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
            Text(
                text = stringResource(R.string.log_detail_title),
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.weight(1f)
            )
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (logWithPhotos == null) {
                CardSkeletonList(count = 2, cardHeight = 140.dp)
            } else {
                val log = logWithPhotos.log

                state.errorMessage?.let { err ->
                    InlineErrorRetryBanner(
                        message = err,
                        onRetry = viewModel::saveCorrections
                    )
                }

                state.feedbackMessage?.let { msg ->
                    StatusChip(
                        label = msg,
                        textColor = SiteColors.StatusOk,
                        backgroundColor = SiteColors.StatusOkBg
                    )
                }

                // Metadata & status card
                FlatCard {
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

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ExtractionBadge(status = log.extractionStatus)
                        if (log.editedByHuman) {
                            StatusChip(
                                label = stringResource(R.string.edited_by_human_badge),
                                textColor = SiteColors.AccentPrimaryDark,
                                backgroundColor = SiteColors.AccentTint
                            )
                        }
                    }

                    log.notes?.takeIf { it.isNotBlank() }?.let { typedNote ->
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = typedNote,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }

                    // Audio playback if local file still exists (within 7-day window)
                    val localAudioFile = log.audioLocalPath?.let { File(it) }?.takeIf { it.exists() }
                    if (localAudioFile != null || log.audioDurationMs != null) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            if (localAudioFile != null) {
                                SecondaryOutdoorButton(
                                    text = if (state.isPlayingAudio) {
                                        stringResource(R.string.stop_audio)
                                    } else {
                                        stringResource(R.string.play_audio)
                                    },
                                    icon = if (state.isPlayingAudio) {
                                        Icons.Outlined.Stop
                                    } else {
                                        Icons.Outlined.PlayArrow
                                    },
                                    onClick = viewModel::toggleAudioPlayback
                                )
                            }
                            log.audioDurationMs?.let { dur ->
                                Text(
                                    text = formatDurationMs(dur.toLong()),
                                    style = SiteTextStyles.MonoLabel
                                )
                            }
                        }
                    }
                }

                // Photos gallery
                if (logWithPhotos.photos.isNotEmpty()) {
                    FlatCard {
                        Text(
                            text = stringResource(R.string.photos_section_title, logWithPhotos.photos.size),
                            style = MaterialTheme.typography.titleMedium
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            items(logWithPhotos.photos, key = { it.id }) { photo ->
                                val model: Any? = photo.localPath?.let { File(it) }
                                    ?.takeIf { it.exists() }
                                    ?: photo.remoteUrl
                                if (model != null) {
                                    Box(
                                        modifier = Modifier
                                            .size(140.dp)
                                            .clip(RoundedCornerShape(8.dp))
                                            .border(1.dp, SiteColors.BorderLight, RoundedCornerShape(8.dp))
                                    ) {
                                        AsyncImage(
                                            model = model,
                                            contentDescription = null,
                                            contentScale = ContentScale.Crop,
                                            modifier = Modifier.fillMaxSize()
                                        )
                                    }
                                }
                            }
                        }
                    }
                }

                // Transcript card
                FlatCard {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = stringResource(
                                R.string.transcript_section,
                                log.detectedLanguage ?: "--"
                            ),
                            style = MaterialTheme.typography.titleMedium
                        )
                        if (log.extractionStatus == "FAILED" ||
                            (log.audioUploadStatus == "UPLOADED" && log.extractionStatus == "PENDING")
                        ) {
                            SecondaryOutdoorButton(
                                text = stringResource(R.string.retry_ai_extraction),
                                icon = Icons.Outlined.Refresh,
                                enabled = !state.isRetryingExtraction,
                                onClick = viewModel::retryExtraction
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = log.transcript?.takeIf { it.isNotBlank() }
                            ?: stringResource(R.string.no_transcript_yet),
                        style = if (log.transcript.isNullOrBlank()) {
                            MaterialTheme.typography.bodyMedium
                        } else {
                            MaterialTheme.typography.bodyLarge
                        }
                    )
                }

                // Human editable structured summary card
                FlatCard {
                    Text(
                        text = stringResource(R.string.summary_section),
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedTextField(
                            value = state.tasksText,
                            onValueChange = viewModel::onTasksChange,
                            label = { Text(stringResource(R.string.tasks_completed_label)) },
                            minLines = 2,
                            maxLines = 6,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 80.dp)
                        )

                        OutlinedTextField(
                            value = state.laborCountText,
                            onValueChange = viewModel::onLaborCountChange,
                            label = { Text(stringResource(R.string.labor_count_label)) },
                            singleLine = true,
                            textStyle = SiteTextStyles.MonoMetric,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 56.dp)
                        )

                        OutlinedTextField(
                            value = state.materialsText,
                            onValueChange = viewModel::onMaterialsChange,
                            label = { Text(stringResource(R.string.materials_label)) },
                            minLines = 2,
                            maxLines = 6,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 80.dp)
                        )

                        OutlinedTextField(
                            value = state.blockersText,
                            onValueChange = viewModel::onBlockersChange,
                            label = { Text(stringResource(R.string.blockers_label)) },
                            minLines = 2,
                            maxLines = 6,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 80.dp)
                        )

                        PrimaryOutdoorButton(
                            text = stringResource(R.string.save_human_edits),
                            minHeight = 56.dp,
                            enabled = !state.isSaving,
                            onClick = viewModel::saveCorrections
                        )
                    }
                }
            }
        }
    }
}
