#!/usr/bin/env node
import { readdir, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { basename, isAbsolute, join, relative, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const packageName = '@rotdrop/nextcloud-vue-components'
const begin = '# BEGIN generated nextcloud-vue-components exclusions'
const end = '# END generated nextcloud-vue-components exclusions'
const sourceFile = /\.(?:vue|[cm]?[jt]sx?)$/

async function files(directory) {
  const result = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) {
      result.push(...await files(path))
    } else if (entry.isFile()) {
      result.push(path)
    } else {
      throw new Error(`Unsupported source entry (possibly a symlink): ${path}`)
    }
  }
  return result.sort()
}

async function readOptional(path) {
  try {
    return await readFile(path, 'utf8')
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error
    }
    return ''
  }
}

function replaceGenerated(contents, entries) {
  const lines = contents.split(/\r?\n/)
  const starts = lines.flatMap((line, index) => line === begin ? [index] : [])
  const ends = lines.flatMap((line, index) => line === end ? [index] : [])
  if (starts.length !== ends.length || starts.length > 1
    || (starts.length && starts[0] >= ends[0])) {
    throw new Error('Malformed generated section in ignore file')
  }
  const block = [begin, ...entries, end]
  if (starts.length) {
    lines.splice(starts[0], ends[0] - starts[0] + 1, ...block)
    return lines.join('\n')
  }
  return `${contents}${contents && !contents.endsWith('\n') ? '\n' : ''}${block.join('\n')}\n`
}

function checkDynamicImports(node, id) {
  if (!node || typeof node !== 'object') {
    return
  }
  if (node.type === 'ImportExpression') {
    const source = node.source
    const literal = ['Literal', 'StringLiteral'].includes(source.type) && typeof source.value === 'string'
    const template = source.type === 'TemplateLiteral' && source.expressions.length === 0
    if (!literal && !template) {
      throw new Error(`Cannot analyze runtime dynamic import in ${id}; use statically analyzable imports or maintain exclusions manually`)
    }
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) {
      value.forEach(child => checkDynamicImports(child, id))
    } else if (value && typeof value === 'object') {
      checkDynamicImports(value, id)
    }
  }
}

async function vueIgnore(app, configFile, ignoreFile, keepFile, modes) {
  const destination = resolve(app, ignoreFile)
  const previous = await readOptional(destination)
  replaceGenerated(previous, [])
  const require = createRequire(join(app, 'package.json'))
  const vite = await import(pathToFileURL(require.resolve('vite')).href)
  const root = await realpath(join(app, 'node_modules', packageName, 'lib'))
  const sources = (await files(root)).filter(path => sourceFile.test(path) && !/\.d\.[cm]?ts$/.test(path))
  const used = new Set()
  const kept = new Set()
  for (const line of (await readOptional(resolve(app, keepFile))).split(/\r?\n/)) {
    const entry = line.trim()
    if (!entry || entry.startsWith('#')) {
      continue
    }
    const marker = `${packageName}/lib/`
    const start = entry.indexOf(marker)
    if (start < 0 || (start > 0 && entry[start - 1] !== '/')) {
      throw new Error(`Invalid keep entry: ${entry}`)
    }
    const path = await realpath(resolve(root, entry.slice(start + marker.length)))
    if (!sources.includes(path)) {
      throw new Error(`Keep entry is not a package source file: ${entry}`)
    }
    kept.add(path)
  }
  const environment = { ...process.env }
  for (const mode of modes) {
    // Vite's dotenv handling and config factories can mutate process.env.
    for (const key of Object.keys(process.env)) {
      if (!Object.hasOwn(environment, key)) {
        delete process.env[key]
      }
    }
    Object.assign(process.env, environment)
    const warnings = new Set()
    const logger = vite.createLogger('error')
    await vite.build({
      root: app,
      configFile: configFile ? resolve(app, configFile) : undefined,
      mode,
      customLogger: {
        ...logger,
        warn(message) { warnings.add(message) },
        warnOnce(message) { warnings.add(message) },
      },
      build: { write: false, emptyOutDir: false, watch: null },
      plugins: [{
        name: 'l10n-ignore',
        enforce: 'pre',
        configResolved(config) {
          if (config.build.write !== false || config.build.emptyOutDir !== false || config.build.watch) {
            throw new Error('Vite configuration overrides the non-writing analysis build')
          }
        },
        onLog: {
          order: 'pre',
          handler(level, log) {
            if (level === 'warn') {
              warnings.add(log.message)
            }
          },
        },
        transform(_code, id) {
          used.add(id)
        },
        buildEnd(error) {
          if (error) {
            return
          }
          const modules = new Set(this.getModuleIds())
          for (const id of modules) {
            const info = this.getModuleInfo(id)
            if ((id.includes(packageName) || id.startsWith(`${root}/`))
              && (!info || info.isExternal || info.code === null)) {
              throw new Error(`Cannot analyze externalized ${packageName} modules: ${id}`)
            }
            // Dynamic imports of unrelated third-party dependencies cannot
            // reach the analyzed library, so only check the library and app code.
            const thirdParty = id.includes('/node_modules/') && !id.startsWith(`${root}/`)
            if (!thirdParty && info?.code?.includes('import')) {
              checkDynamicImports(this.parse(info.code), id)
            }
            for (const dependency of [...(info?.importedIds || []), ...(info?.dynamicallyImportedIds || [])]) {
              modules.add(dependency)
            }
            used.add(id)
          }
          // Rollup exposes watched loader inputs; Rolldown currently does not.
          if (typeof this.getWatchFiles === 'function') {
            for (const id of this.getWatchFiles()) {
              used.add(id)
            }
          }
        },
      }],
    })
    if (warnings.size) {
      throw new Error(`Vite analysis produced warnings:\n${[...warnings].join('\n')}`)
    }
  }
  const paths = [...used].filter(id => isAbsolute(id)).map(id => id.split('?')[0])
  const canonicalUsed = new Set(await Promise.all(paths.map(path => realpath(path))))
  const entries = sources.filter(path => !canonicalUsed.has(path) && !kept.has(path))
    .map(path => `node_modules/${packageName}/lib/${relative(root, path).split('\\').join('/')}`)
  const output = replaceGenerated(previous, entries)
  // Refuse to overwrite edits made while Vite was running.
  if (await readOptional(destination) !== previous) {
    throw new Error('Ignore file changed during dependency analysis; retry')
  }
  const temporary = `${destination}.${process.pid}.tmp`
  await writeFile(temporary, output, { flag: 'wx' })
  try {
    await rename(temporary, destination)
  } finally {
    await rm(temporary, { force: true })
  }
}

