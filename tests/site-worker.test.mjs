import test from 'node:test'
import assert from 'node:assert/strict'
import { createWorker } from '../site/worker.mjs'
const env = { COTTRELL_API_URL: 'https://example.modal.run', COTTRELL_API_TOKEN: 'test-only-secret' }
const request = (path, options = {}) => new Request('https://cottrell.example' + path, options)
test('serves bundled app and returns 404 for missing assets', async () => {
  const worker = createWorker({ '/index.html': { type: 'text/html', data: btoa('<main>Cottrell</main>') } })
  assert.equal(await (await worker.fetch(request('/'), {})).text(), '<main>Cottrell</main>')
  assert.equal((await worker.fetch(request('/unknown.js'), {})).status, 404)
})
test('missing API setup cannot silently accept files', async () => {
  const result = await createWorker({}).fetch(request('/api/upload', { method: 'POST', headers: { Origin: 'https://cottrell.example' }, body: 'image' }), {})
  assert.equal(result.status, 503)
  assert.match((await result.json()).detail, /not been uploaded/)
})
test('only approved backend receives token, never browser credentials', async () => {
  let received
  const worker = createWorker({}, async (url, options) => {
    received = { url: url.toString(), options }
    return Response.json({ status: 'ok' }, { headers: { 'Set-Cookie': 'backend=value' } })
  })
  const result = await worker.fetch(request('/api/capabilities', { headers: { Cookie: 'private-browser-cookie', Authorization: 'private-browser-token' } }), env)
  assert.equal(received.url, 'https://example.modal.run/api/capabilities')
  assert.equal(received.options.headers.get('X-Cottrell-Token'), env.COTTRELL_API_TOKEN)
  assert.equal(received.options.headers.get('Cookie'), null)
  assert.equal(received.options.headers.get('Authorization'), null)
  assert.equal(result.headers.get('Set-Cookie'), null)
  assert.equal(result.headers.get('X-Cottrell-Token'), null)
})
test('cross-site mutation rejected and redirects are not followed', async () => {
  let calls = 0
  const worker = createWorker({}, async () => { calls++; return new Response(null, { status: 302, headers: { Location: 'https://untrusted.example' } }) })
  assert.equal((await worker.fetch(request('/api/runs', { method: 'POST', headers: { Origin: 'https://untrusted.example' } }), env)).status, 403)
  assert.equal(calls, 0)
  assert.equal((await worker.fetch(request('/api/results'), env)).status, 502)
  assert.equal(calls, 1)
})
test('large uploads stream directly without buffering or credential forwarding', async () => {
  const worker = createWorker({}, async (_url, options) => {
    assert.equal(options.method, 'POST')
    assert.equal(options.headers.get('Content-Type'), 'application/octet-stream')
    assert.equal(await new Response(options.body).text(), 'tiff-stream')
    return Response.json({ uploadId: 'saved' })
  })
  const result = await worker.fetch(request('/api/upload', { method: 'POST', headers: { Origin: 'https://cottrell.example', 'Content-Type': 'application/octet-stream' }, body: 'tiff-stream' }), env)
  assert.equal(result.status, 200)
})
