"use client";

import React from 'react';
import { AlertTriangle, DatabaseZap, RefreshCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ErrorState({ message, onRetry }: { message: string, onRetry?: () => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
       <div className="size-16 bg-rose-500/10 border border-rose-500/20 rounded-2xl flex items-center justify-center mb-6">
         <AlertTriangle className="size-8 text-rose-500" />
       </div>
       <h3 className="text-xl font-bold uppercase italic tracking-tighter mb-2">System Analysis Interrupted</h3>
       <p className="text-sm text-slate-400 max-w-xs mb-8">{message}</p>
       {onRetry && (
         <button 
           onClick={onRetry}
           className="flex items-center gap-2 px-6 py-2 bg-rose-500 text-black text-xs font-black uppercase italic rounded-lg hover:bg-rose-400 transition-colors"
         >
           <RefreshCcw className="size-3" />
           Restart Diagnostic
         </button>
       )}
    </div>
  );
}

export function EmptyState({ message, icon }: { message: string, icon?: React.ReactNode }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center opacity-50">
       <div className="size-16 bg-slate-500/10 border border-slate-500/20 rounded-2xl flex items-center justify-center mb-6">
         {icon || <DatabaseZap className="size-8 text-slate-400" />}
       </div>
       <h3 className="text-lg font-bold uppercase italic tracking-tighter mb-2">No Active Data Stream</h3>
       <p className="text-sm text-slate-400 max-w-xs">{message}</p>
    </div>
  );
}
