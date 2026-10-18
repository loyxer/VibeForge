// The person's own photos for a site: shrunk here in the browser (a phone
// photo is 3–8 MB, a web page needs ~300 KB), then uploaded to the backend,
// which keeps them in storage and hands back their public URL.

import { apiFetch } from './api'

export const MAX_PHOTOS_PER_SITE = 10 // keep in sync with backend/app/user_photos.py
export const MAX_FILE_BYTES = 10 * 1024 * 1024 // the original file, before shrinking
const MAX_SIDE = 1600

// A photo in the tray under the chat box, from picking it to being sent.
export type TrayPhoto = {
  key: string
  preview: string // object URL of the shrunk image, for the thumbnail
  status: 'uploading' | 'ready' | 'error'
  id?: string
  error?: string // a dictionary key or the server's English text
}

export async function shrink(file: File): Promise<Blob> {
  if (file.size > MAX_FILE_BYTES) throw new Error('photos.tooLarge')
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
  } catch {
    throw new Error('photos.unsupported') // e.g. HEIC in a browser that can't open it
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()

  const encode = (type: string, quality: number) =>
    new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, quality))
  // WebP is smaller; browsers that can't write it hand back PNG instead.
  let blob = await encode('image/webp', 0.82)
  if (!blob || blob.type !== 'image/webp') blob = await encode('image/jpeg', 0.85)
  if (!blob) throw new Error('photos.unsupported')
  return blob
}

export async function uploadPhoto(blob: Blob, projectId: string | null): Promise<{ id: string; url: string }> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''
  const res = await apiFetch(`/api/photos${query}`, {
    method: 'POST',
    headers: { 'Content-Type': blob.type },
    body: blob,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail ?? 'error.generic')
  return data
}

export function discardPhoto(id: string) {
  // Best effort: a photo left behind is cleaned up by the server a day later.
  apiFetch(`/api/photos/${id}`, { method: 'DELETE' }).catch(() => {})
}
