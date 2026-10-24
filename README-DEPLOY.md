# README — Deploy + AdSense Guide (Madhur ke liye)

Ye tumhari **apni** YouTube Transcript website hai. Koi bhi YouTube link daalo → transcript milta hai.
Code sirf Python standard library use karta hai — koi paid cheez, koi dependency nahi. **₹0 mein deploy ho jayegi.**

```
yt-transcript-website/
├── app.py              ← server (API + website dono chalata hai)
├── public/             ← website ki files (pages, design, ads-config)
├── render.yaml         ← Render.com ke liye ready settings
├── Procfile, runtime.txt, requirements.txt
└── README-DEPLOY.md    ← ye file
```

---

## STEP 1 — Site ko LIVE karo (Render par, free)

Render sabse easy hai kyunki is project mein `render.yaml` pehle se bana hai.

1. **GitHub account** banao (github.com) — Gmail se sign up, free.
2. GitHub par **New repository** banao (naam jaise `yt-transcript`), aur is folder ki saari files wahan **upload** karo
   (GitHub website par hi "uploading an existing file" se ho jata hai, phone se bhi chalega).
3. **render.com** par jao → usi GitHub account se sign up/login karo.
4. **New → Web Service** → apni `yt-transcript` repository select karo.
5. Render khud `render.yaml` padh lega (build: none, start: `python3 app.py`). Bas **Create Web Service / Deploy** dabao.
6. 2–5 minute mein tumhe live URL milega, jaise: `https://yt-transcript-xxxx.onrender.com`
   **Yahi tumhari website hai** — ise kahin bhi share kar sakte ho.

> Free plan ki ek baat: Render free service 15 minute khaali rehne par so jati hai, pehla visitor aane par ~30–50 second mein jaagti hai. Ye normal hai, ghabrana mat.

Live hone ke baad 2 chhoti settings:
- `public/sitemap.xml` aur sab pages ke head mein `{{YOUR_DOMAIN}}` ki jagah apna live URL daalo (GitHub par file edit karke), aur GitHub par dobara push/deploy hone do. (Bina iske bhi site chalegi, ye sirf Google search ke liye hai.)
- `public/contact.html` mein `your-email@example.com` ko apne asli email se badalo, warna contact form ka mail tumhe nahi milega.

### Dusre free options (chaaho to)
- **Railway** (railway.app): GitHub repo connect karo, `Procfile` pehle se hai, deploy dabao — trial credit milta hai.
- **PythonAnywhere** (pythonanywhere.com): free account → files upload → Web tab mein WSGI ki jagah `app.py` ko as a script run karna hota hai; thoda zyada manual hai, isliye pehle Render try karo.

### Custom domain (optional, baad mein)
Pehle free wale `onrender.com` address se shuru karo. Jab site chal pade, apna domain (jaise `yttranscript.in`) ~₹700/saal mein milta hai — Render ki Settings → Custom Domain mein jod sakte ho. **AdSense approval ke liye custom domain helpful hota hai**, lekin shuruaat ke liye zaroori nahi.

---

## STEP 2 — AdSense se Earning (order yahi rakho)

Galti mat karna: **pehle site live + pages complete, fir AdSense.** Isi order mein karo:

1. Site upar wale Step 1 se **live** karo aur khud 2–3 videos par test karke dekho ki transcript aa raha hai.
2. Site par saare pages pehle se hain (Home, How To, Hindi Guide, FAQ, About, Contact, Privacy Policy, Terms) — ye AdSense approval ke liye zaroori hote hain, isliye kuch delete mat karna.
3. **google.com/adsense** par jao → **usi Google account se** sign up karo jo tum use karte ho → apni site ka URL add karo.
4. AdSense tumhe ek **Publisher ID** dega: `ca-pub-XXXXXXXXXXXXXXXX` jaisi.
5. Wo ID yahan daalo (GitHub par file edit karke):
   - `public/ads-config.js` → `ADSENSE_CLIENT_ID: "ca-pub-XXXX..."` (quotes ke andar)
   - AdSense dashboard se mili **ads.txt wali line** ko `public/ads.txt` ki placeholder line se badal do.
   - AdSense agar **verification code** de (site verify karne ke liye), to use har page ke `<head>` mein jahan comment likha hai
     `<!-- ADSENSE VERIFY: ... -->` wahan paste karo (sab HTML files mein ye jagah bani hui hai).
6. GitHub par changes save → Render apne aap dobara deploy kar dega → ads ki jagah jo "Ad Space" boxes dikh rahe the, wahan asli ads aane lagenge (approval ke baad).
7. **Approval ka wait karo** — kuch din se kuch hafte lag sakte hain. Tab tak site ko share karke traffic lao.

### Sach wali baat (dhyaan se padho)
- **Approval guaranteed nahi hai.** Ek-tool wali chhoti sites ko Google kabhi-kabhi **"low value content"** bolkar reject kar deta hai — isiliye is site mein asli guide/FAQ wale pages pehle se jode hain, taaki site sirf ek khaali tool na lage. Reject ho to pages mein aur asli content badhao aur dobara apply karo.
- **Earning = traffic par.** Ads lage hone se hi paise nahi bante; log aayenge tabhi earning hogi. Apne YouTube channel ki videos/descriptions se site ka link do, WhatsApp/Telegram groups mein share karo — wahi asli shuruaat hai.
- Apne hi ads par **kabhi khud click mat karna** aur doston ko click karne ko mat kehna — AdSense account ban ho jata hai, hamesha ke liye.

---

## Roz ke kaam / chhote notes
- **Transcript na aaye to:** kuch videos mein captions hi nahi hote (site saaf message degi). Kabhi-kabhi YouTube server ko thodi der rok deta hai — "Try Again" dabane se ho jata hai. Ye YouTube ki taraf ki limit hai, site ki kharabi nahi.
- **Language badalna:** tool mein video ki saari caption languages apne aap list ho jati hain; Hindi wali ho to Hindi select kar lo.
- **Kuch change karna ho:** GitHub par file edit karo → Render khud redeploy kar dega. Bas `app.py` ko bina test kiye mat chhedna.
