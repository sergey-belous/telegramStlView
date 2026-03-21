<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchMessages, streamDownload, streamUnzip } from '../services/api'
import { parseErrorFromLine, parseProgressFromLine, parseSavedUrlFromLine } from '../services/streamParser'
import type { MessageDoc, MessageDocUi } from '../types'

const data = ref<MessageDocUi[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function getFileName(doc: MessageDoc): string {
  const raw = doc.raw as
    | { media?: { document?: { attributes?: Array<{ file_name?: string }> } } }
    | undefined
  const rawFileName = raw?.media?.document?.attributes?.[0]?.file_name
  if (typeof rawFileName === 'string' && rawFileName.trim() !== '') {
    return rawFileName.trim()
  }

  if (typeof doc.file_name === 'string' && doc.file_name.trim() !== '') {
    return doc.file_name.trim()
  }

  if (typeof doc.savedUrl === 'string' && doc.savedUrl.trim() !== '') {
    const parts = doc.savedUrl.split('/')
    return parts[parts.length - 1] ?? ''
  }

  return ''
}

function getFileType(doc: MessageDoc, fileName?: string): string {
  if (typeof doc.file_type === 'string' && doc.file_type.trim() !== '') {
    return doc.file_type.trim().toLowerCase()
  }

  const resolvedName = (fileName ?? getFileName(doc)).toLowerCase()
  if (resolvedName.endsWith('.stl')) {
    return 'stl'
  }
  if (resolvedName.endsWith('.zip')) {
    return 'zip'
  }
  return 'other'
}

function normalizeDoc(doc: MessageDoc): MessageDocUi {
  const fileName = getFileName(doc)
  const fileType = getFileType(doc, fileName)
  const downloadProgressRaw = doc.processing?.download?.progress
  const unzipProgressRaw = doc.processing?.unzip?.progress
  const downloadProgress =
    typeof downloadProgressRaw === 'number' ? Math.max(0, Math.min(100, downloadProgressRaw)) : doc.uploaded ? 100 : 0
  const unzipProgress =
    typeof unzipProgressRaw === 'number'
      ? Math.max(0, Math.min(100, unzipProgressRaw))
      : doc.archive_extracted
        ? 100
        : 0

  return {
    ...doc,
    fileName,
    fileType,
    uploaded: Boolean(doc.uploaded),
    savedUrl: typeof doc.savedUrl === 'string' ? doc.savedUrl : '',
    archive_extracted: Boolean(doc.archive_extracted),
    downloadProgress,
    unzipProgress,
    downloadInProgress: false,
    unzipInProgress: false,
    operationError: null,
  }
}

function updateDoc(_id: string, patch: Partial<MessageDocUi> | ((doc: MessageDocUi) => Partial<MessageDocUi>)): void {
  data.value = data.value.map((doc) => {
    if (doc._id !== _id) {
      return doc
    }
    const resolvedPatch = typeof patch === 'function' ? patch(doc) : patch
    return { ...doc, ...resolvedPatch }
  })
}

function canDownload(doc: MessageDocUi): boolean {
  const raw = doc.raw as { id?: unknown } | undefined
  return typeof raw?.id === 'number' && Number.isFinite(raw.id) && doc._id.trim() !== ''
}

function getRawMessageId(doc: MessageDocUi): number | null {
  const raw = doc.raw as { id?: unknown } | undefined
  if (typeof raw?.id === 'number' && Number.isFinite(raw.id)) {
    return raw.id
  }

  if (typeof doc.message_id === 'number' && Number.isFinite(doc.message_id)) {
    return doc.message_id
  }

  return null
}

async function refreshData(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const docs = await fetchMessages()
    data.value = docs
      .map((doc) => normalizeDoc(doc))
      .filter((doc) => doc.fileName !== '' && (doc.fileType === 'stl' || doc.fileType === 'zip'))
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to fetch data'
    error.value = message
    data.value = []
  } finally {
    loading.value = false
  }
}

function fetchStl(): void {
  data.value = data.value.filter((doc) => doc.fileType === 'stl')
}

