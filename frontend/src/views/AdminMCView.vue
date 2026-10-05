<template>
  <n-space vertical size="large">
    <n-card size="small" :bordered="false">
      <div class="page-head">
        <h2 class="page-title">Multiple Choice</h2>
        <n-select
          v-model:value="courseId"
          :options="courseOptions"
          placeholder="Select a course"
          style="width: 320px"
        />
      </div>
      <n-empty v-if="!courseId" description="Select a course to manage its questions, cards and sheets." />
      <template v-else>
        <n-text depth="3" class="hint">
          Define questions, group them into cards (max 3 questions each), and present
          time-windowed sheets to students. The same editor is available per course under
          Courses → Multiple Choice.
        </n-text>
        <MCDesigner :course-id="courseId" />
      </template>
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'
import { NSpace, NCard, NSelect, NEmpty, NText } from 'naive-ui'
import MCDesigner from '../components/MCDesigner.vue'

const message = ref('')
const msgType = ref('success')
const courseId = ref(null)
const courses = ref([])

const courseOptions = () => courses.value.map((c) => ({ label: c.name, value: c.id }))

async function loadCourses() {
  courses.value = await api.get('/admin/courses')
}

function flash(msg, type) {
  message.value = msg
  msgType.value = type
}

onMounted(async () => {
  try {
    await loadCourses()
    if (courses.value.length === 1) courseId.value = courses.value[0].id
  } catch (e) {
    flash(e.message, 'error')
  }
})
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--fc-space-sm); }
.page-title { font-size: var(--fc-fs-md); font-weight: 700; color: var(--fc-ink); }
.hint { font-size: var(--fc-fs-sm); }
</style>
