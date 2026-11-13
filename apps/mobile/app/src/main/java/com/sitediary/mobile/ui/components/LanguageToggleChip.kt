package com.sitediary.mobile.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sitediary.mobile.R
import com.sitediary.mobile.ui.theme.SiteColors

@Composable
fun LanguageToggleChip(
    currentLocale: String,
    onToggleLocale: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val nextLocale = if (currentLocale == "ur") "en" else "ur"
    val label = if (currentLocale == "ur") {
        stringResource(R.string.lang_en)
    } else {
        stringResource(R.string.lang_ur)
    }

    OutlinedButton(
        onClick = { onToggleLocale(nextLocale) },
        modifier = modifier.heightIn(min = 48.dp),
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, SiteColors.BorderStrong),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = SiteColors.BgSurface,
            contentColor = SiteColors.TextPrimary
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge.copy(
                color = SiteColors.TextPrimary,
                fontWeight = FontWeight.Bold
            )
        )
    }
}
