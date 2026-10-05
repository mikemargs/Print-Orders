function parts(date:Date,timezone:string){return Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date).map(x=>[x.type,x.value]))}
export function storeDate(timezone:string,now=new Date()){const p=parts(now,timezone);return `${p.year}-${p.month}-${p.day}`}
export function storeWallTime(timezone:string,now=new Date()){const p=parts(now,timezone);return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`}
export function wallTimeCandidates(wall:string,timezone:string){
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(wall))return []
 const base=Date.parse(`${wall}:00Z`);if(!Number.isFinite(base))return []
 const candidates:string[]=[]
 for(let offset=-14*60;offset<=14*60;offset+=15){const date=new Date(base-offset*60_000);if(storeWallTime(timezone,date)===wall)candidates.push(date.toISOString())}
 return candidates.sort()
}
export function displayTime(instant:string,timezone:string){return new Intl.DateTimeFormat('en-US',{timeZone:timezone,dateStyle:'medium',timeStyle:'short'}).format(new Date(instant))}
export function overdue(issue:{status:string;follow_up_date:string|null;store:{timezone:string}|null}){return issue.status!=='Resolved'&&!!issue.follow_up_date&&issue.follow_up_date<storeDate(issue.store?.timezone||'America/New_York')}
