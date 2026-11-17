<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const preview = ref(null)
const msg = ref('')
const err = ref('')

async function load() {
  err.value = ''
  try { preview.value = await api.preview() } catch (e) { err.value = e.message }
}
async function seal() {
  msg.value = ''; err.value = ''
  try {
    const r = await api.seal({})
    msg.value = `已钉扎批次 #${r.batch_id} · ${r.fact_count} 笔 · 合计 ${r.total_amount}`
      + ` · 钉前扫描 #${r.scan_id} 新作废 ${r.scan_voided}（作废总计 ${r.voided_at_seal}）`
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
<template>
  <div class="panel" v-if="preview">
    <div class="grid">
      <div class="stat"><div class="k">业务日</div><div class="v">{{ preview.business_day }}</div></div>
      <div class="stat"><div class="k">待钉笔数</div><div class="v ticket">{{ preview.open_count }}</div></div>
      <div class="stat"><div class="k">待钉合计</div><div class="v ticket">{{ preview.open_total }}</div></div>
      <div class="stat"><div class="k">待作废（未扫）</div><div class="v">{{ preview.pending_expire_count }}</div></div>
      <div class="stat"><div class="k">已作废券码</div><div class="v">{{ preview.voided_total }}</div></div>
      <div class="stat"><div class="k">已钉扎</div><div class="v">{{ preview.already_sealed ? '是' : '否' }}</div></div>
    </div>
    <div class="row">
      <button type="button" @click="seal" :disabled="preview.already_sealed || preview.open_count===0">钉扎本日核销</button>
      <button type="button" class="ghost" @click="load">刷新预览</button>
    </div>
    <p class="msg">open 集合已排除作废券码；钉扎时会在同一事务内先跑过期扫描再钉扎。</p>
    <p class="msg err" v-if="preview.pending_expire_count">
      有 {{ preview.pending_expire_count }} 张过期未核券尚未作废，钉扎将自动扫描作废。
    </p>
    <p class="msg" v-if="msg">{{ msg }}</p>
    <p class="msg err" v-if="err">{{ err }}</p>
  </div>
  <div class="panel">
    <table>
      <thead><tr><th>事实ID</th><th>券码</th><th>活动</th><th>金额</th><th>状态</th></tr></thead>
      <tbody>
        <tr v-for="f in (preview?.facts || [])" :key="f.id">
          <td>{{ f.id }}</td>
          <td>{{ f.coupon_code }}</td>
          <td>{{ f.campaign_code }}</td>
          <td>{{ f.amount }}</td>
          <td><span class="tag warn">{{ f.status }}</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
