package com.sitediary.mobile.ui.screens.record

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.sitediary.mobile.R
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.PrimaryOutdoorButton
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.components.StatusChip
import com.sitediary.mobile.ui.theme.SiteColors
import com.sitediary.mobile.ui.theme.SiteTextStyles
import java.io.File
import java.util.Locale

@Composable
fun RecordNoteScreen(
    onBack: () -> Unit,
    onSaved: () -> Unit,
    viewModel: RecordNoteViewModel = hiltViewModel()
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var hasAudioPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        )
    }

    val audioPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasAudioPermission = granted
        if (granted) {
            viewModel.startRecording()
        }
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
        if (granted) {
            viewModel.openCamera()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SiteColors.BgCanvas)
            .safeDrawingPadding()
    ) {
        // Header
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
                text = stringResource(R.string.record_note_title),
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
            state.errorMessage?.let { msg ->
                InlineErrorRetryBanner(
                    message = msg,
                    onRetry = { viewModel.saveOffline(onSaved) }
                )
            }

            // Voice recording card (M4A mono 32kbps, max 5:00)
            FlatCard {
                Text(
                    text = stringResource(R.string.audio_section_title),
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = "${formatDurationMs(state.elapsedMs)} / 05:00",
                    style = SiteTextStyles.MonoTimer
                )
                Spacer(modifier = Modifier.height(12.dp))

                if (state.isRecording) {
                    PrimaryOutdoorButton(
                        text = stringResource(R.string.stop_recording),
                        icon = Icons.Outlined.Stop,
                        containerColor = SiteColors.StatusExpired,
                        minHeight = 64.dp,
                        onClick = viewModel::stopRecording
                    )
                } else if (state.recordedFile != null) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        SecondaryOutdoorButton(
                            text = if (state.isPlayingPreview) {
                                stringResource(R.string.stop_preview_cta)
                            } else {
                                stringResource(R.string.preview_recording_cta)
                            },
                            icon = if (state.isPlayingPreview) Icons.Outlined.Stop else Icons.Outlined.PlayArrow,
                            modifier = Modifier.fillMaxWidth(),
                            onClick = viewModel::togglePreviewPlayback
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            SecondaryOutdoorButton(
                                text = stringResource(R.string.rerecord_audio),
                                icon = Icons.Outlined.Mic,
                                modifier = Modifier.weight(1f),
                                onClick = {
                                    if (hasAudioPermission) {
                                        viewModel.startRecording()
                                    } else {
                                        audioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                    }
                                }
                            )
                            SecondaryOutdoorButton(
                                text = stringResource(R.string.delete_audio),
                                icon = Icons.Outlined.Delete,
                                onClick = viewModel::deleteRecording
                            )
                        }
                    }
                } else {
                    PrimaryOutdoorButton(
                        text = stringResource(R.string.start_recording),
                        icon = Icons.Outlined.Mic,
                        minHeight = 64.dp,
                        onClick = {
                            if (hasAudioPermission) {
                                viewModel.startRecording()
                            } else {
                                audioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                            }
                        }
                    )
                }
            }

            // CameraX photo section
            FlatCard {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = stringResource(R.string.photos_section_title, state.photos.size),
                        style = MaterialTheme.typography.titleMedium
                    )
                    StatusChip(
                        label = if (state.project?.allowPhotoGps == true) {
                            stringResource(R.string.gps_keep_notice)
                        } else {
                            stringResource(R.string.gps_strip_notice)
                        },
                        textColor = SiteColors.TextSecondary,
                        backgroundColor = SiteColors.BgTonalMuted
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                if (state.isCameraOpen) {
                    CameraCaptureBox(
                        createTempFile = viewModel::createTempPhotoFile,
                        isProcessing = state.isProcessingPhoto,
                        onPhotoCaptured = viewModel::onPhotoCaptured,
                        onError = viewModel::onCameraError,
                        onClose = viewModel::closeCamera
                    )
                } else {
                    SecondaryOutdoorButton(
                        text = stringResource(R.string.open_camera),
                        icon = Icons.Outlined.CameraAlt,
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            if (hasCameraPermission) {
                                viewModel.openCamera()
                            } else {
                                cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        }
                    )
                }

                if (state.photos.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(12.dp))
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        items(state.photos, key = { it.id }) { photo ->
                            Box(
                                modifier = Modifier
                                    .size(96.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .border(1.dp, SiteColors.BorderLight, RoundedCornerShape(8.dp))
                            ) {
                                AsyncImage(
                                    model = photo.processed.file,
                                    contentDescription = null,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.fillMaxSize()
                                )
                                IconButton(
                                    onClick = { viewModel.removePhoto(photo.id) },
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .size(48.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Outlined.Close,
                                        contentDescription = null,
                                        tint = SiteColors.StatusExpired
                                    )
                                }
                            }
                        }
                    }
                }
            }

            // Typed field note
            FlatCard {
                OutlinedTextField(
                    value = state.notes,
                    onValueChange = viewModel::onNotesChange,
                    label = { Text(stringResource(R.string.typed_note_label)) },
                    placeholder = { Text(stringResource(R.string.typed_note_hint)) },
                    minLines = 3,
                    maxLines = 6,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 120.dp)
                )
            }
        }

        // Bottom primary save button
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(SiteColors.BgSurface)
                .padding(16.dp)
        ) {
            PrimaryOutdoorButton(
                text = stringResource(R.string.save_note_offline),
                minHeight = 64.dp,
                enabled = !state.isSaving && !state.isProcessingPhoto,
                onClick = { viewModel.saveOffline(onSaved) }
            )
        }
    }
}