async function phpCandidates(app, toolkit, ignoreFile) {
  const root = resolve(app, toolkit, 'src')
  const sources = (await files(root)).filter(path => path.endsWith('.php'))
  const texts = new Map()
  for (const source of sources) {
    texts.set(source, await readFile(source, 'utf8'))
  }
  const skip = new Set(['.git', 'vendor', 'node_modules', 'l10n', 'l10n-sources', 'js', 'css'])
  async function appTexts(directory) {
    const result = []
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name)
      if (entry.isDirectory() && !skip.has(entry.name) && !entry.name.startsWith('vendor-')
        && resolve(path) !== resolve(app, toolkit)) {
        result.push(...await appTexts(path))
      } else if (entry.isFile() && /\.(?:php|xml|json|in)$/.test(path)) {
        result.push(await readFile(path, 'utf8'))
      }
    }
    return result
  }
  const appSource = (await appTexts(app)).join('\n')
  const existing = new Set()
  for (const line of (await readOptional(resolve(app, ignoreFile))).split(/\r?\n/)) {
    const entry = line.trim()
    if (!entry || entry.startsWith('#')) {
      continue
    }
    const match = entry.match(/(?:^|\/)(rotdrop\/nextcloud-app-toolkit\/src\/.+\.php)$/)
    if (match) {
      existing.add(match[1])
    }
  }
  const candidates = new Set()
  console.log('# Review candidates only: file basenames not referenced in app or other toolkit sources.')
  console.log('# Dynamic references, service discovery and non-class files require manual review.')
  for (const source of sources) {
    const name = basename(source, '.php').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const reference = new RegExp(`\\b${name}\\b`)
    if (!reference.test(appSource)
      && ![...texts].some(([path, text]) => path !== source && reference.test(text))) {
      const entry = `rotdrop/nextcloud-app-toolkit/src/${relative(root, source).split('\\').join('/')}`
      candidates.add(entry)
      console.log(entry)
    }
  }
  console.log(`# Diff against ${ignoreFile} (toolkit PHP entries only; review, do not apply automatically):`)
  console.log('# Legend: + candidate not currently ignored; - existing exclusion not suggested by the heuristic.')
  const removed = [...existing].filter(entry => !candidates.has(entry)).sort()
  const added = [...candidates].filter(entry => !existing.has(entry)).sort()
  for (const entry of removed) {
    console.log(`# - ${entry}`)
  }
  for (const entry of added) {
    console.log(`# + ${entry}`)
  }
  if (!removed.length && !added.length) {
    console.log('# No differences.')
  }
}

try {
  const [command, appPath, ...args] = process.argv.slice(2)
  const app = resolve(appPath || '.')
  if (command === 'vue' && args.length >= 4 && args.slice(3).every(mode => mode !== '')) {
    process.chdir(app)
    await vueIgnore(app, args[0], args[1], args[2], args.slice(3))
  } else if (command === 'php-candidates' && [1, 2].includes(args.length)) {
    await phpCandidates(app, args[0], args[1] ?? '.l10nignore')
  } else {
    throw new Error('Usage: l10n-ignore.mjs vue APP CONFIG IGNORE KEEP MODE [MODE ...] | php-candidates APP TOOLKIT [IGNORE]')
  }
} catch (error) {
  console.error(error.stack || error.message)
  process.exitCode = 1
}
