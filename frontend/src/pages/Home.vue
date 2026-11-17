<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const d = ref(null)
const err = ref('')
async function load() {
  err.value = ''
  try { d.value = await api.dashboard() } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
<template>
  <div class="panel">
    <div class="grid" v-if="d">
      <div class="stat"><div class="k">业务日</div><div class="v">{{ d.business_day }}</div></div>
      <div class="stat"><div class="k">今日事件</div><div class="v">{{ d.event_count }}</div></div>
      <div class="stat"><div class="k">核销事实</div><div class="v ticket">{{ d.fact_count }}</div></div>
      <div class="stat"><div class="k">待钉 open</div><div class="v">{{ d.open_fact_count }}</div></div>
      <div class="stat"><div class="k">今日核销额</div><div class="v ticket">{{ d.redeem_total_today }}</div></div>
      <div class="stat"><div class="k">待作废（未扫）</div><div class="v">{{ d.pending_expire_count }}</div></div>
      <div class="stat"><div class="k">已作废券码</div><div class="v">{{ d.voided_total }}</div></div>
      <div class="stat"><div class="k">日已钉扎</div><div class="v">{{ d.day_sealed ? '是' : '否' }}</div></div>
    </div>
    <p class="msg" v-if="!err && d">
      票根洋红标出核销侧数字；钉扎后禁止再写入该日核销。到期自动作废：过期未核券由扫描作废并拒核。
      <template v-if="d.last_scan_at">最近扫描：{{ d.last_scan_at }}。</template>
      <template v-else>尚未运行过期扫描。</template>
    </p>
    <p class="msg err" v-if="err">{{ err }}</p>
  </div>
</template>
