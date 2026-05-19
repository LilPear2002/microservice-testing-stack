# 🐧 Linux 常用命令练习场

> **使用方式**：进入 `/workspace/linux_cmd_practice/`，按题目序号从易到难练习。
> 先在终端自己敲命令，实在不会了再看答案。每道题建议先思考 30 秒再动手。

---

## 📁 练习环境说明

```
linux_cmd_practice/
├── projects/               # 模拟项目
│   ├── web-app/            # Web 应用（源码、日志、数据）
│   ├── api-service/        # API 服务（handlers、日志、配置）
│   └── data-pipeline/      # 数据处理流水线
├── shared/                 # 共享脚本和文档
│   ├── scripts/            # backup.sh, deploy.sh
│   └── docs/               # architecture.md, deployment.md
├── archive/                # 历史归档
│   ├── 2024/
│   └── 2025/
├── hidden_dir/             # 👻 藏了东西
├── tmp/                    # 临时文件区
└── README.md               # 你正在看的文件
```

---

# 第一部分：基础篇 —— 目录导航与文件查看

---

### 1. **列出目录内容**
> 查看 `projects/web-app/` 下有哪些文件和子目录。

<details>
<summary>🔍 答案</summary>

```bash
ls projects/web-app/
# 或者用 ls -la 查看详细信息（包括隐藏文件）
ls -la projects/web-app/
```
</details>

---

### 2. **查看完整目录树**
> 以树形结构展示 `projects/` 下所有内容（两级深度）。

<details>
<summary>🔍 答案</summary>

```bash
tree -L 2 projects/
# 如果没有 tree，用 find 代替：
find projects/ -maxdepth 2
```
</details>

---

### 3. **显示当前完整路径 & 跳转**
> ① 显示当前所在的绝对路径  
> ② 切换到 `projects/web-app/logs/`  
> ③ 用一条命令回到刚才的目录

<details>
<summary>🔍 答案</summary>

```bash
# ① 显示当前路径
pwd

# ② 切换到目标目录
cd projects/web-app/logs/

# ③ 回到上一个目录
cd -
# 或者 cd $OLDPWD
```
</details>

---

### 4. **查看文件内容（cat / less / head / tail）**
> ① 用 `cat` 查看 `shared/docs/architecture.md` 全文  
> ② 用 `less` 分页浏览同一个文件  
> ③ 用 `head` 只看 `archive/2024/old-log.txt` 的前 5 行  
> ④ 用 `tail` 看同一个文件的最后 3 行

<details>
<summary>🔍 答案</summary>

```bash
# ①
cat shared/docs/architecture.md

# ②
less shared/docs/architecture.md
# 按 q 退出，上下箭头/空格翻页

# ③
head -n 5 archive/2024/old-log.txt

# ④
tail -n 3 archive/2024/old-log.txt
```
</details>

---

### 5. **查看文件大小**
> ① 用 `ls` 查看 `tmp/numbers.txt` 的大小（人类可读格式）  
> ② 用 `du` 查看 `projects/web-app/logs/` 目录占用的磁盘空间

<details>
<summary>🔍 答案</summary>

```bash
# ① 人类可读格式
ls -lh tmp/numbers.txt

# ② 目录占用空间
du -sh projects/web-app/logs/
```
</details>

---

### 6. **文件类型识别**
> 用 `file` 命令判断以下文件是什么类型：  
> `tmp/numbers.txt`、`shared/scripts/backup.sh`、`projects/web-app/data/products.json`

<details>
<summary>🔍 答案</summary>

```bash
file tmp/numbers.txt
file shared/scripts/backup.sh
file projects/web-app/data/products.json
# 或者一条命令搞定：
file tmp/numbers.txt shared/scripts/backup.sh projects/web-app/data/products.json
```
</details>

---

# 第二部分：进阶篇 —— 查找、处理、权限

---

### 7. **搜索文件内容（grep）**
> ① 在 `projects/web-app/src/` 下所有 `.py` 文件中搜索 `logger`  
> ② 搜索并显示行号  
> ③ 只看哪些文件包含 `logger`（不显示具体行）

