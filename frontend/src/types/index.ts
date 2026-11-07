export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}
export interface PageData<T> {
  items: T[]
  total?: number
  count?: number
}
export interface UserInfo {
  user_id?: string
  id?: string
  name: string
  email: string
  role: string
  tenant_id: string
  tenant_name?: string
}
export interface Sku {
  id: string
  code: string
  name: string
  category: string
  description?: string
  images?: string[]
  specs?: Record<string, unknown>
  create_time?: string
}
export interface GenerationConfig {
  language: string
  platform: string
  media_type: 'both'
  max_retries: number
}
export interface Task {
  next_poll_at?: string
  execution_id?: string
  error_message?: string
  id: string
  sku_id: string
  sku_name?: string
  sku_code?: string
  batch_id?: string
  status: string
  current_node?: string
  retry_count?: number
  config?: Partial<GenerationConfig>
  create_time?: string
}
export interface Asset {
  id: string
  task_id?: string
  sku_id?: string
  sku_name?: string
  sku_code?: string
  type: string
  sub_type?: string
  url: string
  status?: string
  is_mock?: number
  archive_status?: 'external' | 'pending' | 'retrying' | 'failed' | 'stored'
  archive_error?: string | null
  meta?: Record<string, unknown>
  create_time?: string
}
export interface CopyContent {
  id?: string
  task_id?: string
  sku_id?: string
  sku_name?: string
  sku_code?: string
  language?: string
  title: string
  bullets: string[]
  description?: string
  keywords: string[]
  status?: string
  create_time?: string
}
export interface HumanReview {
  decision: 'pending' | 'approved' | 'rejected'
  reviewer_id?: string | null
  reviewed_at?: string | null
  note?: string | null
}
export interface Report {
  id?: string
  task_id?: string
  sku_name?: string
  sku_code?: string
  score: number
  passed: number
  status?: string
  scope?: 'generation' | 'copy'
  human_review?: HumanReview
  dimensions?: Record<string, number>
  violations?: unknown[]
  suggestions?: string[]
  create_time?: string
}
export interface NodeRun {
  execution_id?: string
  id?: string
  node_name: string
  status: string
  elapsed_ms?: number
  prompt_tokens?: number
  completion_tokens?: number
  cost?: number
  input_data?: unknown
  output_data?: unknown
  create_time?: string
}
export interface TaskDetail {
  review_media_complete?: boolean
  remote_jobs?: {
    id: string
    remote_id?: string
    round: number
    status: string
    remote_status?: string
    model: string
    error_message?: string
    billing_status?: string
    expires_at?: string
  }[]
  task: Task
  copy?: CopyContent | null
  assets: Asset[]
  compliance_report?: Report | null
}
export interface Batch {
  id: string
  name: string
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  config?: Partial<GenerationConfig>
  create_time?: string
}
export interface Provider {
  configuration_status?: string
  runtime_status?: string
  key_status?: string
  is_active?: boolean
  runtime_has_key?: boolean
  adapter?: string
  effective_config?: Record<string, unknown>
  id: string
  type: string
  name: string
  has_key: boolean
  api_key_masked: string
  config?: Record<string, unknown>
  is_default: number
}
export interface KnowledgeDoc {
  id: string
  name: string
  category: string
  doc_type: string
  vector_status: string
  create_time?: string
}
export interface KnowledgeDetail extends KnowledgeDoc {
  chunks: { id: string; index: number; content: string }[]
}
export interface PackageItem {
  task_id: string
  sku_name: string
  sku_code: string
  package_name: string
  create_time?: string
}
export interface DeliveryManifest {
  task_id: string
  sku_id: string
  copywriting: CopyContent
  media_assets: { type: string; sub_type?: string; url: string }[]
  quality_audit: Pick<Report, 'score' | 'passed' | 'suggestions' | 'human_review'>
  download_archive_url: string | null
  download_block_reason?: string | null
}
export interface Listing {
  id: string
  sku_name: string
  sku_code: string
  platform: string
  status: string
  listing_data?: Record<string, unknown>
  create_time?: string
}
export interface CostSummary {
  unreported_video_jobs?: number
  total_runs: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cost_usd: number
}
export interface OperationLog {
  id: string
  user_name?: string
  user_id?: string
  action: string
  target_type?: string
  target_id?: string
  detail?: unknown
  create_time?: string
}
export interface SystemStatus {
  tenant_id: string
  tenant_name: string
  dependencies: Record<string, string>
}
