package com.sitediary.mobile.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.sitediary.mobile.data.prefs.AppPreferences
import com.sitediary.mobile.ui.screens.auth.ChangePasswordScreen
import com.sitediary.mobile.ui.screens.auth.LoginScreen
import com.sitediary.mobile.ui.screens.detail.LogDetailScreen
import com.sitediary.mobile.ui.screens.diary.ProjectDiaryScreen
import com.sitediary.mobile.ui.screens.permits.PermitsScreen
import com.sitediary.mobile.ui.screens.projects.ProjectsScreen
import com.sitediary.mobile.ui.screens.record.RecordNoteScreen

object Routes {
    const val LOGIN = "login"
    const val CHANGE_PASSWORD = "change_password"
    const val PROJECTS = "projects"
    const val DIARY = "diary/{projectId}"
    const val RECORD_NOTE = "record/{projectId}"
    const val LOG_DETAIL = "log_detail/{logId}"
    const val PERMITS = "permits/{projectId}"

    fun diary(projectId: String) = "diary/$projectId"
    fun recordNote(projectId: String) = "record/$projectId"
    fun logDetail(logId: String) = "log_detail/$logId"
    fun permits(projectId: String) = "permits/$projectId"
}

@Composable
fun SiteDiaryNavHost(
    appPreferences: AppPreferences
) {
    val navController = rememberNavController()
    val session by appPreferences.sessionFlow.collectAsStateWithLifecycle()

    val startDestination = when {
        session == null -> Routes.LOGIN
        session?.user?.mustChangePassword == true -> Routes.CHANGE_PASSWORD
        else -> Routes.PROJECTS
    }

    // Automatically return to Login if session is cleared (e.g. 401 from /v1/auth/refresh or logout)
    LaunchedEffect(session) {
        val currentRoute = navController.currentDestination?.route
        if (session == null && currentRoute != null && currentRoute != Routes.LOGIN) {
            navController.navigate(Routes.LOGIN) {
                popUpTo(0) { inclusive = true }
            }
        } else if (session?.user?.mustChangePassword == true &&
            currentRoute != null &&
            currentRoute != Routes.CHANGE_PASSWORD
        ) {
            navController.navigate(Routes.CHANGE_PASSWORD) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onAuthenticated = { mustChangePassword ->
                    val target = if (mustChangePassword) Routes.CHANGE_PASSWORD else Routes.PROJECTS
                    navController.navigate(target) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.CHANGE_PASSWORD) {
            ChangePasswordScreen(
                onPasswordUpdated = {
                    navController.navigate(Routes.PROJECTS) {
                        popUpTo(Routes.CHANGE_PASSWORD) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.PROJECTS) {
            com.sitediary.mobile.ui.components.NotificationPermissionRequester(shouldRequest = true)
            ProjectsScreen(
                onOpenProject = { projectId ->
                    navController.navigate(Routes.diary(projectId))
                },
                onChangePassword = {
                    navController.navigate(Routes.CHANGE_PASSWORD)
                }
            )
        }

        composable(
            route = Routes.DIARY,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType })
        ) {
            ProjectDiaryScreen(
                onBack = { navController.popBackStack() },
                onRecordNote = { projectId ->
                    navController.navigate(Routes.recordNote(projectId))
                },
                onOpenLogDetail = { logId ->
                    navController.navigate(Routes.logDetail(logId))
                },
                onOpenPermits = { projectId ->
                    navController.navigate(Routes.permits(projectId))
                }
            )
        }

        composable(
            route = Routes.RECORD_NOTE,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType })
        ) {
            RecordNoteScreen(
                onBack = { navController.popBackStack() },
                onSaved = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.LOG_DETAIL,
            arguments = listOf(navArgument("logId") { type = NavType.StringType })
        ) {
            LogDetailScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.PERMITS,
            arguments = listOf(navArgument("projectId") { type = NavType.StringType })
        ) {
            PermitsScreen(
                onBack = { navController.popBackStack() }
            )
        }
    }
}