<details>
<summary>🔍 答案</summary>

```bash
# ① 基础搜索
grep -r "logger" projects/web-app/src/

# ② 显示行号
grep -rn "logger" projects/web-app/src/

# ③ 只看文件名
grep -rl "logger" projects/web-app/src/
```
</details>

---

### 8. **在所有日志中找 ERROR**
> ① 找出 `projects/` 下所有 `.log` 文件中包含 `ERROR` 的行  
> ② 统计一共有多少行 ERROR

<details>
<summary>🔍 答案</summary>

```bash
# ① 递归搜索所有 .log 文件
grep -rn "ERROR" projects/ --include="*.log"

# ② 统计数量
grep -r "ERROR" projects/ --include="*.log" | wc -l
```
</details>

---

### 9. **查找文件（find）**
> ① 找出 `projects/` 下所有 `.py` 文件  
> ② 找出 `/workspace/linux_cmd_practice/` 下最近 1 天内修改过的文件  
> ③ 找出 `tmp/` 下为空的文件

<details>
<summary>🔍 答案</summary>

```bash
# ① 按后缀查找
find projects/ -name "*.py"

# ② 按修改时间查找（-mtime）
find /workspace/linux_cmd_practice/ -mtime -1

# ③ 查找空文件
find tmp/ -type f -empty
```
</details>

---

### 10. **管道与组合**
> ① 统计 `projects/web-app/src/` 下所有 `.py` 文件的总行数（用 `wc -l` + `find`）  
> ② 列出 `projects/web-app/logs/error.log` 中出现最多的错误类型（Top 3）

<details>
<summary>🔍 答案</summary>

```bash
# ① 统计 .py 文件总行数
find projects/web-app/src/ -name "*.py" -exec cat {} + | wc -l
# 或
cat projects/web-app/src/*.py | wc -l

# ② Top 3 错误类型
grep "ERROR" projects/web-app/logs/error.log | \
  sed 's/.*ERROR.*: //' | \
  sed 's/:.*//' | \
  sort | uniq -c | sort -rn | head -3
# 解释：grep 取ERROR行 → sed去掉前缀 → sed去掉后缀 → sort+uniq -c 计数 → sort -rn 倒排 → head -3
```
</details>

---

### 11. **文本处理（cut / sort / uniq）**
> 从 `projects/web-app/data/users.csv` 中：  
> ① 只提取 `name` 列（第 2 列）  
> ② 提取所有 role，去重排序  
> ③ 统计每种 role 有多少人

<details>
<summary>🔍 答案</summary>

```bash
# ① 提取 name 列（跳过表头）
tail -n +2 projects/web-app/data/users.csv | cut -d',' -f2

# ② role 去重排序
tail -n +2 projects/web-app/data/users.csv | cut -d',' -f4 | sort -u

# ③ 统计每种 role 人数
tail -n +2 projects/web-app/data/users.csv | cut -d',' -f4 | sort | uniq -c
```
</details>

---

### 12. **sed 替换**
> ① 把 `shared/docs/architecture.md` 中所有 `production` 替换为 `stable`（只输出，不改文件）  
> ② 把 `tmp/numbers.txt` 中所有以 `00` 结尾的行前面加上 `>>> `

<details>
<summary>🔍 答案</summary>

```bash
# ① 模拟替换（不改文件）
sed 's/production/stable/g' shared/docs/architecture.md

# ② 在 00 结尾行前加标记
sed '/00$/s/^/>>> /' tmp/numbers.txt
# 解释：/00$/ 匹配以00结尾的行，s/^/>>> / 在行首替换
```
</details>

---

### 13. **awk 入门**
> 从 `projects/web-app/logs/error.log` 中：  
> ① 只打印第 1 列（时间）和第 3 列（级别）  
> ② 统计各级别日志的数量（INFO/WARNING/ERROR/FATAL/CRITICAL）

<details>
<summary>🔍 答案</summary>

