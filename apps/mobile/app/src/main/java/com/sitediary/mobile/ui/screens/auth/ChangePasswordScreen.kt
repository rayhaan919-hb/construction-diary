package com.sitediary.mobile.ui.screens.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.sitediary.mobile.R
import com.sitediary.mobile.ui.components.FlatCard
import com.sitediary.mobile.ui.components.InlineErrorRetryBanner
import com.sitediary.mobile.ui.components.PrimaryOutdoorButton
import com.sitediary.mobile.ui.components.SecondaryOutdoorButton
import com.sitediary.mobile.ui.theme.SiteColors

@Composable
fun ChangePasswordScreen(
    onPasswordUpdated: () -> Unit,
    viewModel: ChangePasswordViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(SiteColors.BgCanvas)
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = stringResource(R.string.change_password_title),
            style = MaterialTheme.typography.headlineMedium
        )
        Text(
            text = stringResource(R.string.change_password_subtitle),
            style = MaterialTheme.typography.bodyMedium
        )

        uiState.errorMessage?.let { msg ->
            InlineErrorRetryBanner(
                message = msg,
                onRetry = { viewModel.submit(onPasswordUpdated) }
            )
        }

        FlatCard {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                OutlinedTextField(
                    value = uiState.currentPassword,
                    onValueChange = viewModel::onCurrentPasswordChange,
                    label = { Text(stringResource(R.string.current_password_label)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                )

                OutlinedTextField(
                    value = uiState.newPassword,
                    onValueChange = viewModel::onNewPasswordChange,
                    label = { Text(stringResource(R.string.new_password_label)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                )

                OutlinedTextField(
                    value = uiState.confirmPassword,
                    onValueChange = viewModel::onConfirmPasswordChange,
                    label = { Text(stringResource(R.string.confirm_password_label)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                )

                PrimaryOutdoorButton(
                    text = stringResource(R.string.update_password_cta),
                    enabled = !uiState.isSubmitting,
                    onClick = { viewModel.submit(onPasswordUpdated) }
                )

                Row(modifier = Modifier.fillMaxWidth()) {
                    SecondaryOutdoorButton(
                        text = stringResource(R.string.sign_out),
                        onClick = viewModel::signOut,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}
