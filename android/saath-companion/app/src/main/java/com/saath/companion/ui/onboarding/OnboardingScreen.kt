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

// Step 2 — senior_id + shared secret + backend URL
@Composable
fun PairScreen(
    seniorId: String,
    secret: String,
    backendUrl: String,
    onSeniorIdChange: (String) -> Unit,
    onSecretChange: (String) -> Unit,
    onBackendUrlChange: (String) -> Unit,
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
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = backendUrl,
            onValueChange = onBackendUrlChange,
            label = { Text("Backend URL (e.g. https://saath.example.com)") },
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            singleLine = true,
        )
        Spacer(Modifier.height(24.dp))
        Button(
            onClick = onNext,
            enabled = seniorId.isNotBlank() && secret.isNotBlank() && backendUrl.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Continue")
        }
    }
}

// Step 3 — Health Connect permission grant + last-sync status
@Composable
fun PermissionScreen(
    lastSyncedText: String,
    permissionsGranted: Boolean,
    healthConnectStatus: com.saath.companion.data.HealthConnectAvailability,
    onInstallHealthConnect: () -> Unit,
    onRequestPermissions: () -> Unit,
    onDone: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Grant Health Connect access", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        Text(
            "Saath reads steps, heart rate, sleep, SpO₂, skin temperature, HRV, and exercise from Health Connect once daily. " +
                "Open Samsung Health first and turn on \"Share with Health Connect\" so your watch data flows through.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(32.dp))

        when (healthConnectStatus) {
            com.saath.companion.data.HealthConnectAvailability.NOT_AVAILABLE,
            com.saath.companion.data.HealthConnectAvailability.PROVIDER_UPDATE_REQUIRED -> {
                Text(
                    "Health Connect is not available on this device. Install or update it to continue.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(12.dp))
                Button(onClick = onInstallHealthConnect, modifier = Modifier.fillMaxWidth()) {
                    Text("Install / Update Health Connect")
                }
            }
            com.saath.companion.data.HealthConnectAvailability.AVAILABLE -> {
                Button(
                    onClick = onRequestPermissions,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (permissionsGranted) "Permissions granted ✓" else "Grant Permissions")
                }
                if (!permissionsGranted) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "You can also tap \"Finish\" below without granting — the app will still sync, using mock data to verify the backend connection.",
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        Text(lastSyncedText, style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = onDone, modifier = Modifier.fillMaxWidth()) {
            Text("Finish")
        }
    }
}
