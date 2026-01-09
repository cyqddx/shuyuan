export const queryKeys = {
  files: {
    all: ["files"] as const,
    lists: () => [...queryKeys.files.all, "list"] as const,
    list: (filters: Record<string, string | number>) =>
      [...queryKeys.files.lists(), filters] as const,
    details: () => [...queryKeys.files.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.files.details(), id] as const,
  },
  stats: {
    all: ["stats"] as const,
    storage: () => [...queryKeys.stats.all, "storage"] as const,
    trend: (days: number) => [...queryKeys.stats.all, "trend", days] as const,
    expiring: (days: number) => [...queryKeys.stats.all, "expiring", days] as const,
    admin: () => [...queryKeys.stats.all, "admin"] as const,
  },
  system: {
    all: ["system"] as const,
    health: () => [...queryKeys.system.all, "health"] as const,
  },
}
