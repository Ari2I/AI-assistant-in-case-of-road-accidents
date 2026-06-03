package com.dtp.dtpassist.ui.screens

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.PixelCopy
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Save
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.dtp.dtpassist.R
import com.dtp.dtpassist.ui.constructor.MapExportException
import com.dtp.dtpassist.ui.constructor.MapExportRequest
import com.dtp.dtpassist.ui.constructor.SchemeManager
import com.dtp.dtpassist.ui.constructor.SelectedVehicleState
import com.dtp.dtpassist.ui.constructor.VehicleSize
import com.dtp.dtpassist.ui.constructor.VehicleType
import com.dtp.dtpassist.ui.constructor.exportMapToPng
import com.dtp.dtpassist.ui.constructor.formatForEuroprotocolField
import com.dtp.dtpassist.ui.theme.Primary
import com.dtp.dtpassist.ui.theme.Surface
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.yandex.mapkit.Animation
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.map.CameraListener
import com.yandex.mapkit.map.CameraPosition
import com.yandex.mapkit.map.Map
import com.yandex.mapkit.mapview.MapView
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

private const val EUROPROTOCOL_GUIDE_RATIO = 2f

@Composable
fun ConstructorScreen(onClose: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var mapView by remember { mutableStateOf<MapView?>(null) }
    var schemeManager by remember { mutableStateOf<SchemeManager?>(null) }
    var didRequestLocation by remember { mutableStateOf(false) }
    var isExportInProgress by remember { mutableStateOf(false) }
    var selectedVehicle by remember { mutableStateOf<SelectedVehicleState?>(null) }
    var labelInput by remember { mutableStateOf("") }
    var isEditorVisible by remember { mutableStateOf(true) }

    LaunchedEffect(selectedVehicle?.id, selectedVehicle?.label) {
        labelInput = selectedVehicle?.label.orEmpty()
        if (selectedVehicle != null) {
            isEditorVisible = true
        }
    }

    fun showLocationError() {
        Toast.makeText(context, "Не удалось определить местоположение", Toast.LENGTH_SHORT).show()
    }

    fun moveToPoint(point: Point, zoom: Float = 18f) {
        mapView?.map?.move(
            CameraPosition(point, zoom, 0.0f, 0.0f),
            Animation(Animation.Type.SMOOTH, 0.35f),
            null
        )
    }

    fun moveToCurrentLocation() {
        val client = LocationServices.getFusedLocationProviderClient(context)
        client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
            .addOnSuccessListener { current ->
                if (current != null) {
                    moveToPoint(Point(current.latitude, current.longitude))
                } else {
                    client.lastLocation
                        .addOnSuccessListener { last ->
                            if (last != null) {
                                moveToPoint(Point(last.latitude, last.longitude))
                            } else {
                                showLocationError()
                            }
                        }
                        .addOnFailureListener {
                            showLocationError()
                        }
                }
            }
            .addOnFailureListener {
                showLocationError()
            }
    }

    fun exportCurrentMap() {
        val view = mapView
        val manager = schemeManager
        if (view == null || manager == null || view.width <= 0 || view.height <= 0 || isExportInProgress) {
            return
        }

        isExportInProgress = true
        scope.launch {
            val exportResult = runCatching {
                exportMapToPng(
                    context = context,
                    request = MapExportRequest(
                        sourceMapView = view,
                        cameraPosition = view.map.cameraPosition,
                        mapType = view.map.mapType,
                        overlays = manager.buildExportSnapshot(),
                        cropRectPx = null,
                        qualityScale = 1f,
                    )
                )
            }

            isExportInProgress = false

            val error = exportResult.exceptionOrNull()
            if (error != null) {
                val fallbackBitmap = captureVisibleMapArea(context, view)
                if (fallbackBitmap != null) {
                    val fallbackPath = manager.saveToPng(formatForEuroprotocolField(fallbackBitmap))
                    if (fallbackPath != null) {
                        Toast.makeText(context, "PNG сохранен", Toast.LENGTH_SHORT).show()
                        return@launch
                    }
                }
                val message = when (error) {
                    is MapExportException -> error.message
                    else -> error.message ?: error.javaClass.simpleName
                }?.take(180) ?: "Неизвестная ошибка"
                Toast.makeText(context, "Не удалось экспортировать карту: $message", Toast.LENGTH_LONG).show()
                return@launch
            }

            val result = exportResult.getOrNull() ?: return@launch
            val path = manager.saveToPng(result.bitmap)
            if (path != null) {
                Toast.makeText(context, "PNG сохранен", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(context, "Ошибка сохранения PNG", Toast.LENGTH_SHORT).show()
            }
        }
    }

    val locationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            moveToCurrentLocation()
        } else {
            Toast.makeText(
                context,
                "Для центрирования схемы нужен доступ к геолокации",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { viewContext ->
                val root = LayoutInflater.from(viewContext)
                    .inflate(R.layout.view_constructor_map, null, false) as FrameLayout
                val view = root.findViewById<MapView>(R.id.constructorMapView)
                view.also {
                    view.map.move(
                        CameraPosition(Point(55.751244, 37.618423), 17.0f, 0.0f, 0.0f),
                        Animation(Animation.Type.SMOOTH, 0f),
                        null
                    )
                    mapView = view
                    schemeManager = SchemeManager(viewContext, view.map) { selected ->
                        selectedVehicle = selected
                    }
                    schemeManager?.updateCarScaleForZoom(view.map.cameraPosition.zoom)
                }
                root
            },
            modifier = Modifier.fillMaxSize()
        )

        Canvas(modifier = Modifier.fillMaxSize()) {
            val horizontalPadding = 24.dp.toPx()
            val topPadding = 120.dp.toPx()
            val bottomPadding = 140.dp.toPx()
            val availableWidth = (size.width - horizontalPadding * 2).coerceAtLeast(0f)
            val availableHeight = (size.height - topPadding - bottomPadding).coerceAtLeast(0f)
            if (availableWidth <= 0f || availableHeight <= 0f) return@Canvas

            val widthByHeight = availableHeight * EUROPROTOCOL_GUIDE_RATIO
            val guideWidth = minOf(availableWidth, widthByHeight)
            val guideHeight = guideWidth / EUROPROTOCOL_GUIDE_RATIO
            val left = (size.width - guideWidth) / 2f
            val top = (size.height - guideHeight) / 2f

            drawRect(
                color = Color(0xFF2ECC71),
                topLeft = androidx.compose.ui.geometry.Offset(left, top),
                size = androidx.compose.ui.geometry.Size(guideWidth, guideHeight),
                style = Stroke(width = 3.dp.toPx())
            )
        }

        if (!isExportInProgress) {
            Column(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FloatingActionButton(
                    onClick = ::exportCurrentMap,
                    containerColor = Color.White,
                    contentColor = Primary
                ) {
                    Icon(Icons.Default.Save, contentDescription = "Сохранить карту")
                }
                FloatingActionButton(
                    onClick = {
                        val granted = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.ACCESS_FINE_LOCATION,
                        ) == PackageManager.PERMISSION_GRANTED
                        if (granted) {
                            moveToCurrentLocation()
                        } else {
                            locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                        }
                    },
                    containerColor = Color.White,
                    contentColor = Primary
                ) {
                    Icon(Icons.Default.MyLocation, contentDescription = "Мое местоположение")
                }
            }
        }

        if (!isExportInProgress) {
            Column(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(16.dp),
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FloatingActionButton(
                    onClick = onClose,
                    containerColor = Color.White,
                    contentColor = Color.Red
                ) {
                    Icon(Icons.Default.Close, contentDescription = "Закрыть")
                }
                FloatingActionButton(
                    onClick = {
                        val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                        schemeManager?.addCar(center, "A")
                    },
                    containerColor = Primary,
                    contentColor = Color.White
                ) {
                    Text("\uD83D\uDE97", fontSize = 22.sp)
                }
                FloatingActionButton(
                    onClick = {
                        val center = mapView?.map?.cameraPosition?.target ?: Point(0.0, 0.0)
                        schemeManager?.addArrow(center)
                    },
                    containerColor = Color.White,
                    contentColor = Primary
                ) {
                    Icon(Icons.Default.ArrowUpward, contentDescription = "Добавить стрелку")
                }
                if (selectedVehicle != null) {
                    FloatingActionButton(
                        onClick = { schemeManager?.deleteSelected() },
                        containerColor = Color.White,
                        contentColor = Color.Red
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = "Удалить выбранный объект")
                    }
                }
            }
        }

        if (!isExportInProgress && selectedVehicle != null && isEditorVisible) {
            Card(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(16.dp)
                    .fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = Surface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Редактор схемы", fontWeight = FontWeight.Bold)
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            IconButton(onClick = { isEditorVisible = false }) {
                                Icon(
                                    Icons.Default.KeyboardArrowDown,
                                    contentDescription = "Скрыть меню",
                                    tint = Color.Gray
                                )
                            }
                        }
                    }

                    VehicleControlsPanel(
                        labelInput = labelInput,
                        selectedVehicle = selectedVehicle!!,
                        onLabelChange = { value ->
                            labelInput = value.take(3)
                            schemeManager?.updateSelectedLabel(labelInput)
                        },
                        onRotate = { schemeManager?.rotateSelectedBy(25f) },
                        onSizeChange = { schemeManager?.updateSelectedSize(it) },
                        onPlace = {
                            schemeManager?.clearSelection()
                            isEditorVisible = false
                        },
                    )
                }
            }
        }

        if (!isExportInProgress && selectedVehicle != null && !isEditorVisible) {
            Card(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(16.dp),
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(containerColor = Surface)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text("Редактор схемы", fontWeight = FontWeight.SemiBold)
                    IconButton(onClick = { isEditorVisible = true }) {
                        Icon(
                            Icons.Default.KeyboardArrowUp,
                            contentDescription = "Показать меню",
                            tint = Primary
                        )
                    }
                }
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

    LaunchedEffect(mapView, didRequestLocation) {
        if (mapView == null || didRequestLocation) return@LaunchedEffect
        didRequestLocation = true
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) {
            moveToCurrentLocation()
        } else {
            locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }
}