```bash
# ① 打印第1、3列
awk '{print $1, $3}' projects/web-app/logs/error.log

# ② 统计各级别数量
awk '{count[$3]++} END {for (level in count) print level, count[level]}' projects/web-app/logs/error.log
# 解释：count[$3]++ 以第3列为key计数，END块在读完所有行后执行
```
</details>

---

### 14. **权限管理（chmod / chown）**
> ① 查看 `shared/scripts/backup.sh` 的权限  
> ② 给它加上**所有用户可执行**权限  
> ③ 创建一个只有自己能读写的 `tmp/my_secret.txt`

<details>
<summary>🔍 答案</summary>

```bash
# ① 查看权限
ls -l shared/scripts/backup.sh

# ② 所有人可执行
chmod a+x shared/scripts/backup.sh
# 或 chmod 755 shared/scripts/backup.sh

# ③ 创建私密文件（owner 可读写）
touch tmp/my_secret.txt
chmod 600 tmp/my_secret.txt
ls -l tmp/my_secret.txt    # 验证：-rw-------
```
</details>

---

### 15. **查找隐藏的"秘密"**
> `hidden_dir/` 里藏了一个 `.config` 目录。  
> ① 用 `ls` 列出 `hidden_dir/` 的**所有文件**（包括隐藏的）  
> ② 找到里面的秘密配置文件并查看内容

<details>
<summary>🔍 答案</summary>

```bash
# ① 列出所有文件（包括隐藏）
ls -la hidden_dir/
# ls -a 显示 . 开头的文件，-l 长格式

# ② 深入查看
ls -la hidden_dir/.config/
cat hidden_dir/.config/.secret_config
```
</details>

---

# 第三部分：高级篇 —— 进程、端口、日志分析

---

### 16. **实时监控日志（tail -f）**
> 模拟运维场景：`web-app` 的 `app.log` 在不断写入，你需要实时查看最新日志。
> （先在另一个终端模拟追加日志，然后用 tail -f 监控）

> 💡 **练习提示**：开两个终端  
> 终端1：`tail -f projects/web-app/logs/app.log`  
> 终端2：`echo "2025-05-19 10:00:00 ERROR Test error message" >> projects/web-app/logs/app.log`
> 观察终端1是否实时显示新行。

<details>
<summary>🔍 答案</summary>

```bash
# 终端1 - 实时监控
tail -f projects/web-app/logs/app.log

# 终端2 - 追加日志
echo "2025-05-19 10:00:00 ERROR [test] Something broke!" >> projects/web-app/logs/app.log

# 按 Ctrl+C 退出 tail -f

# 只看最后 20 行并持续监控
tail -n 20 -f projects/web-app/logs/app.log
```
</details>

---

### 17. **分析 Nginx 风格访问日志**
> `projects/web-app/logs/access.log` 是模拟的 Nginx 访问日志。  
> ① 统计一共有多少条请求  
> ② 统计每个 HTTP 状态码出现次数  
> ③ 找出返回 500 状态的请求  
> ④ 找出访问量 Top 5 的 IP 地址

<details>
<summary>🔍 答案</summary>

```bash
# ① 总请求数
wc -l projects/web-app/logs/access.log

# ② 状态码统计
awk '{print $9}' projects/web-app/logs/access.log | sort | uniq -c | sort -rn

# ③ 500 错误的请求
grep '" 500 ' projects/web-app/logs/access.log
# 注意：状态码两边有空格，避免匹配到 500 开头的字节数

# ④ Top 5 IP
awk '{print $2}' projects/web-app/logs/access.log | sort | uniq -c | sort -rn | head -5
```
</details>

---

### 18. **查找大文件 / 磁盘空间**
> ① 找出 `projects/` 下最大的 3 个文件  
> ② 查看 `/workspace/linux_cmd_practice/` 总共占多少磁盘空间  
> ③ 查看 `/` 根分区的磁盘使用情况

<details>
<summary>🔍 答案</summary>

```bash
# ① 最大的 3 个文件（按大小排序）
find projects/ -type f -exec du -h {} + | sort -rh | head -3
# 或
ls -lhS projects/**/* 2>/dev/null | head -3
# -S 按文件大小排序

# ② 目录总占用
du -sh /workspace/linux_cmd_practice/

# ③ 磁盘使用情况
df -h /
```
</details>

