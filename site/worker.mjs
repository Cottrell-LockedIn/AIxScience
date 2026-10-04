/** Same-origin Sites gateway. Browser credentials never reach the analysis service. */
export function createWorker(assets, fetchBackend = fetch) {
  return {
    async fetch(request, env) {
      const url = new URL(request.url)
      if (url.pathname.startsWith('/api/')) {
        if (!['GET', 'HEAD', 'POST'].includes(request.method)) return Response.json({ detail: 'Method not allowed.' }, { status: 405 })
        if (request.method === 'POST' && request.headers.get('Origin') !== url.origin) return Response.json({ detail: 'Request origin does not match this site.' }, { status: 403 })
        let backend
        try {
          backend = new URL(env.COTTRELL_API_URL)
          if (backend.protocol !== 'https:' || backend.username || backend.password || backend.search || backend.hash || backend.pathname !== '/') throw new Error('Invalid backend')
          if (!env.COTTRELL_API_TOKEN) throw new Error('Missing backend authentication')
        } catch {
          return Response.json({ detail: 'The analysis service is not connected yet. Your files have not been uploaded.' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
        }
        const target = new URL(url.pathname + url.search, backend)
        const headers = new Headers({ 'X-Cottrell-Token': env.COTTRELL_API_TOKEN })
        for (const name of ['Content-Type', 'Accept', 'Range']) {
          const value = request.headers.get(name)
          if (value) headers.set(name, value)
        }
        try {
          const response = await fetchBackend(target, { method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body, redirect: 'manual' })
          if (response.status >= 300 && response.status < 400) return Response.json({ detail: 'The analysis service returned an unexpected redirect.' }, { status: 502 })
          const resultHeaders = new Headers({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
          for (const name of ['Content-Type', 'Content-Disposition', 'Content-Range', 'Accept-Ranges']) {
            const value = response.headers.get(name)
            if (value) resultHeaders.set(name, value)
          }
          return new Response(response.body, { status: response.status, headers: resultHeaders })
        } catch {
          return Response.json({ detail: 'The analysis service could not be reached. Please try again.' }, { status: 502, headers: { 'Cache-Control': 'no-store' } })
        }
      }
      if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method not allowed', { status: 405 })
      const assetPath = url.pathname === '/' ? '/index.html' : url.pathname
      const asset = assets[assetPath]
      if (!asset) return new Response('Not found', { status: 404 })
      const body = request.method === 'HEAD' ? null : Uint8Array.from(atob(asset.data), c => c.charCodeAt(0))
      return new Response(body, { headers: { 'Content-Type': asset.type, 'Cache-Control': assetPath.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache', 'X-Content-Type-Options': 'nosniff' } })
    }
  }
}
