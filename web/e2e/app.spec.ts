import { expect, test, type Page } from '@playwright/test'

async function signIn(page: Page) {
  await page.goto('/')
  await page.getByLabel('Company code').fill('TEST-PRINT')
  await page.getByLabel('Company password').fill('company-password')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel('Employee').selectOption({ label: 'Test Admin' })
  await page.getByLabel('PIN').fill('246810')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
}

test('online workflow remains readable after an offline reload', async ({ page, context }) => {
  await signIn(page)

  await page.getByRole('link', { name: 'Customers' }).click()
  await page.getByRole('link', { name: 'New customer' }).click()
  await page.getByLabel('Company').fill('Playwright Customer')
  await page.getByLabel('First name').fill('Pat')
  await page.getByLabel('Last name').fill('Tester')
  await page.getByRole('button', { name: 'Save customer' }).click()
  await page.waitForURL(url => url.pathname.startsWith('/customers/') && !url.pathname.endsWith('/new'))
  const customerId = page.url().split('/').pop()!

  await page.getByRole('link', { name: 'Work Orders' }).click()
  const customerListResponse = page.waitForResponse(response => response.url().includes('/api/customers?limit=200') && response.request().method() === 'GET')
  await page.getByRole('link', { name: 'New work order' }).click()
  const customerResponse = await customerListResponse
  expect(customerResponse.ok()).toBeTruthy()
  const customerPayload = await customerResponse.json() as { customers: Array<{ id: string }> }
  expect(customerPayload.customers.map(customer => customer.id)).toContain(customerId)
  const customerSelect = page.getByLabel('Customer', { exact: true })
  expect(await customerSelect.evaluate(element => element.tagName)).toBe('SELECT')
  const optionValues = await customerSelect.locator('option').evaluateAll(options => options.map(option => (option as HTMLOptionElement).value))
  expect(optionValues).toContain(customerId)
  await customerSelect.selectOption(customerId)
  await page.getByLabel('Description').fill('Offline acceptance order')
  await page.getByPlaceholder('Item / service').fill('Yard Sign')
  await page.getByLabel('Unit price').fill('25')
  await page.getByRole('button', { name: 'Save work order' }).click()
  await page.waitForURL(url => url.pathname.startsWith('/orders/') && !url.pathname.endsWith('/new'))

  await page.getByRole('link', { name: 'Work Orders' }).click()
  await expect(page.getByText('Offline acceptance order')).toBeVisible()
  await page.evaluate(async () => { await navigator.serviceWorker.ready; return true })

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByText(/Offline read-only mode/)).toBeVisible()
  await expect(page.getByText('Offline acceptance order')).toBeVisible()
  await expect(page.getByRole('link', { name: 'New work order' })).toHaveCount(0)
})

test('phone viewport keeps primary navigation usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page)
  await expect(page.getByRole('link', { name: 'Work Orders' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Customers' })).toBeVisible()
})

test('offline sign-out stays signed out when connectivity returns', async ({ page, context }) => {
  await signIn(page)
  await page.evaluate(async () => { await navigator.serviceWorker.ready; return true })

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByText(/Offline read-only mode/)).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Print Order Manager' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toHaveCount(0)

  await context.setOffline(false)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Print Order Manager' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toHaveCount(0)
})
