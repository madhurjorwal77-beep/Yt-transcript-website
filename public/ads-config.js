/* =====================================================================
   AdSense configuration — MADHUR, SIRF YAHI FILE EDIT KARNA ADS KE LIYE
   ---------------------------------------------------------------------
   1. AdSense approval ke baad tumhe ek Publisher ID milegi: ca-pub-XXXX
   2. Use neeche ADSENSE_CLIENT_ID mein daal do (quotes ke andar).
   3. (Optional) Har slot ke liye AdSense dashboard se alag ad unit banao
      aur uski slot ID yahan daalo. Slot khaali chhodo to responsive
      auto ad unit use hogi.
   Jab tak ID khaali hai, site par sirf "Ad Space" wale placeholder
   boxes dikhenge — koi galat/fake ad load nahi hoga.
   ===================================================================== */
window.ADS_CONFIG = {
  ADSENSE_CLIENT_ID: "",          // e.g. "ca-pub-1234567890123456"
  slots: {
    header: "",                   // below-header banner
    tool: "",                     // tool ke form ke neeche
    content: "",                  // transcript ke paas/sidebar
    footer: ""                    // footer ke upar
  }
};
