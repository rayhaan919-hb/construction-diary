package com.sitediary.mobile

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.ui.navigation.SiteDiaryNavHost
import com.sitediary.mobile.ui.theme.SiteDiaryTheme
import dagger.hilt.android.AndroidEntryPoint
import java.util.Locale
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    @Inject lateinit var appPreferences: AppPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            val appLocale by appPreferences.appLocale.collectAsStateWithLifecycle(initialValue = "en")
            val baseContext = LocalContext.current

            val localizedContext = remember(appLocale, baseContext) {
                createLocalizedContext(baseContext, appLocale)
            }
            val layoutDirection = if (appLocale == "ur" || appLocale == "ar") {
                LayoutDirection.Rtl
            } else {
                LayoutDirection.Ltr
            }

            LaunchedEffect(appLocale) {
                val targetLocales = LocaleListCompat.forLanguageTags(appLocale)
                if (AppCompatDelegate.getApplicationLocales() != targetLocales) {
                    AppCompatDelegate.setApplicationLocales(targetLocales)
                }
            }

            CompositionLocalProvider(
                LocalContext provides localizedContext,
                LocalConfiguration provides localizedContext.resources.configuration,
                LocalLayoutDirection provides layoutDirection
            ) {
                SiteDiaryTheme {
                    SiteDiaryNavHost(appPreferences = appPreferences)
                }
            }
        }
    }

    private fun createLocalizedContext(base: Context, languageTag: String): Context {
        val locale = Locale.forLanguageTag(languageTag)
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }
}
