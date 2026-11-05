import client from './client'

export const getTasks = (params?: any) => client.get('/tasks', { params })
export const getTaskDetail = (id: string) => client.get(`/tasks/${id}`)
export const createBatch = (data: any) => client.post('/batches', data)
