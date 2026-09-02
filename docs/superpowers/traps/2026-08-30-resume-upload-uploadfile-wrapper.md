# 2026-08-30 简历上传 422：UploadFile 包装对象未取 raw

## 症状

通过 Element Plus `el-upload` 选择或拖拽简历时，前端请求 `/api/resume/upload` 返回 HTTP 422；通过原生隐藏 file input 的路径与拖拽区域行为不一致。

## 根因

Element Plus `@change` 回调传入的是 `UploadFile` 包装对象，真实浏览器文件位于 `.raw`。前端把包装对象直接传给 `FormData.append('file', file)`，FastAPI 无法将 multipart 字段解析为 `UploadFile`。

## 修复

在 `frontend/src/components/ResumeDiagnosis.vue` 的 `handleFile()` 中兼容 `File | UploadFile`：原生 `File` 直接使用，Element Plus 对象取 `raw`，无有效文件则不发请求。未改变后端接口和匹配逻辑。

## 教训

第三方上传组件的事件对象不能默认等同于浏览器 `File`。上传 API 应在边界处接收并验证原生文件，所有入口都应经过同一归一化函数。
