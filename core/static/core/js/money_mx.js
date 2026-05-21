/**
 * Mexican peso display (es-MX): $1,234.56
 */
(function (global) {
  "use strict";

  var nfMoney = new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  var nfAmount = new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function formatMxn(value) {
    var n = Number(value);
    if (!isFinite(n)) return "—";
    return nfMoney.format(n);
  }

  function formatMxnPlain(value) {
    var n = Number(value);
    if (!isFinite(n)) return "—";
    return nfAmount.format(n);
  }

  function parseMxnInput(s) {
    if (s == null || s === "") return 0;
    var cleaned = String(s).replace(/\$/g, "").replace(/\s/g, "").replace(/,/g, "");
    var n = parseFloat(cleaned);
    return isFinite(n) ? n : 0;
  }

  global.formatMxn = formatMxn;
  global.formatMxnPlain = formatMxnPlain;
  global.parseMxnInput = parseMxnInput;
})(typeof window !== "undefined" ? window : globalThis);
