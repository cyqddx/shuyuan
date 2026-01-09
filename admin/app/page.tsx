"use client"

import { useStorageStats, useExpiringFiles, useUploadTrend } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Files, HardDrive, Calendar, AlertTriangle } from "lucide-react"
import { formatBytes } from "@/lib/utils"
import { TrendChart } from "@/components/dashboard/trend-chart"
import { RecentFiles } from "@/components/dashboard/recent-files"

export default function DashboardPage() {
  const { data: storageStats, isLoading: storageLoading } = useStorageStats()
  const { data: expiringData } = useExpiringFiles(7)
  const { data: trendData } = useUploadTrend(7)

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
        <p className="text-muted-foreground">查看图床服务的运行状态和统计数据</p>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">文件总数</CardTitle>
            <Files className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {storageStats?.total_files || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {storageStats?.expired_count || 0} 个已过期
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">存储使用</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {formatBytes(storageStats?.total_size || 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {Object.keys(storageStats?.by_type || {}).length} 种文件类型
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">今日上传</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {trendData?.counts[trendData.counts.length - 1] || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              最近 7 天累计 {trendData?.counts.reduce((a, b) => a + b, 0) || 0} 个
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">即将过期</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {expiringData?.expiring_soon || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              7 天内过期
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 趋势图表 */}
      <div className="grid gap-4 md:grid-cols-2">
        <TrendChart />
        <Card>
          <CardHeader>
            <CardTitle>文件类型分布</CardTitle>
          </CardHeader>
          <CardContent>
            {storageLoading ? (
              <div className="h-48 animate-pulse bg-muted rounded" />
            ) : (
              <div className="space-y-3">
                {Object.entries(storageStats?.by_type || {})
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 6)
                  .map(([type, count]) => {
                    const total = storageStats?.total_files || 1
                    const percent = (count / total) * 100
                    return (
                      <div key={type} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{type || "无后缀"}</span>
                          <span className="text-muted-foreground">{count} 个</span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 最近文件 */}
      <RecentFiles />
    </div>
  )
}
