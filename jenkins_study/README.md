# 🏗️ Jenkins CI/CD 学习路线

> **环境**：2C2G 阿里云 ECS，内存可用 ~530MB  
> **前置**：Java 17 已安装，Docker 已安装  
> **目录**：`/workspace/jenkins_study/`  
> **方式**：4 阶段渐进，每阶段结束追加笔记到本文件

---

## 资源预算（关键！）

Jenkins 本体比较吃内存，2C2G 必须精打细算：

| 组件 | 运行方式 | 预估内存 | 说明 |
|------|---------|---------|------|
| Jenkins Master | Docker 容器，限制 `-Xmx256m` | ~400MB | 极限压缩，但够学习 |
| Demo 应用 | Python 脚本 | ~50MB | 被 Jenkins 构建的目标 |
| 总计 | | ~450MB | 刚好跑在可用内存内 ✅ |

> ⚠️ 如果跑不动，备选方案：纯 Jenkinsfile 语法学习 + CI/CD 概念，不跑 Jenkins 进程。

---

## 阶段 ①：概念筑基 — CI/CD & Jenkins 是什么

### 目标
理解 CI/CD 的核心思想、Jenkins 的架构、Pipeline as Code 理念，能画出 CI/CD 流程图。

### 做什么

1. **理解核心概念**（先不用装 Jenkins）

   | 概念 | 一句话解释 |
   |------|-----------|
   | CI（持续集成） | 代码提交 → 自动构建 → 自动测试 → 快速反馈 |
   | CD（持续交付/部署） | CI 通过后 → 自动部署到测试/生产环境 |
   | Jenkins | 开源的 CI/CD 自动化服务器，插件生态丰富 |
   | Pipeline（流水线） | 用代码定义构建-测试-部署全过程 |
   | Jenkinsfile | Pipeline 的代码文件，存在 Git 仓库里 |
   | Agent（节点） | 执行构建任务的机器（可 Master 自己跑，也可远程） |
   | Stage（阶段） | Pipeline 里的逻辑分组，如 Build → Test → Deploy |
   | Step（步骤） | Stage 里的具体操作，如 `sh 'npm test'` |

2. **画出 CI/CD 流程图**（文字版）

   ```
   开发者 Push 代码
        │
        ▼
   Git 仓库 (Webhook 触发)
        │
        ▼
   Jenkins 拉取代码
        │
        ▼
   ┌─ Stage: Build ─────┐
   │  编译 / 安装依赖     │
   └────────────────────┘
        │
        ▼
   ┌─ Stage: Test ──────┐
   │  单元测试 / 代码检查  │
   └────────────────────┘
        │
        ▼
   ┌─ Stage: Deploy ────┐
   │  部署到目标环境       │
   └────────────────────┘
        │
        ▼
   通知（邮件 / 钉钉 / Slack）
   ```

3. **Jenkins 架构理解**

   ```
   ┌──────────────┐     ┌──────────────┐
   │   Git Repo   │────▶│   Jenkins    │
   │  (GitHub)    │     │   Master     │
   └──────────────┘     │  (调度中心)   │
                        │  端口: 8080  │
   ┌──────────────┐     └──────┬───────┘
   │   Artifact   │◀───────────┤
   │   (制品仓库)  │            │ 分发任务
   └──────────────┘     ┌──────┴───────┐
                        │   Agent 1    │
                        │   Agent 2    │
                        │   (构建节点)  │
                        └──────────────┘
   ```

4. **Declarative vs Scripted Pipeline 对比**

   | 特性 | Declarative（声明式） | Scripted（脚本式） |
   |------|---------------------|-------------------|
   | 写法 | 结构化，`pipeline { stages { ... } }` | Groovy 脚本，自由灵活 |
   | 入门 | ⭐⭐⭐ 简单 | ⭐ 陡峭 |
   | 错误检查 | 启动时检查语法 | 运行时才报错 |
   | 推荐度 | ✅ 首选 | 高级场景用 |

