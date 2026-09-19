import React, { useEffect } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ type = 'info', message, onClose, duration = 4000 }) {
  useEffect(() => {
    if (duration && onClose) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  if (!message) return null;

  const styles = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800 icon-emerald-600',
    error: 'bg-red-50 border-red-200 text-red-800 icon-red-600',
    warning: 'bg-amber-50 border-amber-200 text-amber-800 icon-amber-600',
    info: 'bg-blue-50 border-blue-200 text-blue-800 icon-blue-600',
  };

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />,
    error: <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" />,
    info: <Info className="w-5 h-5 text-blue-600 flex-shrink-0" />,
  };

  return (
    <div className={`fixed bottom-5 right-5 z-50 flex items-center space-x-3 px-4 py-3 rounded-xl border shadow-lg max-w-md transition-all animate-slide-up ${styles[type] || styles.info}`}>
      {icons[type] || icons.info}
      <div className="text-xs font-medium flex-1">{message}</div>
      {onClose && (
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
