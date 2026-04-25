<template>
  <div class="learning-module-shell">
    <div class="learning-module-main scroll-y">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.learning-module-shell {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
}
.learning-module-main {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}
</style>
