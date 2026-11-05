export interface NavItem {
  path: string
  title: string
  icon: string
  group: string
  admin?: boolean
}
export const navigation: NavItem[] = [
  { path: '/dashboard', title: '工作台', icon: 'overview', group: '工作空间' },
  { path: '/skus', title: '商品资料', icon: 'box', group: '工作空间' },
  { path: '/tasks', title: '生成任务', icon: 'layers', group: '工作空间' },
  { path: '/batches', title: '批量任务', icon: 'grid', group: '工作空间' },
  { path: '/assets', title: '素材库', icon: 'image', group: '内容资产' },
  { path: '/copies', title: '文案内容', icon: 'file', group: '内容资产' },
  { path: '/compliance', title: '审核中心', icon: 'shield', group: '内容资产' },
  { path: '/packages', title: '交付中心', icon: 'download', group: '内容资产' },
  { path: '/listings', title: '刊登准备', icon: 'globe', group: '内容资产' },
  {
    path: '/knowledge',
    title: '品牌知识库',
    icon: 'book',
    group: '品牌与管理',
  },
  {
    path: '/providers',
    title: '模型服务',
    icon: 'spark',
    group: '品牌与管理',
    admin: true,
  },
  { path: '/audit', title: '用量与费用', icon: 'chart', group: '品牌与管理' },
  {
    path: '/settings',
    title: '工作空间设置',
    icon: 'settings',
    group: '品牌与管理',
  },
]
