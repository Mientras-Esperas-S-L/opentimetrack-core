import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default [
  // `e2e-report` y `test-results` los escribe Playwright, y dentro va su propia
  // interfaz empaquetada y minificada: 739 errores que no son de nadie. En la CI
  // no se notaba ---checkout limpio, no existen--- así que `npm run lint` solo
  // se rompía en local, y justo para quien acababa de correr las pruebas.
  { ignores: ['dist', 'node_modules', 'e2e-report', 'test-results'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  {
    // Las pruebas de interfaz y su configuración corren en Node, no en el
    // navegador: sin esto, `process` es una variable no declarada.
    files: ['e2e/**/*.js', 'playwright.config.js'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
]
