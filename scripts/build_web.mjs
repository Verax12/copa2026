// Build de produção do dashboard (sem Babel no browser).
// Concatena ui.jsx + views1/2/3.jsx + o App inline de index.dev.html, transpila o
// JSX com esbuild e gera web/assets/app.js (IIFE) + web/index.html (produção).
// React/ReactDOM continuam vindo do CDN (o bundle usa o React global, runtime clássico).
//
// Uso:  npm run build:web   (ou: node scripts/build_web.mjs)
import esbuild from "esbuild";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import { fileURLToPath } from "url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WEB = path.join(ROOT, "web");
const read = (f) => fs.readFileSync(path.join(WEB, f), "utf8");

// versão do CSS = hash do conteúdo → o <link> só busta o cache quando o CSS muda
// (sem cache-bust, o navegador serviria styles.css antigo com o app.js novo).
const cssVer = crypto.createHash("md5").update(read("styles.css")).digest("hex").slice(0, 8);

// 1) fontes do app (mesma ordem do index.dev.html)
const parts = ["ui.jsx", "views1.jsx", "views2.jsx", "views3.jsx"].map(read);

// 2) extrai o App inline (o único <script type="text/babel"> SEM src) do index.dev.html
const dev = read("index.dev.html");
const m = dev.match(/<script type="text\/babel">([\s\S]*?)<\/script>/);
if (!m) { console.error("Não achei o <script type=\"text/babel\"> inline em index.dev.html"); process.exit(1); }
parts.push(m[1]);

const source = parts.join("\n;\n");

// 3) transpila JSX -> JS (runtime clássico: React.createElement; React é global)
const result = await esbuild.build({
  stdin: { contents: source, loader: "jsx", resolveDir: WEB, sourcefile: "app.jsx" },
  bundle: false,            // sem imports: tudo num só escopo, como no modo Babel
  format: "iife",
  jsx: "transform",
  jsxFactory: "React.createElement",
  jsxFragment: "React.Fragment",
  minify: true,
  target: ["es2018"],
  write: false,
  legalComments: "none",
});
fs.mkdirSync(path.join(WEB, "assets"), { recursive: true });
fs.writeFileSync(path.join(WEB, "assets", "app.js"), result.outputFiles[0].text);
const kb = (result.outputFiles[0].text.length / 1024).toFixed(0);

// 4) gera o index.html de produção (sem Babel; dados e app com cache-bust)
const prod = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Copa 2026 · Dashboard de Predições</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow+Semi+Condensed:wght@400;600;700&family=Noto+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="styles.css?v=${cssVer}" />
</head>
<body>
  <!-- PRODUÇÃO: gerado por scripts/build_web.mjs (NÃO editar à mão; edite os .jsx
       e index.dev.html, depois rode \`npm run build:web\`). Sem Babel no browser. -->
  <div id="root"></div>

  <script src="https://unpkg.com/react@18.3.1/umd/react.production.min.js" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js" crossorigin="anonymous"></script>

  <!-- dados + bundle com cache-bust: a reload sempre pega a versão mais recente -->
  <script>
    (function () {
      var t = Date.now();
      document.write('<scr' + 'ipt src="wc_data.js?t=' + t + '"><\\/scr' + 'ipt>');
      document.write('<scr' + 'ipt src="data.js?t=' + t + '"><\\/scr' + 'ipt>');
      document.write('<scr' + 'ipt src="assets/app.js?t=' + t + '"><\\/scr' + 'ipt>');
    })();
  </script>
</body>
</html>
`;
fs.writeFileSync(path.join(WEB, "index.html"), prod);
console.log(`✓ build: web/assets/app.js (${kb} KB) + web/index.html (produção, sem Babel)`);
