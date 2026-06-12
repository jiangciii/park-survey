# 城市公园研究问卷系统

当前仓库是一套“研究型问卷系统”测试版，适合下周组会演示和小范围试填。系统由两部分组成：

- 前端问卷：移动端优先的网页问卷，包含普通题与 CE 情境选择
- Python 后端：负责提交、存储、管理员登录、后台统计、答卷详情与 CSV 导出

本版本优先目标是“最小可部署、可演示、可继续开发”，没有引入复杂框架或商用级账户体系。

---

## GitHub Pages 静态访问版

如果腾讯云后端已经过期、暂时无法继续访问，可以先使用 GitHub Pages 恢复前台问卷页面访问。

已新增 GitHub Pages 打包目标：

```powershell
python scripts/build_static_bundle.py --target github-pages --output dist/github-pages
```

生成入口：

- `dist/github-pages/index.html`
- `dist/github-pages/survey/index.html`

已新增自动部署工作流：

- `.github/workflows/deploy.yml`

推送到 GitHub 后，在仓库 `Settings > Pages` 中选择 `GitHub Actions`，等待 Actions 完成即可获得 GitHub Pages 链接。

注意：GitHub Pages 只能托管静态页面，不能运行 Python 后端、数据库或管理员后台。GitHub Pages 版本提交后会在封底提供 JSON / CSV 下载，不会写入原腾讯云后台数据库。若要继续正式在线收集数据，需要单独部署后端或接入 Google Sheets / Apps Script 等提交服务。

更详细步骤见：

- `docs/GITHUB_PAGES_DEPLOY.md`

---

## 1. 项目结构与启动入口

### 前端入口

- 问卷页面源文件：`survey_web.html`
- 问卷运行时脚本：`survey_app.js`
- 静态资源目录：`assets/`

### 后端入口

- 后端主程序：`survey_server.py`
- 数据层与导出逻辑：`survey_backend.py`
- SQLite 数据文件：默认 `survey_data.db`

### 管理后台页面

- 登录页：`admin_login.html`
- 仪表盘：`admin_dashboard.html`
- 单份答卷详情：`admin_response.html`
- 后台样式：`admin_app.css`

### 本地快捷启动脚本

- 一键启动服务：`启动问卷系统.bat`
- 打开前台问卷：`打开前台问卷.bat`
- 打开管理员后台：`打开管理员后台.bat`

---

## 2. 本地运行

### 方式 A：直接双击批处理

1. 双击 `启动问卷系统.bat`
2. 浏览器访问：
   - 前台问卷：`http://127.0.0.1:8000/survey`
   - 管理后台：`http://127.0.0.1:8000/admin/login`

管理员默认凭证：

- 用户名：`admin`
- 密码：`admin123456`

### 方式 B：命令行启动

```powershell
python survey_server.py --host 127.0.0.1 --port 8000 --db survey_data.db --root .
```

---

## 3. 环境变量

请先复制一份环境变量模板：

```powershell
copy .env.example .env
```

当前版本没有自动解析 `.env` 文件；你可以手动在系统环境变量中设置，或在启动命令前先 `set`。

### 关键变量

| 变量名 | 含义 | 本地默认值 |
|---|---|---|
| `SURVEY_HOST` | 后端绑定地址 | `127.0.0.1` |
| `SURVEY_PORT` | 后端端口 | `8000` |
| `PORT` | 云托管平台常用端口变量，优先级高于 `SURVEY_PORT` | `8000` |
| `SURVEY_DB_PATH` | SQLite 数据库路径 | `survey_data.db` |
| `SURVEY_PROJECT_ROOT` | 项目根目录 | `.` |
| `SURVEY_BASE_URL` | 本地批处理脚本打开的访问地址 | `http://127.0.0.1:8000` |
| `SURVEY_PUBLIC_BASE_URL` | 对外访问基地址，用于部署日志和运行时配置 | 空 |
| `SURVEY_API_BASE_URL` | 前端调用线上后端接口的地址。为空时走同源相对路径 | 空 |
| `SURVEY_ALLOW_ORIGIN` | 允许跨域调用问卷 API 的前端域名，多个逗号分隔 | 空 |
| `SURVEY_ADMIN_USER` | 管理员账号 | `admin` |
| `SURVEY_ADMIN_PASSWORD` | 管理员密码 | `admin123456` |

---

## 4. 前端如何对接线上后端地址

当前前端运行时会读取：

- `/static/runtime-config.js`

其中最关键的是：

```js
window.__SURVEY_RUNTIME__ = {
  apiBaseUrl: "https://你的后端域名",
  publicBaseUrl: "https://你的前端域名"
}
```

### 本地开发

- `apiBaseUrl` 为空即可
- 前端直接走同源 `/api/...`

### 线上静态前端 + 独立后端

如果前端静态托管在 CloudBase，后端运行在独立云托管域名：

- 前端 `runtime-config.js` 中把 `apiBaseUrl` 设置为后端完整域名
- 后端环境变量 `SURVEY_ALLOW_ORIGIN` 设为前端静态站点域名

示例：

```text
前端静态域名: https://park-survey-123.tcloudbaseapp.com
后端服务域名: https://park-survey-api-123.ap-shanghai.run.tcloudbase.com
```

