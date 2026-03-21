import type { MessageDoc } from '../types'
import { streamTextResponse } from './streamParser'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || 'http://localhost'

type DownloadPayload = {
  id: number
  _id: string
}

type UnzipPayload = {
  _id?: string
  savedUrl?: string
}

export async function fetchMessages(): Promise<MessageDoc[]> {
  const response = await fetch(`${API_BASE_URL}/telegram/messages`)
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `HTTP ${response.status}`)
  }

  const payload = await response.json()
  const docs = Array.isArray(payload?.docs) ? payload.docs : []
  return docs as MessageDoc[]
}

export async function streamDownload(payload: DownloadPayload, onLine: (line: string) => void): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/telegram/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await streamTextResponse(response, { onLine })
}

export async function streamUnzip(payload: UnzipPayload, onLine: (line: string) => void): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/telegram/unzip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await streamTextResponse(response, { onLine })
}

export async function downloadModelBlob(filePath: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/telegram-downloads/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filePath }),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `HTTP ${response.status}`)
  }
  return await response.blob()
}
