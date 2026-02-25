/**
 * Toast Notification Utility
 * Provides user-friendly error and success messages
 */

// Notification container styles
const containerStyles = {
  'top-right': {
    position: 'fixed',
    top: '20px',
    right: '20px',
    zIndex: 10000,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    maxWidth: '400px',
  },
  'bottom-center': {
    position: 'fixed',
    bottom: '20px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 10000,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    width: 'min(480px, calc(100% - 40px))',
  },
  'bottom-left': {
    position: 'fixed',
    bottom: '20px',
    left: '20px',
    zIndex: 10000,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    width: 'min(480px, calc(100% - 40px))',
  },
  'bottom-right': {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    zIndex: 10000,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    width: 'min(480px, calc(100% - 40px))',
  },
};

// Toast styles by type
const toastStyles = {
  base: {
    padding: '16px 20px',
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    fontSize: '14px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    animation: 'slideIn 0.3s ease-out',
    cursor: 'pointer',
    transition: 'opacity 0.2s ease',
  },
  error: {
    backgroundColor: '#fee',
    borderLeft: '4px solid #dc2626',
    color: '#991b1b',
  },
  success: {
    backgroundColor: '#d1fae5',
    borderLeft: '4px solid #10b981',
    color: '#065f46',
  },
  warning: {
    backgroundColor: '#fef3c7',
    borderLeft: '4px solid #f59e0b',
    color: '#92400e',
  },
  info: {
    backgroundColor: '#dbeafe',
    borderLeft: '4px solid #3b82f6',
    color: '#1e40af',
  },
};

// Icons
const icons = {
  error: '❌',
  success: '✅',
  warning: '⚠️',
  info: 'ℹ️',
};

// Create or get container
function getContainer(position = 'top-right') {
  const containerId = `toast-container-${position}`;
  let container = document.getElementById(containerId);
  if (!container) {
    container = document.createElement('div');
    container.id = containerId;
    Object.assign(container.style, containerStyles[position] || containerStyles['top-right']);
    document.body.appendChild(container);
    
    // Add animation keyframes
    if (!document.getElementById('toast-animations')) {
      const style = document.createElement('style');
      style.id = 'toast-animations';
      style.textContent = `
        @keyframes slideIn {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        @keyframes slideOut {
          from {
            transform: translateX(0);
            opacity: 1;
          }
          to {
            transform: translateX(100%);
            opacity: 0;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }
  return container;
}

// Show toast
function showToast(message, type = 'info', duration = 5000, options = {}) {
  const container = getContainer(options.position);
  const toast = document.createElement('div');
  
  // Apply styles
  Object.assign(toast.style, toastStyles.base, toastStyles[type]);
  
  // Set content
  toast.innerHTML = `
    <span style="fontSize: 18px">${icons[type]}</span>
    <span style="flex: 1">${message}</span>
    <span style="opacity: 0.6; fontWeight: bold">×</span>
  `;
  
  // Add to container
  container.appendChild(toast);
  
  // Remove on click
  const remove = () => {
    toast.style.animation = 'slideOut 0.3s ease-in';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  };
  
  toast.addEventListener('click', remove);
  
  // Auto-remove after duration
  if (duration > 0) {
    setTimeout(remove, duration);
  }
  
  return toast;
}

// Convenience methods
export const toast = {
  error: (message, duration, options) => showToast(message, 'error', duration, options),
  success: (message, duration, options) => showToast(message, 'success', duration, options),
  warning: (message, duration, options) => showToast(message, 'warning', duration, options),
  info: (message, duration, options) => showToast(message, 'info', duration, options),
};

// Error handler for API calls
export function handleApiError(error) {
  console.error('API Error:', error);
  
  // Extract user-friendly message
  let message = 'An unexpected error occurred. Please try again.';
  
  if (error?.message) {
    message = error.message;
  } else if (error?.error) {
    message = error.error;
  } else if (typeof error === 'string') {
    message = error;
  }
  
  // Show error toast
  toast.error(message);
  
  return message;
}

// Success handler
export function handleApiSuccess(message, options) {
  toast.success(message, undefined, options);
}

export default toast;