@Composable
private fun VehicleControlsPanel(
    labelInput: String,
    selectedVehicle: SelectedVehicleState,
    onLabelChange: (String) -> Unit,
    onRotate: () -> Unit,
    onSizeChange: (VehicleSize) -> Unit,
    onPlace: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (selectedVehicle.type != VehicleType.Arrow) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Button(
                    onClick = { onSizeChange(VehicleSize.Small) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (selectedVehicle.size == VehicleSize.Small) Primary else Color.LightGray,
                        contentColor = if (selectedVehicle.size == VehicleSize.Small) Color.White else Color.Black
                    )
                ) {
                    Text("Малый")
                }
                Button(
                    onClick = { onSizeChange(VehicleSize.Large) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (selectedVehicle.size == VehicleSize.Large) Primary else Color.LightGray,
                        contentColor = if (selectedVehicle.size == VehicleSize.Large) Color.White else Color.Black
                    )
                ) {
                    Text("Крупный")
                }
            }
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(onClick = onRotate) {
                Text("Повернуть на 25°")
            }
            Button(
                onClick = onPlace,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.LightGray,
                    contentColor = Color.Black
                )
            ) {
                Text("Разместить")
            }
        }

        if (selectedVehicle.type != VehicleType.Arrow) {
            OutlinedTextField(
                value = labelInput,
                onValueChange = onLabelChange,
                label = { Text("Надпись на текстурке") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp)
            )
        }
    }
}

