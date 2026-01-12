import axios from "axios"
import type {
  FileListResponse,
  FileDetail,
  StorageStats,
  TrendData,
  ExpiringData,
  HealthStatus,
  AdminStats,
  ConfigListResponse,
  ConfigUpdateResponse,
  MetricsResponse,
} from "@/lib/types"

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    const apiKey = process.env.NEXT_PUBLIC_API_KEY
    if (apiKey) {
      config.headers["x-api-key"] = apiKey
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 直接返回 data
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || "请求失败"
    return Promise.reject(new Error(message))
  }
)

// 文件管理 API
export const filesApi = {
  list: (params: {
    page?: number
    page_size?: number
    search?: string
    sort?: string
    order?: string
  }): Promise<FileListResponse> =>
    apiClient.get("/admin/files", { params }),

  get: (id: string): Promise<FileDetail> =>
    apiClient.get(`/admin/files/${id}`),

  delete: (id: string): Promise<{ message: string }> =>
    apiClient.delete(`/admin/files/${id}`),

  batchDelete: (fileIds: string[]): Promise<{ success: number; failed: number }> =>
    apiClient.delete("/admin/files/batch", { data: { file_ids: fileIds } }),
}

// 统计 API
export const statsApi = {
  storage: (): Promise<StorageStats> =>
    apiClient.get("/admin/stats/storage"),

  trend: (days: number = 30): Promise<TrendData> =>
    apiClient.get("/admin/stats/trend", { params: { days } }),

  expiring: (days: number = 7): Promise<ExpiringData> =>
    apiClient.get("/admin/stats/expiring", { params: { days } }),

  admin: (): Promise<AdminStats> =>
    apiClient.get("/admin/stats"),
}

// 系统 API
export const systemApi = {
  health: (): Promise<HealthStatus> =>
    apiClient.get("/health"),

  cleanup: (): Promise<{ cleaned: number; message: string }> =>
    apiClient.post("/admin/cleanup"),
}

// 配置 API
export const configApi = {
  list: (): Promise<ConfigListResponse> =>
    apiClient.get("/admin/config"),

  update: (updates: Record<string, string>): Promise<ConfigUpdateResponse> =>
    apiClient.post("/admin/config", { updates }),

  generateKey: (keyType: "api_key" | "encryption_key"): Promise<{ key: string } | { error: string }> =>
    apiClient.post(`/admin/config/generate/${keyType}`),
}

// 监控 API
export const metricsApi = {
  get: (): Promise<MetricsResponse> =>
    apiClient.get("/admin/metrics"),
}
