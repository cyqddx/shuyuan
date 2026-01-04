# 错误码文档

## HTTP 状态码

| 状态码 | 含义 | 示例场景 |
|--------|------|----------|
| 200 | 成功 | 文件上传成功、获取文件成功 |
| 400 | 请求错误 | JSON 格式无效、文件类型不允许、JSON 嵌套过深 |
| 401 | 未授权 | API Key 无效或未提供 |
| 404 | 未找到 | 文件不存在或已过期 |
| 413 | 文件过大 | 超过大小限制 |
| 429 | 请求过多 | 触发限流 |
| 500 | 服务器错误 | 文件损坏、解密失败、存储错误 |

## 业务错误码

| 错误码 | 描述 | 解决方案 |
|--------|------|----------|
| `VALIDATION_ERROR` | 请求参数验证失败 | 检查请求格式和参数类型 |
| `INTERNAL_ERROR` | 服务内部错误 | 稍后重试或联系管理员 |
| `HTTP_ERROR` | HTTP 错误 | 查看具体错误信息 |
| `FILE_TOO_LARGE` | 文件过大 | 减小文件大小，确保符合限制 |
| `INVALID_JSON` | JSON 格式无效 | 检查 JSON 语法是否正确 |
| `JSON_TOO_DEEP` | JSON 嵌套过深 | 简化 JSON 结构，减少嵌套层级 |
| `JSON_TOO_MANY_FIELDS` | JSON 字段过多 | 减少对象字段数量 |
| `API_KEY_INVALID` | API Key 无效 | 检查 `x-api-key` 请求头 |
| `API_KEY_MISSING` | 未提供 API Key | 添加 `x-api-key` 请求头 |
| `FILE_TYPE_NOT_ALLOWED` | 文件类型不允许 | 仅支持 `.json` 文件 |

## 错误响应格式

### 标准错误响应

```json
{
  "code": "INVALID_JSON",
  "msg": "📄 JSON 格式无效，请检查文件内容",
  "data": null
}
```

### 上传错误示例

```json
{
  "code": "FILE_TOO_LARGE",
  "msg": "📦 文件过大，限制为 10485760 字节",
  "data": null
}
```

### 鉴权错误示例

```json
{
  "code": "HTTP_ERROR",
  "msg": "⛔ API Key 无效",
  "data": null
}
```

## JSON 验证限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| 最大嵌套深度 | 20 层 | 防止深度嵌套攻击 |
| 最大字段数 | 1000 个 | 防止超大对象攻击 |
| 最大数组长度 | 1000 个元素 | 防止超大数组攻击 |
| 最大文件大小 | 10 MB | 由 `MAX_FILE_SIZE` 配置 |