private suspend fun captureVisibleMapArea(
    context: Context,
    mapView: MapView,
): Bitmap? {
    val activity = context.findActivity() ?: return null
    val decorView = activity.window.decorView
    val windowWidth = decorView.width
    val windowHeight = decorView.height
    if (windowWidth <= 0 || windowHeight <= 0 || mapView.width <= 0 || mapView.height <= 0) return null

    val windowBitmap = Bitmap.createBitmap(windowWidth, windowHeight, Bitmap.Config.ARGB_8888)
    val copyResult = suspendCancellableCoroutine<Boolean> { continuation ->
        PixelCopy.request(activity.window, windowBitmap, { result ->
            if (continuation.isActive) {
                continuation.resume(result == PixelCopy.SUCCESS)
            }
        }, Handler(Looper.getMainLooper()))
    }
    if (!copyResult) return null

    val location = IntArray(2)
    mapView.getLocationInWindow(location)
    val mapLeft = location[0].coerceIn(0, windowBitmap.width - 1)
    val mapTop = location[1].coerceIn(0, windowBitmap.height - 1)
    val mapWidth = mapView.width.coerceAtMost(windowBitmap.width - mapLeft)
    val mapHeight = mapView.height.coerceAtMost(windowBitmap.height - mapTop)
    if (mapWidth <= 0 || mapHeight <= 0) return null

    return Bitmap.createBitmap(windowBitmap, mapLeft, mapTop, mapWidth, mapHeight)
}

private tailrec fun Context.findActivity(): Activity? {
    return when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }
}
