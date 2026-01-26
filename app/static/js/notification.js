/**
 * Notification system for user feedback
 */

function createNotificationContainer() {
  if (!document.getElementById('notificationContainer')) {
    const container = document.createElement('div');
    container.id = 'notificationContainer';
    container.className = 'notification-container';
    document.body.appendChild(container);
  }
  return document.getElementById('notificationContainer');
}

function showNotification(title, message, type = 'info', duration = 5000) {
  const container = createNotificationContainer();
  
  const icons = {
    info: 'i',
    success: 'OK',
    warning: '!',
    error: 'X'
  };
  
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
    <div class="notification-icon">${icons[type]}</div>
    <div class="notification-content">
      <div class="notification-title">${title}</div>
      <div class="notification-message">${message}</div>
    </div>
    <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
  `;
  
  container.appendChild(notification);
  
  // Auto-remove after duration (unless user closes it)
  if (duration > 0) {
    setTimeout(() => {
      if (notification.parentElement) {
        notification.classList.add('hide');
        setTimeout(() => notification.remove(), 300);
      }
    }, duration);
  }
  
  return notification;
}

// Convenience functions
function notifyInfo(title, message) { return showNotification(title, message, 'info'); }
function notifySuccess(title, message) { return showNotification(title, message, 'success'); }
function notifyWarning(title, message) { return showNotification(title, message, 'warning'); }
function notifyError(title, message) { return showNotification(title, message, 'error'); }
