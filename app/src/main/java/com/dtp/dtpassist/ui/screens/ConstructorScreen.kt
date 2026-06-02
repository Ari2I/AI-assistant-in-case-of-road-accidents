package com.dtp.dtpassist.ui.screens

import android.graphics.Bitmap
import android.graphics.Canvas
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Save
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.dtp.dtpassist.ui.constructor.SchemeManager
import com.dtp.dtpassist.ui.theme.Primary
import com.dtp.dtpassist.ui.theme.Surface
import com.yandex.mapkit.Animation
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.map.CameraListener
import com.yandex.mapkit.map.CameraPosition
import com.yandex.mapkit.map.Map
import com.yandex.mapkit.mapview.MapView

@Composable
fun ConstructorScreen(onClose: () -> Unit) {
    val context = LocalContext.current
    var mapView by remember { mutableStateOf<MapView?>(null) }
    var schemeManager by remember { mutableStateOf<SchemeManager?>(null) }
    var savedPath by remember { mutableStateOf("") }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { viewContext ->
                MapView(viewContext).also { view ->
                    view.map.move(
                        CameraPosition(Point(55.751244, 37.618423), 17.0f, 0.0f, 0.0f),
                        Animation(Animation.Type.SMOOTH, 0f),
                        null
                    )
                    mapView = view
                    schemeManager = SchemeManager(viewContext, view.map)
                    schemeManager?.updateCarScaleForZoom(view.map.cameraPosition.zoom)
                }
            },
            modifier = Modifier.fillMaxSize()
        )

        Column(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FloatingActionButton(
                onClick = onClose,
                containerColor = Color.White,
                contentColor = Color.Red
            ) {
                Icon(Icons.Default.Close, contentDescription = "Close")
            }
            FloatingActionButton(
                onClick = {
                    val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                    schemeManager?.addCar(center, "A")
                },
                containerColor = Primary,
                contentColor = Color.White
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create Car A")
            }
            FloatingActionButton(
                onClick = {
                    val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                    schemeManager?.addCar(center, "B")
                },
                containerColor = Color(0xFF0097A7),
                contentColor = Color.White
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create Car B")
            }
            FloatingActionButton(
                onClick = {
                    val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                    schemeManager?.addRoute(center)
                },
                containerColor = Color(0xFF5D4037),
                contentColor = Color.White
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create Route")
            }
            FloatingActionButton(
                onClick = {
                    val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                    schemeManager?.addImpactPoint(center)
                },
                containerColor = Color.Red,
                contentColor = Color.White
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create Impact")
            }
        }

        Card(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(16.dp)
                .fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = Surface)
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("Конструктор схемы", fontWeight = FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IconButton(onClick = { schemeManager?.clearAll() }) {
                        Icon(Icons.Default.Delete, contentDescription = "Clear", tint = Color.Gray)
                    }
                    Button(
                        onClick = {
                            val view = mapView
                            if (view == null || view.width <= 0 || view.height <= 0) return@Button
                            val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
                            view.draw(Canvas(bitmap))
                            val path = schemeManager?.saveToJpg(bitmap)
                            if (path != null) {
                                savedPath = path
                                Toast.makeText(context, "Сохранено в JPG", Toast.LENGTH_SHORT).show()
                            } else {
                                Toast.makeText(context, "Ошибка сохранения", Toast.LENGTH_SHORT).show()
                            }
                        }
                    ) {
                        Icon(Icons.Default.Save, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Сохранить JPG")
                    }
                }
            }
            if (savedPath.isNotBlank()) {
                Text(
                    text = "Путь: $savedPath",
                    modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color.Gray
                )
            }
        }
    }

    DisposableEffect(mapView, schemeManager) {
        val listener = CameraListener { _: Map, cameraPosition: CameraPosition, _, _ ->
            schemeManager?.updateCarScaleForZoom(cameraPosition.zoom)
        }
        mapView?.map?.addCameraListener(listener)
        onDispose {
            mapView?.map?.removeCameraListener(listener)
            mapView?.onStop()
        }
    }

    LaunchedEffect(mapView) {
        mapView?.onStart()
    }
}
