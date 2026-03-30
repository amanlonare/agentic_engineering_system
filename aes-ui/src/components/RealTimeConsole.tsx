import React, { useEffect, useRef } from 'react';
import { useStore } from '@/store/useStore';
import { Terminal, Copy, Trash2, Maximize2, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as Tooltip from '@radix-ui/react-tooltip';

const TooltipWrapper: React.FC<{ children: React.ReactNode; content: string }> = ({ children, content }) => (
  <Tooltip.Provider delayDuration={300}>
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        {children}
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          className="bg-popover text-popover-foreground px-3 py-2 rounded-lg text-xs shadow-xl border border-border max-w-[200px] animate-in zoom-in-95 duration-200 z-50"
          sideOffset={5}
        >
          {content}
          <Tooltip.Arrow className="fill-border" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  </Tooltip.Provider>
);

export const RealTimeConsole: React.FC = () => {
  const { logs, status, clearLogs } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const copyLogs = () => {
    navigator.clipboard.writeText(logs.join('\n'));
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'running': return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'completed': return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'error': return <AlertCircle className="w-4 h-4 text-red-400" />;
      default: return <Terminal className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const formatLog = (log: string) => {
    // Basic log coloring: [INFO], [WARN], [ERROR]
    const lower = log.toLowerCase();
    if (lower.includes('error')) return 'text-red-400';
    if (lower.includes('warn')) return 'text-yellow-400';
    if (lower.includes('success')) return 'text-green-400';
    if (lower.includes('info')) return 'text-blue-300';
    return 'text-muted-foreground';
  };

  return (
    <div className="flex flex-col h-full glass rounded-2xl border border-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-muted/20 border-b border-border/50">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-sm font-medium tracking-tight h-5">Real-Time Console</span>
          {status === 'running' && (
            <span className="text-[10px] uppercase tracking-widest font-bold text-blue-400 animate-pulse ml-2 px-1.5 py-0.5 rounded border border-blue-400/20 bg-blue-400/5">
              Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <TooltipWrapper content="Copy all console logs to clipboard.">
            <button onClick={copyLogs} className="p-1.5 hover:bg-white/5 rounded-lg transition-colors text-muted-foreground hover:text-primary">
              <Copy className="w-4 h-4" />
            </button>
          </TooltipWrapper>
          <TooltipWrapper content="Clear the console log stream.">
            <button onClick={clearLogs} className="p-1.5 hover:bg-white/5 rounded-lg transition-colors text-muted-foreground hover:text-primary">
              <Trash2 className="w-4 h-4" />
            </button>
          </TooltipWrapper>
          <div className="w-px h-4 bg-border/50 mx-1" />
          <TooltipWrapper content="Toggle fullscreen view of the terminal.">
            <button className="p-1.5 hover:bg-white/5 rounded-lg transition-colors text-muted-foreground hover:text-primary">
              <Maximize2 className="w-4 h-4" />
            </button>
          </TooltipWrapper>
        </div>
      </div>

      {/* Terminal Content */}
      <div 
        ref={scrollRef}
        className="flex-1 p-4 font-mono text-xs overflow-y-auto bg-black/40 selection:bg-primary/20"
      >
        <AnimatePresence mode="popLayout">
          {logs.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-full flex flex-col items-center justify-center text-muted-foreground/30 gap-3"
            >
              <Terminal className="w-8 h-8 opacity-20" />
              <p className="text-sm">Waitng for execution start...</p>
            </motion.div>
          ) : (
            logs.map((log, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.1 }}
                className="py-0.5 leading-relaxed break-all"
              >
                <span className="text-muted-foreground font-bold mr-2 select-none opacity-50">{i + 1}</span>
                <span className={formatLog(log)}>{log}</span>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Footer / Summary Area */}
      {status === 'completed' && (
        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="p-4 bg-green-500/5 border-t border-green-500/20"
        >
          <div className="flex items-center gap-2 text-green-400 text-sm font-semibold mb-2">
            <CheckCircle2 className="w-4 h-4" /> Execution Summary
          </div>
          <div className="text-sm text-foreground/80 leading-relaxed bg-black/20 p-3 rounded-lg border border-white/5">
            The changes have been successfully implemented and verified. Pull request created on branch: 
            <span className="text-primary font-mono ml-2 underline cursor-pointer hover:text-white transition-colors">feature/auth-refactor</span>
          </div>
        </motion.div>
      )}
    </div>
  );
};
