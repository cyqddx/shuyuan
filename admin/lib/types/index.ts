// 文件相关类型
export interface FileListItem {
  id: string
  filename: string
  file_hash: string
  local_path: string
  oss_path: string | null
  expire_at: string | null
  created_at: string
  file_size: number
  is_expired: boolean
}

export interface FileListResponse {
  items: FileListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface FileDetail {
  id: string
  filename: string
  file_hash: string
  hash_algorithm: string
  local_path: string
  oss_path: string | null
  expire_at: string | null
  created_at: string
  file_size: number
  content: string | null
}

// 统计相关类型
export interface StorageStats {
  total_files: number
  total_size: number
  by_type: Record<string, number>
  by_expiry: Record<string, number>
  expired_count: number
}

export interface TrendData {
  dates: string[]
  counts: number[]
  sizes: number[]
}

export interface ExpiringFile {
  id: string
  filename: string
  expire_at: string
  days_until_expiry: number
}

export interface ExpiringData {
  expiring_soon: number
  files: ExpiringFile[]
}

export interface HealthStatus {
  status: string
  version: string
  components: {
    database: string
    encryption: string
    compression: string
    oss: string
    redis: string
  }
}

export interface AdminStats {
  total_files: number
  config_status: {
    auth: boolean
    encryption: boolean
    compression: boolean
    oss: boolean
    redis: boolean
  }
}

// 配置相关类型
export interface ConfigItem {
  key: string
  label: string
  value: string
  type: "text" | "number" | "boolean" | "select"
  category: string
  description: string
  options: string[] | null
  sensitive: boolean
  placeholder: string
  min_value: number | null
  max_value: number | null
  required: boolean
  pattern: string | null
  generate_command: string | null
  generate_type: "api_key" | "encryption_key" | null
}

export interface ConfigCategory {
  name: string
  items: ConfigItem[]
}

export interface ConfigListResponse {
  categories: ConfigCategory[]
  categories_order: string[]
  version: number  // 配置版本号（用于热重载检测）
}

export interface ConfigUpdateRequest {
  updates: Record<string, string>
}

export interface ConfigUpdateResponse {
  success: boolean
  message: string
  restarting: boolean
}
