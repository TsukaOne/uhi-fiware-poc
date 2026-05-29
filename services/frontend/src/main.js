import { createApp } from 'vue'
import * as Cesium from 'cesium'
import App from './App.vue'

// Import Cesium styles
import 'cesium/Build/Cesium/Widgets/widgets.css'

// Import FontAwesome 6
import '@fortawesome/fontawesome-free/css/all.min.css'

Cesium.Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN

createApp(App).mount('#app')


