/*
 * smoke_test.js
 * Prueba automática del simulador: carga el HTML en jsdom, recorre los 3 modos, todos los
 * paquetes, todas las ventanas y el formulario de paquete propio, y cuenta errores de JavaScript.
 *
 *   npm install jsdom            (una sola vez, en una carpeta temporal)
 *   node smoke_test.js docs/simulador_pipeline.html
 *
 * Termina con código 1 si hubo algún error, para poder usarlo en CI.
 */
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs");

const html = fs.readFileSync(process.argv[2], "utf8");
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errors.push("jsdomError: " + ((e.detail && e.detail.stack) || e.message)));
vc.on("error", e => errors.push("console.error: " + e));

const dom = new JSDOM(html, {
  runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w){
    // jsdom no implementa <dialog> ni scrollIntoView: se simulan.
    w.HTMLDialogElement.prototype.showModal = function(){ this.setAttribute("open", ""); };
    w.HTMLDialogElement.prototype.close = function(){ this.removeAttribute("open"); };
    w.Element.prototype.scrollIntoView = function(){};
  }
});
const w = dom.window, d = w.document, $ = s => d.querySelector(s);
const click = e => e.dispatchEvent(new w.MouseEvent("click", { bubbles:true }));
const total = () => +/de (\d+)/.exec($("#progress").textContent)[1];
const out = [];

function walk(name, tab){
  click($(tab));
  const n = total();
  for (let i = 0; i < n; i++) click($("#bStep"));
  out.push(`${name}: ${n} eventos · encendidos=${d.querySelectorAll(".dev:not(.off)").length} · contenedores=${[...d.querySelectorAll(".st-pill")].map(x => x.textContent).join(" | ")}`);
}

walk("modo 3 (viaje)", "#tab-run");
for (const chip of [...d.querySelectorAll(".chip")].filter(c => !c.textContent.includes("Crear"))){
  click(chip); const n = total();
  for (let i = 0; i < n; i++) click($("#bStep"));
  out.push(`  paquete «${chip.textContent.trim()}»: ${n} eventos`);
}
walk("modo 1 (Docker Compose)", "#tab-docker");
walk("modo 2 (proyecto)", "#tab-proj");
click($("#tab-run"));

for (const dv of d.querySelectorAll(".dev")){ click(dv); d.querySelectorAll("#dlgTabs .dtab").forEach(click); }
out.push("ventanas de bloques: " + d.querySelectorAll(".dev").length);
for (const r of d.querySelectorAll(".dkrow")){ click(r); d.querySelectorAll("#dlgTabs .dtab").forEach(click); }
out.push("fichas de contenedores: " + d.querySelectorAll(".dkrow").length);
for (const b of ["#bYml", "#bDf", "#bCmd"]){ click($(b)); out.push(`${b}: ${$("#dlgBody").textContent.length} caracteres`); }

const f = $("#newForm");
f.querySelector("[name=humidity]").value = "150";
f.dispatchEvent(new w.Event("submit", { bubbles:true, cancelable:true }));
out.push("paquete propio: " + d.querySelector(".chip[aria-pressed=true]").textContent.trim());

console.log(out.join("\n"));
console.log("ERRORES:", errors.length ? "\n" + errors.join("\n") : "ninguno");
process.exit(errors.length ? 1 : 0);
