// Minimal Phantom (Solana) wallet connect and signature verification flow.
function getCsrfToken() {
  const el = document.querySelector('meta[name="csrf-token"]');
  return el ? el.getAttribute('content') : '';
}

async function connectPhantom() {
  if (!window.solana || !window.solana.isPhantom) {
    alert('Phantom wallet not found. Please install Phantom or use a Solana wallet.');
    return;
  }

  try {
    // Request connection
    const resp = await window.solana.connect();
    const pubKey = resp.publicKey; // PublicKey object

    // Request a challenge from server
    const c = await fetch('/wallet/challenge');
    const payload = await c.json();
    const challengeB64 = payload.challenge;
    const challengeBytes = Uint8Array.from(atob(challengeB64), c => c.charCodeAt(0));

    // Ask the wallet to sign the challenge
    const signed = await window.solana.signMessage(challengeBytes, 'utf8');

    // Prepare base64-encoded payload to send to server
    const sigB64 = btoa(String.fromCharCode(...signed.signature));
    const pubB64 = btoa(String.fromCharCode(...pubKey.toBytes()));

    const verify = await fetch('/wallet/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ public_key: pubB64, signature: sigB64 })
    });

    const result = await verify.json();
    if (result && result.success) {
      const el = document.getElementById('connect-wallet');
      if (el) el.innerText = pubKey.toString();
      alert('Wallet connected: ' + pubKey.toString());
    } else {
      alert('Wallet verification failed');
    }

  } catch (err) {
    console.error(err);
    alert('Wallet connection error: ' + (err.message || err));
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('connect-wallet');
  if (btn) btn.addEventListener('click', connectPhantom);
});

// Helper: expose for console
window.connectPhantom = connectPhantom;
