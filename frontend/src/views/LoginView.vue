<template>
  <div class="login-container">
    <n-card class="login-card" title="FlameCheck" size="large">
      <n-tabs v-model:value="tab" type="segment">
        <n-tab-pane name="password" tab="Password">
          <n-form ref="formRef" :model="form" :rules="rules" label-placement="left">
            <n-form-item label="Username" path="username">
              <n-input v-model:value="form.username" placeholder="Enter username" />
            </n-form-item>
            <n-form-item label="Password" path="password">
              <n-input v-model:value="form.password" type="password" placeholder="Enter password" />
            </n-form-item>
            <n-button type="primary" block :loading="loading" @click="handleLogin">
              Sign In
            </n-button>
          </n-form>
        </n-tab-pane>
        <n-tab-pane name="barcode" tab="Barcode">
          <div class="barcode-scan">
            <div id="barcode-reader" class="reader"></div>
            <p class="hint">
              Point your camera at a barcode, or type it below.
            </p>
            <n-input-group>
              <n-input v-model:value="manualBarcode" placeholder="FC-…" />
              <n-button type="primary" :loading="loading" @click="handleManualScan">
                Scan
              </n-button>
            </n-input-group>
          </div>
        </n-tab-pane>
      </n-tabs>
      <n-alert v-if="error" type="error" style="margin-top: 12px">{{ error }}</n-alert>
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  NCard, NTabs, NTabPane, NForm, NFormItem, NInput, NInputGroup,
  NButton, NAlert,
} from 'naive-ui'
import { BrowserMultiFormatReader } from '@zxing/browser'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('password')
const loading = ref(false)
const error = ref('')

const form = ref({ username: '', password: '' })
const rules = {
  username: { required: true, message: 'Username is required', trigger: 'blur' },
  password: { required: true, message: 'Password is required', trigger: 'blur' },
}
const formRef = ref(null)

const manualBarcode = ref('')
let codeReader = null

async function handleLogin() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleManualScan() {
  if (!manualBarcode.value) return
  loading.value = true
  error.value = ''
  try {
    await auth.scanBarcode(manualBarcode.value.trim())
    router.push('/')
  } catch (e) {
    error.value = 'Invalid or inactive barcode.'
  } finally {
    loading.value = false
  }
}

function handleDecode(text) {
  handleManualScan()
}

onMounted(() => {
  if (tab.value === 'barcode') {
    startReader()
  }
})

function startReader() {
  const devices = BrowserMultiFormatReader.listVideoInputDevices()
  if (devices.length === 0) return
  codeReader = new BrowserMultiFormatReader()
  codeReader
    .decodeFromVideoDevice(undefined, 'barcode-reader', handleDecode)
    .catch(() => {})
}

onBeforeUnmount(() => {
  if (codeReader) codeReader.reset()
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 420px;
  border-radius: 12px;
}
.barcode-scan {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.reader {
  width: 100%;
  height: 200px;
  border-radius: 8px;
  overflow: hidden;
}
.hint {
  font-size: 13px;
  color: #888;
}
</style>
