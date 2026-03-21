<script setup lang="ts">
import { ref } from 'vue'

import MessagesList from './components/MessagesList.vue'
import ModelViewer from './components/ModelViewer.vue'
import type { MessageDocUi } from './types'

type MessagesListExpose = {
  refreshData: () => Promise<void>
  getUploadedStlModels: () => MessageDocUi[]
}

type ModelViewerExpose = {
  renderFromSavedUrl: (savedUrl: string) => Promise<void>
}

const messagesListRef = ref<MessagesListExpose | null>(null)
const viewerRef = ref<ModelViewerExpose | null>(null)
const messages = ref<MessageDocUi[]>([])
const renderError = ref<string | null>(null)

function getMessageFileName(doc: MessageDocUi): string {
  const raw = doc.raw as
    | { media?: { document?: { attributes?: Array<{ file_name?: string }> } } }
    | undefined
  const rawName = raw?.media?.document?.attributes?.[0]?.file_name
  if (typeof rawName === 'string' && rawName.trim() !== '') {
    return rawName.trim()
  }

  if (typeof doc.file_name === 'string' && doc.file_name.trim() !== '') {
    return doc.file_name.trim()
  }

  if (typeof doc.savedUrl === 'string' && doc.savedUrl.trim() !== '') {
    const parts = doc.savedUrl.split('/')
    return parts[parts.length - 1] ?? ''
  }

  return 'Unknown file'
}

function isStlDoc(doc: MessageDocUi): boolean {
  const explicitType = typeof doc.file_type === 'string' ? doc.file_type.toLowerCase() : ''
  if (explicitType === 'stl') {
    return true
  }
  return getMessageFileName(doc).toLowerCase().endsWith('.stl')
}

function fetchMessagesFromChild(): void {
  const childModels = messagesListRef.value?.getUploadedStlModels() ?? []
  messages.value = childModels.filter((doc) => doc.uploaded === true && isStlDoc(doc))
}

async function renderStlModel(doc: MessageDocUi): Promise<void> {
  renderError.value = null
  const savedUrl = doc.savedUrl
  if (typeof savedUrl !== 'string' || savedUrl.trim() === '') {
    renderError.value = 'savedUrl not found for selected model.'
    return
  }

  try {
    await viewerRef.value?.renderFromSavedUrl(savedUrl)
  } catch (err) {
    renderError.value = err instanceof Error ? err.message : 'Failed to render model.'
  }
}
</script>

<template>
  <div class="app-layout">
    <MessagesList ref="messagesListRef" />

    <div class="canvas-controls">
      <button type="button" @click="fetchMessagesFromChild">Fecth downloadedModels from child component</button>
      <ul class="models-list">
        <li v-for="doc in messages" :key="doc._id" class="uploaded">
          <pre>{{ getMessageFileName(doc) }}</pre>
          <button type="button" @click="renderStlModel(doc)">Render Model</button>
        </li>
      </ul>
      <p v-if="messages.length === 0" class="hint">No messages fetched from Messages component.</p>
      <p v-if="renderError" class="operation-error">{{ renderError }}</p>
    </div>

    <ModelViewer ref="viewerRef" />
  </div>
</template>
