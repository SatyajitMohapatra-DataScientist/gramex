const puppeteer = require('puppeteer')
const bodyParser = require('body-parser')
const minimist = require('minimist')
const express = require('express')
const cookie = require('cookie')
const path = require('path')
const url = require('url')
const tmp = require('tmp')
const fs = require('fs')

const default_port = 8090
const version = '1.0.0'
const server_version = 'ChromeCapture/' + version
const folder = path.dirname(path.resolve(process.argv[1]))
const homepage = path.join(folder, 'index.html')

let browser, page, app, server
let render_dir = folder             // Used by render() to save the file


function delay(ms) {
  return new Promise(res => setTimeout(res, ms))
}

async function render(q) {
  console.log('Opening', q.url)

  ext = q.ext || 'pdf'
  file = (q.file || 'screenshot') + '.' + ext
  target = path.join(render_dir, file)
  if (fs.exists(target))
    fs.unlinkSync(target)

  if (typeof browser == 'undefined')
    browser = await puppeteer.launch()
  if (typeof page == 'undefined')
    page = await browser.newPage()
  // Clear past cookies
  let cookies = await page.cookies(q.url)
  await page.deleteCookie(...cookies)
  // Parse cookies and set them on the page, so that they'll be sent on any
  // requests to this URL
  if (q.cookie) {
    let cookieList = []
    let cookieObj = cookie.parse(q.cookie)
    for (let key in cookieObj)
      cookieList.push({name: key, value: cookieObj[key], url: q.url})
    await page.setCookie(...cookieList)
  }
  await page.goto(q.url)
  await delay(q.delay || 0)
  if (ext == 'pdf') {
    // TODO: header / footer
    await page.pdf({
      path: target,
      format: q.format || 'A4',
      landscape: q.orientation == 'landscape',
      scale: q.scale || 1,
      margin: {top: '1cm', right: '1cm', bottom: '1cm', left: '1cm'}
    })
  } else {
    await page.setViewport({
      width: +q.width || 1200,
      height: +q.height || 768,
      deviceScaleFactor: +q.scale || 1
    })
    const options = {
      path: target,
      fullPage: !q.height && !q.selector  // If height and selector not specified, use full height
    }
    if (q.selector) {
      const rect = await page.evaluate(
        function(selector) {
          let el = document.querySelector(selector)
          if (!el) return
          let rect = el.getBoundingClientRect()
          return {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
        },
        q.selector)
      if (!rect)
        throw new Error("No selector " + q.selector)
      options.clip = rect
    }
    await page.screenshot(options)
  }
  return {path: target, file: file}
}

function webapp(req, res) {
  var q = Object.assign({}, req.query, req.body)
  if (!q.url)
    return res.sendFile(homepage)
  q.cookie = q.cookie || req.headers.cookie
  render(q).then((info) => {
    res.setHeader('Content-Disposition', 'attachment; filename=' + info.file)
    res.sendFile(info.path, (err) => {
      if (err)
        console.error('Error sending file', err)
      fs.unlinkSync(info.path)
    })
  })
  .catch((e) => {
    res.setHeader('Content-Type', 'text/plain')
    res.send(e.toString())
    console.error(e)
  })
}

function main() {
  if (process.version < '8.5') {
    console.error('Requires node.js 8.5 or above, not', process.version)
    process.exit(1)
  }

  const args = minimist(process.argv.slice(2))

  // Render the server if a port is specified
  // If no arguments are specified, start the server on a default port
  // Otherwise, treat it as a command line execution
  if (args.port || Object.keys(args).length <= 1) {
    const tmpdir = tmp.dirSync({unsafeCleanup: true})
    render_dir = tmpdir.name
    app = express()
      .use(bodyParser.urlencoded({extended: false}))
      .use((req, res, next) => {
        res.setHeader('Server', server_version)
        next()
      })
      .get('/', webapp)
      .post('/', webapp)
    const port = args.port || default_port
    server = app.listen(port)
      .on('error', (e) => {
        console.error('Could not bind to port', port, e)
        process.exit()
      })
      .on('listening', () => {
        let proc = ('node.js: ' + process.version + ' chromecapture.js: ' + version +
                    ' port: ' + port + ' pid: ' + process.pid)
        console.log(proc)
        function exit(how) {
          console.log('Ending', proc, 'by', how)
          tmpdir.removeCallback()
          server.close()
        }
        process.on('SIGINT', exit.bind(null, 'SIGINT'))
        process.on('exit', exit.bind(null, 'exit'))
        process.on('SIGUSR1', exit.bind(null, 'SIGUSR1'))
        process.on('SIGUSR2', exit.bind(null, 'SIGUSR2'))
      })
  } else {
    render(args).then((info) => {
      console.log('Saving', args.url, 'to', info.file)
      process.exit()
    }).catch((err) => {
      console.error(err)
      process.exit()
    })
  }
}

main()