### 产出
- [ ] 能口头解释 CI/CD 流程（面试能说 3 分钟）
- [ ] 手绘流程图
- [ ] 理解 Jenkinsfile 的基本结构

---

## 阶段 ②：安装 Jenkins + 第一个 Freestyle Job

### 目标
在 2C2G 机器上把 Jenkins 跑起来，创建第一个构建任务，理解 Web UI 操作。

### 做什么

1. **用 Docker 安装 Jenkins**（限制内存）

   ```bash
   docker run -d \
     --name jenkins \
     --restart unless-stopped \
     -p 8080:8080 \
     -p 50000:50000 \
     -v jenkins_home:/var/jenkins_home \
     -e JAVA_OPTS="-Xmx256m -Xms128m" \
     jenkins/jenkins:lts-jdk17
   ```

2. **获取初始密码并登录**

   ```bash
   docker logs jenkins 2>&1 | grep -A 5 "Please use the following password"
   # 或
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
   浏览器打开 `http://<服务器IP>:8080`，输入密码。

3. **安装推荐插件**（选 "Install suggested plugins"）

4. **创建管理员账号**（记住用户名密码）

5. **创建第一个 Freestyle Job**

   - 新建 Item → 输入名称 "hello-world" → 选择 Freestyle project
   - Build Steps → Add build step → Execute shell
   - 输入：
     ```bash
     echo "Hello from Jenkins!"
     echo "Current date: $(date)"
     echo "Java version:"
     java -version
     echo "Workspace: $(pwd)"
     whoami
     ```
   - 保存 → Build Now → 查看 Console Output

6. **理解 Freestyle Job 的配置项**

   | 配置区 | 作用 |
   |--------|------|
   | General | 描述、丢弃旧构建、参数化 |
   | Source Code Management | 从 Git 拉代码 |
   | Build Triggers | 定时构建、Poll SCM、Webhook |
   | Build Steps | 具体执行的命令 |
   | Post-build Actions | 构建后操作（归档、通知） |

### 产出
- [ ] Jenkins 跑在 `http://IP:8080`
- [ ] 第一个 Job 构建成功（绿色 ✅）
- [ ] 理解 Freestyle Job 配置面板

---

## 阶段 ③：Pipeline as Code — 编写 Jenkinsfile

### 目标
从 Freestyle → Pipeline，学会用代码定义 CI/CD 流程，理解 Jenkinsfile 语法。

### 做什么

1. **创建 Demo 项目**

   在 `/workspace/jenkins_study/demo-app/` 下创建一个简单的 Python 项目：

   ```
   demo-app/
   ├── Jenkinsfile        # Pipeline 定义
   ├── src/
   │   └── main.py        # 主程序
   ├── tests/
   │   └── test_main.py   # 测试
   └── requirements.txt   # 依赖
   ```

   项目包含：
   - 一个简单函数（如计算器）
   - 对应的 pytest 测试
   - 一个 Jenkinsfile

2. **编写 Declarative Pipeline（Jenkinsfile）**

   ```groovy
   pipeline {
       agent any

       environment {
           APP_NAME = 'demo-app'
           PYTHON_VERSION = '3.11'
       }

       stages {
           stage('Checkout') {
               steps {
                   echo "📦 拉取代码..."
                   checkout scm
               }
           }

           stage('Setup') {
               steps {
                   echo "🔧 安装依赖..."
                   sh 'pip install -r requirements.txt'
               }
           }

           stage('Test') {
               steps {
                   echo "🧪 运行测试..."
                   sh 'python -m pytest tests/ -v --tb=short'
               }
               post {
                   success {
                       echo "✅ 所有测试通过！"
                   }
                   failure {
                       echo "❌ 测试失败，请检查！"
                   }
               }
           }

           stage('Build') {
               steps {
                   echo "📦 构建中..."
                   sh 'tar -czf demo-app.tar.gz src/'
                   archiveArtifacts artifacts: 'demo-app.tar.gz'
               }
           }
       }

       post {
           always {
               echo "🏁 Pipeline 执行完毕"
               cleanWs()
           }
       }
   }
   ```

