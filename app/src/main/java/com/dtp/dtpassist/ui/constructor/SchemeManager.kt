package com.dtp.dtpassist.ui.constructor

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.os.Environment
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.geometry.Polyline
import com.yandex.mapkit.map.IconStyle
import com.yandex.mapkit.map.MapObject
import com.yandex.mapkit.map.MapObjectCollection
import com.yandex.mapkit.map.MapObjectDragListener
import com.yandex.mapkit.map.PlacemarkMapObject
import com.yandex.mapkit.map.PolylineMapObject
import com.yandex.mapkit.map.RotationType
import com.yandex.runtime.image.ImageProvider
import java.io.File
import java.io.FileOutputStream
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import com.yandex.mapkit.map.Map as MapKitMap

class SchemeManager(private val context: Context, private val map: MapKitMap) {

    private val masterCollection = map.mapObjects.addCollection().apply { zIndex = 1_000_000f }
    private val carPlacemarks = mutableListOf<PlacemarkMapObject>()
    private val routeObjects = mutableListOf<RouteObject>()
    private val impactPlacemarks = mutableListOf<PlacemarkMapObject>()
    private var currentCarScale = 0.6f

    fun addCar(center: Point, label: String) {
        CarObject(center, label)
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
        carPlacemarks.clear()
        routeObjects.clear()
        impactPlacemarks.clear()
    }

    fun saveToJpg(mapBitmap: Bitmap): String? {
        return runCatching {
            val outputDir = File(
                context.getExternalFilesDir(Environment.DIRECTORY_PICTURES),
                "dtp_schemes"
            ).apply { mkdirs() }
            val file = File(outputDir, "scheme_${System.currentTimeMillis()}.jpg")
            FileOutputStream(file).use { stream ->
                mapBitmap.compress(Bitmap.CompressFormat.JPEG, 92, stream)
            }
            file.absolutePath
        }.getOrNull()
    }

    fun updateCarScaleForZoom(zoom: Float) {
        val newScale = ((zoom / 17f) * 0.6f).coerceIn(0.25f, 1.6f)
        if (abs(newScale - currentCarScale) < 0.01f) return
        currentCarScale = newScale
        carPlacemarks.forEach { placemark ->
            placemark.setIconStyle(
                IconStyle().apply {
                    rotationType = RotationType.ROTATE
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 10f
                    scale = currentCarScale
                }
            )
        }
    }

    private inner class CarObject(center: Point, private val label: String) {
        private var carPosition = center
        private var rotation = 0f
        private val collection = masterCollection.addCollection()

        private val carPlacemark = collection.addPlacemark(carPosition).apply {
            setIcon(
                ImageProvider.fromBitmap(createCarBitmap(label)),
                IconStyle().apply {
                    rotationType = RotationType.ROTATE
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 10f
                    scale = currentCarScale
                }
            )
            isDraggable = true
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) = Unit
                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    carPosition = point
                    updateRotationHandlePosition()
                }
                override fun onMapObjectDragEnd(mapObject: MapObject) = Unit
            })
        }

        private val rotationHandle = collection.addPlacemark(offsetPoint(carPosition, rotation, 0.00008)).apply {
            setIcon(
                ImageProvider.fromBitmap(createCircleBitmap(Color.RED)),
                IconStyle().apply {
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 20f
                    scale = 0.75f
                }
            )
            isDraggable = true
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) = Unit
                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    val dLat = point.latitude - carPosition.latitude
                    val dLon = point.longitude - carPosition.longitude
                    rotation = Math.toDegrees(atan2(dLon, dLat)).toFloat()
                    carPlacemark.direction = rotation
                    updateRotationHandlePosition()
                }
                override fun onMapObjectDragEnd(mapObject: MapObject) {
                    updateRotationHandlePosition()
                }
            })
        }

        init {
            carPlacemarks.add(carPlacemark)
        }

        private fun updateRotationHandlePosition() {
            rotationHandle.geometry = offsetPoint(carPosition, rotation, 0.00008)
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

        private val routeLine: PolylineMapObject = collection.addPolyline(Polyline(buildCurvePoints())).apply {
            setStrokeColor(Color.BLACK)
            setStrokeWidth(4f)
            zIndex = 7f
        }

        private fun updateRoute() {
            routeLine.geometry = Polyline(buildCurvePoints())
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

    private fun routeHandleStyle(scale: Float = 0.55f, z: Float = 25f): IconStyle {
        return IconStyle().apply {
            anchor = PointF(0.5f, 0.5f)
            this.scale = scale
            zIndex = z
        }
    }

    private fun offsetPoint(center: Point, angleDeg: Float, distance: Double): Point {
        val angleRad = Math.toRadians(angleDeg.toDouble())
        return Point(
            center.latitude + distance * cos(angleRad),
            center.longitude + distance * sin(angleRad)
        )
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

    private fun createCarBitmap(label: String): Bitmap {
        val width = 120
        val height = 200
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = Color.WHITE
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), 25f, 25f, paint)
        paint.color = Color.BLACK
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 10f
        canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), 25f, 25f, paint)
        paint.style = Paint.Style.FILL
        paint.textSize = 80f
        paint.textAlign = Paint.Align.CENTER
        canvas.drawText(label, width / 2f, height / 2f + 30f, paint)
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
        val size = 100
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint().apply {
            color = Color.BLUE
            style = Paint.Style.FILL
            isAntiAlias = true
        }
        val path = Path().apply {
            moveTo(size / 2f, 0f)
            lineTo(size.toFloat(), size.toFloat())
            lineTo(0f, size.toFloat())
            close()
        }
        canvas.drawPath(path, paint)
        return bitmap
    }
}
