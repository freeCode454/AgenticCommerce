import client from './client'

export const getTaskNodeRuns = (taskId: string) => client.get(`/tasks/${taskId}/nodes`)
export const getTaskCompliance = (taskId: string) => client.get(`/tasks/${taskId}/compliance`)
