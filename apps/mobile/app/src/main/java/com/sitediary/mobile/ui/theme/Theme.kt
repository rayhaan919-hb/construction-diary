package com.sitediary.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val OutdoorLightColorScheme = lightColorScheme(
    primary = SiteColors.AccentPrimary,
    onPrimary = Color.White,
    primaryContainer = SiteColors.AccentTint,
    onPrimaryContainer = SiteColors.TextPrimary,
    secondary = SiteColors.TextPrimary,
    onSecondary = Color.White,
    background = SiteColors.BgCanvas,
    onBackground = SiteColors.TextPrimary,
    surface = SiteColors.BgSurface,
    onSurface = SiteColors.TextPrimary,
    surfaceVariant = SiteColors.BgTonalMuted,
    onSurfaceVariant = SiteColors.TextSecondary,
    outline = SiteColors.BorderLight,
    error = SiteColors.StatusExpired,
    onError = Color.White
)

@Composable
fun SiteDiaryTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = OutdoorLightColorScheme,
        typography = SiteDiaryTypography,
        content = content
    )
}
