<script setup lang="ts">
import { RouterLink } from 'vue-router'
import LearningModuleShell from '../components/LearningModuleShell.vue'
</script>

<template>
  <LearningModuleShell>
  <div class="guide">
    <div class="view-hero">
      <h1>AI 私教 · 功能简介</h1>
      <p class="lead">
        主入口是<strong>首页私教对话</strong>：用自然语言说明目标即可，系统会识别意图、调度知识库 / RAG / 联网等能力，并以文字流与<strong>结构化卡片</strong>（大纲、计划、测验）呈现。
        本页的「大纲 / 计划 / 进度」用于查看与补充，日常学习以私教为主。
      </p>
    </div>

    <section class="card block">
      <h2>一、意图与说法示例</h2>
      <p class="muted">与后端意图分类一致，你可直接说类似下面的话（也支持输入框上方的快捷按钮）。</p>
      <div class="doc-table-wrap table-wrap">
      <table class="doc-table">
        <thead>
          <tr>
            <th>意图</th>
            <th>适合场景</th>
            <th>示例</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>ONBOARD</td>
            <td>新学一个领域、定目标</td>
            <td>「我想学 Python」「准备三个月入门数据分析」</td>
          </tr>
          <tr>
            <td>PLAN</td>
            <td>今天学什么、排计划</td>
            <td>「今天学什么？」「帮我列本周安排」</td>
          </tr>
          <tr>
            <td>LEARN</td>
            <td>讲概念、技术问答</td>
            <td>「什么是 RAG？」「LangGraph 的 State 怎么用」</td>
          </tr>
          <tr>
            <td>REVIEW</td>
            <td>复习之前内容</td>
            <td>「帮我复习上次的内容」</td>
          </tr>
          <tr>
            <td>PROGRESS</td>
            <td>汇报或查看进度</td>
            <td>「我学完第二章了」「查看我的学习进度」</td>
          </tr>
          <tr>
            <td>QUIZ</td>
            <td>做题测验</td>
            <td>「考考我吧」</td>
          </tr>
          <tr>
            <td>EXPLORE</td>
            <td>扩展话题、比较方案</td>
            <td>「Docker 和 Podman 区别」</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <section class="card block">
      <h2>二、对话里会出现什么</h2>
      <ul>
        <li>
          <strong>流式文字</strong>：私教最终说明与指导（支持完成后渲染的 Markdown 样式）。
        </li>
        <li>
          <strong>意图条</strong>：思考中会显示当前判断的意图类型。
        </li>
        <li>
          <strong>卡片 event: card</strong>
          <ul>
            <li><code>outline</code>：学习大纲。可在卡片上确认；确认后会保存到账户并提示私教续接制定计划（与侧栏「大纲章节」同步）。</li>
            <li><code>plan</code>：今日任务列表，可在卡片里勾选；系统会尽量同步到计划与侧栏。</li>
            <li><code>quiz</code>：测验题，可选做题与查看解释。</li>
          </ul>
        </li>
      </ul>
    </section>

    <section class="card block">
      <h2>三、与知识库、RAG、专家工具的关系</h2>
      <ul>
        <li>
          <RouterLink to="/knowledge">知识库</RouterLink>：上传个人资料后，私教在合适意图下会<strong>检索</strong>你的笔记（<code>search_knowledge</code>）。
        </li>
        <li>
          <RouterLink to="/chat">RAG 问答</RouterLink>：专注「问一句、流式答」的检索增强对话，不带私教总控的意图/卡片。适合长文档精读后追问。
        </li>
        <li>
          <RouterLink to="/agent">Agent</RouterLink>：工具调用/研究向演示，与私教流式是不同入口。
        </li>
        <li>
          私教在部分意图下还会组合联网摘要等能力，具体以回复与日志为准。
        </li>
      </ul>
    </section>

    <section class="card block">
      <h2>四、推荐学习流</h2>
      <ol>
        <li>在私教中表达学习目标 → 需要时出现<strong>大纲卡片</strong>并确认保存。</li>
        <li>在私教或「计划」页拉取<strong>今日计划</strong>，在侧栏或计划页更新任务状态。</li>
        <li>在「进度」页查看历史计划完成率；空数据时先完成「大纲 + 计划」并勾选任务。</li>
      </ol>
      <p>
        独立页
        <RouterLink to="/outline">大纲</RouterLink> 可管理已保存大纲列表、选定当前；与私教用同一账户（<code>X-User-Id</code>）打通。
      </p>
    </section>

    <section class="card block">
      <h2>五、当前能手动做哪些事（设预期）</h2>
      <div class="doc-table-wrap table-wrap">
      <table class="doc-table">
        <thead>
          <tr>
            <th>模块</th>
            <th>可手动/半手动</th>
            <th>本阶段不提供的</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>大纲</td>
            <td>重新生成、确认保存、在「大纲」页从列表里选「当前使用」并同步私教</td>
            <td>在线改已存章节全文（无编辑 API）</td>
          </tr>
          <tr>
            <td>计划</td>
            <td>改「今日目标句」再拉取计划；任务改状态（与侧栏一致）</td>
            <td>在 UI 里改单条任务描述/时间字段</td>
          </tr>
          <tr>
            <td>进度</td>
            <td>只读总览，随任务完成变化</td>
            <td>手改历史统计</td>
          </tr>
          <tr>
            <td>知识库</td>
            <td>上传、分块浏览</td>
            <td>按源删除、改向量块内容</td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <p class="back">
      <RouterLink to="/" class="primary-link">返回 AI 私教</RouterLink>
    </p>
  </div>
  </LearningModuleShell>
</template>

<style scoped>
.guide {
  max-width: 100%;
  width: 100%;
  box-sizing: border-box;
}
.block {
  margin-top: 1rem;
}
.lead {
  line-height: 1.65;
  color: var(--text, #e0e6f7);
}
.muted {
  color: var(--muted, #8899cc);
  font-size: 0.95rem;
}
h2 {
  margin-top: 0;
  font-size: 1.1rem;
}
ul,
ol {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
  line-height: 1.6;
}
ul ul {
  margin-top: 0.35rem;
}
.back {
  margin-top: 1.5rem;
}
.primary-link {
  color: #8ab4f8;
  font-weight: 600;
}
</style>
