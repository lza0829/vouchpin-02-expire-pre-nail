<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const scans = ref([])
const voids = ref([])
const recon = ref(null)
const msg = ref('')
const err = ref('')
const busy = ref(false)

const pending = computed(() => {
  const c = recon.value?.checks?.find((x) => x.key === 'unredeemed_expired')
  return c ? c.count : 0
})

async function load() {
  err.value = ''
  try {
    const [s, v, r] = await Promise.all([api.expireScans(), api.expireVoids(), api.expireReconcile()])
    scans.value = s
    voids.value = v
    recon.value = r
  } catch (e) { err.value = e.message }
}
async function scan() {
  msg.value = ''; err.value = ''; busy.value = true
  try {
    const r = await api.expireScan({ note: 'manual' })
    msg.value = `扫描 #${r.scan_id} 完成：检查 ${r.scanned_issues} 张发放，过期 ${r.expired_count}，新作废 ${r.voided_count}（已核销跳过 ${r.redeemed_skip}，已作废 ${r.already_void}）`
    await load()
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
onMounted(load)
</script>
<template>
  <div class="panel">
    <div class="grid">
      <div class="stat"><div class="k">待作废（过期未核未扫）</div><div class="v ticket">{{ pending }}</div></div>
      <div class="stat"><div class="k">已作废券码</div><div class="v">{{ voids.length }}</div></div>
      <div class="stat"><div class="k">扫描次数</div><div class="v">{{ scans.length }}</div></div>
      <div class="stat"><div class="k">核对结论</div><div class="v">{{ recon ? (recon.ok ? '全清' : '有差异') : '—' }}</div></div>
    </div>
    <div class="row">
      <button type="button" @click="scan" :disabled="busy">运行过期扫描</button>
      <button type="button" class="ghost" @click="load">刷新</button>
    </div>
    <p class="msg">策略：到期自动作废。过期未核券由扫描写 void 事件并标记作废，核销闸即时拒核；钉扎前会自动再扫一次。</p>
    <p class="msg" v-if="msg">{{ msg }}</p>
    <p class="msg err" v-if="err">{{ err }}</p>
  </div>

  <div class="panel" v-if="recon">
    <h3>核对（两场景 + 防撕裂）</h3>
    <table>
      <thead><tr><th>核对</th><th>规则</th><th>结论</th><th>差异数</th></tr></thead>
      <tbody>
        <tr v-for="c in recon.checks" :key="c.key">
          <td>{{ c.title }}</td>
          <td>{{ c.rule }}</td>
          <td><span class="tag" :class="c.ok ? 'ok' : 'bad'">{{ c.ok ? '清' : '差异' }}</span></td>
          <td>{{ c.count }}</td>
        </tr>
      </tbody>
    </table>
    <template v-for="c in recon.checks" :key="c.key + '-items'">
      <table v-if="c.items.length" class="sub">
        <thead><tr><th colspan="5">{{ c.title }} · 差异明细</th></tr></thead>
        <tbody>
          <tr v-for="(it, i) in c.items" :key="i">
            <td>{{ it.coupon_code }}</td>
            <td>{{ it.campaign_code }}</td>
            <td>{{ it.issued_at || it.redeemed_at || it.business_day }}</td>
            <td>{{ it.expired_at || it.voided_at || '' }}</td>
            <td>{{ it.status || (it.voided ? '已作废' : '') }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>

  <div class="panel">
    <h3>作废券码（coupon_voids 落库）</h3>
    <table>
      <thead><tr><th>券码</th><th>活动</th><th>发放</th><th>过期时刻</th><th>作废时刻</th><th>来源</th><th>扫描#</th></tr></thead>
      <tbody>
        <tr v-for="v in voids" :key="v.coupon_code">
          <td>{{ v.coupon_code }}</td>
          <td>{{ v.campaign_code }}</td>
          <td>{{ v.issued_at }}</td>
          <td>{{ v.expired_at }}</td>
          <td>{{ v.voided_at }}</td>
          <td><span class="tag" :class="v.source === 'scan' ? 'warn' : ''">{{ v.source }}</span></td>
          <td>{{ v.scan_id ?? '—' }}</td>
        </tr>
        <tr v-if="!voids.length"><td colspan="7">暂无作废券码</td></tr>
      </tbody>
    </table>
  </div>

  <div class="panel">
    <h3>扫描运行（expire_scans 落库）</h3>
    <table>
      <thead><tr><th>#</th><th>运行时刻</th><th>业务日</th><th>检查发放</th><th>过期</th><th>新作废</th><th>已核销跳过</th><th>已作废</th><th>备注</th></tr></thead>
      <tbody>
        <tr v-for="s in scans" :key="s.id">
          <td>{{ s.id }}</td>
          <td>{{ s.ran_at }}</td>
          <td>{{ s.business_day }}</td>
          <td>{{ s.scanned_issues }}</td>
          <td>{{ s.expired_count }}</td>
          <td>{{ s.voided_count }}</td>
          <td>{{ s.redeemed_skip }}</td>
          <td>{{ s.already_void }}</td>
          <td>{{ s.note }}</td>
        </tr>
        <tr v-if="!scans.length"><td colspan="9">尚未运行过扫描</td></tr>
      </tbody>
    </table>
  </div>
</template>
