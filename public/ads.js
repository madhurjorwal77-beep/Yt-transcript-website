/* Ad loader: reads window.ADS_CONFIG (ads-config.js).
   - No client ID  -> ad slots keep their dashed "Ad Space" placeholder.
   - ID present    -> loads Google AdSense and swaps in real <ins> units. */
(function () {
  var cfg = window.ADS_CONFIG || { ADSENSE_CLIENT_ID: "", slots: {} };
  var slots = document.querySelectorAll(".ad-slot");
  if (!cfg.ADSENSE_CLIENT_ID) {
    slots.forEach(function (el) { el.classList.add("ad-placeholder"); });
    return;
  }
  var s = document.createElement("script");
  s.async = true;
  s.crossOrigin = "anonymous";
  s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
          encodeURIComponent(cfg.ADSENSE_CLIENT_ID);
  document.head.appendChild(s);
  slots.forEach(function (el) {
    var name = el.getAttribute("data-slot") || "";
    var slotId = (cfg.slots && cfg.slots[name]) || "";
    el.classList.remove("ad-placeholder");
    el.innerHTML = "";
    var ins = document.createElement("ins");
    ins.className = "adsbygoogle";
    ins.style.display = "block";
    ins.setAttribute("data-ad-client", cfg.ADSENSE_CLIENT_ID);
    if (slotId) ins.setAttribute("data-ad-slot", slotId);
    ins.setAttribute("data-ad-format", "auto");
    ins.setAttribute("data-full-width-responsive", "true");
    el.appendChild(ins);
    try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
  });
})();
