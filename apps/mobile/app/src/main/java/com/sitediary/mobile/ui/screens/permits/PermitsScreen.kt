package com.sitediary.mobile.ui.screens.permits

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Sync
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.sitediary.mobile.R
import com.sitediary.mobile.domain.model.EvaluatedPermit
import com.sitediary.mobile.domain.model.PermitStatus
import com.sitediary.mobile.ui.components.ActionableEmptyState
import com.sitediary.mobile.ui.components.CardSkeletonList
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.PrimaryOutdoorButton
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.components.StatusChip
import com.sitediary.mobile.ui.screens.record.CameraCaptureBox
import com.sitediary.mobile.ui.theme.SiteColors
import com.sitediary.mobile.ui.theme.SiteTextStyles
import java.io.File
import java.time.Instant
import java.time.ZoneOffset
import kotlin.math.abs

@Composable
fun PermitsScreen(
    onBack: () -> Unit,
    viewModel: PermitsViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

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
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(R.string.permits_title),
                    style = MaterialTheme.typography.titleLarge
                )
                state.project?.name?.let { name ->
                    Text(text = name, style = MaterialTheme.typography.bodyMedium)
                }
            }
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
            state.lastSyncError?.let { error ->
                item {
                    InlineErrorRetryBanner(
                        message = stringResource(R.string.sync_error_prefix, error),
                        onRetry = viewModel::syncNow
                    )
                }
            }

            item {
                PrimaryOutdoorButton(
                    text = stringResource(R.string.add_permit_cta),
                    icon = Icons.Outlined.Add,
                    minHeight = 56.dp,
                    onClick = viewModel::openAddDialog
                )
            }

            if (state.isInitialLoading) {
                item {
                    CardSkeletonList(count = 3, cardHeight = 116.dp)
                }
            } else if (state.permits.isEmpty()) {
                item {
                    ActionableEmptyState(
                        icon = Icons.Outlined.VerifiedUser,
                        title = stringResource(R.string.permits_empty_title),
                        description = stringResource(R.string.permits_empty_desc),
                        ctaText = stringResource(R.string.add_permit_cta),
                        onCtaClick = viewModel::openAddDialog
                    )
                }
            } else {
                items(state.permits, key = { it.id }) { permit ->
                    PermitCard(
                        permit = permit,
                        onEdit = { viewModel.openEditDialog(permit) },
                        onDelete = { viewModel.deletePermit(permit.id) }
                    )
                }
            }
        }
    }

    if (state.showAddDialog) {
        AddPermitDialog(
            state = state,
            onDismiss = viewModel::closeAddDialog,
            onPermitNameChange = viewModel::onPermitNameChange,
            onAuthorityChange = viewModel::onAuthorityChange,
            onPermitNumberChange = viewModel::onPermitNumberChange,
            onIssueDateChange = viewModel::onIssueDateChange,
            onExpiryDateChange = viewModel::onExpiryDateChange,
            onOpenCamera = viewModel::openDocumentCamera,
            onCloseCamera = viewModel::closeDocumentCamera,
            createTempDocFile = viewModel::createTempDocFile,
            onDocumentCaptured = viewModel::onDocumentCaptured,
            onCameraError = viewModel::onCameraError,
            onSave = viewModel::savePermit
        )
    }
}

