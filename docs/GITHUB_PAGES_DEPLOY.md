# GitHub Pages 部署说明

这份说明用于把当前问卷前台恢复为可公开访问的 GitHub Pages 静态网页。

## 1. 当前项目判断

当前项目不是纯静态问卷，包含两部分：

- 前台问卷：`survey_web.html`、`survey_app.js`、`assets/`
- Python 后端：`后端/survey_server.py`、`后端/survey_backend.py`，负责提交、数据库、后台和导出

GitHub Pages 只能托管静态 HTML/CSS/JS，不能运行 Python 后端、SQLite/MySQL 数据库或管理员后台。

因此本次 GitHub Pages 版本的定位是：

- 保留问卷页面、题目、CE 选择流程和前端交互
- 不连接已过期的腾讯云后端
- 提交后在封底提供 JSON / CSV 下载
- 若后续需要继续线上收集数据，需要另行部署后端或接入 Google Sheets / Apps Script 等服务

## 2. 本地生成 GitHub Pages 静态产物

在项目根目录运行：

```powershell
python scripts/build_static_bundle.py --target github-pages --output dist/github-pages
```

也可以使用 npm 脚本：

```powershell
npm run build:github-pages
```

生成目录：

```text
dist/github-pages
```

入口文件：

```text
dist/github-pages/index.html
```

也会额外生成：

```text
dist/github-pages/survey/index.html
```

这样 GitHub Pages 根路径和 `/survey/` 子路径都可以打开问卷。

本地预览：

```powershell
python -m http.server 8123 --directory dist/github-pages
```

然后访问：

```text
http://127.0.0.1:8123/
http://127.0.0.1:8123/survey/
```

## 3. GitHub Pages 自动部署

仓库已新增：

```text
.github/workflows/deploy.yml
```

推送到 GitHub 的 `main` 或 `master` 分支后，GitHub Actions 会自动：

1. 检出代码
2. 使用 Python 生成 `dist/github-pages`
3. 上传静态产物
4. 发布到 GitHub Pages

## 4. GitHub 控制台设置

进入 GitHub 仓库：

1. 打开 `Settings`
2. 打开 `Pages`
3. `Build and deployment` 选择 `GitHub Actions`
4. 回到 `Actions` 页面，等待 `Deploy GitHub Pages` 运行完成
5. 部署完成后，进入 workflow 详情页或 `Settings > Pages` 查看访问链接

访问地址通常类似：

```text
https://你的用户名.github.io/仓库名/
```

如果使用 `/survey/` 子路径：

```text
https://你的用户名.github.io/仓库名/survey/
```

## 5. 数据提交说明

GitHub Pages 版本没有后端数据库，提交后不会写入原腾讯云后台。

静态版提交完成后，封底会显示下载入口：

- 下载 JSON 结果
- 下载普通题 CSV
- 下载 CE CSV

这些文件可用于临时测试、演示和人工回收。

如果要恢复正式在线收集，建议二选一：

- 继续部署 Python 后端到云服务器或云托管，再把 `runtime-config.js` 的 `apiBaseUrl` 指向后端
- 接入 Google Sheets / Apps Script 等轻量提交服务

## 6. 不变内容

本次 GitHub Pages 适配不修改：

- 问卷题目
- 选项文字
- CE 任务组合
- 变量字段名称
- 页面顺序
- 原后端接口文件
- 原数据库文件
- 管理后台逻辑

主要修改仅用于：

- 让资源路径适配 GitHub Pages 子路径
- 让静态版本提交时改为本地导出 JSON / CSV
- 增加自动部署工作流
