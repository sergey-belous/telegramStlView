export type StreamHandlers = {
  onLine?: (line: string) => void
}

export async function streamTextResponse(
  response: Response,
  handlers: StreamHandlers = {},
): Promise<void> {
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `HTTP ${response.status}`)
  }

  if (!response.body) {
    const text = await response.text()
    if (text.trim() !== '') {
      handlers.onLine?.(text.trim())
    }
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const normalized = line.trim()
      if (normalized !== '') {
        handlers.onLine?.(normalized)
      }
    }
  }

  buffer += decoder.decode()
  const tail = buffer.trim()
  if (tail !== '') {
    handlers.onLine?.(tail)
  }
}

export function parseProgressFromLine(line: string): number | null {
  const match = line.match(/Progress:\s*([0-9]{1,3})%/i)
  if (!match) {
    return null
  }

  const parsed = Number(match[1])
  if (!Number.isFinite(parsed)) {
    return null
  }

  return Math.max(0, Math.min(100, parsed))
}

export function parseSavedUrlFromLine(line: string): string | null {
  const match = line.match(/Saved to:\s*(.+)$/i)
  if (!match) {
    return null
  }

  const absolutePath = (match[1] ?? '').trim()
  const publicPathMatch = absolutePath.match(/\/app\/public(\/.+)$/)
  if (publicPathMatch && publicPathMatch[1]) {
    return publicPathMatch[1]
  }

  return absolutePath
}

export function parseErrorFromLine(line: string): string | null {
  if (!line.startsWith('[ERROR]')) {
    return null
  }
  return line.replace('[ERROR]', '').trim() || 'Operation failed'
}
