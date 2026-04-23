package com.saath.companion.ui.onboarding

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

// Step 1 — Welcome
@Composable
fun WelcomeScreen(onNext: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Saath", style = MaterialTheme.typography.displayMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            "Your health companion — syncs Samsung Health data to keep your family informed.",
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(Modifier.height(40.dp))
        Button(onClick = onNext, modifier = Modifier.fillMaxWidth()) {
            Text("Get Started")
        }
    }
}

// Step 2 — senior_id + shared secret
@Composable
fun PairScreen(
    seniorId: String,
    secret: String,
    onSeniorIdChange: (String) -> Unit,
    onSecretChange: (String) -> Unit,
    onNext: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Link your account", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = seniorId,
            onValueChange = onSeniorIdChange,
            label = { Text("Senior ID (UUID)") },
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
            singleLine = true,
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = secret,
            onValueChange = onSecretChange,
            label = { Text("Shared Secret") },
            modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            singleLine = true,
        )
        Spacer(Modifier.height(24.dp))
        Button(
            onClick = onNext,
            enabled = seniorId.isNotBlank() && secret.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Continue")
        }
    }
}

// Step 3 — Samsung Health permission grant + last-sync status
@Composable
fun PermissionScreen(
    lastSyncedText: String,
    onRequestPermissions: () -> Unit,
    onDone: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Grant Samsung Health access", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        Text(
            "Saath reads steps, heart rate, sleep, SpO₂, skin temp, HRV, stress, and exercise data once daily.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(32.dp))
        Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth()) {
            Text("Grant Permissions")
        }
        Spacer(Modifier.height(16.dp))
        Text(lastSyncedText, style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = onDone, modifier = Modifier.fillMaxWidth()) {
            Text("Done")
        }
    }
}
