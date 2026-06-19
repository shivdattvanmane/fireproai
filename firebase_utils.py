"""
Firebase Utilities — Auth + Firestore
Modes (auto-detected):
  1. Full mode  — serviceAccountKey.json present → full token verification
  2. JWT mode   — no service account → decodes JWT without verification (still works)
  3. Demo mode  — idToken == "demo-token" → bypasses Firebase entirely
"""

import os, json, base64, time
from datetime import datetime
from typing import Optional, Tuple

# ── Globals ───────────────────────────────────────────────────────────────────
FIREBASE_FULL      = False   # Admin SDK with service account
FIREBASE_JWT_ONLY  = False   # Admin SDK installed but no service account
_db                = None
FIRESTORE_AVAILABLE = False
_local_detections: list[dict] = []

# ── Try to load Firebase Admin SDK ────────────────────────────────────────────
_CRED_PATH = os.environ.get("FIREBASE_CRED", "serviceAccountKey.json")

try:
    import firebase_admin
    from firebase_admin import credentials, auth as fb_auth, firestore

    if not firebase_admin._apps:
        if os.path.exists(_CRED_PATH):
            # ── FULL MODE ─────────────────────────────────────────────────────
            firebase_admin.initialize_app(credentials.Certificate(_CRED_PATH))
            FIREBASE_FULL = True
            print(f"✅ Firebase FULL mode — service account: {_CRED_PATH}")
        else:
            # ── JWT-ONLY MODE — do NOT call initialize_app without creds ──────
            # Calling initialize_app() without credentials causes verify_id_token
            # to crash. Instead we skip admin init and decode JWT manually.
            FIREBASE_JWT_ONLY = True
            print(f"⚠️  No serviceAccountKey.json found at '{_CRED_PATH}'")
            print("   → JWT-decode mode: tokens decoded but not cryptographically verified")
    else:
        FIREBASE_FULL = True   # already initialised elsewhere

    # Firestore only works in full mode
    if FIREBASE_FULL:
        try:
            _db = firestore.client()
            FIRESTORE_AVAILABLE = True
            print("✅ Firestore connected")
        except Exception as fe:
            print(f"⚠️  Firestore unavailable: {fe}")

except ImportError:
    print("⚠️  firebase-admin not installed → demo/local mode only")
except Exception as e:
    print(f"⚠️  Firebase init error: {e}")


# ── JWT payload decoder (no signature check) ──────────────────────────────────
def _decode_jwt(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        pad     = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(pad)
        return json.loads(decoded)
    except Exception as e:
        print(f"JWT decode error: {e}")
        return {}


# ── Main auth function ─────────────────────────────────────────────────────────
def verify_firebase_token(id_token: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (uid, email, error). error is None on success."""

    # ── Demo mode ─────────────────────────────────────────────────────────────
    if id_token == "demo-token":
        print("✅ Demo login accepted")
        return "demo-uid", "admin@demo.com", None

    # ── Full mode (service account present) ───────────────────────────────────
    if FIREBASE_FULL:
        try:
            decoded = fb_auth.verify_id_token(id_token)
            uid     = decoded.get("uid",   "unknown")
            email   = decoded.get("email", "unknown@unknown.com")
            print(f"✅ Token verified — {email}")
            return uid, email, None
        except fb_auth.ExpiredIdTokenError:
            return None, None, "Token expired. Please login again."
        except fb_auth.RevokedIdTokenError:
            return None, None, "Token revoked. Please login again."
        except fb_auth.InvalidIdTokenError as e:
            return None, None, f"Invalid token: {e}"
        except Exception as e:
            print(f"Full verify failed: {e} → falling back to JWT decode")
            # fall through to JWT decode below

    # ── JWT-decode fallback ────────────────────────────────────────────────────
    payload = _decode_jwt(id_token)
    if not payload:
        return None, None, (
            "Could not read token. Make sure your Firebase config in login.html "
            "is correct and the user exists in Firebase Authentication."
        )

    # Check expiry
    if payload.get("exp", 0) < time.time():
        return None, None, "Token expired. Please login again."

    uid   = payload.get("user_id") or payload.get("sub") or "unknown"
    email = payload.get("email")   or "admin@firepro.com"
    print(f"ℹ️  JWT decoded (unverified) — {email}")
    return uid, email, None


# ── Firestore / local write ───────────────────────────────────────────────────
def save_detection_to_firestore(alert: dict) -> Optional[str]:
    record = {
        "label":     alert.get("label",     "unknown"),
        "conf":      alert.get("conf",      0.0),
        "severity":  alert.get("severity",  "MEDIUM"),
        "source":    alert.get("source",    ""),
        "timestamp": alert.get("timestamp", datetime.now().isoformat()),
        "date":      alert.get("date",      datetime.now().strftime("%Y-%m-%d")),
        "time":      alert.get("time",      datetime.now().strftime("%H:%M:%S")),
        "bbox":      alert.get("bbox",      []),
    }
    if FIRESTORE_AVAILABLE and _db:
        try:
            record["created_at"] = firestore.SERVER_TIMESTAMP
            ref = _db.collection("detections").add(record)
            return ref[1].id
        except Exception as e:
            print(f"Firestore write error: {e}")
    _local_detections.append({**record, "created_at": time.time()})
    return f"local-{len(_local_detections)}"


# ── History read ──────────────────────────────────────────────────────────────
def get_detection_history(limit: int = 100, label_filter: Optional[str] = None) -> list[dict]:
    if FIRESTORE_AVAILABLE and _db:
        try:
            q = _db.collection("detections").order_by(
                "created_at", direction=firestore.Query.DESCENDING
            )
            if label_filter:
                q = q.where("label", "==", label_filter)
            records = []
            for doc in q.limit(limit).stream():
                d = doc.to_dict(); d["id"] = doc.id
                if hasattr(d.get("created_at"), "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                records.append(d)
            return records
        except Exception as e:
            print(f"Firestore read error: {e}")
    records = list(reversed(_local_detections))
    if label_filter:
        records = [r for r in records if r.get("label") == label_filter]
    return records[:limit]


# ── Stats ─────────────────────────────────────────────────────────────────────
def get_stats_summary() -> dict:
    records = get_detection_history(limit=10000)
    lc, sc, dc = {}, {}, {}
    for r in records:
        l = r.get("label","?"); s = r.get("severity","MEDIUM"); d = r.get("date","?")
        lc[l] = lc.get(l,0)+1; sc[s] = sc.get(s,0)+1; dc[d] = dc.get(d,0)+1
    return {
        "total":           len(records),
        "high_priority":   sc.get("HIGH",   0),
        "medium":          sc.get("MEDIUM", 0),
        "top_labels":      [{"label":k,"count":v} for k,v in sorted(lc.items(),key=lambda x:-x[1])[:10]],
        "timeline":        [{"date":k,"count":v}  for k,v in list(sorted(dc.items()))[-7:]],
        "label_counts":    lc,
        "severity_counts": sc,
    }
