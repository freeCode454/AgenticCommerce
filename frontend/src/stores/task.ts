import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTaskStore = defineStore('task', () => {
  const currentTask = ref<any>(null)
  const taskList = ref<any[]>([])

  return { currentTask, taskList }
})