@Composable
fun CameraCaptureBox(
    createTempFile: () -> File,
    isProcessing: Boolean,
    onPhotoCaptured: (File) -> Unit,
    onError: (String) -> Unit,
    onClose: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember { PreviewView(context) }
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .build()
    }

    DisposableEffect(lifecycleOwner) {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        val executor = ContextCompat.getMainExecutor(context)
        cameraProviderFuture.addListener({
            runCatching {
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().apply {
                    surfaceProvider = previewView.surfaceProvider
                }
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageCapture
                )
            }.onFailure { err ->
                onError(err.message ?: "Camera initialization failed")
            }
        }, executor)

        onDispose {
            runCatching {
                if (cameraProviderFuture.isDone) {
                    cameraProviderFuture.get().unbindAll()
                }
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        AndroidView(
            factory = { previewView },
            modifier = Modifier
                .fillMaxWidth()
                .height(260.dp)
                .clip(RoundedCornerShape(8.dp))
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            PrimaryOutdoorButton(
                text = stringResource(R.string.capture_photo),
                icon = Icons.Outlined.CameraAlt,
                enabled = !isProcessing,
                modifier = Modifier.weight(1f),
                onClick = {
                    val tempFile = createTempFile()
                    val outputOptions = ImageCapture.OutputFileOptions.Builder(tempFile).build()
                    imageCapture.takePicture(
                        outputOptions,
                        ContextCompat.getMainExecutor(context),
                        object : ImageCapture.OnImageSavedCallback {
                            override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                                onPhotoCaptured(tempFile)
                            }

                            override fun onError(exception: ImageCaptureException) {
                                tempFile.delete()
                                onError(exception.message ?: "Photo capture failed")
                            }
                        }
                    )
                }
            )
            SecondaryOutdoorButton(
                text = stringResource(R.string.close_camera),
                onClick = onClose
            )
        }
    }
}

fun formatDurationMs(durationMs: Long): String {
    val totalSeconds = (durationMs / 1000L).coerceAtLeast(0L)
    val minutes = totalSeconds / 60L
    val seconds = totalSeconds % 60L
    return String.format(Locale.US, "%02d:%02d", minutes, seconds)
}
