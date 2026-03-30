'use client';

import React from 'react';
import { Header } from '@/components/Header';
import { ConfigPanel } from '@/components/ConfigPanel';
import { RealTimeConsole } from '@/components/RealTimeConsole';
import { TriggerButton } from '@/components/TriggerButton';
import { LayoutDashboard, History, Settings, ExternalLink, Shield, Zap } from 'lucide-react';

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
          className="bg-popover text-popover-foreground px-3 py-2 rounded-lg text-xs shadow-xl border border-border max-w-[250px] animate-in zoom-in-95 duration-200 z-50"
          sideOffset={5}
        >
          {content}
          <Tooltip.Arrow className="fill-border" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  </Tooltip.Provider>
);
export default function Home() {
  const fetchAppStatus = useStore((state) => state.fetchAppStatus);
  const fetchConfiguredSources = useStore((state) => state.fetchConfiguredSources);

  React.useEffect(() => {
    // Initial fetch
    fetchConfiguredSources();
    fetchAppStatus();

    // Continuous polling for Backend Health and Status
    const interval = setInterval(() => {
      fetchAppStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchAppStatus, fetchConfiguredSources]);

  return (
    <div className="min-h-screen flex flex-col bg-background selection:bg-primary/10">
      <Header />

      <main className="flex-1 flex gap-8 p-8 overflow-hidden max-w-[1600px] mx-auto w-full">
        {/* Left Column: Configuration & Trigger */}
        <div className="flex-[4] flex flex-col gap-6 overflow-y-auto pr-2 custom-scrollbar">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <LayoutDashboard className="w-5 h-5 text-primary" />
              <h2 className="text-xl font-bold tracking-tight">Main Workbench</h2>
            </div>
            <div className="flex gap-2">
              <TooltipWrapper content="Review history of past engineering runs and outcomes.">
                <button className="p-2 hover:bg-muted border border-border rounded-lg transition-colors text-muted-foreground">
                  <History className="w-4 h-4" />
                </button>
              </TooltipWrapper>
              <TooltipWrapper content="Configure persistent agent settings and system defaults.">
                <button className="p-2 hover:bg-muted border border-border rounded-lg transition-colors text-muted-foreground">
                  <Settings className="w-4 h-4" />
                </button>
              </TooltipWrapper>
            </div>
          </div>

          <ConfigPanel />
          <TriggerButton />

          {/* Quick Actions / Tips */}
          <div className="grid grid-cols-1 gap-4 mt-2">
            <TooltipWrapper content="Analyze agent reasoning paths, latency, and token consumption on Langfuse.">
              <div 
                onClick={() => window.open('https://cloud.langfuse.com/project/cmn6xwmg4009jad073z0gocmr/traces', '_blank')}
                className="p-4 glass rounded-xl border border-border hover:border-primary/20 transition-all cursor-pointer group flex items-center justify-between"
              >
                <div className="flex flex-col">
                  <h3 className="text-sm font-semibold mb-1 flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-primary" />
                    Live Trace & Observability
                  </h3>
                  <p className="text-xs text-muted-foreground">Monitor real-time agent reasoning, latency, and cost metrics.</p>
                </div>
                <ExternalLink className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </div>
            </TooltipWrapper>
          </div>
        </div>

        {/* Right Column: Console Output */}
        <div className="flex-[6] flex flex-col h-[calc(100vh-140px)] sticky top-24">
          <RealTimeConsole />
        </div>
      </main>

      {/* Footer / Info Bar */}
      <footer className="px-8 py-3 border-t border-border/50 bg-background/50 text-[10px] text-muted-foreground font-medium flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><Shield className="w-3 h-3 text-green-500" /> AES COMPLIANT v1.2</span>
          <span className="flex items-center gap-1.5 opacity-50">•</span>
          <span className="flex items-center gap-1.5">HYBRID CONTEXT: ENABLED</span>
          <span className="flex items-center gap-1.5 opacity-50">•</span>
          <span className="flex items-center gap-1.5">AUTH: EPHEMERAL INJECTION</span>
        </div>
        <div>
          © 2026 AGENTIC ENGINEERING SYSTEM • POWERED BY CLAUDE 3.7 SONNET & LANGGRAPH
        </div>
      </footer>
    </div>
  );
}
