"use client"

import { useUploadTrend } from "@/lib/hooks"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

export function TrendChart() {
  const { data: trendData, isLoading } = useUploadTrend(7)

  const chartData = trendData?.dates.map((date, i) => ({
    date: new Date(date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" }),
    count: trendData.counts[i],
  })) || []

  return (
    <Card>
      <CardHeader>
        <CardTitle>上传趋势（最近 7 天）</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-48 animate-pulse bg-muted rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <XAxis
                dataKey="date"
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
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
              <Bar
                dataKey="count"
                fill="hsl(var(--primary))"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
