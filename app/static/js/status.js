// Format seconds to readable format (d h m s)
function formatTime(seconds) {
  if (seconds <= 0) return "0s";
  
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
  
  return parts.join(' ');
}

// Poll API to update remaining seconds
function initializeStatusPage(code, isDeveloper) {
  const countdownEl = document.getElementById('countdown');
  const expiryEl = document.getElementById('expiry');

  function fetchStatus() {
    // Skip polling for developer codes
    if (isDeveloper) return;
    
    fetch(`/api/status/${code}`)
      .then(r => r.json())
      .then(data => {
        const secs = data.remaining_seconds || 0;
        countdownEl.textContent = formatTime(secs);
        if (data.expiry_time) expiryEl.textContent = 'Expires: ' + new Date(data.expiry_time).toLocaleString();
        if (!data.active || secs <= 0) {
          // Session expired — update UI
          countdownEl.classList.remove('text-green-600');
          countdownEl.classList.add('text-red-600');
        }
      })
      .catch(err => console.error('status fetch error', err));
  }

  // Start polling every 2 seconds (only for non-developer codes)
  if (!isDeveloper) {
    fetchStatus();
    setInterval(fetchStatus, 2000);
  }
}
