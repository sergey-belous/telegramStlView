<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

import { downloadModelBlob } from '../services/api'

const renderHostRef = ref<HTMLDivElement | null>(null)
const info = ref('')

const loader = new STLLoader()
let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let currentModel: THREE.Mesh | null = null
let animationFrameId = 0

function setupScene(): void {
  if (!renderHostRef.value) {
    return
  }

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(1024, 800)
  renderHostRef.value.appendChild(renderer.domElement)

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xffffff)

  camera = new THREE.PerspectiveCamera(40, 1024 / 800, 1, 100)
  camera.position.set(1, 1, 1)
  camera.lookAt(0, 0, 0)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 0)
  controls.enablePan = false
  controls.enableDamping = true
  controls.update()

  const groundGeometry = new THREE.PlaneGeometry(20, 20)
  const groundMaterial = new THREE.MeshStandardMaterial({ color: 0xf2f2f2 })
  const ground = new THREE.Mesh(groundGeometry, groundMaterial)
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -1
  ground.receiveShadow = true
  scene.add(ground)

  const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.7)
  directionalLight1.position.set(1, 1, 1)
  scene.add(directionalLight1)

  const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.5)
  directionalLight2.position.set(-1, -1, -1)
  scene.add(directionalLight2)

  const ambientLight = new THREE.AmbientLight(0x404040, 0.5)
  scene.add(ambientLight)
}

function startLoop(): void {
  if (!renderer || !scene || !camera) {
    return
  }

  const tick = () => {
    if (!renderer || !scene || !camera) {
      return
    }
    controls?.update()
    renderer.render(scene, camera)
    animationFrameId = window.requestAnimationFrame(tick)
  }
  animationFrameId = window.requestAnimationFrame(tick)
}

function clearCurrentModel(): void {
  if (!scene || !currentModel) {
    return
  }
  scene.remove(currentModel)
  currentModel.geometry.dispose()
  if (Array.isArray(currentModel.material)) {
    currentModel.material.forEach((material) => material.dispose())
  } else {
    currentModel.material.dispose()
  }
  currentModel = null
}

async function renderFromSavedUrl(savedUrl: string): Promise<void> {
  if (!scene || !camera || !controls) {
    return
  }
  if (!savedUrl || savedUrl.trim() === '') {
    throw new Error('savedUrl is required.')
  }

  const blob = await downloadModelBlob(savedUrl)
  const arrayBuffer = await blob.arrayBuffer()

  clearCurrentModel()
  const geometry = loader.parse(arrayBuffer)
  geometry.computeBoundingBox()

  const size = new THREE.Vector3(0, 0, 0)
  if (geometry.boundingBox) {
    geometry.boundingBox.getSize(size)
  }

  const material = new THREE.MeshPhongMaterial({
    color: 0xffffff,
    specular: 0x888888,
    shininess: 50,
    flatShading: true,
  })

  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set(0, 0, 0)
  mesh.scale.set(0.01, 0.01, 0.01)

  mesh.traverse((node) => {
    const asMesh = node as THREE.Mesh
    if (asMesh.isMesh && asMesh.material && 'needsUpdate' in asMesh.material) {
      ;(asMesh.material as THREE.Material).needsUpdate = true
    }
  })

  scene.add(mesh)
  currentModel = mesh

  controls.update()
  const vertices = geometry.attributes.position?.count ?? 0
  info.value = [
    'STL Model Loaded',
    `Vertices: ${vertices}`,
    `Dimensions: ${size.x.toFixed(2)} x ${size.y.toFixed(2)} x ${size.z.toFixed(2)}`,
  ].join(' | ')
}

defineExpose({
  renderFromSavedUrl,
})

onMounted(() => {
  setupScene()
  startLoop()
})

onBeforeUnmount(() => {
  window.cancelAnimationFrame(animationFrameId)
  clearCurrentModel()
  controls?.dispose()
  controls = null
  if (renderer) {
    renderer.dispose()
    const dom = renderer.domElement
    dom.parentElement?.removeChild(dom)
  }
  renderer = null
  scene = null
  camera = null
})
</script>

<template>
  <div class="viewer-wrap">
    <div id="info">{{ info }}</div>
    <div ref="renderHostRef" class="render-host" />
  </div>
</template>
