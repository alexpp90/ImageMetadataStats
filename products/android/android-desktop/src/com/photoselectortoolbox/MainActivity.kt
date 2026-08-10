package com.photoselectortoolbox

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.windowsizeclass.ExperimentalMaterial3WindowSizeClassApi
import androidx.compose.material3.windowsizeclass.calculateWindowSizeClass
import com.photoselectortoolbox.ui.navigation.PhotoSelectorApp
import com.photoselectortoolbox.ui.theme.PhotoSelectorToolboxTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @OptIn(ExperimentalMaterial3WindowSizeClassApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action != null && intent.action != Intent.ACTION_MAIN) {
            finish()
            return
        }
        enableEdgeToEdge()
        setContent {
            PhotoSelectorToolboxTheme {
                val windowSizeClass = calculateWindowSizeClass(this)
                PhotoSelectorApp(windowSizeClass = windowSizeClass)
            }
        }
    }
}
