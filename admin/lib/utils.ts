import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 MB"

  const k = 1024
  const mb = bytes / k / k

  // 小于 1KB 显示 B
  if (bytes < k) return `${bytes} B`
  // 小于 1MB 显示 KB
  if (bytes < k * k) return `${(bytes / k).toFixed(1)} KB`
  // 1MB - 1GB 显示 MB（保留1位小数）
  if (bytes < k * k * k) return `${mb.toFixed(1)} MB`
  // 大于等于 1GB 显示 GB（保留2位小数）
  return `${(mb / 1024).toFixed(2)} GB`
}

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}
