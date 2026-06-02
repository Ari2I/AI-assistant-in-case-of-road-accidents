package com.dtp.dtpassist.audio

import android.annotation.SuppressLint
import android.content.Context
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class LocationProvider(private val context: Context) {
    @SuppressLint("MissingPermission")
    suspend fun lastPoint(): String = suspendCancellableCoroutine { cont ->
        val client = LocationServices.getFusedLocationProviderClient(context)
        client.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, null)
            .addOnSuccessListener { current ->
                if (current != null) {
                    cont.resume("%.6f, %.6f".format(current.latitude, current.longitude))
                } else {
                    client.lastLocation
                        .addOnSuccessListener { last ->
                            cont.resume(if (last == null) "Геоточка недоступна: включите геолокацию и разрешите доступ" else "%.6f, %.6f".format(last.latitude, last.longitude))
                        }
                        .addOnFailureListener { cont.resume("Геоточка недоступна: ${it.message}") }
                }
            }
            .addOnFailureListener { cont.resume("Геоточка недоступна: ${it.message}") }
    }
}
