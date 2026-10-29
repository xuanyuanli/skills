---
name: pdf-to-markdown
description: 把 PDF、EPUB、DOCX、PPT 等原书或附件转成干净的 Markdown，含扫描件 OCR、测速选型、断点续跑与转换后清理。当用户要求「把 PDF 转成 md」「原书转 Markdown」「提取这本书的文字」「扫描件 OCR」「EPUB/DOCX 转 md」，或需要处理 OCR 出来的乱码、页眉、假标题时使用。
license: MIT
metadata:
  version: "1.1.0"
  author: xuanyuanli
  language: zh-CN
  tags: "pdf, ocr, markdown, conversion"
---

# 文档转 Markdown（anydoc / pdf-inspector）

把原书、论文、扫描件转成可用的 Markdown。核心原则：**先探测再开转，先测速再跑全书，边转边写可续跑。**

## 何时用

- PDF / EPUB / DOCX / PPT 需要变成 `.md`
- 扫描件需要 OCR
- 已经转出来但乱码、页眉混入正文、标题层级错乱，需要清理

**不用**：只需要读几页内容（直接用阅读工具看）；PDF 是表单或图纸（不是文本转换问题）。

## 前置：环境检查

```bash
python scripts/probe.py --check
```

> 下文命令中的相对路径都相对**本技能目录**，执行前先 `cd` 到该目录。

它会检查：`pdf_inspector` 是否可导入、`PDFIUM_LIB_PATH` / `ORT_DYLIB_PATH` 是否已设置且文件存在、`anydoc` 是否在 PATH。

运行时要用的环境变量：

| 变量 | 默认 | 用途 |
|---|---|---|
| `OCR_HOME` | `~/.ocr-runtime` | 共享库与模型的根目录 |
| `PDFIUM_LIB_PATH` | `$OCR_HOME/pdfium/bin/pdfium.dll` | PDFium 动态库 |
| `ORT_DYLIB_PATH` | `$OCR_HOME/ort/lib/onnxruntime.dll` | ONNX Runtime |
| `PYTHONUNBUFFERED` | — | 长任务日志实时输出，建议设为 `1` |

缺库时按上游文档下载：Firecrawl PDFium（`native-v7988`，win-x64 / linux-x64 / mac）与 ONNX Runtime 1.27.0 对应平台包，解压到 `$OCR_HOME`。首次 OCR 会自动下载约 31 MB 的 PP-OCRv6 Small 模型。

> 不要把 OCR 运行时或模型放进笔记库、仓库或任何会被同步的目录。

## 决策树

1. **先试 anydoc**——有文字层的 PDF / docx / epub，速度快、无需 OCR
2. anydoc 报 `no extractable text` / `Scanned` / `OCR is required` → **改用 pdf-inspector OCR**
3. 开转全书前，先 **1–3 页热启动测速**：本机约 ≤3 s/页可接受（330 页 ≈ 15 分钟）。明显更慢再考虑换引擎
4. **不要默认上 RapidOCR / Marker**：CPU 上通常更慢（见性能基线）

## 方案 A：anydoc

```bash
anydoc "path/to/book.pdf" -o "out/书名.md"
anydoc --help          # 可选 -f pdf|docx|epub|...
```

- 有文字层：直接抽文本并转 GFM Markdown
- **不做 OCR**，扫描件失败属预期
- 诊断走 stderr，Markdown 写到 `-o` 或 stdout

## 方案 B：pdf-inspector OCR

### 探测与测速

```bash
# 分类：scanned / text_based / mixed
python scripts/probe.py "book.pdf"

# 指定页测速（页码 1-indexed），并估算全书耗时
python scripts/probe.py "book.pdf" --pages 20,21,22 --time
```

### 全书转换

```bash
python scripts/convert.py "book.pdf" "out/书名.md"
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--start` / `--end` | 全书 | 页码范围（1-indexed，含端点） |
| `--pages` | — | 与 `--start/--end` 等价的单参数写法，如 `--pages 20-50` |
| `--batch` | 10 | 每批页数；机器内存小就降到 5 |
| `--dpi` | 150 | OCR 渲染分辨率；提高会变慢 |
| `--mode` | force | `force` 强制 OCR；`auto` 交给引擎路由 |
| `--overwrite` | 关 | 忽略进度文件，从头转 |
| `--quiet` | 关 | 只输出错误 |

