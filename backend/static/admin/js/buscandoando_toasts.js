/**
 * BuscandoAndo Admin — Toast Notifications
 * Shows success/error messages as popup toasts.
 */
(function() {
  document.addEventListener('DOMContentLoaded', function() {

    // Inject toast CSS
    const style = document.createElement('style');
    style.textContent = `
      .ba-toast-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 100000;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 420px;
      }
      .ba-toast {
        padding: 14px 20px;
        border-radius: 8px;
        font-family: var(--font, 'Segoe UI', sans-serif);
        font-size: 14px;
        font-weight: 600;
        color: #fff;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        display: flex;
        align-items: flex-start;
        gap: 10px;
        animation: ba-slide-in 0.3s ease;
        cursor: pointer;
        line-height: 1.4;
      }
      .ba-toast--success { background: #16a34a; border-left: 4px solid #22c55e; }
      .ba-toast--error   { background: #dc2626; border-left: 4px solid #ef4444; }
      .ba-toast--warning { background: #b45309; border-left: 4px solid #f59e0b; }
      .ba-toast--info    { background: #1d4ed8; border-left: 4px solid #3b82f6; }
      .ba-toast__icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
      .ba-toast__body { flex: 1; }
      .ba-toast__title { font-weight: 800; margin-bottom: 2px; }
      .ba-toast__detail { font-weight: 400; opacity: 0.9; font-size: 13px; }
      .ba-toast__close {
        background: none; border: none; color: #fff; font-size: 18px;
        cursor: pointer; opacity: 0.7; padding: 0 0 0 8px; line-height: 1;
      }
      .ba-toast__close:hover { opacity: 1; }
      @keyframes ba-slide-in {
        from { transform: translateX(100%); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
      @keyframes ba-slide-out {
        from { transform: translateX(0);    opacity: 1; }
        to   { transform: translateX(100%); opacity: 0; }
      }
    `;
    document.head.appendChild(style);

    // Create toast container
    const container = document.createElement('div');
    container.className = 'ba-toast-container';
    document.body.appendChild(container);

    function showToast(type, title, detail, duration) {
      duration = duration || 5000;
      const icons = {
        success: '&#10003;',
        error: '&#10007;',
        warning: '&#9888;',
        info: '&#8505;'
      };
      const toast = document.createElement('div');
      toast.className = 'ba-toast ba-toast--' + type;
      toast.innerHTML =
        '<span class="ba-toast__icon">' + (icons[type] || '') + '</span>' +
        '<div class="ba-toast__body">' +
          '<div class="ba-toast__title">' + title + '</div>' +
          (detail ? '<div class="ba-toast__detail">' + detail + '</div>' : '') +
        '</div>' +
        '<button class="ba-toast__close">&times;</button>';

      toast.querySelector('.ba-toast__close').addEventListener('click', function() {
        dismissToast(toast);
      });
      toast.addEventListener('click', function() {
        dismissToast(toast);
      });

      container.appendChild(toast);

      if (duration > 0) {
        setTimeout(function() { dismissToast(toast); }, duration);
      }
    }

    function dismissToast(toast) {
      if (toast._dismissing) return;
      toast._dismissing = true;
      toast.style.animation = 'ba-slide-out 0.3s ease forwards';
      setTimeout(function() { toast.remove(); }, 300);
    }

    // --- 1. Show Django messages as toasts ---
    const djangoMsgs = document.querySelectorAll('.messagelist .success, .messagelist .error, .messagelist .warning, .messagelist .info');
    djangoMsgs.forEach(function(el) {
      let type = 'info';
      if (el.classList.contains('success')) type = 'success';
      else if (el.classList.contains('error')) type = 'error';
      else if (el.classList.contains('warning')) type = 'warning';

      const text = el.textContent.trim();
      // Try to extract location hint from error messages
      let detail = '';
      const fieldMatch = text.match(/field[s]?\s+([\w_,\s]+)/i) || text.match(/ campo[s]?\s+([\w_,\s]+)/i);
      if (fieldMatch) {
        detail = 'Campo: ' + fieldMatch[1].trim();
      }
      showToast(type, type === 'success' ? 'Guardado' : type === 'error' ? 'Error' : 'Aviso', detail || text, 6000);
      el.style.display = 'none';
    });

    // Hide the default message list container
    const msgList = document.querySelector('.messagelist');
    if (msgList) msgList.style.display = 'none';

    // --- 2. Intercept form submissions ---
    const forms = document.querySelectorAll('#content-main form');
    forms.forEach(function(form) {
      form.addEventListener('submit', function(e) {
        // Show saving indicator
        showToast('info', 'Guardando...', '', 0);
      });
    });

    // --- 3. Watch for errors after page load (validation errors) ---
    const errorList = document.querySelectorAll('.errornote, .error');
    errorList.forEach(function(el) {
      const text = el.textContent.trim();
      if (text) {
        showToast('error', 'Error de validacion', text, 8000);
        el.style.display = 'none';
      }
    });

    // --- 4. Watch for inline form errors ---
    const inlineErrors = document.querySelectorAll('.inline-group .errors, .inline-group .error');
    inlineErrors.forEach(function(el) {
      const text = el.textContent.trim();
      if (text) {
        showToast('error', 'Error en formulario', text, 8000);
      }
    });

  });
})();
