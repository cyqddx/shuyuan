"use client"

import { useState } from "react"
import { useHealth, useConfig, useUpdateConfig, useCleanup } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  CheckCircle2,
  XCircle,
  Trash2,
  Settings as SettingsIcon,
  Info,
  Save,
  Eye,
  EyeOff,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react"
import type { ConfigItem } from "@/lib/types"
import { configApi } from "@/lib/api"
import { toast } from "sonner"

function ConfigInput({
  item,
  value,
  onChange,
  showPassword,
  onTogglePassword,
}: {
  item: ConfigItem
  value: string
  onChange: (value: string) => void
  showPassword: boolean
  onTogglePassword: () => void
}) {
  const inputId = `config-${item.key}`
  const [generating, setGenerating] = useState(false)

  const handleGenerate = async () => {
    if (!item.generate_type) return
    setGenerating(true)
    try {
      const result = await configApi.generateKey(item.generate_type)
      if ("key" in result) {
        onChange(result.key)
        toast.success("密钥已生成")
      } else {
        toast.error(result.error || "生成失败")
      }
    } catch {
      toast.error("生成失败，请检查服务连接")
    } finally {
      setGenerating(false)
    }
  }

  if (item.type === "boolean") {
    const boolValue = value === "true" || value === "1"
    return (
      <div className="flex items-center justify-between py-2">
        <div className="space-y-0.5">
          <Label htmlFor={inputId}>{item.label}</Label>
          {item.description && (
            <p className="text-xs text-muted-foreground">{item.description}</p>
          )}
        </div>
        <Switch
          id={inputId}
          checked={boolValue}
          onCheckedChange={(checked) => onChange(checked ? "true" : "false")}
        />
      </div>
    )
  }

  if (item.type === "select" && item.options) {
    return (
      <div className="space-y-2">
        <Label htmlFor={inputId}>
          {item.label}
          {item.required && <span className="text-destructive ml-1">*</span>}
        </Label>
        {item.description && (
          <p className="text-xs text-muted-foreground">{item.description}</p>
        )}
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger id={inputId}>
            <SelectValue placeholder={item.placeholder || `请选择${item.label}`} />
          </SelectTrigger>
          <SelectContent>
            {item.options.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label htmlFor={inputId}>
          {item.label}
          {item.required && <span className="text-destructive ml-1">*</span>}
        </Label>
        {item.generate_type && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleGenerate}
            disabled={generating}
            className="h-7 text-xs"
          >
            {generating ? (
              <>
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                生成中
              </>
            ) : (
              <>
                <RefreshCw className="mr-1 h-3 w-3" />
                生成
              </>
            )}
          </Button>
        )}
      </div>
      {item.description && (
        <p className="text-xs text-muted-foreground">{item.description}</p>
      )}
      <div className="relative">
        <Input
          id={inputId}
          type={item.sensitive && !showPassword ? "password" : item.type === "number" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={item.placeholder}
          min={item.min_value ?? undefined}
          max={item.max_value ?? undefined}
          className={item.sensitive ? "pr-10" : ""}
        />
        {item.sensitive && (
          <button
            type="button"
            onClick={onTogglePassword}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
    </div>
  )
}

function ConfigCategorySection({
  categoryName,
  items,
  values,
  onChange,
  showPasswords,
  onTogglePassword,
}: {
  categoryName: string
  items: ConfigItem[]
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  showPasswords: Record<string, boolean>
  onTogglePassword: (key: string) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{categoryName}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.map((item) => (
          <ConfigInput
            key={item.key}
            item={item}
            value={values[item.key] ?? ""}
            onChange={(value) => onChange(item.key, value)}
            showPassword={showPasswords[item.key] ?? false}
            onTogglePassword={() => onTogglePassword(item.key)}
          />
        ))}
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { data: health, isLoading: healthLoading } = useHealth()
  const { data: configData, isLoading: configLoading } = useConfig()
  const updateConfig = useUpdateConfig()
  const cleanup = useCleanup()

  // 配置值状态
  const [configValues, setConfigValues] = useState<Record<string, string>>({})
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
  const [hasChanges, setHasChanges] = useState(false)

  // 当配置加载完成后初始化值
  if (configData?.categories && Object.keys(configValues).length === 0) {
    const initialValues: Record<string, string> = {}
    configData.categories.forEach((cat) => {
      cat.items.forEach((item) => {
        initialValues[item.key] = item.value
      })
    })
    setConfigValues(initialValues)
  }

  const getStatusIcon = (status: string) => {
    if (status.includes("正常") || status.includes("已启用") || status.includes("已连接") || status.includes("健康")) {
      return <CheckCircle2 className="h-5 w-5 text-green-500" />
    }
    return <XCircle className="h-5 w-5 text-destructive" />
  }

  const isHealthy = health?.status?.includes("健康") || false

  const handleConfigChange = (key: string, value: string) => {
    setConfigValues((prev) => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const handleSaveConfig = () => {
    updateConfig.mutate(configValues, {
      onSuccess: () => {
        setHasChanges(false)
      },
    })
  }

  const handleResetConfig = () => {
    if (configData?.categories) {
      const initialValues: Record<string, string> = {}
      configData.categories.forEach((cat) => {
        cat.items.forEach((item) => {
          initialValues[item.key] = item.value
        })
      })
      setConfigValues(initialValues)
      setHasChanges(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">系统设置</h1>
          <p className="text-muted-foreground">查看和管理图床服务配置</p>
        </div>
        {hasChanges && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleResetConfig}>
              重置
            </Button>
            <Button onClick={handleSaveConfig} disabled={updateConfig.isPending}>
              {updateConfig.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  保存中...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  保存配置
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* 配置已更改提示 */}
      {hasChanges && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            配置已修改，保存后服务将自动重启以使配置生效。
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="config" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="config">配置管理</TabsTrigger>
          <TabsTrigger value="status">系统状态</TabsTrigger>
        </TabsList>

        {/* 配置管理标签页 */}
        <TabsContent value="config" className="space-y-6 mt-6">
          {configLoading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <Card key={i}>
                  <CardContent className="pt-6">
                    <div className="space-y-4">
                      {[...Array(3)].map((_, j) => (
                        <div key={j} className="h-16 animate-pulse bg-muted rounded" />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : configData?.categories ? (
            <div className="space-y-6">
              {configData.categories.map((category) => (
                <ConfigCategorySection
                  key={category.name}
                  categoryName={category.name}
                  items={category.items}
                  values={configValues}
                  onChange={handleConfigChange}
                  showPasswords={showPasswords}
                  onTogglePassword={(key) =>
                    setShowPasswords((prev) => ({ ...prev, [key]: !prev[key] }))
                  }
                />
              ))}
            </div>
          ) : (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>加载配置失败，请检查服务连接</AlertDescription>
            </Alert>
          )}
        </TabsContent>

        {/* 系统状态标签页 */}
        <TabsContent value="status" className="space-y-6 mt-6">
          {/* 系统状态 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SettingsIcon className="h-5 w-5" />
                系统状态
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {healthLoading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-12 animate-pulse bg-muted rounded" />
                  ))}
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">服务状态</p>
                      <p className="text-sm text-muted-foreground">图床服务运行状态</p>
                    </div>
                    <Badge variant={isHealthy ? "default" : "destructive"}>
                      {health?.status || "未知"}
                    </Badge>
                  </div>

                  <Separator />

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span>数据库</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health?.components?.database || "")}
                        <span className="text-sm">{health?.components?.database || "未知"}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <span>加密服务</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health?.components?.encryption || "")}
                        <span className="text-sm">{health?.components?.encryption || "未知"}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <span>压缩服务</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health?.components?.compression || "")}
                        <span className="text-sm">{health?.components?.compression || "未知"}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <span>OSS 存储</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health?.components?.oss || "")}
                        <span className="text-sm">{health?.components?.oss || "未知"}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <span>Redis 限流</span>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health?.components?.redis || "")}
                        <span className="text-sm">{health?.components?.redis || "未知"}</span>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* 系统操作 */}
          <Card>
            <CardHeader>
              <CardTitle>系统操作</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  清理操作将永久删除所有已过期的文件，此操作不可恢复。
                </AlertDescription>
              </Alert>

              <Button
                variant="destructive"
                onClick={() => cleanup.mutate()}
                disabled={cleanup.isPending}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                清理过期文件
              </Button>
            </CardContent>
          </Card>

          {/* 版本信息 */}
          <Card>
            <CardHeader>
              <CardTitle>版本信息</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">版本号</span>
                  <span className="font-mono">{health?.version || "1.0.0"}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
