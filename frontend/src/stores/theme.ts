import { ref, watch } from 'vue'

const THEME_KEY = 'ops_theme'

function initialDark(): boolean {
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'dark') return true
  if (saved === 'light') return false
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
}

const isDark = ref(initialDark())

function applyTheme(dark: boolean) {
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
}

watch(
  isDark,
  (val) => {
    applyTheme(val)
  },
  { immediate: true },
)

export function useThemeStore() {
  function toggleTheme() {
    isDark.value = !isDark.value
  }

  function setDark(val: boolean) {
    isDark.value = val
  }

  return { isDark, toggleTheme, setDark }
}

export const globalSearch = ref('')
