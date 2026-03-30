import React from 'react';
import { useStore } from '@/store/useStore';
import { Play, Square, Loader2, Rocket, ShieldCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import * as Tooltip from '@radix-ui/react-tooltip';

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

export const TriggerButton: React.FC = () => {
  const store = useStore();

  const handleExecute = async () => {
    // 1. Basic Validation
    if (!store.query) {
      alert('Please enter a goal or task description.');
      return;
    }

    // 2. Source-Based Credential Validation (Enforced ONLY in Custom mode)
    if (store.mode === 'custom') {
      const needsGithub = store.sources.some(s => s.type === 'repo');
      const needsGoogle = store.sources.some(s => s.type === 'doc' || s.type === 'sheet');

      if (needsGithub && !store.githubToken) {
        alert('GitHub Token is required for repository sources in Custom Mode.');
        return;
      }
      if (needsGoogle && !store.googleServiceAccountJson) {
        alert('Google Service Account JSON is required for document/sheet sources in Custom Mode.');
        return;
      }
    }

    // 3. Provider-Based Credential Validation (Custom Mode)
    if (store.mode === 'custom') {
      if (store.provider === 'openai' && !store.openaiApiKey) {
        alert('OpenAI API Key is required in Custom Mode.');
        return;
      }
      if (store.provider === 'bedrock' && (!store.awsAccessKeyId || !store.awsSecretAccessKey)) {
        alert('AWS Access & Secret Keys are required in Custom Mode.');
        return;
      }
    }

    store.setStatus('running');
    store.addLog('🚀 Initiating execution session...');

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/orchestration/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: store.query,
          sources: store.sources,
          provider: store.provider,
          model: store.model,
          mode: store.mode,
          openai_api_key: store.openaiApiKey || null,
          aws_access_key_id: store.awsAccessKeyId || null,
          aws_secret_access_key: store.awsSecretAccessKey || null,
          aws_region: store.awsRegion || 'us-east-1',
          github_token: store.githubToken || null,
          google_service_account_json: store.googleServiceAccountJson || null,
        }),
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'log') {
                store.addLog(data.content);
              } else if (data.type === 'status') {
                store.addLog(`[SYSTEM] ${data.content}`);
              } else if (data.type === 'complete') {
                store.setStatus('completed');
                store.addLog('✅ Execution completed successfully.');
              } else if (data.type === 'error') {
                store.setStatus('error');
                store.addLog(`❌ Error: ${data.content}`);
              } else if (data.type === 'summary') {
                store.setSummary(data.content);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e, 'Line:', line);
            }
          }
        }
      }
    } catch (error: any) {
      store.setStatus('error');
      store.addLog(`❌ Fatal Error: ${error.message}`);
    }
  };

  return (
    <TooltipWrapper content="Trigger the agentic engineering cycle. All ephemeral keys are injected into the execution context and never stored.">
      <motion.button
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={handleExecute}
        disabled={store.status === 'running'}
        className={`relative w-full py-3 px-4 rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg ${
          store.status === 'running' 
            ? 'bg-muted/50 text-muted-foreground border border-border cursor-not-allowed'
            : 'bg-primary text-primary-foreground hover:shadow-primary/20 hover:-translate-y-0.5'
        }`}
      >
        <div className="absolute inset-0 bg-white/5 opacity-0 hover:opacity-100 transition-opacity rounded-xl" />
        <div className="flex items-center gap-2 flex-1 justify-center">
          {store.status === 'running' ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <span className="text-xs sm:text-sm">Implementing Run...</span>
            </>
          ) : (
            <>
              <Rocket className="w-4 h-4" />
              <span className="text-xs sm:text-sm whitespace-nowrap">Execute Engineering Run</span>
            </>
          )}
        </div>
        
        <div className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 bg-black/10 rounded-md text-[8px] uppercase tracking-tighter opacity-50 shrink-0">
          <ShieldCheck className="w-2.5 h-2.5" />
          SECURE
        </div>
      </motion.button>
    </TooltipWrapper>
  );
};
