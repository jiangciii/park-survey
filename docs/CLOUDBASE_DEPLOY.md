# CloudBase 部署步骤

本文按“前端静态托管 + Python 后端云托管”的方式整理，目标是让你把当前问卷系统先部署成一个下周可演示的测试版。

## 0. 先在本地准备两个部署产物

在项目根目录执行：

```powershell
python scripts/build_static_bundle.py --api-base-url https://你的后端域名 --public-base-url https://你的前端域名
python scripts/build_backend_bundle.py
```

执行完成后你会得到：

- 前端静态包：`dist/cloudbase-static`
- 后端部署包：`dist/cloudbase-backend`

建议你先不要直接上传整个项目根目录。测试和演示阶段，用这两个目录最稳。

---

## 1. 你需要先定下两个线上地址

部署前先确定两件事：

1. 前端地址
   - 用 CloudBase 静态托管默认域名即可
   - 后面可替换成自定义域名

2. 后端地址
   - 用 CloudBase 云托管服务自动分配的访问域名即可
   - 后面可替换成自定义域名

建议你先按这个命名理解：

- 前端：`https://park-survey-web.xxx.tcloudbaseapp.com`
- 后端：`https://park-survey-api.xxx.run.tcloudbase.com`

前端运行时会通过 `runtime-config.js` 调你的后端接口，所以这两个地址要区分开。

---

## 2. 部署前端到 CloudBase 静态托管

官方参考：

