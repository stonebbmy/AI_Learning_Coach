# AI 私教页（TutorView）视觉与展示优化

## 目标

- 布局与侧栏可扫读（前序方案）：主区放宽、侧栏任务 line-clamp、快捷区收束等。
- **流式/打字机与刷新后展示一致**（本补充）：流式过程中换行、段落与完成后 Markdown 效果尽量对齐，避免出现「一坨不换行、刷新后突然多行」的割裂感。

---

## 一、流式与刷新后不一致：现象与根因

### 现象

- 打字机输出时：内容像**一整段**，`---`、`##`、引号行 `>` 等 Markdown **原样出现**，行距与成稿后差距大。
- **刷新/历史恢复**后：同一条助理消息以 `isStreaming: false` 走 `renderMarkdown()`，会解析标题、加粗、列表并在末尾将 `\n` 转为 `<br>`，**视觉上换行、层级明显多**。

### 代码位置

[`TutorView.vue`](d:\traeProject\AI_Learning_Coach\web\src\views\TutorView.vue) 中助理消息（约 501–510 行）：

- 流式：`escapeForStream(msg.content)` + `v-html`。
- 完成：`renderMarkdown(msg.content)` + `v-html`。

`escapeForStream`（约 368–375 行）仅做 HTML 转义并把 `\n` 换成 `<br>`，**不做** Markdown 解析，故流式阶段会长期看到 `##`、列表符号等，与成稿后不一致属预期；但 **换行若仍不对**，需单独排查。

### 可能根因（按优先级）

1. **换行符未归一**  
   若流里混用 `\r\n` 或单 `\r`，只替换 `\n` 可能留下 `\r`，在部分环境下表现为**异常或「粘成一行」**的显示。  
   修复：在 `escapeForStream`（及可选在 `renderMarkdown` 入参）**开头**将 `\r\n`、`\r` 统一为 `\n`。

2. **`v-html` + 外层 `white-space` 组合**  
   当前 `.bubble` 在流式时带 `streaming` 类，会保留/参与 `white-space` 与内联 `<br>` 的混排；个别浏览器下**内联 `span` + 大量 `br` 的排版**不如「纯文本 + `pre-wrap`」稳定。  
   修复：流式阶段改为**不经过 `v-html` 的转义纯文本**（`{{ msg.content }}` 放在 `div` 上），用 CSS 统一：

   - `white-space: pre-wrap;`
   - `word-break: break-word;`（或 `overflow-wrap: anywhere`）

   使模型发来的 `\n` 原样成段，与「记事本中粘贴」效果一致，避免依赖把 `\n` 改成 `<br>` 的路径。

3. **认知预期**  
   流式阶段**仍不会**把 `**粗体**`、`##` 等渲染成终态样式，除非对流式分片也跑 `renderMarkdown`（有截断/半句 Markdown 风险，可作为二期）。  
   与产品共识：**一期保证「换行/段」一致**；**二期**可评估节流 `renderMarkdown` 或 `markdown-it` 增量等。

### 与「前序视觉优化计划」关系

- 不冲突：本项主要改**助理气泡流式展示分支**与**少量 CSS/工具函数**；侧栏、主区全宽、快捷区仍为独立改动，可同迭代合并验收。

---

## 二、建议实现步骤（流式一致性）

1. 增加 `normalizeLineEndings(s: string): string`：`return s.replace(/\r\n/g, '\n').replace(/\r/g, '\n')`，在 `sendMessage` 的 `onChunk` 里写入 `messages` 前调用，**或**在 `escapeForStream` / 显示层首次读取时调用（去重一次即可）。  
2. 流式助理消息：用「纯文本 + `pre-wrap`」的容器替代 `v-html(escapeForStream)`（`cursor-blink` 可保留在同级行尾）。非流式仍用 `v-html` + `renderMarkdown`。  
3. 在 `.bubble` / `.stream-plain` 上为流式分支单独设 `white-space: pre-wrap; word-break: break-word;`，**避免**与 `renderMarkdown` 的块级 HTML 时冲突（可用双分支类名区分）。  
4. 回归：长回复、多 `\n`、`\r\n` 混合、含 `<` 和 `&` 的内容；流式结束与刷新后/历史同一条在「换行」上对齐；`npm run build`。

---

## 三、前序布局与美观项（保留）

- `App.vue` + `styles.css`：私教路由主区放宽（`main--tutor` 等）。
- 侧栏：任务 `line-clamp`、可滚动、序号/层次。
- 快捷指令：横向滚动或折叠（见前序 to-do）。

---

## 四、验收

- 流式输出过程中中文长文、标题符号、多段之间**能按模型换行拆开阅读**（与刷新后「至少段落换行」一致，不要求流式中已出现粗体/小标题终态）。  
- 无 XSS 回归（纯文本流式用 `{{ }}`，不注入 HTML）。  
- 构建与手动对比：同一条完成前后与历史记录一致（除 Markdown 样式增强仅在完成后出现）。

---

## 待办（合并）

- [x] `main-fullwidth`：主区全宽/放宽
- [x] `sidebar-tasks`：侧栏任务可读性
- [x] `quick-commands`：快捷区收束
- [x] `stream-linebreak`：**换行归一 + 流式用 pre-wrap 纯文本**（本补充）
- [x] `chat-bubble`：气泡 spacing / flex 滚动
