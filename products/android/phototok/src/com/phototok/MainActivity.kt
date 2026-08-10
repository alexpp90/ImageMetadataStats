package com.phototok

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.phototok.ui.phonemode.PhoneModeScreen
import com.phototok.ui.theme.PhotoTokTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action != null && intent.action != Intent.ACTION_MAIN) {
            finish()
            return
        }
        enableEdgeToEdge()
        setContent {
            PhotoTokTheme {
                PhoneModeScreen()
            }
        }
    }
}
