<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/api/client'
import type { CommunityOut } from '@/api/types'
import LiaisonBubble from '@/components/LiaisonBubble.vue'
import LiaisonComposer from '@/components/LiaisonComposer.vue'
import PageCrumb from '@/components/PageCrumb.vue'
import { useAuthStore } from '@/stores/auth'

type CommunityMsg = { id: number; sender_name: string; body: string; mine: boolean }

const auth = useAuthStore()
const communities = ref<CommunityOut[]>([])
const talk = ref<CommunityMsg[]>([])
const communityId = ref(0)
const error = ref('')

const crumbs = [{ label: '导师工作台', to: '/mentor' }, { label: '社区对话' }]

const mine = computed(() => communities.value)

const currentName = computed(() => mine.value.find((item) => item.id === communityId.value)?.name || '社区')

async function loadTalk() {
  const me = auth.user?.id
  if (!communityId.value || !me) {
    talk.value = []
    return
  }
  const { data } = await api.get<CommunityMsg[]>('/liaison/thread', {
    params: { community_id: communityId.value, channel: 'mentor', peer_user_id: me },
  })
  talk.value = data
}

async function send(body: string) {
  const me = auth.user?.id
  if (!communityId.value || !me || !body.trim()) return
  await api.post('/liaison', {
    community_id: communityId.value,
    channel: 'mentor',
    peer_user_id: me,
    body,
  })
  await loadTalk()
}

async function load() {
  error.value = ''
  try {
    if (!auth.user) await auth.fetchMe()
    const { data } = await api.get<CommunityOut[]>('/communities/mine')
    communities.value = data
    communityId.value = mine.value[0]?.id || 0
    await loadTalk()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

watch(communityId, () => {
  void loadTalk()
})

onMounted(load)
</script>

<template>
  <div class="page">
    <PageCrumb :items="crumbs" />
    <header>
      <div>
        <h1>和社区对话</h1>
        <p>只和社区管理员说话，不会出现在学生的开发记录里。</p>
      </div>
      <label v-if="mine.length > 1">
        社区
        <select v-model.number="communityId">
          <option v-for="item in mine" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </label>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <section v-else-if="!mine.length" class="sheet">
      <p class="muted">尚未绑定社区。请用社区邀请码完成导师注册后再来对话。</p>
      <RouterLink class="back" to="/mentor">返回导师工作台</RouterLink>
    </section>
    <section v-else class="sheet">
      <h2>{{ currentName }}</h2>
      <p v-if="!talk.length" class="muted">社区还没有单独找你。有事可以直接写在下面。</p>
      <LiaisonBubble v-for="m in talk" :key="m.id" :body="m.body" :mine="m.mine" :name="m.sender_name" />
      <LiaisonComposer placeholder="写给社区管理员" send-label="发送" @send="send" />
      <RouterLink class="back" to="/mentor">返回导师工作台</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.page { max-width: 720px; margin: 0 auto; padding: 16px 20px 48px; }
header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
}
h1 { margin: 0; font-size: 1.35rem; }
header p { margin: 6px 0 0; color: #8c8c8c; font-size: 0.9rem; }
label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
  color: #595959;
}
select {
  font: inherit;
  padding: 8px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  min-width: 180px;
}
.sheet {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sheet h2 { margin: 0; font-size: 1.1rem; }
.muted { margin: 0; color: #8c8c8c; }
.error { color: #cf1322; }
.back {
  margin-top: 8px;
  align-self: flex-start;
  color: #1677ff;
  text-decoration: none;
  font-size: 0.9rem;
}
</style>
