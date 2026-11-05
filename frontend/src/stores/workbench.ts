import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWorkbenchStore = defineStore('workbench', () => {
  const activeNode = ref<string>('orchestrator')
  const nodeStates = ref<Record<string, any>>({})
  const logs = ref<any[]>([])

  function updateNode(nodeName: string, data: any) {
    nodeStates.value[nodeName] = { ...nodeStates.value[nodeName], ...data }
  }

  return { activeNode, nodeStates, logs, updateNode }
})
