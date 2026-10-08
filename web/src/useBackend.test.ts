import { describe, expect, it } from 'vitest'
import { nextDelay } from './useBackend'

describe('reconnect back-off', () => {
  it('doubles from one second and never waits more than fifteen', () => {
    expect([0, 1, 2, 3, 4].map(nextDelay)).toEqual([1000, 2000, 4000, 8000, 15_000])
    expect(nextDelay(50)).toBe(15_000)
  })
})
