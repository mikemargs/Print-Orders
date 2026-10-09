import { expect, it } from 'vitest'
import { paymentStatus } from './paymentStatus'

it('distinguishes paid, deposit, unpaid, and zero-total orders including older cached records',()=>{
  expect(paymentStatus({paid_in_full:true,total:100,deposit:25,balance:0})).toBe('Paid in full')
  expect(paymentStatus({total:100,deposit:100,balance:0})).toBe('Paid in full')
  expect(paymentStatus({total:100,deposit:25,balance:75})).toBe('Deposit received')
  expect(paymentStatus({total:100,deposit:0,balance:100})).toBe('Unpaid')
  expect(paymentStatus({total:0,deposit:0,balance:0})).toBe('No balance due')
})
