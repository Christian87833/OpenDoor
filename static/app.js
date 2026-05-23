// ── Base64url helpers ──────────────────────────────────────────────────────────

function b64urlToBuffer(b64url) {
  const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(b64);
  const buf = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) buf[i] = binary.charCodeAt(i);
  return buf.buffer;
}

function bufferToB64url(buf) {
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

// ── WebAuthn: registration ─────────────────────────────────────────────────────

async function registerDevice(deviceName) {
  const optionsRaw = await fetch("/api/register/begin").then(r => r.json());

  // Convert binary fields to ArrayBuffer
  optionsRaw.challenge = b64urlToBuffer(optionsRaw.challenge);
  optionsRaw.user.id   = b64urlToBuffer(optionsRaw.user.id);
  if (optionsRaw.excludeCredentials) {
    optionsRaw.excludeCredentials = optionsRaw.excludeCredentials.map(c => ({
      ...c, id: b64urlToBuffer(c.id),
    }));
  }

  const credential = await navigator.credentials.create({ publicKey: optionsRaw });

  // Serialize back to base64url for the server
  const body = {
    deviceName,
    id:    credential.id,
    rawId: bufferToB64url(credential.rawId),
    type:  credential.type,
    response: {
      clientDataJSON:    bufferToB64url(credential.response.clientDataJSON),
      attestationObject: bufferToB64url(credential.response.attestationObject),
    },
  };

  const res = await fetch("/api/register/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Registrierung fehlgeschlagen");
  return await res.json();
}

// ── WebAuthn: authentication + open door ──────────────────────────────────────

async function openDoor() {
  const optionsRaw = await fetch("/api/auth/begin").then(async r => {
    if (!r.ok) throw new Error((await r.json()).detail || "Keine registrierten Geräte");
    return r.json();
  });

  optionsRaw.challenge = b64urlToBuffer(optionsRaw.challenge);
  if (optionsRaw.allowCredentials) {
    optionsRaw.allowCredentials = optionsRaw.allowCredentials.map(c => ({
      ...c, id: b64urlToBuffer(c.id),
    }));
  }

  const assertion = await navigator.credentials.get({ publicKey: optionsRaw });

  const body = {
    id:    assertion.id,
    rawId: bufferToB64url(assertion.rawId),
    type:  assertion.type,
    response: {
      clientDataJSON:    bufferToB64url(assertion.response.clientDataJSON),
      authenticatorData: bufferToB64url(assertion.response.authenticatorData),
      signature:         bufferToB64url(assertion.response.signature),
      userHandle: assertion.response.userHandle
        ? bufferToB64url(assertion.response.userHandle) : null,
    },
  };

  const res = await fetch("/api/auth/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Authentifizierung fehlgeschlagen");
  return await res.json();
}

// ── Device list ───────────────────────────────────────────────────────────────

async function loadDevices() {
  const devices = await fetch("/api/devices").then(r => r.json());
  const list = document.getElementById("device-list");

  if (!devices.length) {
    list.innerHTML = '<p id="no-devices">Keine Geräte registriert.</p>';
    return;
  }

  list.innerHTML = devices.map((d, i) => `
    <div class="device-item">
      <div>
        <div class="device-name">${escapeHtml(d.name)}</div>
        <div class="device-date">${new Date(d.created_at).toLocaleDateString("de-DE")}</div>
      </div>
      <button class="btn-del" data-index="${i}" title="Gerät entfernen">&#x2715;</button>
    </div>
  `).join("");

  list.querySelectorAll(".btn-del").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm(`Gerät entfernen?`)) return;
      await fetch(`/api/devices/${btn.dataset.index}`, { method: "DELETE" });
      loadDevices();
    });
  });
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── UI wiring ─────────────────────────────────────────────────────────────────

const btnOpen     = document.getElementById("btn-open");
const statusEl    = document.getElementById("status");
const btnRegister = document.getElementById("btn-register");
const regStatusEl = document.getElementById("reg-status");

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className   = type;
}

function setRegStatus(msg, type = "") {
  regStatusEl.textContent = msg;
  regStatusEl.className   = type;
}

btnOpen.addEventListener("click", async () => {
  btnOpen.disabled = true;
  setStatus("Warte auf Bestätigung…");
  btnOpen.className = "";

  try {
    const result = await openDoor();
    btnOpen.classList.add("success");
    setStatus(result.message, "ok");
  } catch (err) {
    btnOpen.classList.add("error");
    if (err.name === "NotAllowedError") {
      setStatus("Abgebrochen oder biometrische Prüfung fehlgeschlagen.", "err");
    } else {
      setStatus(err.message, "err");
    }
  } finally {
    btnOpen.disabled = false;
    setTimeout(() => {
      btnOpen.className = "";
      setStatus("");
    }, 4000);
  }
});

btnRegister.addEventListener("click", async () => {
  const name = document.getElementById("device-name").value.trim() || "Mein Gerät";
  btnRegister.disabled = true;
  setRegStatus("Warte auf biometrische Bestätigung…");

  try {
    const result = await registerDevice(name);
    setRegStatus(`"${result.name}" erfolgreich registriert!`, "ok");
    document.getElementById("device-name").value = "";
    loadDevices();
  } catch (err) {
    if (err.name === "NotAllowedError") {
      setRegStatus("Abgebrochen.", "err");
    } else {
      setRegStatus(err.message, "err");
    }
  } finally {
    btnRegister.disabled = false;
  }
});

document.getElementById("btn-refresh").addEventListener("click", loadDevices);

// Initial load
loadDevices();