脚本行为：
- 每批转完立即追加写入，进程被杀也不会丢已完成的页
- 进度写在 `<out>.progress.json`，**重复执行同一条命令即自动续跑**
- 中途 Ctrl-C 会保存进度并以 130 退出
- 结束时校验页数覆盖，打印总耗时与字符数

### 长任务

全书转换通常十几分钟到几小时。放在后台跑，把 stdout/stderr 重定向到日志，然后轮询日志尾部，不要阻塞会话：

```bash
python scripts/convert.py book.pdf out.md > convert.log 2>&1 &
```

（Windows PowerShell 用 `Start-Process -RedirectStandardOutput`。）

## 转换后整理

扫描件转出后常见四类问题：封面/版权页乱码、目录页被当正文、页眉页码变成标题、正文被标成 `#`。按顺序处理。

### 1. 删封面垃圾

从丛书序 / 中文序 / 正文序切到真正开篇。ISBN、CIP 数据、版权页、丛书广告整段丢掉。

### 2. 重写目录

原书目录页的 OCR 通常错乱，**不要当正文保留**。按原书结构重写一份干净的 `## 目录` 列表，章节标题以正文里的实际标题为准。

### 3. 先降假标题，再插真标题

1. 剥掉所有误标的 `#`–`######` 前缀，把文本还原成段落
2. 按目录锚点在正文里插入真标题
3. 切章时必须用**正文里**书名/章名那次出现（后面紧跟正文首句），不能用目录页那一行

层级约定（若目标是 Obsidian 读书笔记，另见 `obsidian-reading-notes` 技能）：

| 层级 | 用途 |
|---|---|
| `##` | 丛书序、中文版序言、引言、第×部分、附录 |
| `###` | 章（一、二、三…）、部分结论、附录 A/B/… |
| `####` | 节（少用；只标目录里有的小节） |

### 4. 删页眉页脚

识别并删除单独成行的模式：`第一部分 … 27`、`引 言 3`、`附 录 299`，以及黏在段首的同款前缀。用正则按「书名/部件名 + 空格 + 页码」匹配，比逐条手删可靠。

### 5. 补附录标题

OCR 常把 `C307`、`316E` 这类页眉残余落成残行。按原书目录补 `### A`–`### F`。

### 6. 错字

只改**高置信** OCR 错误（形近字、常见混淆，如 间题→问题、性畜→牲畜）。不做全文校勘；不确定的保留并在交付说明里列出。

### 7. 缺段要补

假标题切断的序言/章首段落，按上下文接上，不要静默丢弃。

### 8. 整理脚本放哪

放临时工作目录（如 `$OCR_HOME`），**不要写进笔记库或业务仓库**。

## 性能基线

本机实测（CPU、无 NVIDIA），仅作参考：

| 引擎 | 热启动约 | 说明 |
|---|---|---|
| anydoc（有文字层） | < 1 s/页 | 首选，无需 OCR |
| pdf-inspector OCR | ~2.6 s/页 | 扫描件首选 |
| RapidOCR onnxruntime | ~22 s/页 | 同机对比过，勿优先 |
| Marker | 未测 | CPU 上通常更慢，不默认 |

## 禁止

- 未测速就对数百页扫描件开重型版面引擎
- 把 OCR 运行时、模型、缓存塞进笔记库或 git 仓库
- 用 anydoc 强转已确认的纯扫描 PDF（只会失败）
- 边转边删正文（先出全书，再整理）
- 把转换脚本和日志留在笔记目录里

## 验收标准

交付前确认：

- [ ] 页数覆盖：输出页数与 PDF 页数一致（允许明确声明跳过封面/空白页）
- [ ] 无残留页眉、页码、CIP 垃圾
- [ ] 标题层级符合目标规范，无 `#` 与 `**` 双重标记
- [ ] 目录与正文标题一致
- [ ] 随机抽 3–5 页与原文比对，无整段缺失
- [ ] 交付说明里列出：使用的引擎、耗时、跳过的页、未修的低置信错字