3. **创建 Pipeline Job 关联这个 Jenkinsfile**

   - New Item → Pipeline → 名称 "demo-pipeline"
   - Pipeline → Definition → Pipeline script from SCM
   - SCM → Git → Repository URL 填你的 Git 仓库地址
   - Script Path → `Jenkinsfile`
   - 保存 → Build Now

4. **理解 Pipeline 语法要点**

   ```groovy
   pipeline {
       agent any              // 在任何可用节点上运行

       environment {          // 环境变量（所有 stage 可见）
           FOO = 'bar'
       }

       stages {               // 阶段容器
           stage('名称') {     // 一个阶段
               steps {        // 步骤
                   sh '...'   // 执行 shell 命令
               }
           }
       }

       post {                 // 构建后动作
           always { ... }     // 无论如何都执行
           success { ... }    // 成功时
           failure { ... }    // 失败时
       }
   }
   ```

5. **常用 Step 速查**

   | Step | 作用 |
   |------|------|
   | `sh 'command'` | 执行 shell 命令 |
   | `echo 'msg'` | 输出日志 |
   | `checkout scm` | 拉取 Git 代码 |
   | `archiveArtifacts` | 归档构建产物 |
   | `junit '**/report.xml'` | 收集测试报告 |
   | `input message: '确认部署?'` | 人工审批 |
   | `timeout(time: 5, unit: 'MINUTES')` | 超时控制 |
   | `retry(3) { ... }` | 重试 |
   | `parallel(...)` | 并行执行 |

### 产出
- [ ] 一个完整的 Jenkinsfile（能跑通 4 个 stage）
- [ ] 理解 `stages → stage → steps` 三级结构
- [ ] 理解 `post` 条件块的使用

---

## 阶段 ④：进阶特性 + 测试集成

### 目标
掌握触发器、参数化构建、通知、并行执行等进阶特性，最后做一个综合实战。

### 做什么

1. **定时触发器（Cron）**

   在 Jenkinsfile 的 `triggers` 块中配置：

   ```groovy
   pipeline {
       triggers {
           cron('H/30 * * * *')    // 每 30 分钟构建一次
       }
       // ...
   }
   ```

   | Cron 表达式 | 含义 |
   |-------------|------|
   | `H/15 * * * *` | 每 15 分钟 |
   | `@daily` | 每天午夜 |
   | `@weekly` | 每周一次 |
   | `H 9 * * 1-5` | 工作日早 9 点 |

2. **参数化构建**

   ```groovy
   pipeline {
       parameters {
           string(name: 'BRANCH', defaultValue: 'main', description: '要构建的分支')
           choice(name: 'ENV', choices: ['dev', 'staging', 'prod'], description: '部署环境')
           booleanParam(name: 'RUN_TESTS', defaultValue: true, description: '是否运行测试')
       }
       stages {
           stage('Build') {
               steps {
                   echo "构建分支: ${params.BRANCH}"
                   echo "目标环境: ${params.ENV}"
               }
           }
       }
   }
   ```

3. **条件判断（when）**

   ```groovy
   stage('Deploy to Prod') {
       when {
           branch 'main'                  // 只有 main 分支
           expression { params.ENV == 'prod' }  // 且选了 prod 环境
       }
       steps {
           echo '🚀 部署到生产环境！'
       }
   }
   ```

4. **并行执行**

   ```groovy
   stage('Parallel Tests') {
       parallel {
           stage('Unit Tests') {
               steps {
                   sh 'pytest tests/unit/'
               }
           }
           stage('Integration Tests') {
               steps {
                   sh 'pytest tests/integration/'
               }
           }
           stage('Lint') {
               steps {
                   sh 'flake8 src/'
               }
           }
       }
   }
   ```