@Composable
private fun PermitCard(
    permit: EvaluatedPermit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var showDeleteConfirm by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    var zoomDocModel by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf<Any?>(null) }

    val (statusLabel, statusColor, statusBg) = when (permit.status) {
        PermitStatus.ACTIVE -> Triple(
            stringResource(R.string.permit_status_active),
            SiteColors.StatusOk,
            SiteColors.StatusOkBg
        )
        PermitStatus.EXPIRING_SOON -> Triple(
            stringResource(R.string.permit_status_expiring),
            SiteColors.StatusWarn,
            SiteColors.StatusWarnBg
        )
        PermitStatus.EXPIRED -> Triple(
            stringResource(R.string.permit_status_expired),
            SiteColors.StatusExpired,
            SiteColors.StatusExpiredBg
        )
    }

    val daysLabel = when {
        permit.daysToExpiry < 0 -> stringResource(R.string.permit_days_overdue, abs(permit.daysToExpiry))
        permit.daysToExpiry == 0 -> stringResource(R.string.permit_expires_today)
        else -> stringResource(R.string.permit_days_remaining, permit.daysToExpiry)
    }

    FlatCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f).padding(end = 12.dp)) {
                Text(
                    text = permit.permitName,
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = permit.authority,
                    style = MaterialTheme.typography.bodyMedium
                )
                permit.permitNumber?.let { num ->
                    Text(
                        text = "#$num",
                        style = SiteTextStyles.MonoLabel
                    )
                }
            }
            StatusChip(
                label = statusLabel,
                textColor = statusColor,
                backgroundColor = statusBg
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "EXP: ${permit.expiryDate} ($daysLabel)",
                style = SiteTextStyles.MonoLabel.copy(color = statusColor)
            )
            if (permit.syncDirty) {
                StatusChip(
                    label = stringResource(R.string.status_pending_push),
                    textColor = SiteColors.StatusWarn,
                    backgroundColor = SiteColors.StatusWarnBg
                )
            }
        }

        val docFile = permit.documentLocalPath?.let { File(it) }?.takeIf { it.exists() }
        val docModel: Any? = docFile ?: permit.documentPhotoUri?.takeIf {
            it.startsWith("https://", ignoreCase = true) || it.startsWith("http://", ignoreCase = true)
        }
        if (docModel != null) {
            Spacer(modifier = Modifier.height(12.dp))
            AsyncImage(
                model = docModel,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .border(1.dp, SiteColors.BorderLight, RoundedCornerShape(6.dp))
                    .clickable { zoomDocModel = docModel }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            SecondaryOutdoorButton(
                text = stringResource(R.string.edit_permit_cta),
                icon = Icons.Outlined.Edit,
                modifier = Modifier.weight(1f),
                onClick = onEdit
            )
            SecondaryOutdoorButton(
                text = stringResource(R.string.delete_permit_cta),
                icon = Icons.Outlined.Delete,
                onClick = { showDeleteConfirm = true }
            )
        }
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text(text = stringResource(R.string.delete_permit_confirm_title)) },
            text = { Text(text = stringResource(R.string.delete_permit_confirm_body)) },
            confirmButton = {
                androidx.compose.material3.TextButton(
                    onClick = {
                        showDeleteConfirm = false
                        onDelete()
                    }
                ) {
                    Text(
                        text = stringResource(R.string.delete_confirm_cta),
                        color = SiteColors.StatusExpired
                    )
                }
            },
            dismissButton = {
                androidx.compose.material3.TextButton(onClick = { showDeleteConfirm = false }) {
                    Text(text = stringResource(R.string.cancel_cta))
                }
            }
        )
    }

    zoomDocModel?.let { model ->
        androidx.compose.ui.window.Dialog(
            onDismissRequest = { zoomDocModel = null },
            properties = androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false)
        ) {
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(SiteColors.TextPrimary)
            ) {
                AsyncImage(
                    model = model,
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp)
                )
                IconButton(
                    onClick = { zoomDocModel = null },
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(16.dp)
                ) {
                    Icon(
                        imageVector = Icons.Outlined.Close,
                        contentDescription = stringResource(R.string.photo_preview_close),
                        tint = SiteColors.BgSurface
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddPermitDialog(
    state: PermitsUiState,
    onDismiss: () -> Unit,
    onPermitNameChange: (String) -> Unit,
    onAuthorityChange: (String) -> Unit,
    onPermitNumberChange: (String) -> Unit,
    onIssueDateChange: (String) -> Unit,
    onExpiryDateChange: (String) -> Unit,
    onOpenCamera: () -> Unit,
    onCloseCamera: () -> Unit,
    createTempDocFile: () -> File,
    onDocumentCaptured: (File) -> Unit,
    onCameraError: (String) -> Unit,
    onSave: () -> Unit
) {
    val context = LocalContext.current
    var showExpiryPicker by remember { mutableStateOf(false) }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) onOpenCamera()
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(12.dp),
            color = SiteColors.BgSurface
        ) {
            Column(
                modifier = Modifier
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = stringResource(R.string.add_permit_cta),
                    style = MaterialTheme.typography.titleLarge
                )

                state.formError?.let { err ->
                    InlineErrorRetryBanner(message = err, onRetry = onSave)
                }

                OutlinedTextField(
                    value = state.permitName,
                    onValueChange = onPermitNameChange,
                    label = { Text(stringResource(R.string.permit_name_label)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                )

                OutlinedTextField(
                    value = state.authority,
                    onValueChange = onAuthorityChange,
                    label = { Text(stringResource(R.string.permit_authority_label)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                )

                OutlinedTextField(
                    value = state.permitNumber,
                    onValueChange = onPermitNumberChange,
                    label = { Text(stringResource(R.string.permit_number_label)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                )

                OutlinedTextField(
                    value = state.issueDate,
                    onValueChange = onIssueDateChange,
                    label = { Text(stringResource(R.string.permit_issue_date_label)) },
                    singleLine = true,
                    textStyle = SiteTextStyles.MonoLabel,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = state.expiryDate,
                        onValueChange = onExpiryDateChange,
                        label = { Text(stringResource(R.string.permit_expiry_date_label)) },
                        singleLine = true,
                        textStyle = SiteTextStyles.MonoLabel,
                        modifier = Modifier.weight(1f).heightIn(min = 56.dp)
                    )
                    SecondaryOutdoorButton(
                        text = "Pick",
                        onClick = { showExpiryPicker = true }
                    )
                }

                if (state.isCameraOpen) {
                    CameraCaptureBox(
                        createTempFile = createTempDocFile,
                        isProcessing = false,
                        onPhotoCaptured = onDocumentCaptured,
                        onError = onCameraError,
                        onClose = onCloseCamera
                    )
                } else {
                    SecondaryOutdoorButton(
                        text = if (state.documentFile != null) {
                            stringResource(R.string.permit_photo_attached)
                        } else {
                            stringResource(R.string.attach_permit_photo)
                        },
                        icon = Icons.Outlined.CameraAlt,
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            val granted = ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED
                            if (granted) onOpenCamera() else cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    SecondaryOutdoorButton(
                        text = stringResource(R.string.cancel),
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f)
                    )
                    PrimaryOutdoorButton(
                        text = stringResource(R.string.save),
                        enabled = !state.isSaving,
                        minHeight = 48.dp,
                        onClick = onSave,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }

    if (showExpiryPicker) {
        val datePickerState = rememberDatePickerState()
        DatePickerDialog(
            onDismissRequest = { showExpiryPicker = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        datePickerState.selectedDateMillis?.let { millis ->
                            val date = Instant.ofEpochMilli(millis)
                                .atZone(ZoneOffset.UTC)
                                .toLocalDate()
                            onExpiryDateChange(date.toString())
                        }
                        showExpiryPicker = false
                    }
                ) {
                    Text(stringResource(R.string.save))
                }
            },
            dismissButton = {
                TextButton(onClick = { showExpiryPicker = false }) {
                    Text(stringResource(R.string.cancel))
                }
            }
        ) {
            DatePicker(state = datePickerState)
        }
    }
}
