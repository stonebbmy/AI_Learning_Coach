const [maj] = process.versions.node.split('.').map(Number)
// 依赖链含现代语法（如 ||=），Node 14 及更早会直接在加载阶段报错
if (maj < 16) {
  console.error(
    `\n[ai-learning-coach-web] 当前 Node 为 ${process.version}，版本过低。\n` +
      `请安装 Node.js 18 LTS 或 20 LTS：https://nodejs.org/zh-cn\n` +
      `若使用 nvm-windows：在 web 目录执行  nvm install 20  与  nvm use 20（见 .nvmrc）\n`
  )
  process.exit(1)
}
