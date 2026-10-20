export function allowRealPreviewRequest(remote:string|undefined,host:string|undefined,origin:string|undefined) {
  return ['127.0.0.1','::1','::ffff:127.0.0.1'].includes(remote||'')
    && /^(?:127\.0\.0\.1|localhost)(?::\d+)?$/.test(host||'')
    && (!origin || origin===`http://${host}`)
}
