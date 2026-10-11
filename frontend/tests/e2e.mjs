// Browser checks against the running dev servers (scripts/dev.py start).
//
//   node frontend/tests/e2e.mjs          Read-only: login and registration screens of both portals at
//                                         320/390/768/1440px, no horizontal overflow, no console errors.
//   E2E_ALLOW_WRITES=yes E2E_DOCTOR_PHONE=… E2E_DOCTOR_PASSWORD=… node frontend/tests/e2e.mjs --full
//                                         Full patient ⇄ doctor workflow. It creates an account and cases,
//                                         so only run it with the services pointed at a disposable database.
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const artifacts = path.join(root, 'artifacts')
const patientUrl = `http://127.0.0.1:${process.env.PATIENT_PORT || 5173}`
const doctorUrl = `http://127.0.0.1:${process.env.DOCTOR_PORT || 5174}`
const full = process.argv.includes('--full')
await fs.mkdir(artifacts, { recursive: true })

if (full && process.env.E2E_ALLOW_WRITES !== 'yes') {
  console.error('--full writes test data. Point the services at a disposable database and set E2E_ALLOW_WRITES=yes.')
  process.exit(1)
}

const installedChrome = await fs.access('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').then(() => true, () => false)
const browser = await chromium.launch({
  headless: true,
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : installedChrome ? { channel: 'chrome' } : {}),
})
const errors = []

function watch(page, who) {
  page.on('pageerror', error => errors.push(`${who}: ${error.message}`))
  page.on('console', message => {
    // 4xx responses from deliberate validation checks are expected in the full flow.
    if (message.type() === 'error' && !/status of 4\d\d/.test(message.text())) errors.push(`${who}: ${message.text()}`)
  })
}

async function check(page, name, width) {
  await page.setViewportSize({ width, height: width <= 720 ? 844 : 900 })
  await page.waitForTimeout(300)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Horizontal overflow: ${name} at ${width}px`)
  await page.screenshot({ path: path.join(artifacts, `${name}-${width}.png`), fullPage: true })
}

function nationalId(body) {
  const weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
  return body + '10X98765432'[[...body].reduce((sum, digit, i) => sum + Number(digit) * weights[i], 0) % 11]
}

async function login(page, url, phone, password) {
  await page.goto(url)
  await page.getByLabel('手机号码').fill(phone)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
}

try {
  for (const [portal, url] of [['patient', patientUrl], ['doctor', doctorUrl]]) {
    const page = await browser.newPage()
    watch(page, portal)
    await page.goto(url)
    await page.getByRole('heading', { name: portal === 'doctor' ? '医生登录' : '登录', exact: true }).waitFor()
    for (const width of [320, 390, 768, 1440]) await check(page, `${portal}-login`, width)
    if (portal === 'patient') {
      await page.getByRole('button', { name: '创建账号' }).click()
      await page.getByRole('button', { name: '注册并继续' }).waitFor()
      await check(page, 'patient-register', 390)
    } else {
      assert.equal(await page.getByRole('button', { name: '创建账号' }).count(), 0, 'Doctors cannot self-register')
    }
    await page.close()
  }

  if (full) {
    const phone = '138' + String(Math.floor(Math.random() * 1e8)).padStart(8, '0')
    const patient = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
    const doctor = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
    watch(patient, 'patient')
    watch(doctor, 'doctor')
    await login(doctor, doctorUrl, process.env.E2E_DOCTOR_PHONE, process.env.E2E_DOCTOR_PASSWORD)
    await doctor.getByRole('heading', { name: '接诊队列' }).waitFor()
    const doctorName = await doctor.locator('.side-account-text strong').textContent()

    await patient.goto(patientUrl)
    await patient.getByRole('button', { name: '创建账号' }).click()
    await patient.getByLabel('姓名').fill('测试患者')
    await patient.getByLabel('手机号码').fill(phone)
    await patient.getByLabel('密码', { exact: true }).fill('Patient123')
    await patient.getByRole('button', { name: '注册并继续' }).click()
    await patient.getByRole('heading', { name: '完善健康档案' }).waitFor()
    await patient.getByLabel('身份证号').fill(nationalId('11010119960506124'))
    await patient.getByLabel('过敏史').fill('青霉素')
    await patient.getByLabel('当前用药').fill('无')
    await patient.getByRole('button', { name: '保存健康档案' }).click()
    await patient.locator('.home-head').waitFor()

    await patient.goto(`${patientUrl}/cases/new`)
    await patient.getByLabel('一句话概括').fill('咳嗽三天伴咽痛（测试）')
    await patient.getByLabel('详细描述').fill('三天前开始咳嗽，夜间明显，咽喉痛，没有发烧，无胸痛。这是自动化测试数据。')
    await patient.getByRole('button', { name: '下一步：预问诊' }).click()
    await patient.locator('.alert-calm').waitFor()
    await patient.getByRole('button', { name: '下一步：选择医生' }).click()
    await patient.locator('.doctor-option', { hasText: doctorName }).click()
    await patient.getByRole('button', { name: '下一步：确认提交' }).click()
    await patient.locator('.consents .check').first().click()
    await patient.getByRole('button', { name: /^提交给/ }).click()
    await patient.locator('.case-head h1').waitFor()
    const caseUrl = patient.url()
    await check(patient, 'flow-patient-pending', 390)

    await doctor.goto(doctorUrl + new URL(caseUrl).pathname)
    await doctor.getByRole('button', { name: '接诊' }).first().click()
    await doctor.getByRole('button', { name: '请患者补充' }).click()
    await doctor.getByLabel('需要补充什么').fill('请说明夜间最多咳醒几次。')
    await doctor.getByRole('button', { name: '发送请求' }).click()
    await doctor.locator('.case-head-meta', { hasText: '待补充资料' }).waitFor()

    await patient.reload()
    await patient.getByLabel('补充说明').fill('昨晚咳醒了两次。')
    await patient.getByRole('button', { name: '提交补充资料' }).click()
    await patient.locator('.case-head-meta', { hasText: '评估中' }).waitFor()

    await doctor.reload()
    const fields = doctor.locator('.editor textarea')
    for (const [index, text] of ['考虑急性上呼吸道感染（测试）', '咳嗽三天，无发热', '多饮水，注意休息', '如出现气促请及时就医'].entries()) await fields.nth(index).fill(text)
    await doctor.getByRole('radio', { name: '暂不需要线下就诊' }).click()
    await doctor.getByRole('radio', { name: '7 天' }).click()
    await doctor.getByRole('button', { name: '审核并发布' }).click()
    await doctor.getByLabel('我已逐项核对报告内容，并对发布的结论负责').check()
    await doctor.getByRole('button', { name: '发布报告' }).click()
    await doctor.locator('.case-head-meta', { hasText: '已完成' }).waitFor()
    await check(doctor, 'flow-doctor-completed', 1440)

    await patient.reload()
    await patient.locator('.paper .seal').waitFor()
    await patient.getByRole('radio', { name: '5 星，非常满意' }).click()
    await patient.getByRole('button', { name: '提交评价' }).click()
    await patient.locator('.after-card', { hasText: '你的评价' }).waitFor()
    await check(patient, 'flow-patient-report', 390)
  }

  assert.deepEqual(errors, [])
  console.log(`PASS: ${full ? 'full patient ⇄ doctor workflow and ' : ''}login/registration layouts at 320–1440px without overflow or console errors`)
} finally {
  await browser.close()
}
