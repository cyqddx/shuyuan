"use client"

import { useFiles } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Link as LinkIcon } from "lucide-react"
import { formatBytes } from "@/lib/utils"
import Link from "next/link"

export function RecentFiles() {
  const { data: filesData, isLoading } = useFiles({ page: 1, page_size: 5, sort: "created_at", order: "desc" })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>最近上传</CardTitle>
        <Link
          href="/files"
          className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
        >
          查看全部 <LinkIcon className="h-4 w-4" />
        </Link>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 animate-pulse bg-muted rounded" />
            ))}
          </div>
        ) : filesData?.items.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            暂无文件
          </div>
        ) : (
          <div className="space-y-3">
            {filesData?.items.map((file) => (
              <Link
                key={file.id}
                href={`/files/${file.id}`}
                className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <LinkIcon className="h-5 w-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium truncate">{file.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatBytes(file.file_size)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {file.is_expired && (
                    <Badge variant="destructive">已过期</Badge>
                  )}
                  {file.expire_at && !file.is_expired && (
                    <Badge variant="outline" className="text-xs">
                      {new Date(file.expire_at).toLocaleDateString("zh-CN")}
                    </Badge>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
