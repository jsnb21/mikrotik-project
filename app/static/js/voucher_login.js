// Show initial notification
window.onload = function() {
    notifyInfo('WiFi Portal', 'Enter your voucher code to access the internet');
    
    const debugDiv = document.getElementById('debugInfo');
    const currentUrl = window.location.href;
    const testUrl = window.location.origin + '/test';
    debugDiv.innerHTML = '<strong>Debug Info:</strong><br>' +
        'Current URL: ' + currentUrl + '<br>' +
        'Test endpoint: ' + testUrl + '<br>' +
        'Time: ' + new Date().toLocaleTimeString();
    
    // Add form submission listener
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function() {
            const code = document.getElementById('voucher_code').value;
            notifyInfo('Processing', `Validating code: ${code}...`);
        });
    }
};

function testConnection() {
    const btn = document.getElementById('testConnectionBtn');
    const resultDiv = document.getElementById('testResult');
    const debugDiv = document.getElementById('debugInfo');
    const testUrl = window.location.origin + '/test';
    
    // Disable button and show loading
    btn.disabled = true;
    btn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Testing...';
    resultDiv.innerHTML = '';
    
    notifyInfo('Testing', 'Checking connection to server...');
    
    debugDiv.innerHTML = '<strong>Requesting:</strong> ' + testUrl + '<br>Status: Sending...<br>Method: POST';
    
    // Make AJAX request to test endpoint
    fetch(testUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: 'Hello from phone!',
            timestamp: new Date().toISOString()
        }),
        cache: 'no-cache'
    })
    .then(response => {
        debugDiv.innerHTML += '<br>Status Code: ' + response.status + '<br>Status Text: ' + response.statusText + '<br>Content-Type: ' + response.headers.get('content-type');
        
        // Get response as text first to see what we actually got
        return response.text().then(text => {
            debugDiv.innerHTML += '<br>Response (first 200 chars): ' + text.substring(0, 200);
            
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + text.substring(0, 100));
            }
            
            // Try to parse as JSON
            try {
                return JSON.parse(text);
            } catch (e) {
                throw new Error('Response is not JSON: ' + text.substring(0, 100));
            }
        });
    })
    .then(data => {
        // Success!
        resultDiv.innerHTML = '<div class="result-success">Success: ' + data.message + '<br><small>Your IP: ' + data.client_ip + '</small></div>';
        debugDiv.innerHTML += '<br><strong style="color: green;">SUCCESS!</strong>';
        notifySuccess('Connected', 'Server is responding correctly!');
    })
    .catch(error => {
        // Error
        resultDiv.innerHTML = '<div class="result-error">Error: ' + error.message + '</div>';
        debugDiv.innerHTML += '<br><strong style="color: red;">ERROR: ' + error.message + '</strong>';
        notifyError('Connection Failed', error.message);
    })
    .finally(() => {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>Test Connection (AJAX)';
    });
}