则：

- 前端 `apiBaseUrl = "https://park-survey-api-123.ap-shanghai.run.tcloudbase.com"`
- 后端 `SURVEY_ALLOW_ORIGIN = "https://park-survey-123.tcloudbaseapp.com"`

说明：

- 普通受访者前台可以走“静态前端 -> 远程 API”
- 管理后台建议直接由后端服务域名承载，不建议拆到静态站点，以避免跨域 cookie 登录问题

---

## 5. 前端静态部署产物

已提供静态打包脚本：

```powershell
python scripts/build_static_bundle.py --api-base-url https://你的后端域名 --public-base-url https://你的前端域名
```

默认输出目录：

```text
dist/cloudbase-static
```

输出内容包括：

- `dist/cloudbase-static/survey/index.html`
- `dist/cloudbase-static/static/survey_app.js`
- `dist/cloudbase-static/static/runtime-config.js`
- `dist/cloudbase-static/assets/...`
- `dist/cloudbase-static/index.html`（会自动跳转到 `/survey/`）

这些文件就是 CloudBase 静态托管需要上传的内容。

后端也已提供精简部署包构建脚本：

```powershell
python scripts/build_backend_bundle.py
```

输出目录：

```text
dist/cloudbase-backend
```

CloudBase 逐步部署说明见：

- `docs/CLOUDBASE_DEPLOY.md`

---

## 6. CloudBase 目标部署方式

当前推荐采用：

### A. 前端：CloudBase 静态托管

部署内容：

- 上传 `dist/cloudbase-static/` 到 CloudBase 静态托管

前端上线后访问：

- `https://你的静态站点域名/survey/`

### B. 后端：CloudBase 云托管（Docker）

已补齐：

- `Dockerfile`
- `requirements.txt`
- `.dockerignore`

云托管容器启动时，至少需要配置：

- `PORT`
- `SURVEY_HOST=0.0.0.0`
- `SURVEY_DB_PATH=/data/survey_data.db`
- `SURVEY_PROJECT_ROOT=/app`
- `SURVEY_ADMIN_USER`
- `SURVEY_ADMIN_PASSWORD`
- `SURVEY_ALLOW_ORIGIN`
- `SURVEY_PUBLIC_BASE_URL`

建议：

- 把数据库文件挂载到持久化路径，如 `/data/survey_data.db`
- 管理后台走后端域名：
  - `https://你的后端域名/admin/login`

### C. 后端健康检查

已提供：

- `GET /healthz`

可用于云托管的基础存活检查。

---

## 7. Docker 本地验证

```powershell
docker build -t park-survey:demo .
docker run --rm -p 8000:8000 ^
  -e SURVEY_HOST=0.0.0.0 ^
  -e PORT=8000 ^
  -e SURVEY_DB_PATH=/data/survey_data.db ^
  -e SURVEY_ADMIN_USER=admin ^
  -e SURVEY_ADMIN_PASSWORD=admin123456 ^
  park-survey:demo
```

---

## 8. 当前系统能力

### 已支持

- 前台问卷完整作答流程
- Python 后端提交、存储、草稿保存
- `respondents` / `ce_choices` 两张核心表
- 管理员登录
- 后台统计卡片
- 答卷列表
- 单份答卷详情
- 导出 `respondents.csv`
- 导出 `ce_choices.csv`
- 基于运行时配置的前后端分离部署准备

### 当前仍然是测试版

- 认证仍为单管理员账号密码
- 数据库存储仍为 SQLite
- 后台暂无复杂图表
- 未接正式公网文件存储、监控、异常告警

---

## 9. 部署前检查清单

### 我已完成

- [x] 梳理当前前端与后端启动入口
- [x] 将运行层的 `127.0.0.1 / localhost` 改为环境变量可配置（服务器与批处理脚本）
- [x] 补齐 `requirements.txt`
- [x] 补齐 `Dockerfile`
- [x] 补齐 `.dockerignore`
- [x] 补齐前端静态打包脚本
- [x] 补齐运行时配置文件 `runtime-config.js`
- [x] 后端补充 `healthz`
- [x] 后端补充跨域配置入口 `SURVEY_ALLOW_ORIGIN`
- [x] 生成本 README

### 你还需要手动做

- [ ] 决定线上前端域名和后端域名
- [ ] 设置正式的管理员账号密码
- [ ] 在 CloudBase 控制台创建静态托管站点
- [ ] 在 CloudBase 控制台创建 Python 云托管服务
- [ ] 配置云托管环境变量
- [ ] 执行 `python scripts/build_static_bundle.py --api-base-url ... --public-base-url ...`
- [ ] 上传 `dist/cloudbase-static/` 到静态托管
- [ ] 将后端容器部署到云托管
- [ ] 首次上线后手动验证：
  - [ ] 前台可提交
  - [ ] 后台可登录
  - [ ] CSV 可导出
  - [ ] 跨域是否生效
  - [ ] 数据文件是否持久化

---

## 10. 组会演示建议

如果你下周主要是做演示而不是正式开放外部填写，建议顺序是：

1. 先用本地 `.bat` 跑通完整前后台
2. 再用 Docker 本地跑一遍
3. 最后再上 CloudBase

这样风险最小，组会现场也更稳。
