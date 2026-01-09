"use client"

import { useFile, useDeleteFile } from "@/lib/hooks"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Trash2, Copy, ExternalLink, FileText } from "lucide-react"
import { formatBytes, formatDate } from "@/lib/utils"
import { toast } from "sonner"

export default function FileDetailPage() {
  const params = useParams()
  const router = useRouter()
  const fileId = params.id as string

  const { data: file, isLoading } = useFile(fileId)
  const deleteFile = useDeleteFile()

  const handleDelete = () => {
    if (confirm(`确定要删除 ${file?.filename} 吗？此操作不可恢复。`)) {
      deleteFile.mutate(fileId, {
        onSuccess: () => {
          router.push("/files")
        },
      })
    }
  }

  const handleCopyLink = () => {
    const url = `${window.location.origin}/f/${fileId}`
    navigator.clipboard.writeText(url)
    toast.success("链接已复制到剪贴板")
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 animate-pulse bg-muted rounded w-48" />
        <div className="h-64 animate-pulse bg-muted rounded" />
      </div>
    )
  }

  if (!file) {
    return (
      <div className="flex flex-col items-center justify-center h-full space-y-4">
        <FileText className="h-16 w-16 text-muted-foreground" />
        <div className="text-center">
          <h2 className="text-xl font-semibold">文件不存在</h2>
          <p className="text-muted-foreground">该文件可能已被删除</p>
        </div>
        <Button onClick={() => router.push("/files")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回文件列表
        </Button>
      </div>
    )
  }

  const fileUrl = `/f/${fileId}`

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/files")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <FileText className="h-6 w-6" />
              {file.filename}
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              ID: {file.id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleCopyLink}>
            <Copy className="mr-2 h-4 w-4" />
            复制链接
          </Button>
          <Button
            variant="outline"
            onClick={() => window.open(fileUrl, "_blank")}
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            打开
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteFile.isPending}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            删除
          </Button>
        </div>
      </div>

      {/* 元数据 */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">文件大小</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatBytes(file.file_size)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">创建时间</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">{formatDate(file.created_at)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">过期时间</CardTitle>
          </CardHeader>
          <CardContent>
            {file.expire_at ? (
              <div className="text-sm">{formatDate(file.expire_at)}</div>
            ) : (
              <Badge variant="secondary">永久存储</Badge>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 详细信息 */}
      <Card>
        <CardHeader>
          <CardTitle>文件信息</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 md:grid-cols-2">
            <div>
              <dt className="text-sm text-muted-foreground">文件 ID</dt>
              <dd className="font-mono text-sm">{file.id}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">文件哈希</dt>
              <dd className="font-mono text-sm">{file.file_hash}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">哈希算法</dt>
              <dd className="text-sm">{file.hash_algorithm}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">本地路径</dt>
              <dd className="font-mono text-sm truncate">{file.local_path}</dd>
            </div>
            {file.oss_path && (
              <div className="md:col-span-2">
                <dt className="text-sm text-muted-foreground">OSS 路径</dt>
                <dd className="font-mono text-sm truncate">{file.oss_path}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* 文件内容 */}
      {file.content && (
        <Card>
          <CardHeader>
            <CardTitle>文件内容</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-sm">
              <code>{file.content}</code>
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
