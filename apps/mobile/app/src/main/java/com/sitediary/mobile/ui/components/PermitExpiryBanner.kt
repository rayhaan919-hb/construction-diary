package com.sitediary.mobile.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sitediary.mobile.R
import com.sitediary.mobile.domain.model.PermitBannerSummary
import com.sitediary.mobile.ui.theme.SiteColors
import kotlin.math.abs

@Composable
fun PermitExpiryBanner(
    summary: PermitBannerSummary,
    onViewPermits: () -> Unit,
    modifier: Modifier = Modifier
) {
    val isExpired = summary.expiredCount > 0
    val accentColor = if (isExpired) SiteColors.StatusExpired else SiteColors.StatusWarn
    val bgColor = if (isExpired) SiteColors.StatusExpiredBg else SiteColors.StatusWarnBg

    val message = when {
        summary.expiredCount == 1 -> stringResource(
            R.string.permit_banner_expired_single,
            summary.highlightPermitName,
            abs(summary.highlightDaysToExpiry)
        )
        summary.expiredCount > 1 -> stringResource(
            R.string.permit_banner_expired_multi,
            summary.expiredCount,
            summary.highlightPermitName
        )
        summary.expiringSoonCount == 1 -> stringResource(
            R.string.permit_banner_expiring_single,
            summary.highlightDaysToExpiry,
            summary.highlightPermitName
        )
        else -> stringResource(
            R.string.permit_banner_expiring_multi,
            summary.expiringSoonCount,
            summary.highlightPermitName,
            summary.highlightDaysToExpiry
        )
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(bgColor)
            .border(1.dp, accentColor, RoundedCornerShape(8.dp))
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Icon(
            imageVector = Icons.Outlined.WarningAmber,
            contentDescription = null,
            tint = accentColor,
            modifier = Modifier.size(28.dp)
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium.copy(
                    color = SiteColors.TextPrimary,
                    fontWeight = FontWeight.Bold
                )
            )
        }
        OutlinedButton(
            onClick = onViewPermits,
            modifier = Modifier.heightIn(min = 48.dp),
            shape = RoundedCornerShape(8.dp),
            border = BorderStroke(1.dp, accentColor),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = accentColor)
        ) {
            Text(
                text = stringResource(R.string.view_permits),
                style = MaterialTheme.typography.labelMedium.copy(
                    color = accentColor,
                    fontWeight = FontWeight.Bold
                )
            )
        }
    }
}
