(function () {
  "use strict";

  var cfg = window.FT_PROFIT;
  if (!cfg || typeof Chart === "undefined") return;

  var from = cfg.rangeFrom;
  var to = cfg.rangeTo;
  var granularity = "day";
  var compareChart;
  var lineChart;

  var colors = {
    sales: "#2f5563",
    salesLight: "rgba(47, 85, 99, 0.65)",
    payments: "#c25628",
    paymentsLight: "rgba(194, 86, 40, 0.65)",
    profit: "#2d7a4f",
    profitNeg: "#b42318",
    grid: "rgba(47, 85, 99, 0.08)",
  };

  var alertEl = document.getElementById("ft-profit-alert");

  function showError(msg) {
    if (!alertEl) return;
    alertEl.textContent = msg;
    alertEl.classList.add("ft-visible");
  }

  function qs() {
    return (
      "from=" +
      encodeURIComponent(from) +
      "&to=" +
      encodeURIComponent(to) +
      "&granularity=" +
      granularity
    );
  }

  function setEmpty(chartId, visible) {
    var el = document.querySelector('[data-empty-for="' + chartId + '"]');
    if (el) el.classList.toggle("ft-visible", visible);
  }

  async function fetchJson(url) {
    var res = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
    });
    if (!res.ok) {
      var text = await res.text();
      throw new Error(text || "Error " + res.status);
    }
    return res.json();
  }

  function moneyTick(value) {
    if (typeof formatMxn === "function") return formatMxn(value);
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value));
  }

  function resizeChart(chart) {
    if (!chart) return;
    requestAnimationFrame(function () {
      chart.resize();
    });
  }

  function hasSeriesData(data) {
    if (!data.labels || !data.labels.length) return false;
    return data.sales.some(function (v) {
      return v > 0;
    }) || data.payments.some(function (v) {
      return v > 0;
    });
  }

  function loadCompareChart(data) {
    var ctx = document.getElementById("profitCompareChart");
    if (!ctx) return;
    if (compareChart) compareChart.destroy();

    var hasData = hasSeriesData(data);
    setEmpty("profitCompareChart", !hasData);

    compareChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Ventas",
            data: data.sales,
            backgroundColor: colors.salesLight,
            borderColor: colors.sales,
            borderWidth: 1,
            borderRadius: 4,
            order: 2,
          },
          {
            label: "Pagos proveedor",
            data: data.payments,
            backgroundColor: colors.paymentsLight,
            borderColor: colors.payments,
            borderWidth: 1,
            borderRadius: 4,
            order: 3,
          },
          {
            label: "Ganancia (efectivo)",
            data: data.profit_cash,
            type: "line",
            borderColor: colors.profit,
            backgroundColor: "transparent",
            borderWidth: 2,
            tension: 0.3,
            pointRadius: data.labels.length > 18 ? 0 : 3,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { boxWidth: 12, font: { size: 11 } },
          },
          tooltip: {
            backgroundColor: "#152a33",
            callbacks: {
              label: function (ctx) {
                var v = ctx.parsed.y;
                return ctx.dataset.label + ": " + moneyTick(v);
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 14, font: { size: 10 } } },
          y: {
            beginAtZero: true,
            grid: { color: colors.grid },
            ticks: { callback: moneyTick, font: { size: 10 } },
          },
        },
      },
    });
    resizeChart(compareChart);
  }

  function loadLineChart(data) {
    var ctx = document.getElementById("profitLineChart");
    if (!ctx) return;
    if (lineChart) lineChart.destroy();

    var cumulative = [];
    var sum = 0;
    data.profit_cash.forEach(function (v) {
      sum += v;
      cumulative.push(sum);
    });

    setEmpty("profitLineChart", !cumulative.length);

    lineChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Ganancia acumulada",
            data: cumulative,
            borderColor: colors.profit,
            backgroundColor: "rgba(45, 122, 79, 0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: data.labels.length > 18 ? 0 : 3,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#152a33",
            callbacks: {
              label: function (ctx) {
                return moneyTick(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 9 } } },
          y: {
            grid: { color: colors.grid },
            ticks: { callback: moneyTick, font: { size: 10 } },
          },
        },
      },
    });
    resizeChart(lineChart);
  }

  async function reloadCharts() {
    if (alertEl) alertEl.classList.remove("ft-visible");
    try {
      var data = await fetchJson(cfg.apiUrl + "?" + qs());
      loadCompareChart(data);
      loadLineChart(data);
    } catch (err) {
      showError("No se pudieron cargar los gráficos. " + (err.message || ""));
      console.error(err);
    }
  }

  document.querySelectorAll(".profit-gran-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".profit-gran-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      granularity = btn.dataset.gran;
      reloadCharts();
    });
  });

  window.addEventListener("resize", function () {
    resizeChart(compareChart);
    resizeChart(lineChart);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", reloadCharts);
  } else {
    reloadCharts();
  }
})();
