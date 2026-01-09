"use client"

import { useState } from "react"
import { useStorageStats, useUploadTrend, useExpiringFiles } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertTriangle, TrendingUp, HardDrive, Clock } from "lucide-react"
import { formatBytes, formatDate } from "@/lib/utils"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts"
import Link from "next/link"

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

export default function StatsPage() {
  const [trendDays, setTrendDays] = useState(30)
  const [expiringDays, setExpiringDays] = useState(7)

  const { data: storageStats, isLoading: storageLoading } = useStorageStats()
  const { data: trendData } = useUploadTrend(trendDays)
  const { data: expiringData } = useExpiringFiles(expiringDays)

  // 准备图表数据
  const trendChartData = trendData?.dates.map((date, i) => ({
    date: new Date(date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }),
    count: trendData.counts[i],
  })) || []

  const expiryChartData = Object.entries(storageStats?.by_expiry || {}).map(([key, value]) => ({
    name: key === "permanent" ? "永久" : key === "1d" ? "1天内" : key === "7d" ? "7天内" : "30天内",
    value,
  }))

  const typeChartData = Object.entries(storageStats?.by_type || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6)
    .map(([type, count]) => ({
      name: type || "无后缀",
      value: count,
    }))

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">数据统计</h1>
        <p className="text-muted-foreground">查看图床服务的详细统计数据</p>
      </div>

      {/* 概览卡片 */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">文件总数</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <div className="text-2xl font-bold">{storageStats?.total_files || 0}</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">存储使用</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <div className="text-2xl font-bold">
                {formatBytes(storageStats?.total_size || 0)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">已过期文件</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <div className="text-2xl font-bold">{storageStats?.expired_count || 0}</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 图表 */}
      <Tabs defaultValue="trend" className="space-y-4">
        <TabsList>
          <TabsTrigger value="trend">上传趋势</TabsTrigger>
          <TabsTrigger value="expiry">过期分布</TabsTrigger>
          <TabsTrigger value="type">文件类型</TabsTrigger>
        </TabsList>

        <TabsContent value="trend" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>上传趋势</CardTitle>
              <div className="flex gap-2">
                {[7, 30, 90].map((days) => (
                  <Button
                    key={days}
                    variant={trendDays === days ? "default" : "outline"}
                    size="sm"
                    onClick={() => setTrendDays(days)}
                  >
                    {days} 天
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={trendChartData}>
                  <XAxis
                    dataKey="date"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload?.length) {
                        return (
                          <div className="rounded-lg border bg-background p-2 shadow-sm">
                            <div className="text-sm font-medium">{payload[0].payload.date}</div>
                            <div className="text-xs text-muted-foreground">
                              {payload[0].value} 个文件
                            </div>
                          </div>
                        )
                      }
                      return null
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="expiry" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>过期时间分布</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={expiryChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                      outerRadius={100}
                      dataKey="value"
                    >
                      {expiryChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="type" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>文件类型分布</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={typeChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                      outerRadius={100}
                      dataKey="value"
                    >
                      {typeChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 即将过期的文件 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>即将过期</CardTitle>
          <div className="flex gap-2">
            {[3, 7, 30].map((days) => (
              <Button
                key={days}
                variant={expiringDays === days ? "default" : "outline"}
                size="sm"
                onClick={() => setExpiringDays(days)}
              >
                {days} 天
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {expiringData && expiringData.expiring_soon > 0 ? (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>有 {expiringData.expiring_soon} 个文件即将过期</AlertTitle>
              <AlertDescription>
                这些文件将在 {expiringDays} 天内过期，建议及时备份。
              </AlertDescription>
            </Alert>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              没有 {expiringDays} 天内即将过期的文件
            </div>
          )}

          {expiringData && expiringData.files.length > 0 && (
            <div className="mt-4 space-y-2">
              {expiringData.files.map((file) => (
                <Link
                  key={file.id}
                  href={`/files/${file.id}`}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent transition-colors"
                >
                  <span className="font-medium truncate flex-1">{file.filename}</span>
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    <span className="text-sm text-muted-foreground">
                      {formatDate(file.expire_at)}
                    </span>
                    <span className="text-sm font-medium text-destructive">
                      剩余 {file.days_until_expiry} 天
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
