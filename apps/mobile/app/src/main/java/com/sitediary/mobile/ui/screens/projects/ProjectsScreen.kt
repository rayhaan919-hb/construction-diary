package com.sitediary.mobile.ui.screens.projects

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Apartment
import androidx.compose.material.icons.outlined.Sync
import androidx.compose.material.icons.outlined.LockReset
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.sitediary.mobile.R
import com.sitediary.mobile.data.repository.ProjectCardModel
import com.sitediary.mobile.domain.model.PermitHealth
import com.sitediary.mobile.ui.components.ActionableEmptyState
import com.sitediary.mobile.ui.components.CardSkeletonList
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.LanguageToggleChip
import com.sitediary.mobile.ui.components.OfflineStatusBanner
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.components.StatusChip
import com.sitediary.mobile.ui.components.rememberIsOnline
import com.sitediary.mobile.ui.theme.SiteColors
import com.sitediary.mobile.ui.theme.SiteTextStyles

@Composable
fun ProjectsScreen(
    onOpenProject: (String) -> Unit,
    onChangePassword: () -> Unit = {},
    viewModel: ProjectsViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val isOnline = rememberIsOnline()
    var showSignOutConfirm by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SiteColors.BgCanvas)
            .safeDrawingPadding()
    ) {
        if (!isOnline) {
            OfflineStatusBanner()
        }
        // Top header bar
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(SiteColors.BgSurface)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.projects_title),
                        style = MaterialTheme.typography.headlineMedium
                    )
                    if (state.userName.isNotBlank()) {
                        Text(
                            text = state.userName,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = onChangePassword) {
                        Icon(
                            imageVector = Icons.Outlined.LockReset,
                            contentDescription = stringResource(R.string.change_password_cta),
                            tint = SiteColors.TextPrimary
                        )
                    }
                    LanguageToggleChip(
                        currentLocale = state.currentLocale,
                        onToggleLocale = viewModel::toggleLocale
                    )
                    SecondaryOutdoorButton(
                        text = stringResource(R.string.sign_out),
                        onClick = { showSignOutConfirm = true }
                    )
                }
            }

            if (showSignOutConfirm) {
                AlertDialog(
                    onDismissRequest = { showSignOutConfirm = false },
                    title = { Text(text = stringResource(R.string.sign_out_confirm_title)) },
                    text = {
                        Text(
                            text = if (state.pendingSyncCount > 0) {
                                stringResource(R.string.sign_out_pending_warning, state.pendingSyncCount)
                            } else {
                                stringResource(R.string.sign_out_clean_message)
                            }
                        )
                    },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                showSignOutConfirm = false
                                viewModel.signOut()
                            }
                        ) {
                            Text(text = stringResource(R.string.sign_out))
                        }
                    },
                    dismissButton = {
                        TextButton(onClick = { showSignOutConfirm = false }) {
                            Text(text = stringResource(R.string.cancel_cta))
                        }
                    }
                )
            }

            // Sync status & manual trigger
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                val syncLabel = when {
                    state.isSyncing -> stringResource(R.string.syncing)
                    state.pendingSyncCount > 0 -> stringResource(
                        R.string.pending_sync_count,
                        state.pendingSyncCount
                    )
                    else -> stringResource(R.string.all_synced)
                }
                val syncColor = when {
                    state.pendingSyncCount > 0 -> SiteColors.StatusWarn
                    else -> SiteColors.StatusOk
                }
                val syncBg = when {
                    state.pendingSyncCount > 0 -> SiteColors.StatusWarnBg
                    else -> SiteColors.StatusOkBg
                }
                StatusChip(
                    label = syncLabel,
                    textColor = syncColor,
                    backgroundColor = syncBg
                )

                SecondaryOutdoorButton(
                    text = stringResource(R.string.sync_now),
                    icon = Icons.Outlined.Sync,
                    enabled = !state.isSyncing,
                    onClick = viewModel::syncNow
                )
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Mobile-data upload toggle card
            item {
                FlatCard {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp)
                            .clickable {
                                viewModel.setUploadOnMobileData(!state.uploadOnMobileData)
                            },
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(end = 12.dp)
                        ) {
                            Text(
                                text = stringResource(R.string.mobile_data_upload_label),
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text(
                                text = stringResource(R.string.mobile_data_upload_hint),
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                        Switch(
                            checked = state.uploadOnMobileData,
                            onCheckedChange = viewModel::setUploadOnMobileData,
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = SiteColors.BgSurface,
                                checkedTrackColor = SiteColors.AccentPrimary
                            )
                        )
                    }
                }
            }

            // Inline error banner
            state.lastSyncError?.let { error ->
                item {
                    InlineErrorRetryBanner(
                        message = stringResource(R.string.sync_error_prefix, error),
                        onRetry = viewModel::syncNow
                    )
                }
            }

            if (state.isInitialLoading) {
                item {
                    CardSkeletonList(count = 3, cardHeight = 128.dp)
                }
            } else if (state.projects.isEmpty()) {
                item {
                    ActionableEmptyState(
                        icon = Icons.Outlined.Apartment,
                        title = stringResource(R.string.projects_empty_title),
                        description = stringResource(R.string.projects_empty_desc),
                        ctaText = stringResource(R.string.sync_now),
                        onCtaClick = viewModel::syncNow
                    )
                }
            } else {
                items(state.projects, key = { it.project.id }) { card ->
                    ProjectBentoCard(
                        model = card,
                        onClick = { onOpenProject(card.project.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun ProjectBentoCard(
    model: ProjectCardModel,
    onClick: () -> Unit
) {
    val (healthLabel, healthColor, healthBg) = when (model.permitHealth) {
        PermitHealth.OK -> Triple(
            stringResource(R.string.permit_health_ok),
            SiteColors.StatusOk,
            SiteColors.StatusOkBg
        )
        PermitHealth.WARN -> Triple(
            stringResource(R.string.permit_health_warn),
            SiteColors.StatusWarn,
            SiteColors.StatusWarnBg
        )
        PermitHealth.EXPIRED -> Triple(
            stringResource(R.string.permit_health_expired),
            SiteColors.StatusExpired,
            SiteColors.StatusExpiredBg
        )
        PermitHealth.NONE -> Triple(
            stringResource(R.string.permit_health_none),
            SiteColors.TextSecondary,
            SiteColors.BgTonalMuted
        )
    }

    FlatCard(onClick = onClick) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f).padding(end = 12.dp)) {
                Text(
                    text = model.project.name,
                    style = MaterialTheme.typography.titleLarge
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = model.project.siteAddress,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            StatusChip(
                label = healthLabel,
                textColor = healthColor,
                backgroundColor = healthBg
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(R.string.today_logs_count, model.todayLogCount),
                style = SiteTextStyles.MonoLabel.copy(
                    color = SiteColors.TextPrimary,
                    fontWeight = FontWeight.Bold
                )
            )
            Text(
                text = if (model.todayLaborMax != null) {
                    stringResource(R.string.today_labor_count, model.todayLaborMax)
                } else {
                    stringResource(R.string.today_labor_none)
                },
                style = SiteTextStyles.MonoLabel
            )
            if (model.pendingSyncCount > 0) {
                StatusChip(
                    label = stringResource(R.string.pending_sync_count, model.pendingSyncCount),
                    textColor = SiteColors.StatusWarn,
                    backgroundColor = SiteColors.StatusWarnBg
                )
            }
        }
    }
}
