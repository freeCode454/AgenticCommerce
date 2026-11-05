<template>
  <div class="settings-page">
    <div class="page-title-row">
      <div>
        <h1 class="page-title">系统与多租户设置</h1>
        <p class="page-desc">平台基础设施隔离运行参数、审计规范与租户配置</p>
      </div>
    </div>

    <div class="settings-grid">
      <!-- 租户信息 -->
      <div class="card mb-4">
        <h3 class="card-title mb-3">🏢 当前企业租户信息</h3>
        <div class="info-list">
          <div class="info-item">
            <span class="info-k">租户 ID:</span>
            <code class="info-v">tenant_default</code>
          </div>
          <div class="info-item">
            <span class="info-k">企业全称:</span>
            <span class="info-v">环球出海科技有限公司</span>
          </div>
          <div class="info-item">
            <span class="info-k">服务等级 (Plan):</span>
            <span class="badge badge-success">ENTERPRISE (旗舰版)</span>
          </div>
          <div class="info-item">
            <span class="info-k">多租户隔离规范:</span>
            <span class="info-v">全表强制挂载 tenant_id 物理逻辑字段，向量空间隔离</span>
          </div>
        </div>
      </div>

      <!-- 独立 Docker 端口隔离配置 -->
      <div class="card mb-4">
        <h3 class="card-title mb-3">🐳 宿主机 Docker 端口隔离状态</h3>
        <p class="text-sm text-muted mb-3">
          为防止与宿主机现有业务容器发生冲突，本项目使用专属隔离命名空间与非冲突端口：
        </p>
        <div class="ports-table table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>服务组件</th>
                <th>容器命名</th>
                <th>隔离绑定端口</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>PostgreSQL 16 + pgvector</td>
                <td><code>agentic-postgres</code></td>
                <td><strong>5434</strong> (宿主机 5432/5433 已隔离)</td>
                <td><span class="badge badge-success">HEALTHY</span></td>
              </tr>
              <tr>
                <td>Redis 7 缓存与信号量</td>
                <td><code>agentic-redis</code></td>
                <td><strong>6381</strong> (宿主机 6379/6380 已隔离)</td>
                <td><span class="badge badge-success">HEALTHY</span></td>
              </tr>
              <tr>
                <td>MinIO 对象存储 (S3)</td>
                <td><code>agentic-minio</code></td>
                <td><strong>9010 (API) / 9011 (Console)</strong></td>
                <td><span class="badge badge-success">HEALTHY</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 执行审计规范 -->
      <div class="card">
        <h3 class="card-title mb-2">📜 执行日志归档规范 (Execution Logger)</h3>
        <p class="text-sm text-muted">
          严格按照规范执行：所有大模型集成、工作流流转与系统操作均在项目根目录 <code>ailog/</code> 中以 <code>YYYY-MM-DD_HH-mm-ss_任务主题.md</code> 完整备份，100% 具备历史追溯与 Mermaid 架构图还原能力。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.page-title-row { margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 700; }
.page-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 13.5px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.info-k { color: var(--text-muted); }
.info-v { font-weight: 500; }
.mb-4 { margin-bottom: 20px; }
</style>
