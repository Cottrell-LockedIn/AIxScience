import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs'
import { join, extname, relative } from 'node:path'
const types = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json' }
const base = 'frontend/dist'
const assets = {}
function add(directory) {
  for (const name of readdirSync(directory)) {
    const path = join(directory, name)
    if (statSync(path).isDirectory()) add(path)
    else assets['/' + relative(base, path).split('\\').join('/')] = { type: types[extname(path)] || 'application/octet-stream', data: readFileSync(path).toString('base64') }
  }
}
add(base)
mkdirSync('dist/server', { recursive: true })
const worker = readFileSync('site/worker.mjs', 'utf8') + '\nexport default createWorker(' + JSON.stringify(assets) + ')\n'
if (Buffer.byteLength(worker) > 3 * 1024 * 1024) throw new Error('Sites worker exceeds the conservative 3 MiB budget. Move static assets to supported asset hosting before publishing.')
writeFileSync('dist/server/index.js', worker)
console.log(`Sites worker built with ${Object.keys(assets).length} frontend assets.`)
