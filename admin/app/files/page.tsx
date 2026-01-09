"use client"

import { useState } from "react"
import { useFiles, useDeleteFile, useBatchDeleteFiles } from "@/lib/hooks"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { Search, MoreHorizontal, Trash2, RefreshCw, FileText, ExternalLink } from "lucide-react"
import Link from "next/link"
import { formatBytes, formatDate } from "@/lib/utils"
import { Checkbox } from "@/components/ui/checkbox"
import { toast } from "sonner"

export default function FilesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState("created_at")
  const [order, setOrder] = useState("desc")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const { data: filesData, isLoading, refetch } = useFiles({
    page,
    page_size: 20,
    search,
    sort,
    order,
  })

  const deleteFile = useDeleteFile()
  const batchDelete = useBatchDeleteFiles()

  const handleSelectAll = () => {
    if (selectedIds.size === filesData?.items.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filesData?.items.map((f) => f.id) || []))
    }
  }

  const handleSelect = (id: string) => {
    const newSet = new Set(selectedIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedIds(newSet)
  }

  const handleBatchDelete = () => {
    if (selectedIds.size === 0) {
      toast.error("请先选择要删除的文件")
      return
    }
    batchDelete.mutate(Array.from(selectedIds))
    setSelectedIds(new Set())
  }

  const totalPages = filesData?.total_pages || 1

  return (
    <div className="space-y-6">
      {/* 标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">文件管理</h1>
          <p className="text-muted-foreground">
            共 {filesData?.total || 0} 个文件
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleBatchDelete}
              disabled={batchDelete.isPending}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              删除 {selectedIds.size} 个文件
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>
      </div>

      {/* 搜索和筛选 */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索文件名或 ID..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="pl-10"
          />
        </div>
        <Select value={sort} onValueChange={(v) => setSort(v)}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="排序方式" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_at">创建时间</SelectItem>
            <SelectItem value="filename">文件名</SelectItem>
            <SelectItem value="expire_at">过期时间</SelectItem>
          </SelectContent>
        </Select>
        <Select value={order} onValueChange={(v: "asc" | "desc") => setOrder(v)}>
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">降序</SelectItem>
            <SelectItem value="asc">升序</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* 文件列表 */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedIds.size === filesData?.items.length && filesData?.items.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                </TableHead>
                <TableHead>文件名</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>过期时间</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                [...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={7}>
                      <div className="h-12 animate-pulse bg-muted rounded" />
                    </TableCell>
                  </TableRow>
                ))
              ) : filesData?.items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    {search ? "未找到匹配的文件" : "暂无文件"}
                  </TableCell>
                </TableRow>
              ) : (
                filesData?.items.map((file) => (
                  <TableRow key={file.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(file.id)}
                        onCheckedChange={() => handleSelect(file.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/files/${file.id}`}
                        className="font-medium hover:underline flex items-center gap-2"
                      >
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="truncate max-w-[200px] block">{file.filename}</span>
                      </Link>
                    </TableCell>
                    <TableCell>{formatBytes(file.file_size)}</TableCell>
                    <TableCell>{formatDate(file.created_at)}</TableCell>
                    <TableCell>
                      {file.expire_at ? formatDate(file.expire_at) : "永久"}
                    </TableCell>
                    <TableCell>
                      {file.is_expired ? (
                        <Badge variant="destructive">已过期</Badge>
                      ) : file.expire_at ? (
                        <Badge variant="outline">限时</Badge>
                      ) : (
                        <Badge variant="secondary">永久</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/files/${file.id}`}>
                              <ExternalLink className="mr-2 h-4 w-4" />
                              查看详情
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => {
                              if (confirm(`确定要删除 ${file.filename} 吗？`)) {
                                deleteFile.mutate(file.id)
                              }
                            }}
                            disabled={deleteFile.isPending}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* 分页 */}
      {totalPages > 1 && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className={page === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
            {[...Array(totalPages)].map((_, i) => {
              const pageNum = i + 1
              if (
                pageNum === 1 ||
                pageNum === totalPages ||
                (pageNum >= page - 2 && pageNum <= page + 2)
              ) {
                return (
                  <PaginationItem key={pageNum}>
                    <PaginationLink
                      onClick={() => setPage(pageNum)}
                      isActive={page === pageNum}
                      className="cursor-pointer"
                    >
                      {pageNum}
                    </PaginationLink>
                  </PaginationItem>
                )
              }
              return null
            })}
            <PaginationItem>
              <PaginationNext
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className={page === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}
    </div>
  )
}
