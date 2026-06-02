package com.yandex.navikitdemo.ui.map

import android.os.Bundle
import android.view.View
import androidx.fragment.app.viewModels
import androidx.navigation.fragment.findNavController
import androidx.lifecycle.lifecycleScope
import com.yandex.mapkit.geometry.Point
import com.yandex.navikitdemo.ui.R
import com.yandex.navikitdemo.ui.common.BaseMapFragment
import com.yandex.navikitdemo.ui.utils.subscribe
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MapFragment : BaseMapFragment(R.layout.fragment_map) {

    private val viewModel: MapViewModel by viewModels()
    private var schemeManager: SchemeManager? = null
    private var carCount = 0

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        schemeManager = SchemeManager(requireContext(), mapWindow.map)

        if (savedInstanceState == null && viewModel.isGuidanceInProgress()) {
            openGuidance()
        }

        mapControlsView.setFindMeButtonClickCallback {
            cameraManager.moveCameraToUserLocation()
        }

        view.findViewById<View>(R.id.button_add_scheme).setOnClickListener {
            val center = mapWindow.map.cameraPosition.target
            val label = if (carCount == 0) "A" else if (carCount == 1) "B" else (carCount + 1).toString()
            schemeManager?.addScheme(center, label)
            carCount++
        }

        mapTapManager.longTapActions.subscribe(viewLifecycleOwner) {
            showDialogAlert(it)
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.clearNavigationSerialization()
    }

    private fun showDialogAlert(point: Point) {
        alertDialogFactory
            .requestToPointDialog {
                viewModel.setToPoint(point)
                openRouteVariants()
            }
            .show()
    }

    private fun openRouteVariants() {
        val action = MapFragmentDirections.actionMapFragmentToRouteVariantsFragment()
        findNavController().navigate(action)
    }

    private fun openGuidance() {
        val action = MapFragmentDirections.actionMapFragmentToGuidanceFragment()
        findNavController().navigate(action)
    }
}
