"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { filesApi, statsApi, systemApi, configApi } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

// 文件相关 Hooks
export function useFiles(params: Record<string, string | number> = {}) {
  return useQuery({
    queryKey: queryKeys.files.list(params),
    queryFn: () => filesApi.list(params),
    refetchInterval: 10000, // 10秒自动刷新
  })
}

export function useFile(id: string) {
  return useQuery({
    queryKey: queryKeys.files.detail(id),
    queryFn: () => filesApi.get(id),
    enabled: !!id,
    refetchInterval: 10000, // 10秒自动刷新
  })
}

export function useDeleteFile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => filesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.files.lists() })
      toast.success("文件已删除")
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })
}

export function useBatchDeleteFiles() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fileIds: string[]) => filesApi.batchDelete(fileIds),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.files.lists() })
      toast.success(`已删除 ${data.success} 个文件`)
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })
}

// 统计相关 Hooks
export function useStorageStats() {
  return useQuery({
    queryKey: queryKeys.stats.storage(),
    queryFn: () => statsApi.storage(),
    refetchInterval: 30000, // 30秒自动刷新
  })
}

export function useUploadTrend(days: number = 30) {
  return useQuery({
    queryKey: queryKeys.stats.trend(days),
    queryFn: () => statsApi.trend(days),
  })
}

export function useExpiringFiles(days: number = 7) {
  return useQuery({
    queryKey: queryKeys.stats.expiring(days),
    queryFn: () => statsApi.expiring(days),
    refetchInterval: 60000, // 60秒自动刷新
  })
}

export function useAdminStats() {
  return useQuery({
    queryKey: queryKeys.stats.admin(),
    queryFn: () => statsApi.admin(),
    refetchInterval: 30000,
  })
}

// 系统相关 Hooks
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.system.health(),
    queryFn: () => systemApi.health(),
    refetchInterval: 10000, // 10秒自动刷新（配合配置热重载）
  })
}

export function useCleanup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => systemApi.cleanup(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.stats.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.files.lists() })
      toast.success(data.message)
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })
}

// 配置相关 Hooks
export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => configApi.list(),
    refetchOnWindowFocus: false,
    refetchInterval: 30000, // 30秒自动刷新（配合后端配置热重载）
    staleTime: 10000, // 10秒内认为数据是新鲜的
  })
}

export function useUpdateConfig() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (updates: Record<string, string>) => configApi.update(updates),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["config"] })
      queryClient.invalidateQueries({ queryKey: queryKeys.system.health() })
      toast.success("配置已更新", {
        duration: 3000,
      })
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })
}
