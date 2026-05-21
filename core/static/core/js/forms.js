(function () {
  "use strict";

  var PAYMENT_ICONS = {
    cash: "bi-cash",
    card: "bi-credit-card",
    transfer: "bi-bank",
    mixed: "bi-wallet2",
  };

  function enhanceInputWrap(wrap) {
    var input = wrap.querySelector(".ft-control, .form-select");
    if (!input) return;

    function sync() {
      wrap.classList.toggle("ft-has-value", String(input.value || "").trim() !== "");
    }

    input.addEventListener("focus", function () {
      wrap.classList.add("ft-focused");
    });
    input.addEventListener("blur", function () {
      wrap.classList.remove("ft-focused");
    });
    input.addEventListener("input", sync);
    input.addEventListener("change", sync);
    sync();
  }

  function initPaymentPills(fieldEl) {
    var select = fieldEl.querySelector("select[name='payment_method']");
    if (!select || fieldEl.querySelector(".ft-payment-pills")) return;

    var pills = document.createElement("div");
    pills.className = "ft-payment-pills";
    pills.setAttribute("role", "group");
    pills.setAttribute("aria-label", "Forma de pago");

    Array.prototype.forEach.call(select.options, function (opt) {
      if (!opt.value) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ft-payment-pill" + (select.value === opt.value ? " ft-active" : "");
      btn.dataset.value = opt.value;
      var icon = PAYMENT_ICONS[opt.value] || "bi-circle";
      btn.innerHTML = '<i class="bi ' + icon + '" aria-hidden="true"></i> ' + opt.textContent;
      btn.addEventListener("click", function () {
        select.value = opt.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        pills.querySelectorAll(".ft-payment-pill").forEach(function (p) {
          p.classList.toggle("ft-active", p.dataset.value === opt.value);
        });
      });
      pills.appendChild(btn);
    });

    fieldEl.appendChild(pills);
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
  }

  function initForm(form) {
    form.querySelectorAll(".ft-input-wrap").forEach(enhanceInputWrap);
    form.querySelectorAll(".ft-field-payment").forEach(initPaymentPills);
    requestAnimationFrame(function () {
      form.classList.add("ft-form-ready");
    });
  }

  function initPurchaseFormset(form) {
    var tbody = form.querySelector("[data-ft-lines-body]");
    var template = form.querySelector("[data-ft-line-template]");
    var addBtn = form.querySelector("[data-ft-add-line]");
    var totalInput = form.querySelector('input[name$="-TOTAL_FORMS"]');
    if (!tbody || !template || !addBtn || !totalInput) return;

    var prefix = totalInput.name.replace(/-TOTAL_FORMS$/, "");
    var nameRe = new RegExp("^" + prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "-\\d+-");
    var idRe = new RegExp("^id_" + prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "-\\d+-");

    function renumber() {
      var rows = tbody.querySelectorAll("tr[data-ft-line]");
      rows.forEach(function (tr, i) {
        tr.querySelectorAll("[name],[id]").forEach(function (el) {
          if (el.name) el.name = el.name.replace(nameRe, prefix + "-" + i + "-");
          if (el.id) el.id = el.id.replace(idRe, "id_" + prefix + "-" + i + "-");
        });
      });
      totalInput.value = String(rows.length);
    }

    addBtn.addEventListener("click", function () {
      var idx = tbody.querySelectorAll("tr[data-ft-line]").length;
      var clone = template.content
        ? document.importNode(template.content, true).querySelector("tr")
        : template.cloneNode(true);
      if (!clone) return;
      clone.querySelectorAll("[name],[id]").forEach(function (el) {
        if (el.name) el.name = el.name.replace(/__prefix__/g, String(idx));
        if (el.id) el.id = el.id.replace(/__prefix__/g, String(idx));
      });
      clone.setAttribute("data-ft-line", "");
      tbody.appendChild(clone);
      tbody.querySelectorAll(".ft-input-wrap").forEach(enhanceInputWrap);
      renumber();
    });

    tbody.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-ft-remove-line]");
      if (!btn) return;
      var tr = btn.closest("tr");
      var del = tr && tr.querySelector('input[name$="-DELETE"]');
      if (del) {
        del.checked = true;
        tr.classList.add("d-none");
      } else if (tr) {
        tr.remove();
      }
      renumber();
    });
  }

  document.querySelectorAll(".ft-form").forEach(function (form) {
    initForm(form);
    initPurchaseFormset(form);
  });
})();
