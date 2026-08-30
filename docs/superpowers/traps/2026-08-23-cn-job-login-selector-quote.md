# 智联/猎聘登录检测选择器字符串多一层引号

- 症状：智联/猎聘页面已经人工登录，但采集在登录检测阶段报 `Runtime.evaluate Uncaught`。
- 根因：嵌入页面执行的 CSS selector 字符串多了一层单引号，浏览器执行 `querySelectorAll` 时把非法 selector 当成语法错误。
- 修复：恢复为合法的 `querySelectorAll` selector 字符串，并用当前真实登录页面做两平台冒烟验证。
- 教训：拼接 JavaScript/CSS selector 时不要重复包裹引号；新增 DOM 抽取逻辑至少保留生成字符串的回归断言，并在真实页面执行一次语法冒烟。
