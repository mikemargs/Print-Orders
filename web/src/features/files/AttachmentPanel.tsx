import { useCallback, useEffect, useRef, useState } from 'react'
import Uppy from '@uppy/core'
import Tus from '@uppy/tus'
import { apiFetch } from '../../api/http'
import type { Attachment } from '../../api/types'
import { useOnline } from '../../offline/OnlineState'

type Authorization={attachment:Attachment;object_key:string;tus_endpoint:string;token:string;bucket:string;publishable_key:string;chunk_size:number}

export function AttachmentPanel({orderId}:{orderId:string}){
  const {online}=useOnline(); const [files,setFiles]=useState<Attachment[]>([]); const [progress,setProgress]=useState(''); const [error,setError]=useState(''); const input=useRef<HTMLInputElement>(null)
  const refresh=useCallback(()=>apiFetch<{files:Attachment[]}>(`/api/orders/${orderId}/files`).then(x=>setFiles(x.files)),[orderId])
  useEffect(()=>{if(online)void refresh()},[online,refresh])
  async function upload(file:File){if(!online)return;setError('');setProgress('Authorizing…');const uppy=new Uppy({autoProceed:false});try{
    const auth=await apiFetch<Authorization>(`/api/orders/${orderId}/files/upload-authorizations`,{method:'POST',body:JSON.stringify({filename:file.name,mime_type:file.type||'application/octet-stream',size_bytes:file.size})})
    uppy.use(Tus,{endpoint:auth.tus_endpoint,chunkSize:auth.chunk_size,uploadDataDuringCreation:true,removeFingerprintOnSuccess:true,retryDelays:[0,3000,5000,10000,20000],headers:{apikey:auth.publishable_key,'x-signature':auth.token},allowedMetaFields:['bucketName','objectName','contentType']})
    uppy.addFile({name:file.name,type:file.type,data:file,meta:{bucketName:auth.bucket,objectName:auth.object_key,contentType:file.type||'application/octet-stream'}})
    uppy.on('upload-progress',(_file,p)=>setProgress(`${Math.round(((p.bytesUploaded??0)/(p.bytesTotal||1))*100)}% uploaded`))
    const result=await uppy.upload(); if(!result)throw new Error('Upload did not start'); if(result.failed?.length)throw result.failed[0].error??new Error('Upload failed')
    await apiFetch(`/api/orders/${orderId}/files/finalize`,{method:'POST',body:JSON.stringify({attachment_id:auth.attachment.id})});setProgress('Upload complete');await refresh()
  }catch(e){setError(e instanceof Error?e.message:'Upload failed');setProgress('')}finally{uppy.destroy()}}
  if(!online)return <div className="panel"><h2>Artwork & files</h2><p className="muted">Artwork is not cached offline. Reconnect to upload, download, or delete files.</p></div>
  return <div className="panel"><div className="section-heading"><h2>Artwork & files</h2><><input ref={input} hidden type="file" onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);e.currentTarget.value=''}}/><button type="button" className="secondary" onClick={()=>input.current?.click()}>Upload artwork</button></></div>{progress&&<p>{progress}</p>}{error&&<p className="error">{error}</p>}<div className="attachment-list">{files.map(f=><div key={f.id}><span><strong>{f.original_filename}</strong><small>{(f.size_bytes/1024/1024).toFixed(1)} MB</small></span><span><button type="button" className="link-button" onClick={async()=>{const d=await apiFetch<{url:string}>(`/api/orders/${orderId}/files/${f.id}/download`);window.open(d.url,'_blank','noopener')}}>Download</button><button type="button" className="danger-link" onClick={async()=>{await apiFetch(`/api/orders/${orderId}/files/${f.id}`,{method:'DELETE'});await refresh()}}>Delete</button></span></div>)}</div>{!files.length&&!progress&&<p className="muted">No artwork attached.</p>}</div>
}
