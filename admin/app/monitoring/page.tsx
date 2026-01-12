"use client"

import { useMetrics } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Activity, Zap, HardDrive, Clock, Cpu } from "lucide-react"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts"

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

// 格式化运行时长
function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  return `${days} 天 ${hours} 小时`
}

export default function MonitoringPage() {
  const { data: metrics, isLoading, error } = useMetrics()

  // 处理加载状态
  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">系统监控</h1>
        </div>
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <p className="text-destructive">加载监控数据失败</p>
            <p className="text-sm text-muted-foreground mt-2">请确保后端服务正在运行</p>
          </div>
        </div>
      </div>
    )
  }

  // 准备图表数据 - 添加默认空对象防止 undefined 错误
  const requests = metrics?.requests || { total: 0, qps: 0, by_method: {}, by_path: {} }
  const latency = metrics?.latency || { p50: 0, p90: 0, p95: 0, p99: 0, avg: 0 }
  const errors = metrics?.errors || { total: 0, rate: 0, by_status: {} }
  const system = metrics?.system || { uptime: 0, memory_usage: 0, total_memory: 0, cpu_usage: 0 }

  const methodChartData = Object.entries(requests.by_method || {}).map(([method, count]) => ({
    name: method,
    value: count,
  }))

  const pathChartData = Object.entries(requests.by_path || {})
    .slice(0, 8)
    .map(([path, count]) => ({
      name: path.length > 20 ? path.substring(0, 20) + "..." : path,
      value: count,
    }))

  const statusChartData = Object.entries(errors.by_status || {}).map(([status, count]) => ({
    name: status,
    value: count,
  }))

  const latencyData = [
    { name: "P50", value: latency.p50 },
    { name: "P90", value: latency.p90 },
    { name: "P95", value: latency.p95 },
    { name: "P99", value: latency.p99 },
  ]

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">系统监控</h1>
          <p className="text-muted-foreground">查看实时性能指标和系统状态</p>
        </div>
        {metrics && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Activity className="h-4 w-4 animate-pulse text-green-500" />
            <span>实时更新中</span>
          </div>
        )}
      </div>

      {/* 概览卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">总请求数</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {requests.total || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  QPS: {requests.qps || 0}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">平均延迟</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {latency.avg || 0}
                  <span className="text-sm font-normal text-muted-foreground"> ms</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  P99: {latency.p99 || 0} ms
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">错误率</CardTitle>
            <div className={`h-4 w-4 rounded-full ${(errors.rate || 0) > 5 ? "bg-red-500" : "bg-green-500"}`} />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {errors.rate || 0}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {errors.total || 0} 个错误
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">运行时长</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <div className="text-2xl font-bold">
                {system.uptime ? formatUptime(system.uptime) : "-"}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 系统资源 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5" />
              内存使用
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-32 animate-pulse bg-muted rounded" />
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-muted-foreground">已用 / 总量</span>
                    <span className="font-medium">
                      {system.memory_usage || 0} MB / {system.total_memory || 0} MB
                    </span>
                  </div>
                  <div className="h-3 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{
                        width: `${Math.min(((system.memory_usage || 0) / (system.total_memory || 1)) * 100, 100)}%`
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground mt-1">
                    <span>使用率</span>
                    <span>{((system.memory_usage || 0) / (system.total_memory || 1) * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5" />
              CPU 使用率
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-32 animate-pulse bg-muted rounded" />
            ) : (
              <div className="space-y-4">
                <div className="flex items-end justify-center">
                  <div className="text-center">
                    <div className="text-5xl font-bold">
                      {system.cpu_usage?.toFixed(1) || "0.0"}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">%</div>
                  </div>
                </div>
                <div>
                  <div className="h-3 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        (system.cpu_usage || 0) > 80
                          ? "bg-red-500"
                          : (system.cpu_usage || 0) > 50
                            ? "bg-yellow-500"
                            : "bg-green-500"
                      }`}
                      style={{ width: `${Math.min(system.cpu_usage || 0, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground mt-1">
                    <span>低负载</span>
                    <span>高负载</span>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 详细图表 */}
      <Tabs defaultValue="latency" className="space-y-4">
        <TabsList>
          <TabsTrigger value="latency">延迟分布</TabsTrigger>
          <TabsTrigger value="methods">请求方法</TabsTrigger>
          <TabsTrigger value="paths">请求路径</TabsTrigger>
          <TabsTrigger value="errors">错误状态</TabsTrigger>
        </TabsList>

        <TabsContent value="latency" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>延迟分位数</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-64 animate-pulse bg-muted rounded" />
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={latencyData}>
                    <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload?.length) {
                          return (
                            <div className="rounded-lg border bg-background p-2 shadow-sm">
                              <div className="text-sm font-medium">{payload[0].payload.name}</div>
                              <div className="text-xs text-muted-foreground">
                                {payload[0].value} ms
                              </div>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Bar dataKey="value" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="methods" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>请求方法分布</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-64 animate-pulse bg-muted rounded" />
              ) : methodChartData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-muted-foreground">
                  暂无数据
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={methodChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                      outerRadius={100}
                      dataKey="value"
                    >
                      {methodChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="paths" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>请求路径 Top 8</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-64 animate-pulse bg-muted rounded" />
              ) : pathChartData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-muted-foreground">
                  暂无数据
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={pathChartData} layout="vertical">
                    <XAxis type="number" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis dataKey="name" type="category" fontSize={12} tickLine={false} axisLine={false} width={120} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload?.length) {
                          return (
                            <div className="rounded-lg border bg-background p-2 shadow-sm">
                              <div className="text-sm font-medium">{payload[0].payload.name}</div>
                              <div className="text-xs text-muted-foreground">
                                {payload[0].value} 次请求
                              </div>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Bar dataKey="value" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="errors" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>错误状态码分布</CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="h-64 animate-pulse bg-muted rounded" />
              ) : statusChartData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-green-600">
                  <div className="text-center">
                    <div className="text-4xl mb-2">✓</div>
                    <div>暂无错误</div>
                  </div>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={statusChartData}>
                    <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload?.length) {
                          return (
                            <div className="rounded-lg border bg-background p-2 shadow-sm">
                              <div className="text-sm font-medium">状态码 {payload[0].payload.name}</div>
                              <div className="text-xs text-muted-foreground">
                                {payload[0].value} 次
                              </div>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Bar dataKey="value" fill="hsl(var(--destructive))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
