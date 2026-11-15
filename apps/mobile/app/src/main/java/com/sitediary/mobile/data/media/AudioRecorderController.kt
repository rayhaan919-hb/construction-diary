package com.sitediary.mobile.data.media

import android.content.Context
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.os.Build
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

data class RecordingResult(
    val file: File,
    val durationMs: Int
)

/**
 * Records M4A (MPEG_4 + AAC), mono, 32kbps audio capped at 5 minutes (300,000 ms).
 */
class AudioRecorderController @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null
    private var startEpochMs: Long = 0L
    private var timerJob: Job? = null

    private val _isRecording = MutableStateFlow(false)
    val isRecording: StateFlow<Boolean> = _isRecording.asStateFlow()

    private val _elapsedMs = MutableStateFlow(0L)
    val elapsedMs: StateFlow<Long> = _elapsedMs.asStateFlow()

    private val _completedRecording = MutableStateFlow<RecordingResult?>(null)
    val completedRecording: StateFlow<RecordingResult?> = _completedRecording.asStateFlow()

    private var player: MediaPlayer? = null
    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    fun startRecording(targetFile: File) {
        stopRecording()
        stopPlayback()
        targetFile.parentFile?.mkdirs()
        if (targetFile.exists()) {
            targetFile.delete()
        }

        val mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }

        mediaRecorder.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioChannels(1)
            setAudioEncodingBitRate(AUDIO_BITRATE_BPS)
            setAudioSamplingRate(AUDIO_SAMPLE_RATE_HZ)
            setMaxDuration(MAX_DURATION_MS)
            setOutputFile(targetFile.absolutePath)
            setOnInfoListener { _, what, _ ->
                if (what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED) {
                    stopRecording()
                }
            }
            prepare()
            start()
        }

        recorder = mediaRecorder
        outputFile = targetFile
        startEpochMs = System.currentTimeMillis()
        _elapsedMs.value = 0L
        _completedRecording.value = null
        _isRecording.value = true

        timerJob?.cancel()
        timerJob = scope.launch {
            while (_isRecording.value) {
                val elapsed = (System.currentTimeMillis() - startEpochMs)
                    .coerceAtMost(MAX_DURATION_MS.toLong())
                _elapsedMs.value = elapsed
                if (elapsed >= MAX_DURATION_MS) {
                    stopRecording()
                    break
                }
                delay(200L)
            }
        }
    }

    fun stopRecording(): RecordingResult? {
        timerJob?.cancel()
        timerJob = null
        val activeRecorder = recorder ?: return null
        val file = outputFile
        val duration = (System.currentTimeMillis() - startEpochMs)
            .toInt()
            .coerceIn(0, MAX_DURATION_MS)

        recorder = null
        outputFile = null
        _isRecording.value = false

        runCatching { activeRecorder.stop() }
        runCatching { activeRecorder.reset() }
        runCatching { activeRecorder.release() }

        return if (file != null && file.exists() && file.length() > 0L) {
            val result = RecordingResult(file = file, durationMs = duration)
            _completedRecording.value = result
            result
        } else {
            null
        }
    }

    fun clearCompletedRecording() {
        _completedRecording.value = null
        _elapsedMs.value = 0L
    }

    fun togglePlayback(audioSource: String) {
        if (_isPlaying.value) {
            stopPlayback()
            return
        }
        val isRemote = audioSource.startsWith("https://", ignoreCase = true) ||
            audioSource.startsWith("http://", ignoreCase = true)
        if (!isRemote) {
            val file = File(audioSource)
            if (!file.exists()) return
        }
        runCatching {
            val mediaPlayer = MediaPlayer().apply {
                setDataSource(if (isRemote) audioSource else File(audioSource).absolutePath)
                setOnCompletionListener {
                    stopPlayback()
                }
                setOnErrorListener { _, _, _ ->
                    stopPlayback()
                    true
                }
                if (isRemote) {
                    setOnPreparedListener { mp ->
                        mp.start()
                        _isPlaying.value = true
                    }
                    prepareAsync()
                } else {
                    prepare()
                    start()
                    _isPlaying.value = true
                }
            }
            player = mediaPlayer
        }.onFailure {
            stopPlayback()
        }
    }

    fun stopPlayback() {
        val activePlayer = player ?: run {
            _isPlaying.value = false
            return
        }
        player = null
        _isPlaying.value = false
        runCatching { activePlayer.stop() }
        runCatching { activePlayer.release() }
    }

    fun release() {
        stopRecording()
        stopPlayback()
    }

    companion object {
        const val AUDIO_BITRATE_BPS = 32_000
        const val AUDIO_SAMPLE_RATE_HZ = 22_050
        const val MAX_DURATION_MS = 300_000
    }
}
