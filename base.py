// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyCD8wfnsghjiWUTPH38w2O4nZQrKWkpvXM",
  authDomain: "firepro-ai.firebaseapp.com",
  projectId: "firepro-ai",
  storageBucket: "firepro-ai.firebasestorage.app",
  messagingSenderId: "791548297288",
  appId: "1:791548297288:web:9ceb5368a744aa717bd87d",
  measurementId: "G-86FMMXK8VD"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);


<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FirePro AI — Admin Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400;600&family=Space+Grotesk:wght@300;400;600&display=swap" rel="stylesheet">

  <!-- Firebase Compat SDK -->
  <script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js"></script>
  <script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-auth-compat.js"></script>

  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #05050d;
      --surface:   #0e0e1e;
      --card:      #141428;
      --border:    #1e1e3f;
      --fire:      #ff4500;
      --fire-glow: #ff6b35;
      --cyan:      #00d4ff;
      --text:      #e8e8f0;
      --muted:     #5a5a7a;
      --green:     #00e676;
      --mono:      'JetBrains Mono', monospace;
      --display:   'Bebas Neue', sans-serif;
      --body:      'Space Grotesk', sans-serif;
    }

    html, body {
      height: 100%; background: var(--bg);
      font-family: var(--body); color: var(--text); overflow: hidden;
    }

    .grid-bg {
      position: fixed; inset: 0; z-index: 0;
      background-image:
        linear-gradient(rgba(255,69,0,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,69,0,.04) 1px, transparent 1px);
      background-size: 60px 60px;
      animation: grid-drift 20s linear infinite;
    }
    @keyframes grid-drift { from{background-position:0 0} to{background-position:60px 60px} }

    .orb { position:fixed; border-radius:50%; filter:blur(120px); pointer-events:none; z-index:0; }
    .orb-1 { width:500px; height:500px; background:rgba(255,69,0,.12); top:-150px; right:-100px; }
    .orb-2 { width:400px; height:400px; background:rgba(0,212,255,.08); bottom:-100px; left:-100px; }

    .page {
      position:relative; z-index:1; min-height:100vh;
      display:flex; align-items:center; justify-content:center; padding:2rem;
    }

    .login-card {
      background:var(--card); border:1px solid var(--border); border-radius:2px;
      padding:3rem 2.5rem; width:100%; max-width:440px;
      box-shadow:0 0 60px rgba(255,69,0,.08), 0 0 120px rgba(0,0,0,.6);
      position:relative; overflow:hidden;
      animation:card-in .6s cubic-bezier(0.22,1,0.36,1) both;
    }
    @keyframes card-in {
      from { opacity:0; transform:translateY(30px) scale(.96); }
      to   { opacity:1; transform:none; }
    }
    .login-card::before {
      content:''; position:absolute; top:0; left:0; right:0; height:2px;
      background:linear-gradient(90deg, var(--fire), var(--fire-glow), var(--cyan));
    }
    .login-card::after {
      content:''; position:absolute; bottom:0; right:0;
      width:40px; height:40px;
      border-right:2px solid var(--fire); border-bottom:2px solid var(--fire);
    }

    .brand { display:flex; align-items:center; gap:.75rem; margin-bottom:2rem; }
    .brand-icon {
      font-size:2.2rem; filter:drop-shadow(0 0 12px rgba(255,69,0,.6));
      animation:flicker 3s infinite;
    }
    @keyframes flicker {
      0%,92%,96%,100%{opacity:1} 93%{opacity:.6} 95%{opacity:.8}
    }
    .brand-name { font-family:var(--display); font-size:2rem; color:var(--fire-glow); line-height:1; }
    .brand-sub  { font-family:var(--mono); font-size:.6rem; color:var(--muted);
                  letter-spacing:.2em; text-transform:uppercase; }

    h2 { font-size:.9rem; font-weight:300; color:var(--muted);
         letter-spacing:.1em; text-transform:uppercase;
         margin-bottom:1.75rem; font-family:var(--mono); }

    .field { margin-bottom:1.1rem; }
    .field label {
      display:block; font-family:var(--mono); font-size:.65rem;
      color:var(--muted); letter-spacing:.15em; text-transform:uppercase; margin-bottom:.4rem;
    }
    .field input {
      width:100%; background:var(--surface); border:1px solid var(--border);
      border-radius:2px; padding:.75rem 1rem; color:var(--text);
      font-family:var(--mono); font-size:.9rem; outline:none;
      transition:border-color .2s, box-shadow .2s;
    }
    .field input:focus { border-color:var(--fire); box-shadow:0 0 0 3px rgba(255,69,0,.12); }
    .field input::placeholder { color:var(--muted); }

    .btn-login {
      width:100%; margin-top:1.25rem;
      background:var(--fire); border:none; border-radius:2px;
      color:#fff; font-family:var(--display); font-size:1.2rem;
      letter-spacing:.1em; padding:.85rem; cursor:pointer;
      position:relative; overflow:hidden; transition:background .2s;
    }
    .btn-login:hover { background:var(--fire-glow); }
    .btn-login:disabled { background:#2a2a2a; cursor:not-allowed; color:#555; }

    .btn-demo {
      display:block; width:100%; margin-top:.6rem;
      background:transparent; border:1px solid var(--border); border-radius:2px;
      color:var(--muted); font-family:var(--mono); font-size:.72rem;
      letter-spacing:.1em; padding:.55rem; cursor:pointer; text-align:center;
      transition:border-color .2s, color .2s;
    }
    .btn-demo:hover { border-color:var(--cyan); color:var(--cyan); }

    /* Messages */
    .msg {
      margin-top:.9rem; padding:.6rem .8rem; border-radius:2px;
      font-family:var(--mono); font-size:.72rem; display:none; word-break:break-word;
      line-height:1.5;
    }
    .msg.show { display:block; }
    .msg.error   { background:rgba(255,68,68,.1); border:1px solid rgba(255,68,68,.3); color:#ff6464; }
    .msg.success { background:rgba(0,230,118,.08); border:1px solid rgba(0,230,118,.25); color:var(--green); }
    .msg.info    { background:rgba(0,212,255,.06); border:1px solid rgba(0,212,255,.2); color:var(--cyan); }

    /* Debug panel */
    .debug-panel {
      margin-top:.75rem; padding:.6rem .8rem; border-radius:2px;
      background:rgba(255,255,255,.03); border:1px solid var(--border);
      font-family:var(--mono); font-size:.6rem; color:var(--muted);
      display:none; max-height:120px; overflow-y:auto; line-height:1.6;
    }
    .debug-panel.show { display:block; }

    /* Status bar */
    .status-bar {
      position:fixed; bottom:0; left:0; right:0; z-index:10;
      background:rgba(5,5,13,.95); border-top:1px solid var(--border);
      padding:.35rem 1.5rem; display:flex; align-items:center; gap:1.5rem;
      font-family:var(--mono); font-size:.58rem; color:var(--muted);
    }
    .sdot {
      width:6px; height:6px; border-radius:50%; background:var(--fire);
      animation:pulse 2s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

    .fb-badge {
      padding:.15rem .5rem; border-radius:999px; border:1px solid; font-size:.55rem;
    }
    .fb-badge.ok    { color:var(--green);  border-color:rgba(0,230,118,.3);  background:rgba(0,230,118,.06); }
    .fb-badge.err   { color:#ff6464;       border-color:rgba(255,68,68,.3);   background:rgba(255,68,68,.06); }
    .fb-badge.wait  { color:var(--muted);  border-color:var(--border); }
  </style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="orb orb-1"></div>
  <div class="orb orb-2"></div>

  <div class="page">
    <div class="login-card">

      <div class="brand">
        <span class="brand-icon">🔥</span>
        <div>
          <div class="brand-name">FIREPRO AI</div>
          <div class="brand-sub">Smart Surveillance System</div>
        </div>
      </div>

      <h2>Admin Authentication</h2>

      <div class="field">
        <label>Email Address</label>
        <input type="email" id="email" placeholder="admin@yourdomain.com" autocomplete="email">
      </div>
      <div class="field">
        <label>Password</label>
        <input type="password" id="password" placeholder="••••••••••" autocomplete="current-password">
      </div>

      <button class="btn-login" id="loginBtn" onclick="doLogin()">AUTHENTICATE</button>
      <button class="btn-demo"  onclick="demoLogin()">⚡ Demo Mode (no Firebase needed)</button>

      <div class="msg error"   id="errMsg"></div>
      <div class="msg success" id="okMsg"></div>
      <div class="msg info"    id="infoMsg"></div>
      <div class="debug-panel" id="debugPanel"></div>
    </div>
  </div>

  <div class="status-bar">
    <div class="sdot"></div>
    <span>FIREPRO AI v2.0</span>
    <span id="fbBadge" class="fb-badge wait">⏳ LOADING…</span>
    <span style="margin-left:auto">localhost:5000</span>
  </div>

  <script>
    // ════════════════════════════════════════════════════════════════
    //   PASTE YOUR FIREBASE CONFIG HERE
    //   Firebase Console → Project Settings → Your apps → Config
    // ════════════════════════════════════════════════════════════════
    const firebaseConfig = {
  apiKey: "AIzaSyCD8wfnsghjiWUTPH38w2O4nZQrKWkpvXM",
  authDomain: "firepro-ai.firebaseapp.com",
  projectId: "firepro-ai",
  storageBucket: "firepro-ai.firebasestorage.app",
  messagingSenderId: "791548297288",
  appId: "1:791548297288:web:9ceb5368a744aa717bd87d",
  measurementId: "G-86FMMXK8VD"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
    // ════════════════════════════════════════════════════════════════

    let auth = null;
    let firebaseReady = false;

    // ── Init Firebase ───────────────────────────────────────────────
    try {
      firebase.initializeApp(firebaseConfig);
      auth = firebase.auth();
      firebaseReady = true;
      setBadge("✅ FIREBASE OK", "ok");
      log("Firebase initialized successfully");
    } catch(e) {
      setBadge("⚠ FIREBASE ERROR", "err");
      log("Firebase init failed: " + e.message);
    }

    // Enter = login
    document.addEventListener("keydown", e => { if(e.key==="Enter") doLogin(); });

    // ── Main Login ──────────────────────────────────────────────────
    async function doLogin() {
      const email    = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const btn      = document.getElementById("loginBtn");

      clearAll();

      if (!email)    { showErr("Please enter your email."); return; }
      if (!password) { showErr("Please enter your password."); return; }

      if (!firebaseReady) {
        showErr("Firebase not initialized. Check your firebaseConfig values above and reload.");
        return;
      }

      btn.disabled    = true;
      btn.textContent = "AUTHENTICATING…";

      try {
        // ── Step 1: Firebase sign in ──────────────────────────────
        log("Step 1: Signing in with Firebase...");
        showInfo("🔐 Signing in with Firebase…");

        const userCred = await auth.signInWithEmailAndPassword(email, password);
        log("Step 1 OK — UID: " + userCred.user.uid);

        // ── Step 2: Get ID token ──────────────────────────────────
        log("Step 2: Getting ID token...");
        showInfo("🔑 Getting session token…");
        const idToken = await userCred.user.getIdToken(true);
        log("Step 2 OK — token length: " + idToken.length);

        // ── Step 3: Send token to Flask backend ───────────────────
        log("Step 3: Sending token to Flask /api/auth/login...");
        showInfo("🌐 Connecting to server…");

        const res = await fetch("/api/auth/login", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ idToken }),
        });

        log("Step 3 — HTTP status: " + res.status);

        // ── Step 4: Parse response ────────────────────────────────
        const text = await res.text();
        log("Step 4 — Raw response: " + text);

        let data = {};
        try { data = JSON.parse(text); } catch(e) { log("JSON parse error: " + e); }

        if (data.success) {
          showOk("✅ Login successful! Redirecting to dashboard…");
          log("Redirecting to /dashboard");
          setTimeout(() => { window.location.href = "/dashboard"; }, 800);
        } else {
          const errMsg = data.error || "Server rejected login (unknown reason)";
          log("Server error: " + errMsg);
          showErr(errMsg + "\n\nTip: Check that serviceAccountKey.json is in E:\\firepro\\");
        }

      } catch(err) {
        log("Caught error — code: " + err.code + " | msg: " + err.message);
        showErr(getFirebaseError(err.code) || err.message);
      } finally {
        btn.disabled    = false;
        btn.textContent = "AUTHENTICATE";
      }
    }

    // ── Demo Login ──────────────────────────────────────────────────
    async function demoLogin() {
      clearAll();
      showInfo("🚀 Connecting in demo mode…");
      try {
        const res  = await fetch("/api/auth/login", {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ idToken: "demo-token" }),
        });
        const data = await res.json();
        if (data.success) {
          showOk("✅ Demo login OK! Redirecting…");
          setTimeout(() => { window.location.href = "/dashboard"; }, 600);
        } else {
          showErr(data.error || "Demo login failed");
        }
      } catch(e) {
        showErr("Cannot reach server: " + e.message);
      }
    }

    // ── Helpers ──────────────────────────────────────────────────────
    function showErr(msg)  { show("errMsg",  msg); }
    function showOk(msg)   { show("okMsg",   msg); }
    function showInfo(msg) { show("infoMsg", msg); }

    function show(id, msg) {
      clearAll();
      const el = document.getElementById(id);
      el.textContent = msg;
      el.classList.add("show");
    }

    function clearAll() {
      ["errMsg","okMsg","infoMsg"].forEach(id =>
        document.getElementById(id).classList.remove("show")
      );
    }

    function log(msg) {
      const p = document.getElementById("debugPanel");
      p.classList.add("show");
      p.innerHTML += `<div>› ${msg}</div>`;
      p.scrollTop = p.scrollHeight;
      console.log("[FirePro]", msg);
    }

    function setBadge(text, cls) {
      const el = document.getElementById("fbBadge");
      el.textContent = text;
      el.className   = "fb-badge " + cls;
    }

    function getFirebaseError(code) {
      const map = {
        "auth/user-not-found":          "No account with this email.",
        "auth/wrong-password":          "Wrong password.",
        "auth/invalid-credential":      "Invalid email or password.",
        "auth/invalid-email":           "Invalid email format.",
        "auth/too-many-requests":       "Too many attempts. Wait a few minutes.",
        "auth/network-request-failed":  "Network error. Check your connection.",
        "auth/user-disabled":           "This account is disabled.",
        "auth/api-key-not-valid":       "Firebase API key is invalid. Re-check your firebaseConfig.",
        "auth/configuration-not-found": "Firebase project not configured properly.",
      };
      return map[code] || null;
    }
  </script>
</body>
</html>
