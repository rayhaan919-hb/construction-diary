package com.sitediary.mobile.data.media

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.io.FileOutputStream
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.max
import kotlin.math.roundToInt

data class ProcessedPhotoResult(
    val file: File,
    val width: Int,
    val height: Int,
    val byteSize: Int
)

/**
 * Downscales captured JPEG photos to a maximum 1600px long edge at JPEG quality 80 (~300KB)
 * and enforces the project's EXIF GPS privacy policy (`allowPhotoGps`).
 */
@Singleton
class PhotoProcessor @Inject constructor() {

    fun processCapturedPhoto(
        sourceFile: File,
        targetFile: File,
        allowPhotoGps: Boolean
    ): ProcessedPhotoResult {
        val sourceExif = runCatching { ExifInterface(sourceFile.absolutePath) }.getOrNull()
        val orientation = sourceExif?.getAttributeInt(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL
        ) ?: ExifInterface.ORIENTATION_NORMAL

        val boundsOpts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(sourceFile.absolutePath, boundsOpts)
        val rawWidth = boundsOpts.outWidth.coerceAtLeast(1)
        val rawHeight = boundsOpts.outHeight.coerceAtLeast(1)

        var sampleSize = 1
        val rawLongEdge = max(rawWidth, rawHeight)
        while (rawLongEdge / (sampleSize * 2) >= MAX_LONG_EDGE_PX) {
            sampleSize *= 2
        }

        val decodeOpts = BitmapFactory.Options().apply { inSampleSize = sampleSize }
        val sampledBitmap = BitmapFactory.decodeFile(sourceFile.absolutePath, decodeOpts)
            ?: throw IllegalStateException("Failed to decode captured photo: ${sourceFile.absolutePath}")

        val orientedBitmap = applyExifOrientation(sampledBitmap, orientation)
        if (orientedBitmap !== sampledBitmap) {
            sampledBitmap.recycle()
        }

        val finalBitmap = downscaleIfNeeded(orientedBitmap, MAX_LONG_EDGE_PX)
        if (finalBitmap !== orientedBitmap) {
            orientedBitmap.recycle()
        }

        targetFile.parentFile?.mkdirs()
        FileOutputStream(targetFile).use { out ->
            finalBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
        }

        val finalWidth = finalBitmap.width
        val finalHeight = finalBitmap.height
        finalBitmap.recycle()

        applyGpsExifPolicy(
            sourceExif = sourceExif,
            targetFile = targetFile,
            allowPhotoGps = allowPhotoGps
        )

        return ProcessedPhotoResult(
            file = targetFile,
            width = finalWidth,
            height = finalHeight,
            byteSize = targetFile.length().toInt()
        )
    }

    private fun downscaleIfNeeded(bitmap: Bitmap, maxEdge: Int): Bitmap {
        val longEdge = max(bitmap.width, bitmap.height)
        if (longEdge <= maxEdge) return bitmap
        val scale = maxEdge.toFloat() / longEdge.toFloat()
        val targetWidth = (bitmap.width * scale).roundToInt().coerceAtLeast(1)
        val targetHeight = (bitmap.height * scale).roundToInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(bitmap, targetWidth, targetHeight, true)
    }

    private fun applyExifOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.postRotate(90f)
                matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.postRotate(270f)
                matrix.postScale(-1f, 1f)
            }
            else -> return bitmap
        }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    private fun applyGpsExifPolicy(
        sourceExif: ExifInterface?,
        targetFile: File,
        allowPhotoGps: Boolean
    ) {
        val targetExif = runCatching { ExifInterface(targetFile.absolutePath) }.getOrNull() ?: return
        targetExif.setAttribute(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL.toString()
        )
        sourceExif?.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL)?.let { dt ->
            targetExif.setAttribute(ExifInterface.TAG_DATETIME_ORIGINAL, dt)
        }

        if (allowPhotoGps && sourceExif != null) {
            GPS_EXIF_TAGS.forEach { tag ->
                sourceExif.getAttribute(tag)?.let { value ->
                    targetExif.setAttribute(tag, value)
                }
            }
        } else {
            GPS_EXIF_TAGS.forEach { tag ->
                targetExif.setAttribute(tag, null)
            }
        }
        runCatching { targetExif.saveAttributes() }
    }

    companion object {
        const val MAX_LONG_EDGE_PX = 1600
        const val JPEG_QUALITY = 80

        val GPS_EXIF_TAGS = listOf(
            ExifInterface.TAG_GPS_LATITUDE,
            ExifInterface.TAG_GPS_LATITUDE_REF,
            ExifInterface.TAG_GPS_LONGITUDE,
            ExifInterface.TAG_GPS_LONGITUDE_REF,
            ExifInterface.TAG_GPS_ALTITUDE,
            ExifInterface.TAG_GPS_ALTITUDE_REF,
            ExifInterface.TAG_GPS_TIMESTAMP,
            ExifInterface.TAG_GPS_DATESTAMP,
            ExifInterface.TAG_GPS_PROCESSING_METHOD,
            ExifInterface.TAG_GPS_SPEED,
            ExifInterface.TAG_GPS_SPEED_REF,
            ExifInterface.TAG_GPS_TRACK,
            ExifInterface.TAG_GPS_TRACK_REF,
            ExifInterface.TAG_GPS_IMG_DIRECTION,
            ExifInterface.TAG_GPS_IMG_DIRECTION_REF,
            ExifInterface.TAG_GPS_AREA_INFORMATION,
            ExifInterface.TAG_GPS_DIFFERENTIAL,
            ExifInterface.TAG_GPS_H_POSITIONING_ERROR,
            ExifInterface.TAG_GPS_DEST_BEARING,
            ExifInterface.TAG_GPS_DEST_BEARING_REF,
            ExifInterface.TAG_GPS_DEST_DISTANCE,
            ExifInterface.TAG_GPS_DEST_DISTANCE_REF,
            ExifInterface.TAG_GPS_DEST_LATITUDE,
            ExifInterface.TAG_GPS_DEST_LATITUDE_REF,
            ExifInterface.TAG_GPS_DEST_LONGITUDE,
            ExifInterface.TAG_GPS_DEST_LONGITUDE_REF,
            ExifInterface.TAG_GPS_MAP_DATUM,
            ExifInterface.TAG_GPS_MEASURE_MODE,
            ExifInterface.TAG_GPS_SATELLITES,
            ExifInterface.TAG_GPS_STATUS,
            ExifInterface.TAG_GPS_VERSION_ID
        )
    }
}
