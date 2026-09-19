import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function PaginationControls({ page, totalPages, totalItems, limit, onPageChange }) {
  if (totalPages <= 1 && totalItems <= limit) return null;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between pt-4 border-t border-slate-200 text-xs text-slate-500 gap-3">
      <div className="font-medium">
        Showing page <span className="font-extrabold text-slate-900">{page}</span> of{' '}
        <span className="font-extrabold text-slate-900">{totalPages}</span> ({totalItems} total items)
      </div>

      <div className="flex items-center space-x-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-3.5 py-1.5 bg-white hover:bg-slate-50 text-slate-700 font-bold rounded-xl flex items-center space-x-1 border border-slate-200 transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="w-4 h-4" />
          <span>Previous</span>
        </button>

        <span className="px-3 py-1.5 bg-slate-100 border border-slate-200 rounded-xl font-mono font-bold text-slate-800">
          {page} / {totalPages}
        </span>

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-3.5 py-1.5 bg-white hover:bg-slate-50 text-slate-700 font-bold rounded-xl flex items-center space-x-1 border border-slate-200 transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span>Next</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
