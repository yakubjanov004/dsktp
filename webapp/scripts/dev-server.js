#!/usr/bin/env node

/**
 * Cross-platform Next.js dev launcher.
 * - Cleans up port 3200 on start/exit (Windows + Linux/macOS)
 * - Forwards Ctrl+C once so port is freed immediately
 */

const { spawn, execSync } = require("child_process")

const DEFAULT_PORT = 3200
const port = Number(process.env.PORT || process.env.NEXT_PORT || DEFAULT_PORT)
const host = process.env.HOST || "0.0.0.0"
const isWindows = process.platform === "win32"
let shuttingDown = false

function killPort() {
  try {
    if (isWindows) {
      const psScript = `Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`
      execSync(`powershell -Command "${psScript}"`, { stdio: "ignore" })
      return
    }

    try {
      execSync(`fuser -k ${port}/tcp`, { stdio: "ignore" })
      return
    } catch {}

    execSync(`lsof -ti tcp:${port} | xargs kill -9`, { stdio: "ignore" })
  } catch {
    // Port was already free
  }
}

if (process.env.FORCE_PORT_CLEAN === "1") {
  killPort()
}

const env = {
  ...process.env,
  NODE_OPTIONS: process.env.NODE_OPTIONS || "--no-deprecation",
}

// On Windows, run via shell with full command string to avoid EINVAL and deprecation warning
const args = ["next", "dev", "-H", host, "-p", String(port)]
const child = isWindows
  ? spawn(`npx ${args.join(" ")}`, [], { stdio: "inherit", env, shell: true })
  : spawn("npx", args, { stdio: "inherit", env })

function shutdown(reason) {
  if (shuttingDown) return
  shuttingDown = true
  console.log(`\n[dev-server] ${reason} — serverni to'xtatyapman...`)

  if (child && !child.killed) {
    child.kill("SIGINT")
    setTimeout(() => {
      if (!child.killed) {
        child.kill("SIGTERM")
      }
    }, 4000)
  }
}

process.on("SIGINT", () => shutdown("Ctrl+C bosildi"))
process.on("SIGTERM", () => shutdown("SIGTERM qabul qilindi"))

child.on("exit", (code, signal) => {
  killPort()
  if (signal) {
    process.exitCode = 1
  } else {
    process.exitCode = code ?? 0
  }
})

child.on("error", (err) => {
  console.error("[dev-server] Next.js ni ishga tushirib bo'lmadi:", err)
  killPort()
  process.exit(1)
})
