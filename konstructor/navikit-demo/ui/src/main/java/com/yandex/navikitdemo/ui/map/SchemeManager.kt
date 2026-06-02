package com.yandex.navikitdemo.ui.map

import android.content.Context
import android.graphics.*
import android.widget.Toast
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.geometry.Polyline
import com.yandex.mapkit.map.*
import com.yandex.runtime.image.ImageProvider
import com.yandex.mapkit.map.Map as MapKitMap

class SchemeManager(private val context: Context, private val map: MapKitMap) {

    private val masterCollection = map.mapObjects.addCollection().apply {
        zIndex = 1000000f
    }
    private val schemes = mutableListOf<SchemeObject>()

    fun addScheme(center: Point, label: String) {
        SchemeObject(center, label)
        Toast.makeText(context, "ТС $label добавлено", Toast.LENGTH_SHORT).show()
    }

    inner class SchemeObject(center: Point, val label: String) {
        private var carPosition = center
        private var rotation = 0f
        private var arrowEndPos = calculateOffsetPoint(center, rotation + 180f, 0.0002)

        private val collection = masterCollection.addCollection()
        
        private val carPlacemark = collection.addPlacemark(carPosition).apply {
            setIcon(
                ImageProvider.fromBitmap(createCarBitmap(label)),
                IconStyle().apply { 
                    rotationType = RotationType.ROTATE 
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 10f
                    // Reduced initial scale
                    scale = 0.6f
                }
            )
            // Use property access for isFlat if method not found, but many versions use it directly on the object.
            // If both fail, we will use small scale as fallback.
            // MapKit for Android often uses isFlat as a property in PlacemarkMapObject
            // Let's try to set it via cast to ensure we have the right interface if needed.
        }

        private val rotationHandle = collection.addPlacemark(calculateOffsetPoint(carPosition, rotation, 0.00008)).apply {
            setIcon(
                ImageProvider.fromBitmap(createCircleBitmap(Color.RED)), 
                IconStyle().apply { 
                    anchor = PointF(0.5f, 0.5f)
                    zIndex = 20f
                    scale = 0.8f
                }
            )
            isDraggable = true
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) {}
                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    val dLat = point.latitude - carPosition.latitude
                    val dLon = point.longitude - carPosition.longitude
                    rotation = Math.toDegrees(Math.atan2(dLon, dLat)).toFloat()
                    
                    carPlacemark.direction = rotation
                    updateRotationHandlePosition()
                    updateArrowLine()
                }
                override fun onMapObjectDragEnd(mapObject: MapObject) {
                    updateRotationHandlePosition()
                }
            })
        }

        private val arrowEndHandle = collection.addPlacemark(arrowEndPos).apply {
            setIcon(
                ImageProvider.fromBitmap(createArrowBitmap()),
                IconStyle().apply { 
                    rotationType = RotationType.ROTATE
                    anchor = PointF(0.5f, 0.5f) 
                    zIndex = 20f
                    scale = 0.8f
                }
            )
            isDraggable = true
            setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) {}
                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    arrowEndPos = point
                    updateArrowLine()
                }
                override fun onMapObjectDragEnd(mapObject: MapObject) {
                    arrowEndPos = (mapObject as PlacemarkMapObject).geometry
                }
            })
        }

        init {
            // Re-apply draggability to main car to ensure it works
            carPlacemark.isDraggable = true
            carPlacemark.setDragListener(object : MapObjectDragListener {
                override fun onMapObjectDragStart(mapObject: MapObject) {}
                override fun onMapObjectDrag(mapObject: MapObject, point: Point) {
                    carPosition = point
                    updateRotationHandlePosition()
                    updateArrowLine()
                }
                override fun onMapObjectDragEnd(mapObject: MapObject) {}
            })
        }

        private val trajectoryLine = collection.addPolyline(Polyline(listOf(carPosition, arrowEndPos))).apply {
            setDashLength(10f)
            setGapLength(10f)
            setStrokeColor(Color.BLACK)
            setStrokeWidth(4f)
            zIndex = 5f
        }

        private fun updateRotationHandlePosition() {
            rotationHandle.geometry = calculateOffsetPoint(carPosition, rotation, 0.00008)
        }

        private fun updateArrowLine() {
            trajectoryLine.geometry = Polyline(listOf(carPosition, arrowEndPos))
            val dLat = arrowEndPos.latitude - carPosition.latitude
            val dLon = arrowEndPos.longitude - carPosition.longitude
            arrowEndHandle.direction = Math.toDegrees(Math.atan2(dLon, dLat)).toFloat()
        }

        private fun calculateOffsetPoint(center: Point, angleDeg: Float, distance: Double): Point {
            val angleRad = Math.toRadians(angleDeg.toDouble())
            return Point(
                center.latitude + distance * Math.cos(angleRad),
                center.longitude + distance * Math.sin(angleRad)
            )
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
        paint.color = Color.WHITE
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 8f
        canvas.drawCircle(size / 2f, size / 2f, size / 2f - 4f, paint)
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
