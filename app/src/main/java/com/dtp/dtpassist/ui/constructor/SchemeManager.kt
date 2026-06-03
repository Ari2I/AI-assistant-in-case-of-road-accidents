package com.dtp.dtpassist.ui.constructor

import android.content.ContentValues
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.geometry.Polyline
import com.yandex.mapkit.map.IconStyle
import com.yandex.mapkit.map.MapObject
import com.yandex.mapkit.map.MapObjectCollection
import com.yandex.mapkit.map.MapObjectDragListener
import com.yandex.mapkit.map.MapObjectTapListener
import com.yandex.mapkit.map.PlacemarkMapObject
import com.yandex.mapkit.map.PolylineMapObject
import com.yandex.mapkit.map.RotationType
import com.yandex.runtime.image.ImageProvider
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStream
import kotlin.math.abs
import kotlin.math.pow
import com.yandex.mapkit.map.Map as MapKitMap

class SchemeManager(
    private val context: Context,
    private val map: MapKitMap,
    private val onSelectionChanged: (SelectedVehicleState?) -> Unit = {},
) {

    private val masterCollection = map.mapObjects.addCollection().apply { zIndex = 1_000_000f }
    private val vehicleObjects = mutableListOf<VehicleObject>()
    private val routeObjects = mutableListOf<RouteObject>()
    private val impactPlacemarks = mutableListOf<PlacemarkMapObject>()
    private var currentVehicleScale = 0.18f
    private var selectedVehicle: VehicleObject? = null
    private var nextVehicleId = 1L
    private var didCreateBootstrapVehicle = false

    fun addCar(center: Point, label: String) {
        ensureVehicleBootstrap(center)
        val vehicle = VehicleObject(nextVehicleId++, center, label, VehicleType.Car)
        vehicleObjects.add(vehicle)
        selectVehicle(vehicle)
    }

    fun addArrow(center: Point) {
        ensureVehicleBootstrap(center)
        val arrow = VehicleObject(nextVehicleId++, center, "", VehicleType.Arrow)
        vehicleObjects.add(arrow)
        selectVehicle(arrow)
    }

    private fun ensureVehicleBootstrap(center: Point) {
        if (didCreateBootstrapVehicle) return
        didCreateBootstrapVehicle = true
        val bootstrap = VehicleObject(nextVehicleId++, center, "_", VehicleType.Car)
        bootstrap.remove()
    }

    fun rotateSelectedBy(degrees: Float) {
        selectedVehicle?.rotateBy(degrees)
    }

    fun clearSelection() {
        selectedVehicle?.setSelected(false)
        selectedVehicle = null
        onSelectionChanged(null)
    }

    fun deleteSelected() {
        val vehicle = selectedVehicle ?: return
        vehicle.remove()
        vehicleObjects.remove(vehicle)
        selectedVehicle = null
        onSelectionChanged(null)
    }

    fun updateSelectedLabel(label: String) {
        selectedVehicle?.updateLabel(label)
    }

    fun updateSelectedSize(size: VehicleSize) {
        selectedVehicle?.updateSize(size)
    }

    fun addImpactPoint(center: Point) {
        val impact = masterCollection.addPlacemark(center).apply {
            setIcon(
                ImageProvider.fromBitmap(createCircleBitmap(Color.RED)),
                IconStyle().apply {
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 30f
                    scale = 0.6f
                }
            )
            isDraggable = true
        }
        impactPlacemarks.add(impact)
    }

    fun addRoute(center: Point) {
        routeObjects.add(RouteObject(center))
    }

    fun clearAll() {
        masterCollection.clear()
        vehicleObjects.clear()
        routeObjects.clear()
        impactPlacemarks.clear()
        selectedVehicle = null
        onSelectionChanged(null)
    }

    fun saveToJpg(mapBitmap: Bitmap): String? {
        return saveBitmap(
            mapBitmap = mapBitmap,
            extension = "jpg",
            mimeType = "image/jpeg",
            format = Bitmap.CompressFormat.JPEG,
            quality = 92,
        )
    }

    fun saveToPng(mapBitmap: Bitmap): String? {
        return saveBitmap(
            mapBitmap = mapBitmap,
            extension = "png",
            mimeType = "image/png",
            format = Bitmap.CompressFormat.PNG,
            quality = 100,
        )
    }

    private fun saveToGallery(mapBitmap: Bitmap): String? {
        return saveToGallery(
            mapBitmap = mapBitmap,
            extension = "jpg",
            mimeType = "image/jpeg",
            format = Bitmap.CompressFormat.JPEG,
            quality = 92,
        )
    }

    private fun saveBitmap(
        mapBitmap: Bitmap,
        extension: String,
        mimeType: String,
        format: Bitmap.CompressFormat,
        quality: Int,
    ): String? {
        return saveToGallery(mapBitmap, extension, mimeType, format, quality)
            ?: saveToAppPictures(mapBitmap, extension, format, quality)
    }

    private fun saveToGallery(
        mapBitmap: Bitmap,
        extension: String,
        mimeType: String,
        format: Bitmap.CompressFormat,
        quality: Int,
    ): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        return runCatching {
            val fileName = "scheme_${System.currentTimeMillis()}.$extension"
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
                put(MediaStore.Images.Media.MIME_TYPE, mimeType)
                put(MediaStore.Images.Media.RELATIVE_PATH, "${Environment.DIRECTORY_PICTURES}/DtpAssist")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: return@runCatching null

            resolver.openOutputStream(uri)?.use { stream ->
                writeBitmap(mapBitmap, stream, format, quality)
            } ?: return@runCatching null

            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            uri.toString()
        }.getOrNull()
    }

    private fun saveToAppPictures(
        mapBitmap: Bitmap,
        extension: String,
        format: Bitmap.CompressFormat,
        quality: Int,
    ): String? {
        return runCatching {
            val outputDir = File(
                context.getExternalFilesDir(Environment.DIRECTORY_PICTURES),
                "dtp_schemes"
            ).apply { mkdirs() }
            val file = File(outputDir, "scheme_${System.currentTimeMillis()}.$extension")
            FileOutputStream(file).use { stream ->
                writeBitmap(mapBitmap, stream, format, quality)
            }
            file.absolutePath
        }.getOrNull()
    }

    private fun writeBitmap(
        mapBitmap: Bitmap,
        stream: OutputStream,
        format: Bitmap.CompressFormat,
        quality: Int,
    ) {
        mapBitmap.compress(format, quality, stream)
    }

    fun buildExportSnapshot(): MapExportSnapshot {
        return MapExportSnapshot(
            vehicles = vehicleObjects.map { it.snapshot() },
            routes = routeObjects.map { it.snapshot() },
            impacts = impactPlacemarks.map { ExportPointOverlay(it.geometry, Color.RED, 0.6f, 30f) },
        )
    }

    fun updateCarScaleForZoom(zoom: Float) {
        val zoomFactor = 2.0.pow(((zoom - 17f) / 5f).toDouble()).toFloat()
        val newScale = (0.18f * zoomFactor).coerceIn(0.07f, 0.34f)
        if (abs(newScale - currentVehicleScale) < 0.005f) return
        currentVehicleScale = newScale
        vehicleObjects.forEach { it.updateVisuals() }
    }

    private fun selectVehicle(vehicle: VehicleObject) {
        if (selectedVehicle === vehicle) {
            onSelectionChanged(vehicle.state())
            return
        }
        selectedVehicle?.setSelected(false)
        selectedVehicle = vehicle
        vehicle.setSelected(true)
        onSelectionChanged(vehicle.state())
    }

    private inner class VehicleObject(
        private val id: Long,
        center: Point,
        initialLabel: String,
        private val type: VehicleType,
    ) {
        private var vehiclePosition = center
        private var label = initialLabel
        private var rotation = 0f
        private var size = VehicleSize.Small
        private var isSelected = false
        private val collection = masterCollection.addCollection()

        private val vehiclePlacemark = collection.addPlacemark(vehiclePosition).apply {
            setIcon(
                ImageProvider.fromBitmap(createVehicleBitmap(label, type)),
                vehicleIconStyle(currentVehicleScale * size.scaleMultiplier)
            )
            isDraggable = false
            addTapListener(
                MapObjectTapListener { _, _ ->
                    selectVehicle(this@VehicleObject)
                    true
                }
            )
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) {
                    selectVehicle(this@VehicleObject)
                }

                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    vehiclePosition = point
                    syncGeometry()
                }

                override fun onMapObjectDragEnd(mapObject: MapObject) {
                    vehiclePosition = (mapObject as PlacemarkMapObject).geometry
                    syncGeometry()
                }
            })
        }

        private val hitboxPlacemark = collection.addPlacemark(vehiclePosition).apply {
            setIcon(
                ImageProvider.fromBitmap(createHitboxBitmap(type)),
                hitboxIconStyle(currentVehicleScale * size.hitboxMultiplier)
            )
            isDraggable = false
            addTapListener(
                MapObjectTapListener { _, _ ->
                    selectVehicle(this@VehicleObject)
                    true
                }
            )
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) {
                    selectVehicle(this@VehicleObject)
                }

                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    vehiclePosition = point
                    syncGeometry()
                }

                override fun onMapObjectDragEnd(mapObject: MapObject) {
                    vehiclePosition = (mapObject as PlacemarkMapObject).geometry
                    syncGeometry()
                }
            })
        }

        init {
            syncGeometry()
        }

        fun setSelected(selected: Boolean) {
            isSelected = selected
            vehiclePlacemark.isDraggable = selected
            hitboxPlacemark.isDraggable = selected
        }

        fun rotateBy(degrees: Float) {
            rotation += degrees
            syncGeometry()
            onSelectionChanged(state())
        }

        fun updateLabel(newLabel: String) {
            label = newLabel.take(3)
            vehiclePlacemark.setIcon(
                ImageProvider.fromBitmap(createVehicleBitmap(label, type)),
                vehicleIconStyle(currentVehicleScale * size.scaleMultiplier)
            )
            syncGeometry()
            onSelectionChanged(state())
        }

        fun updateSize(newSize: VehicleSize) {
            if (type == VehicleType.Arrow) {
                onSelectionChanged(state())
                return
            }
            size = newSize
            updateVisuals()
            onSelectionChanged(state())
        }

        fun updateVisuals() {
            vehiclePlacemark.setIconStyle(vehicleIconStyle(currentVehicleScale * size.scaleMultiplier))
            hitboxPlacemark.setIconStyle(hitboxIconStyle(currentVehicleScale * size.hitboxMultiplier))
            syncGeometry()
        }

        fun state(): SelectedVehicleState {
            return SelectedVehicleState(
                id = id,
                label = label,
                size = size,
                type = type,
            )
        }

        fun remove() {
            collection.clear()
        }

        fun snapshot(): ExportVehicleOverlay {
            return ExportVehicleOverlay(
                position = vehiclePosition,
                label = label,
                rotation = normalizedDirection(rotation),
                size = size,
                type = type,
            )
        }

        private fun syncGeometry() {
            val direction = normalizedDirection(rotation)
            vehiclePlacemark.geometry = vehiclePosition
            hitboxPlacemark.geometry = vehiclePosition
            vehiclePlacemark.direction = direction
            hitboxPlacemark.direction = direction
            vehiclePlacemark.isDraggable = isSelected
            hitboxPlacemark.isDraggable = isSelected
        }
    }

    private inner class RouteObject(center: Point) {
        private val collection = masterCollection.addCollection()
        private var startPoint = Point(center.latitude + 0.0001, center.longitude - 0.0001)
        private var endPoint = Point(center.latitude - 0.0001, center.longitude + 0.0001)
        private var curvePoint = center

        private val startHandle = collection.addPlacemark(startPoint).apply {
            setIcon(ImageProvider.fromBitmap(createCircleBitmap(Color.GREEN)), routeHandleStyle())
            isDraggable = true
            setDragListener(simpleDrag { point ->
                startPoint = point
                updateRoute()
            })
        }

        private val endHandle = collection.addPlacemark(endPoint).apply {
            setIcon(ImageProvider.fromBitmap(createCircleBitmap(Color.BLUE)), routeHandleStyle())
            isDraggable = true
            setDragListener(simpleDrag { point ->
                endPoint = point
                updateRoute()
            })
        }

        private val curveHandle = collection.addPlacemark(curvePoint).apply {
            setIcon(
                ImageProvider.fromBitmap(createCircleBitmap(Color.MAGENTA)),
                routeHandleStyle(scale = 0.5f, z = 26f)
            )
            isDraggable = true
            setDragListener(simpleDrag { point ->
                curvePoint = point
                updateRoute()
            })
        }

        private val routeLine: PolylineMapObject =
            collection.addPolyline(Polyline(buildCurvePoints())).apply {
                setStrokeColor(Color.BLACK)
                setStrokeWidth(4f)
                zIndex = 7f
            }

        private fun updateRoute() {
            routeLine.geometry = Polyline(buildCurvePoints())
        }

        fun snapshot(): ExportRouteOverlay {
            return ExportRouteOverlay(
                startPoint = startPoint,
                endPoint = endPoint,
                curvePoint = curvePoint,
                strokeColor = Color.BLACK,
                strokeWidth = 4f,
                handleOverlays = listOf(
                    ExportPointOverlay(startPoint, Color.GREEN, 0.55f, 25f),
                    ExportPointOverlay(endPoint, Color.BLUE, 0.55f, 25f),
                    ExportPointOverlay(curvePoint, Color.MAGENTA, 0.5f, 26f),
                )
            )
        }

        private fun buildCurvePoints(steps: Int = 24): List<Point> {
            val points = ArrayList<Point>(steps + 1)
            for (i in 0..steps) {
                val t = i / steps.toDouble()
                val oneMinus = 1.0 - t
                val lat = oneMinus * oneMinus * startPoint.latitude +
                    2 * oneMinus * t * curvePoint.latitude +
                    t * t * endPoint.latitude
                val lon = oneMinus * oneMinus * startPoint.longitude +
                    2 * oneMinus * t * curvePoint.longitude +
                    t * t * endPoint.longitude
                points.add(Point(lat, lon))
            }
            return points
        }
    }

    private fun vehicleIconStyle(scale: Float): IconStyle {
        return IconStyle().apply {
            rotationType = RotationType.ROTATE
            anchor = PointF(0.5f, 0.5f)
            zIndex = 10f
            this.scale = scale
        }
    }

    private fun hitboxIconStyle(scale: Float): IconStyle {
        return IconStyle().apply {
            rotationType = RotationType.ROTATE
            anchor = PointF(0.5f, 0.5f)
            zIndex = 8f
            this.scale = scale
        }
    }

    private fun routeHandleStyle(scale: Float = 0.55f, z: Float = 25f): IconStyle {
        return IconStyle().apply {
            anchor = PointF(0.5f, 0.5f)
            this.scale = scale
            zIndex = z
        }
    }

    private fun normalizedDirection(rotation: Float): Float {
        var normalized = rotation % 360f
        if (normalized < 0f) normalized += 360f
        return normalized
    }

    private fun simpleDrag(onDrag: (Point) -> Unit): MapObjectDragListener {
        return object : MapObjectDragListener {
            override fun onMapObjectDragStart(mapObject: MapObject) = Unit
            override fun onMapObjectDrag(mapObject: MapObject, point: Point) = onDrag(point)
            override fun onMapObjectDragEnd(mapObject: MapObject) {
                onDrag((mapObject as PlacemarkMapObject).geometry)
            }
        }
    }

    private fun createVehicleBitmap(label: String, type: VehicleType): Bitmap {
        if (type == VehicleType.Arrow) {
            return createArrowBitmap()
        }
        val width = if (type == VehicleType.Truck) 150 else 110
        val height = if (type == VehicleType.Truck) 250 else 180
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = Color.WHITE
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), 24f, 24f, paint)
        if (type == VehicleType.Truck) {
            paint.color = Color.LTGRAY
            canvas.drawRoundRect(
                width * 0.18f,
                height * 0.05f,
                width * 0.82f,
                height * 0.32f,
                18f,
                18f,
                paint
            )
            paint.color = Color.WHITE
        }
        paint.color = Color.BLACK
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 8f
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), 24f, 24f, paint)
        paint.style = Paint.Style.FILL
        paint.textSize = if (type == VehicleType.Truck) 58f else 68f
        paint.textAlign = Paint.Align.CENTER
        if (label.isNotBlank()) {
            canvas.drawText(label, width / 2f, height / 2f + 22f, paint)
        }
        return bitmap
    }

    private fun createHitboxBitmap(type: VehicleType): Bitmap {
        val width = when (type) {
            VehicleType.Truck -> 230
            VehicleType.Arrow -> 210
            VehicleType.Car -> 180
        }
        val height = when (type) {
            VehicleType.Truck -> 330
            VehicleType.Arrow -> 210
            VehicleType.Car -> 260
        }
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = Color.argb(1, 0, 0, 0)
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), 32f, 32f, paint)
        return bitmap
    }

    private fun createCircleBitmap(colorInt: Int): Bitmap {
        val size = 100
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = colorInt
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        canvas.drawCircle(size / 2f, size / 2f, size / 2f, paint)
        return bitmap
    }

    private fun createArrowBitmap(): Bitmap {
        val width = 110
        val height = 240
        val size = width.coerceAtLeast(height)
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = Color.WHITE
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        val path = Path().apply {
            moveTo(size * 0.5f, size * 0.04f)
            lineTo(size * 0.82f, size * 0.28f)
            lineTo(size * 0.62f, size * 0.28f)
            lineTo(size * 0.62f, size * 0.94f)
            lineTo(size * 0.38f, size * 0.94f)
            lineTo(size * 0.38f, size * 0.28f)
            lineTo(size * 0.18f, size * 0.28f)
            close()
        }
        canvas.drawPath(path, paint)
        paint.color = Color.BLACK
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 8f
        canvas.drawPath(path, paint)
        return bitmap
    }
}

data class MapExportSnapshot(
    val vehicles: List<ExportVehicleOverlay>,
    val routes: List<ExportRouteOverlay>,
    val impacts: List<ExportPointOverlay>,
)

data class ExportVehicleOverlay(
    val position: Point,
    val label: String,
    val rotation: Float,
    val size: VehicleSize,
    val type: VehicleType,
)

data class ExportRouteOverlay(
    val startPoint: Point,
    val endPoint: Point,
    val curvePoint: Point,
    val strokeColor: Int,
    val strokeWidth: Float,
    val handleOverlays: List<ExportPointOverlay>,
)

data class ExportPointOverlay(
    val point: Point,
    val color: Int,
    val scale: Float,
    val zIndex: Float,
)

data class SelectedVehicleState(
    val id: Long,
    val label: String,
    val size: VehicleSize,
    val type: VehicleType,
)

enum class VehicleSize(val scaleMultiplier: Float, val hitboxMultiplier: Float) {
    Small(scaleMultiplier = 1.0f, hitboxMultiplier = 1.0f),
    Large(scaleMultiplier = 1.45f, hitboxMultiplier = 1.3f),
}

enum class VehicleType {
    Car,
    Truck,
    Arrow,
}