5. **邮件 / 钉钉通知**

   ```groovy
   post {
       failure {
           emailext(
               to: 'team@example.com',
               subject: "❌ ${env.JOB_NAME} #${env.BUILD_NUMBER} 失败",
               body: "详情: ${env.BUILD_URL}"
           )
       }
   }
   ```

6. **综合实战：完整的 CI/CD Pipeline**

   ```groovy
   pipeline {
       agent any
       triggers { cron('H 9 * * 1-5') }

       parameters {
           choice(name: 'DEPLOY_ENV', choices: ['dev', 'staging', 'prod'])
       }

       stages {
           stage('Checkout') {
               steps { checkout scm }
           }

           stage('Parallel Checks') {
               parallel {
                   stage('Unit Test') {
                       steps { sh 'pytest tests/ -v' }
                   }
                   stage('Code Style') {
                       steps { sh 'flake8 src/ --max-line-length=120' }
                   }
               }
           }

           stage('Build') {
               steps {
                   sh 'tar -czf app.tar.gz src/'
                   archiveArtifacts 'app.tar.gz'
               }
           }

           stage('Deploy') {
               when { expression { params.DEPLOY_ENV != 'prod' } }
               steps {
                   sh "echo 'Deploying to ${params.DEPLOY_ENV}...'"
               }
           }

           stage('Deploy to Prod') {
               when { expression { params.DEPLOY_ENV == 'prod' } }
               input { message '确认部署到生产环境?' }
               steps {
                   sh "echo 'Deploying to PRODUCTION...'"
               }
           }
       }

       post {
           success { echo '✅ Pipeline 成功' }
           failure { echo '❌ Pipeline 失败' }
       }
   }
   ```

### 产出
- [ ] 掌握触发器、参数化、条件判断
- [ ] 能写带并行+通知的 Jenkinsfile
- [ ] 完成综合实战 Pipeline

---

## 🗂️ 学习目录结构

```
/workspace/jenkins_study/
├── README.md                  # 👈 这个文件（笔记 + 规划）
├── demo-app/                  # 阶段③的 Demo 项目
│   ├── Jenkinsfile
│   ├── src/
│   │   └── main.py
│   ├── tests/
│   │   └── test_main.py
│   └── requirements.txt
└── notes/                     # 额外笔记
    ├── concepts.md            # 概念笔记
    └── troubleshooting.md     # 踩坑记录
```

---

## 📋 检查清单

| 知识点 | ✅ |
|--------|-----|
| CI/CD 是什么 | ☐ |
| Jenkins 架构（Master/Agent） | ☐ |
| Freestyle Job 配置 | ☐ |
| Declarative Pipeline 语法 | ☐ |
| `stages → stage → steps` 结构 | ☐ |
| `environment` 环境变量 | ☐ |
| `post` 条件块 | ☐ |
| `when` 条件判断 | ☐ |
| `parameters` 参数化构建 | ☐ |
| `triggers` 定时构建 | ☐ |
| `parallel` 并行执行 | ☐ |
| `archiveArtifacts` 归档产物 | ☐ |
| 邮件/钉钉通知 | ☐ |
| 综合 Pipeline 实战 | ☐ |

---

## 🔧 常见踩坑预判

| 问题 | 原因 | 解决 |
|------|------|------|
| Jenkins 启动后 OOM | 默认分配内存太大 | 加 `JAVA_OPTS="-Xmx256m"` |
| `checkout scm` 报错 | 未配置 Git 仓库地址 | Pipeline Job 里配 SCM |
| `sh` 命令找不到 | 容器内缺工具 | `docker exec jenkins apt install ...` |
| Pipeline 语法报错 | 缩进不对 | Declarative 对缩进敏感，用 4 空格 |
| 插件安装失败 | 网络问题 | 配置国内镜像源 |

---

> 🎯 学完 4 个阶段，你就能看懂公司 Jenkins 上的 Pipeline，能自己写 Jenkinsfile，面试 CI/CD 方向不虚。
