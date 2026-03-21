export type ProgressState = {
  status?: string
  progress?: number
  updated_at?: string
  error?: string
}

export type ProcessingState = {
  download?: ProgressState
  unzip?: ProgressState
}

export type MessageDoc = {
  _id: string
  raw?: Record<string, unknown>
  file_name?: string
  file_type?: string
  savedUrl?: string
  uploaded?: boolean
  archive_extracted?: boolean
  processing?: ProcessingState
  source?: string
  parent_doc_id?: string
  message_id?: number
  [key: string]: unknown
}

export type MessageDocUi = MessageDoc & {
  fileName: string
  fileType: string
  downloadProgress: number
  unzipProgress: number
  downloadInProgress: boolean
  unzipInProgress: boolean
  operationError: string | null
}