async function download(doc: MessageDocUi): Promise<void> {
  const messageId = getRawMessageId(doc)
  if (messageId === null) {
    updateDoc(doc._id, { operationError: 'Message id is missing for download.' })
    return
  }

  updateDoc(doc._id, {
    downloadInProgress: true,
    downloadProgress: 0,
    operationError: null,
  })

  let hasErrors = false
  try {
    await streamDownload({ id: messageId, _id: doc._id }, (line: string) => {
      const progress = parseProgressFromLine(line)
      if (progress !== null) {
        updateDoc(doc._id, { downloadProgress: progress })
      }

      const savedUrl = parseSavedUrlFromLine(line)
      if (savedUrl) {
        updateDoc(doc._id, {
          uploaded: true,
          savedUrl,
          downloadProgress: 100,
        })
      }

      const operationError = parseErrorFromLine(line)
      if (operationError) {
        hasErrors = true
        updateDoc(doc._id, { operationError })
      }
    })

    updateDoc(doc._id, (current) => ({
      downloadInProgress: false,
      downloadProgress: current.uploaded ? 100 : current.downloadProgress,
      operationError: hasErrors ? current.operationError : null,
    }))
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Download request failed'
    updateDoc(doc._id, {
      downloadInProgress: false,
      operationError: message,
    })
  }
}

async function unzip(doc: MessageDocUi): Promise<void> {
  updateDoc(doc._id, {
    unzipInProgress: true,
    unzipProgress: 0,
    operationError: null,
  })

  let hasErrors = false
  try {
    await streamUnzip({ _id: doc._id }, (line: string) => {
      const progress = parseProgressFromLine(line)
      if (progress !== null) {
        updateDoc(doc._id, { unzipProgress: progress })
      }

      if (line.startsWith('Unzip done')) {
        updateDoc(doc._id, {
          archive_extracted: true,
          unzipProgress: 100,
        })
      }

      const operationError = parseErrorFromLine(line)
      if (operationError) {
        hasErrors = true
        updateDoc(doc._id, { operationError })
      }
    })

    updateDoc(doc._id, { unzipInProgress: false })
    if (!hasErrors) {
      await refreshData()
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unzip request failed'
    updateDoc(doc._id, {
      unzipInProgress: false,
      operationError: message,
    })
  }
}

function getUploadedStlModels(): MessageDocUi[] {
  return data.value.filter((doc) => Boolean(doc.uploaded) && doc.fileType === 'stl')
}

defineExpose({
  refreshData,
  getUploadedStlModels,
})

onMounted(async () => {
  await refreshData()
})
</script>

<template>
  <div class="messages-panel">
    <h2>CouchDB Data</h2>
    <div class="controls">
      <button type="button" @click="refreshData">Refresh Data</button>
      <button type="button" @click="fetchStl">Fetch STL</button>
    </div>

    <p v-if="loading">Loading data from CouchDB...</p>
    <p v-else-if="error" class="operation-error">Error: {{ error }}</p>
    <p v-else-if="data.length === 0">No documents found in the database.</p>

    <ul v-else class="docs-list">
      <li v-for="doc in data" :key="doc._id" class="doc-row">
        <pre>{{ doc.fileName }}</pre>
        <div class="row-actions">
          <button v-if="canDownload(doc)" type="button" :disabled="doc.downloadInProgress" @click="download(doc)">
            {{ doc.downloadInProgress ? 'Downloading...' : 'Download' }}
          </button>
          <button
            v-if="doc.fileType === 'zip' && doc.savedUrl"
            type="button"
            :disabled="doc.unzipInProgress"
            @click="unzip(doc)"
          >
            {{ doc.unzipInProgress ? 'Unzipping...' : 'Unzip' }}
          </button>
        </div>

        <div v-if="doc.downloadInProgress || doc.downloadProgress > 0" class="progress-wrap">
          <div class="progress-label">Download: {{ doc.downloadProgress }}%</div>
          <div class="progress-track">
            <div class="progress-value" :style="{ width: `${doc.downloadProgress}%` }" />
          </div>
        </div>

        <div v-if="doc.unzipInProgress || doc.unzipProgress > 0 || doc.archive_extracted" class="progress-wrap">
          <div class="progress-label">Unzip: {{ doc.unzipProgress }}%</div>
          <div class="progress-track">
            <div class="progress-value unzip" :style="{ width: `${doc.unzipProgress}%` }" />
          </div>
        </div>

        <div v-if="doc.uploaded" class="uploaded">Uploaded</div>
        <div v-if="doc.fileType === 'zip' && doc.archive_extracted" class="uploaded">Unzipped</div>
        <div v-if="doc.operationError" class="operation-error">{{ doc.operationError }}</div>
      </li>
    </ul>
  </div>
</template>
