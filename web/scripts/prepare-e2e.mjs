import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const path = fileURLToPath(new URL('../e2e/app.spec.ts', import.meta.url))
const source = readFileSync(path, 'utf8')
const ambiguous = "getByLabel('Customer').selectOption"
const exact = "getByLabel('Customer', { exact: true }).selectOption"

if (source.includes(exact)) process.exit(0)
if (!source.includes(ambiguous)) throw new Error('Expected Customer selector was not found')
writeFileSync(path, source.replace(ambiguous, exact))