---

### 19. **进程管理（ps / top / kill）**
> ① 查看当前所有正在运行的进程  
> ② 只看 Python 相关的进程  
> ③ 在自己终端里启动一个后台任务 `sleep 300 &`，然后找到它并杀掉

<details>
<summary>🔍 答案</summary>

```bash
# ① 所有进程
ps aux

# ② 只看 Python 进程
ps aux | grep python
# 或者 pgrep -a python

# ③ 启动后台任务 → 找PID → 杀掉
sleep 300 &
# 输出：[1] 12345 （这是 PID）
jobs              # 查看后台任务
kill 12345        # 杀掉进程
# 或 kill %1       # 按 jobs 编号杀
# 确认已杀掉：
jobs
```
</details>

---

### 20. **端口与网络**
> ① 查看所有正在监听的端口（TCP + UDP）  
> ② 只看 TCP 端口，显示进程名和 PID  
> ③ 测试 `github.com` 的 443 端口是否可达

<details>
<summary>🔍 答案</summary>

```bash
# ① 所有监听端口
ss -tuln
# -t: TCP, -u: UDP, -l: listening, -n: 数字格式

# ② TCP+进程信息
ss -tlnp
# 需要 root 权限才能看到所有进程信息

# ③ 端口连通性测试
nc -zv github.com 443
# 或
timeout 3 bash -c '</dev/tcp/github.com/443' && echo "可达" || echo "不可达"
```
</details>

---

### 21. **系统资源监控**
> ① 只看一次内存使用情况  
> ② 实时查看 CPU 和内存（类似 top 的替代品）  
> ③ 查看系统运行了多久（uptime）

<details>
<summary>🔍 答案</summary>

```bash
# ① 内存
free -h

# ② 实时监控（htop 更友好，没有就用 top）
htop
# 或
top

# ③ 系统运行时间
uptime
# 输出示例：10:30:00 up 15 days, 3:25, 1 user, load average: 0.15, 0.10, 0.05
```
</details>

---

### 22. **日志分析综合题**
> `error.log` 记录了今天上午的系统错误。  
> ① 统计早上 8 点到 9 点之间有多少条 ERROR  
> ② 找出所有 "connection" 相关的错误  
> ③ 提取所有错误出现的**服务名**（如 `[web-app]`、`[api-service]`），统计每个服务报错几次  
> ④ 找出哪些错误重复出现了 3 次以上

<details>
<summary>🔍 答案</summary>

```bash
# ① 8:00-9:00 的 ERROR
grep "2025-05-19 08:" projects/web-app/logs/error.log | grep "ERROR" | wc -l

# ② connection 相关错误（不区分大小写）
grep -i "connection" projects/web-app/logs/error.log

# ③ 按服务统计错误数
# 方法1：提取 [] 中的服务名
grep -oP '\[.*?\]' projects/web-app/logs/error.log | sort | uniq -c | sort -rn

# 方法2：awk
awk -F'[][]' '{print $2}' projects/web-app/logs/error.log | sort | uniq -c | sort -rn

# ④ 重复出现 3 次以上的错误
# 提取错误类型（去掉时间戳和方括号内容后的关键信息）
grep "ERROR" projects/web-app/logs/error.log | \
  sed 's/.*ERROR \[[^]]*\] //' | \
  sort | uniq -c | sort -rn | awk '$1 >= 3'
```
</details>

---

### 23. **压缩、归档与传输**
> ① 把 `projects/web-app/logs/` 整个目录打包成 `logs_backup.tar.gz`  
> ② 查看压缩包里的文件列表（不解压）  
> ③ 把 `archive/` 目录打包并用 gzip 压缩，存到 `tmp/archive_backup.tar.gz`

<details>
<summary>🔍 答案</summary>

```bash
# ① 打包压缩
tar -czf logs_backup.tar.gz projects/web-app/logs/

# ② 查看内容不解压
tar -tzf logs_backup.tar.gz

# ③ 打包 archive
tar -czf tmp/archive_backup.tar.gz archive/
# 验证：
tar -tzf tmp/archive_backup.tar.gz
```
</details>