- 静态网站托管概述  
  [https://docs.cloudbase.net/hosting/introduce](https://docs.cloudbase.net/hosting/introduce)
- 静态网站部署方式  
  [https://docs.cloudbase.net/hosting/web-hosting](https://docs.cloudbase.net/hosting/web-hosting)
- 自定义域名  
  [https://docs.cloudbase.net/hosting/custom-domain](https://docs.cloudbase.net/hosting/custom-domain)

### 控制台步骤

1. 打开 CloudBase 控制台
2. 进入你的云开发环境
3. 左侧进入“静态网站托管”
4. 如果还没开通，先点“开通”
5. 进入后点“新建部署”

### 你在控制台里这样填

如果你选择“上传代码包/文件夹”：

- 部署方式：`上传代码包` 或 `上传文件夹`
- 上传内容：`dist/cloudbase-static`
- 构建方式：`不构建`
  - 原因：我们已经本地打好了静态产物，不需要 CloudBase 再构建
- 输出目录：留空
- 安装命令：留空
- 构建命令：留空
- Node 版本：不用填

### 部署完成后你要做的事

1. 记下默认访问域名
2. 访问：

```text
https://你的静态托管域名/survey/
```

3. 确认页面能打开

说明：

- 根路径 `/` 会跳转到 `/survey/`
- 静态站本身不存数据，只负责页面展示和调用后端 API

---

## 3. 部署后端到 CloudBase 云托管

官方参考：

- 新建服务  
  [https://docs.cloudbase.net/run/deploy/create-service](https://docs.cloudbase.net/run/deploy/create-service)
- 部署服务  
  [https://docs.cloudbase.net/run/deploy/deploy-service](https://docs.cloudbase.net/run/deploy/deploy-service)
- 版本配置说明  
  [https://docs.cloudbase.net/run/deploy/version-setting](https://docs.cloudbase.net/run/deploy/version-setting)
- 环境变量  
  [https://docs.cloudbase.net/run/deploy/configuring/environment/envs](https://docs.cloudbase.net/run/deploy/configuring/environment/envs)

### 控制台步骤

1. 打开 CloudBase 控制台
2. 进入你的云开发环境
3. 左侧进入“云托管”
4. 点击“新建服务”

### 新建服务时这样填

#### 基础信息

- 服务名称：`park-survey-api`
- 部署类型：`容器服务`
- 上传方式：`本地代码`
- 代码内容：上传 `dist/cloudbase-backend` 目录或其 zip 包
- Dockerfile 名称：`Dockerfile`
- 目标目录：`/`
- 访问类型：`WEB`

#### 监听与流量

- 监听端口：`8000`
- 流量策略：`部署完成后自动开启 100% 流量`
  - 如果你想先自己验证，也可以选“先不开流量”，部署成功后再手动切到 100%

#### 资源配置

测试版建议这样填：

- CPU：`0.5 核`
- 内存：`1 GiB`
- 副本模式：`低成本`
- 最小实例数：`0`
- 最大实例数：`2`

如果你非常介意冷启动，改成：

- 副本模式：`高可用`
- 最小实例数：`1`
- 最大实例数：`2`

对组会演示更稳，但成本略高。

#### 高级配置

- InitialDelaySeconds：`5`
- 日志采集路径：`stdout`

### 环境变量这样填

在“环境变量”里逐项添加：

- `SURVEY_HOST` = `0.0.0.0`
- `PORT` = `8000`
- `SURVEY_DB_PATH` = `/data/survey_data.db`
- `SURVEY_PROJECT_ROOT` = `/app`
- `SURVEY_ADMIN_USER` = `你自己的后台账号`
- `SURVEY_ADMIN_PASSWORD` = `你自己的后台密码`
- `SURVEY_ALLOW_ORIGIN` = `https://你的静态托管域名`
- `SURVEY_PUBLIC_BASE_URL` = `https://你的后端访问域名`
- `SURVEY_API_BASE_URL` = 留空

说明：

- `SURVEY_API_BASE_URL` 对后端自己没有强依赖，可以先留空
- 真正关键的是 `SURVEY_ALLOW_ORIGIN`，否则前端静态站跨域请求会被拦

---

## 4. 前后端联动时你要这样改

在正式上传前端静态包之前，先重新打一遍前端包：

```powershell
python scripts/build_static_bundle.py --api-base-url https://你的后端访问域名 --public-base-url https://你的前端访问域名
```

然后重新上传新生成的：

- `dist/cloudbase-static`

这样前端页面里的：

- `/api/respondents/start`
- `/api/respondents/draft`
- `/api/respondents/submit`

会自动改成请求你的线上后端域名。

---

## 5. 管理后台怎么访问

后台不要放静态托管里。

部署后直接通过后端域名访问：

```text
https://你的后端访问域名/admin/login
```

因为后台依赖：

- 登录 cookie
- `/api/admin/*`
- CSV 导出

这些都应由同一个后端服务域名承载，最稳。

---

## 6. 关于 SQLite 持久化，这里你要特别注意

这是当前方案里唯一真正需要你清醒面对的点。

你现在的后端数据层是：

- SQLite
- 文件路径：`/data/survey_data.db`

CloudBase 云托管官方文档提供了“对象存储挂载”的持久化思路：  
[https://docs.cloudbase.net/run/deploy/configuring/storage/cos](https://docs.cloudbase.net/run/deploy/configuring/storage/cos)

但这类对象存储挂载并不适合 SQLite 作为长期正式数据库使用，原因很直接：

- SQLite 依赖本地文件锁
- 对象存储/挂载语义不等于本地块存储
- 多实例或重启场景下存在一致性风险

### 对你当前测试版的建议

如果目标只是“下周组会可演示”，你有两条路：

#### 路线 A：最省事

- 云托管只开 `1` 个常驻实例
- 不频繁重新部署
- 用当前 SQLite 先跑演示

这能用，但你要知道它不是正式长期方案。

#### 路线 B：更稳

- 后端暂时仍放本地电脑演示
- 前端静态托管上线
- 组会时展示线上前端 + 本地后端，或直接全本地演示

这是最稳的展示方案。

#### 路线 C：下一阶段再做

- 把 `respondents` 和 `ce_choices` 改到真正的数据库
- 再上云长期跑

如果你只是为了组会，我建议 A 或 B，不建议现在临时重构数据库。

---

## 7. 你在控制台里按这个顺序操作最稳

1. 先部署后端
2. 访问后端健康检查：

```text
https://你的后端访问域名/healthz
```

3. 确认返回：

```json
{"status":"ok"}
```

4. 再重新生成前端静态包，填入线上后端地址
5. 上传前端静态包
6. 打开：

```text
https://你的静态托管域名/survey/
```

7. 实测：
   - 前台是否能开始答题
   - 提交是否成功
   - 后台是否能登录
   - `respondents.csv` 是否能下载
   - `ce_choices.csv` 是否能下载

---

## 8. 你可以直接照抄的发布前检查

### 前端

- [ ] 已重新执行 `build_static_bundle.py`
- [ ] `--api-base-url` 已填后端线上域名
- [ ] `dist/cloudbase-static` 已重新上传
- [ ] `/survey/` 能打开

### 后端

- [ ] `dist/cloudbase-backend` 已上传到云托管
- [ ] 服务端口填的是 `8000`
- [ ] 访问类型选的是 `WEB`
- [ ] 环境变量已配置
- [ ] `/healthz` 返回 200

### 管理后台

- [ ] `/admin/login` 能打开
- [ ] 管理员账号密码可登录
- [ ] dashboard 能看到统计卡片
- [ ] 详情页能打开
- [ ] 两个 CSV 都能下载

### 风险提醒

- [ ] 你已接受 SQLite 仅作为测试版方案
- [ ] 若用于正式长期收数，后续需要换数据库
