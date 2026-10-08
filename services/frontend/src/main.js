import { createApp } from 'vue'
import * as Cesium from 'cesium'
import App from './App.vue'

// Import Cesium styles
import 'cesium/Build/Cesium/Widgets/widgets.css'

// Import FontAwesome 6
import '@fortawesome/fontawesome-free/css/all.min.css'

Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN

// Cesium defaults to 6 concurrent requests per host. The 3D tilesets (OVH S3),
// the terrain (Ion) and the WMS layers (GeoServer) are distinct hosts competing
// for that quota, which starves the building tiles. Raise it.
Cesium.RequestScheduler.maximumRequestsPerServer = 18
Cesium.RequestScheduler.maximumRequests = 40

createApp(App).mount('#app')