---

### 24. **diff 对比 & 文件差异**
> ① 对比 `shared/docs/architecture.md` 和 `shared/docs/deployment.md` 有什么不同  
> ② 把 `projects/web-app/logs/error.log` 复制一份到 `tmp/error_v2.log`，手动改几行，然后用 `diff` 找出差异

<details>
<summary>🔍 答案</summary>

```bash
# ① 对比两个文件
diff shared/docs/architecture.md shared/docs/deployment.md
# 或用 side-by-side 模式（更直观）
diff -y shared/docs/architecture.md shared/docs/deployment.md

# ② 复制 → 修改 → 对比
cp projects/web-app/logs/error.log tmp/error_v2.log
# 手动编辑 tmp/error_v2.log，改几行
diff projects/web-app/logs/error.log tmp/error_v2.log
# 或用彩色输出：
diff --color projects/web-app/logs/error.log tmp/error_v2.log
```
</details>

---

### 25. **终极挑战：一键生成运维报告**
> 写一条组合命令，输出以下信息：  
> ① 系统当前时间 + uptime  
> ② 磁盘使用率  
> ③ 内存使用率  
> ④ 今天的 ERROR 日志条数  
> ⑤ 访问量 Top 3 的 API 路径  

<details>
<summary>🔍 答案</summary>

```bash
echo "=== 每日运维报告 ==="
echo "生成时间: $(date)"
echo ""
echo "--- 系统状态 ---"
uptime
echo ""
echo "--- 磁盘 ---"
df -h / | tail -1
echo ""
echo "--- 内存 ---"
free -h | grep Mem
echo ""
echo "--- 今日 ERROR ---"
grep "$(date +%Y-%m-%d)" projects/web-app/logs/error.log | grep -c ERROR 2>/dev/null \
  || echo "今天暂无ERROR"
echo ""
echo "--- Top 3 API 路径 ---"
awk '{print $7}' projects/web-app/logs/access.log | sort | uniq -c | sort -rn | head -3
echo ""
echo "=== 报告完毕 ==="
```

> 💡 更高级的写法：把以上内容存为一个脚本 `daily_report.sh`，加可执行权限，一劳永逸。
</details>

---

## 🏁 检查清单

自检：以下命令你能不查资料直接敲出来吗？

| 命令 | 作用 | ✅ |
|------|------|-----|
| `ls -la` | 列出所有文件（含隐藏） | ☐ |
| `cd -` | 返回上一个目录 | ☐ |
| `find -name "*.log"` | 按文件名查找 | ☐ |
| `grep -rn "ERROR" .` | 递归搜索文件内容 | ☐ |
| `tail -f app.log` | 实时监控日志 | ☐ |
| `awk '{print $1}'` | 提取列 | ☐ |
| `sort \| uniq -c \| sort -rn` | 统计频率排序 | ☐ |
| `chmod 755 file.sh` | 修改权限 | ☐ |
| `ps aux \| grep python` | 查看特定进程 | ☐ |
| `ss -tlnp` | 查看监听端口 | ☐ |
| `tar -czf` / `tar -xzf` | 打包压缩/解压 | ☐ |
| `df -h` / `free -h` | 磁盘/内存查看 | ☐ |
| `diff file1 file2` | 文件对比 | ☐ |
| `sed 's/A/B/g'` | 文本替换 | ☐ |

---

## 📚 延伸学习

- **jq**：JSON 处理神器 → `cat products.json | jq '.products[].name'`
- **xargs**：将标准输入转为命令行参数 → `find . -name "*.log" | xargs grep "ERROR"`
- **tee**：同时输出到屏幕和文件 → `./script.sh | tee output.log`
- **crontab**：定时任务 → `crontab -e`
- **journalctl**：systemd 日志管理 → `journalctl -u nginx -f`

---

> 🎉 完成全部 25 题后，你已经掌握了日常运维 90% 的 Linux 命令行操作！
