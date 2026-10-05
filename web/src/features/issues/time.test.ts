import { expect, it } from 'vitest'
import { wallTimeCandidates, storeDate } from './time'
it('uses store date across UTC midnight',()=>expect(storeDate('America/New_York',new Date('2026-10-05T01:00:00Z'))).toBe('2026-10-04'))
it('rejects daylight-saving gaps and provides both repeated times',()=>{
 expect(wallTimeCandidates('2026-03-08T02:30','America/New_York')).toEqual([])
 expect(wallTimeCandidates('2026-11-01T01:30','America/New_York')).toEqual(['2026-11-01T05:30:00.000Z','2026-11-01T06:30:00.000Z'])
 expect(wallTimeCandidates('2026-10-05T10:00','America/New_York')).toEqual(['2026-10-05T14:00:00.000Z'])
})
