import React from 'react';
import { Cpu, Globe, Shield, Command, Zap } from 'lucide-react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { useStore } from '@/store/useStore';

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

export const Header: React.FC = () => {
  const isApiOnline = useStore((state) => state.isApiOnline);

  return (
    <header className="flex items-center justify-between px-8 py-4 border-b border-border/50 glass sticky top-0 z-50">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
          <Cpu className="text-primary-foreground w-6 h-6" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight">Agentic Engineering System</h1>
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">Autonomous Infrastructure & Rework</p>
        </div>
      </div>

      <nav className="flex items-center gap-6">
        <TooltipWrapper content="Access the system documentation and API reference.">
          <a href="https://docs.google.com/document/d/1ML5sNYow-XRYYWdhBKEubGS9xUVwBZTSzVks2rOPJ7U/edit?tab=t.0#heading=h.2xldkyfci0bm" target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
            <Command className="w-4 h-4" /> Docs
          </a>
        </TooltipWrapper>
        <TooltipWrapper content="View the core service source code on GitHub.">
          <a href="#" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
            <Globe className="w-4 h-4" /> Repo
          </a>
        </TooltipWrapper>
        <div className="w-px h-4 bg-border/50 mx-2" />
        <TooltipWrapper content={isApiOnline ? "Gateway connection status with the orchestration backend." : "Backend is currently unreachable."}>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border cursor-help transition-all duration-500 ${
            isApiOnline 
              ? 'bg-green-500/10 border-green-500/20' 
              : 'bg-destructive/10 border-destructive/20'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              isApiOnline 
                ? 'bg-green-500 animate-pulse' 
                : 'bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.5)]'
            }`} />
            <span className={`text-[11px] font-bold ${
              isApiOnline ? 'text-green-400' : 'text-red-400'
            }`}>
              {isApiOnline ? 'API ONLINE' : 'API OFFLINE'}
            </span>
          </div>
        </TooltipWrapper>
      </nav>
    </header>
  );
};
