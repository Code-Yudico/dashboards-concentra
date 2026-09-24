(() => {
  "use strict";

  const SNAPSHOT_URL = "./data/snapshot.json";

  // Paleta categórica (Okabe-Ito, accesible para daltonismo), se recicla si
  // hay más categorías que colores.
  const PALETTE = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#999999",
  ];

  const elAgrupar = document.getElementById("agrupar_por");
  const elGranularidad = document.getElementById("granularidad");
  const elTipoGrafico = document.getElementById("tipo_grafico");
  const elPlot = document.getElementById("plot");
  const elEstado = document.getElementById("estado");
  const elPie = document.getElementById("pie");

  let registros = [];

  function mostrarError(mensaje) {
    elEstado.hidden = false;
    elEstado.classList.add("error");
    elEstado.textContent = mensaje;
  }

  function mostrarInfo(mensaje) {
    elEstado.hidden = false;
    elEstado.classList.remove("error");
    elEstado.textContent = mensaje;
  }

  function ocultarEstado() {
    elEstado.hidden = true;
  }

  // Fecha viene como "YYYY-MM-DD" (serializada por extraer_snapshot.py).
  // Se trunca en UTC para evitar corrimientos por zona horaria del navegador.
  function truncarFecha(fechaIso, granularidad) {
    const d = new Date(`${fechaIso}T00:00:00Z`);
    if (granularidad === "dia") {
      return fechaIso;
    }
    if (granularidad === "semana") {
      // Lunes de esa semana (ISO).
      const diaSemana = d.getUTCDay() === 0 ? 7 : d.getUTCDay(); // 1=lun ... 7=dom
      const lunes = new Date(d);
      lunes.setUTCDate(d.getUTCDate() - (diaSemana - 1));
      return lunes.toISOString().slice(0, 10);
    }
    if (granularidad === "mes") {
      return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
    }
    throw new Error(`Granularidad desconocida: ${granularidad}`);
  }

  // Pivotea los registros en { fechas: string[], categorias: string[], matriz: Map<fecha, Map<categoria, total>> }
  function agregar(registros, columnaCategoria, granularidad) {
    const totales = new Map(); // fecha -> Map(categoria -> total)
    const categorias = new Set();

    for (const fila of registros) {
      const fecha = truncarFecha(fila.Fecha, granularidad);
      const categoria = String(fila[columnaCategoria] ?? "(sin dato)");
      categorias.add(categoria);

      if (!totales.has(fecha)) totales.set(fecha, new Map());
      const porCategoria = totales.get(fecha);
      porCategoria.set(categoria, (porCategoria.get(categoria) || 0) + Number(fila.num_usuarios || 0));
    }

    const fechas = [...totales.keys()].sort();
    const categoriasOrdenadas = [...categorias].sort();

    return { fechas, categorias: categoriasOrdenadas, totales };
  }

  function construirTraces(fechas, categorias, totales, tipoGrafico) {
    const esLinea = tipoGrafico === "lineas";
    const esAreaApilada = tipoGrafico === "area_apilada";

    return categorias.map((categoria, idx) => {
      const y = fechas.map((fecha) => totales.get(fecha)?.get(categoria) || 0);
      const color = PALETTE[idx % PALETTE.length];

      if (esLinea) {
        return {
          type: "scatter",
          mode: "lines+markers",
          name: categoria,
          x: fechas,
          y,
          line: { color, width: 2 },
          marker: { color, size: 5 },
        };
      }

      if (esAreaApilada) {
        return {
          type: "scatter",
          mode: "lines",
          name: categoria,
          x: fechas,
          y,
          stackgroup: "total",
          line: { color, width: 0.5 },
        };
      }

      // barras_apiladas y barras_100 usan el mismo trace; la diferencia
      // (barnorm) se aplica a nivel de layout.
      return {
        type: "bar",
        name: categoria,
        x: fechas,
        y,
        marker: { color },
      };
    });
  }

  function construirLayout(tipoGrafico, columnaCategoria) {
    const layout = {
      autosize: true,
      margin: { t: 20, r: 20, b: 40, l: 55 },
      xaxis: {
        title: "Fecha",
        rangeslider: { visible: true },
        rangeselector: {
          buttons: [
            { count: 30, label: "30d", step: "day", stepmode: "backward" },
            { count: 90, label: "90d", step: "day", stepmode: "backward" },
            { count: 6, label: "6m", step: "month", stepmode: "backward" },
            { count: 1, label: "1a", step: "year", stepmode: "backward" },
            { step: "all", label: "Todo" },
          ],
        },
      },
      yaxis: { title: "Usuarios (suma)" },
      legend: { title: { text: columnaCategoria } },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
    };

    if (tipoGrafico === "barras_apiladas" || tipoGrafico === "barras_100") {
      layout.barmode = "stack";
    }
    if (tipoGrafico === "barras_100") {
      layout.barnorm = "percent";
      layout.yaxis.title = "Usuarios (% del total)";
    }

    return layout;
  }

  function render() {
    if (registros.length === 0) return;

    const columnaCategoria = elAgrupar.value;
    const granularidad = elGranularidad.value;
    const tipoGrafico = elTipoGrafico.value;

    const { fechas, categorias, totales } = agregar(registros, columnaCategoria, granularidad);
    const traces = construirTraces(fechas, categorias, totales, tipoGrafico);
    const layout = construirLayout(tipoGrafico, elAgrupar.selectedOptions[0].textContent);

    Plotly.react(elPlot, traces, layout, { responsive: true, displaylogo: false });
  }

  async function cargar() {
    mostrarInfo("Cargando snapshot...");
    try {
      const resp = await fetch(SNAPSHOT_URL, { cache: "no-store" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      registros = payload.registros || [];

      if (registros.length === 0) {
        mostrarError("El snapshot no tiene registros todavía. Espera a que corra la extracción diaria.");
        return;
      }

      ocultarEstado();
      elPie.textContent = `Snapshot generado: ${payload.generado_en} · ${payload.total_filas} filas`;
      render();
    } catch (err) {
      mostrarError(`No se pudo cargar el snapshot de datos: ${err.message}`);
    }
  }

  elAgrupar.addEventListener("change", render);
  elGranularidad.addEventListener("change", render);
  elTipoGrafico.addEventListener("change", render);
  window.addEventListener("resize", () => Plotly.Plots.resize(elPlot));

  cargar();
})();
