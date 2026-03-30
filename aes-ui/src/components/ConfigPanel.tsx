import React, { useState } from 'react';
import { useStore, Source } from '@/store/useStore';
import { Info, Shield, Zap, Database, Globe, Cpu, Key, Plus, Trash2, FileText, BarChart, Loader2, CheckCircle, Sparkles } from 'lucide-react';
import * as Tooltip from '@radix-ui/react-tooltip';

const OPENAI_MODELS = [
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', accuracy: '90%', desc: 'Fast, efficient model for iterative coding tasks.' },
  { id: 'gpt-4o', name: 'GPT-4o', accuracy: '95%', desc: 'High-performance multimodal model.' },
  { id: 'o1-preview', name: 'o1 Preview', accuracy: '98%', desc: 'Highest reasoning capability for complex architecture.' },
  { id: 'o1-mini', name: 'o1 Mini', accuracy: '88%', desc: 'Fast reasoning for smaller tasks.' },
];

const BEDROCK_MODELS = [
  { id: 'anthropic.claude-3-5-sonnet-20240620-v1:0', name: 'Claude 3.5 Sonnet', accuracy: '96%', desc: 'State-of-the-art Claude model on AWS.' },
  { id: 'anthropic.claude-3-opus-20240229-v1:0', name: 'Claude 3 Opus', accuracy: '94%', desc: 'Most capable Claude 3 model.' },
];

const SUGGESTED_QUERIES = [
  { label: 'Health Check', query: "Create a new FastAPI health endpoint in `backend/app/api/health.py` that returns `{ 'status': 'ok' }` in testing_agentic_engineering_team." },
  { label: 'Auth Schema', query: "Define Pydantic models for a Token containing `access_token` and `token_type` in `backend/app/schemas/token.py` in testing_agentic_engineering_team." },
  { label: 'Frontend Deps', query: "Update `frontend/package.json` to include `tailwindcss` and latest stable `next` versions in testing_agentic_engineering_team." },
  { label: 'Logic Test', query: "Create a Python test in `tests/` verifying the authentication service returns a valid token on login in testing_agentic_engineering_team." },
  { label: 'Docs Update', query: "Update the 'Architecture' section of `README.md` to include the Growth agent responsibilities in testing_agentic_engineering_team." },
];

const TooltipWrapper: React.FC<{ children: React.ReactNode; content: string; delay?: number }> = ({ children, content, delay = 300 }) => (
  <Tooltip.Provider delayDuration={delay}>
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

export const ConfigPanel: React.FC = () => {
  const store = useStore();
  const [newSourceUrl, setNewSourceUrl] = useState('');
  const [newSourceType, setNewSourceType] = useState<Source['type']>('repo');

  const handleAddSource = () => {
    if (!newSourceUrl) return;
    store.addSource(newSourceUrl, newSourceType);
    setNewSourceUrl('');
  };


  const currentModels = store.provider === 'openai' ? OPENAI_MODELS : BEDROCK_MODELS;
  const needsGithub = store.sources.some(s => s.type === 'repo');
  const needsGoogle = store.sources.some(s => s.type === 'doc' || s.type === 'sheet');

  const handleIngest = async () => {
    // Only enforce UI validation in "Custom" mode. 
    // In "Standard" mode, we assume the backend has the keys in .env.
    if (store.mode === 'custom') {
      if (needsGithub && !store.githubToken) {
        store.addLog('❌ Ingestion blocked: GitHub Token is required in Custom mode.');
        alert('Please provide a GitHub Token in "Custom" mode settings or switch to "Standard" to use system defaults.');
        return;
      }
      if (needsGoogle && !store.googleServiceAccountJson) {
        store.addLog('❌ Ingestion blocked: Google Service Account JSON is required in Custom mode.');
        alert('Please provide Google Service Account JSON in "Custom" mode settings or switch to "Standard" to use system defaults.');
        return;
      }
    }

    store.setIngesting(true);
    store.addLog('🚀 Starting bulk ingestion of sources...');
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/orchestration/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: store.sources,
          github_token: store.githubToken || undefined,
          google_service_account_json: store.googleServiceAccountJson || undefined,
        }),
      });

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.substring(5));
            if (data.type === 'log') store.addLog(data.content);
            if (data.type === 'status') store.addLog(`[STATUS] ${data.content}`);
            if (data.type === 'complete') {
               store.addLog(`✨ ${data.content}`);
               store.setIngesting(false);
               if (store.mode === 'custom') {
                 store.setCustomIngested(true);
               } else {
                 store.setIngested(true);
               }
            }
          }
        }
      }
    } catch (error) {
      store.addLog(`❌ Ingestion failed: ${error}`);
      store.setIngesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 glass rounded-2xl overflow-y-auto max-h-[85vh] custom-scrollbar">
      {/* Header & Mode Switch */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" />
          <h2 className="text-xl font-semibold">Project Config</h2>
        </div>
        <TooltipWrapper content="Toggle between Standard (pre-configured) and Custom (bring your own keys) modes.">
          <div className="flex items-center gap-3 bg-muted/50 p-1 rounded-full border border-border">
            {['standard', 'custom'].map((m) => (
              <button
                key={m}
                onClick={() => store.setMode(m as 'standard' | 'custom')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all capitalize ${
                  store.mode === m ? 'bg-primary text-primary-foreground shadow-lg' : 'hover:text-primary'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </TooltipWrapper>
      </div>

      <div className="space-y-6">
        {/* Step 1: Source Ingestion */}
        <div className="space-y-3">
          {store.mode === 'standard' && (
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Database className="w-4 h-4" /> 1. Data Sources
              </label>
              <TooltipWrapper content="Analyze and index sources to build the context graph.">
                <button
                  disabled={store.sources.length === 0 || store.isIngesting}
                  onClick={handleIngest}
                  className={`text-xs flex items-center gap-1.5 font-semibold transition-colors ${
                    store.isIngested && !store.isIngesting 
                      ? 'text-emerald-500 hover:text-emerald-400' 
                      : 'text-primary hover:underline'
                  } disabled:opacity-50 disabled:no-underline`}
                >
                  {store.isIngesting ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : store.isIngested ? (
                    <CheckCircle className="w-3 h-3" />
                  ) : (
                    <Zap className="w-3 h-3" />
                  )}
                  {store.isIngesting ? 'Ingesting...' : store.isIngested ? 'Context Ready' : 'Ingest All'}
                </button>
              </TooltipWrapper>
            </div>
          )}

          <div className="space-y-4">
            {/* Source Addition UI - ONLY in Custom Mode */}
            {store.mode === 'custom' ? (
              <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <Database className="w-4 h-4 text-primary/70" /> 1. Custom Data Sources
                  </label>
                  <TooltipWrapper content="Analyze and index sources to build the context graph.">
                    <button
                      disabled={store.sources.length === 0 || store.isIngesting}
                      onClick={handleIngest}
                      className={`text-xs flex items-center gap-1.5 font-semibold transition-colors ${
                        store.isCustomIngested && !store.isIngesting 
                          ? 'text-emerald-500 hover:text-emerald-400' 
                          : 'text-primary hover:underline'
                      } disabled:opacity-50 disabled:no-underline`}
                    >
                      {store.isIngesting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : store.isCustomIngested ? (
                        <CheckCircle className="w-3 h-3" />
                      ) : (
                        <Zap className="w-3 h-3" />
                      )}
                      {store.isIngesting ? 'Ingesting...' : store.isCustomIngested ? 'Context Ready' : 'Ingest All'}
                    </button>
                  </TooltipWrapper>
                </div>
                <div className="flex gap-2">
                <select
                  value={newSourceType}
                  onChange={(e) => setNewSourceType(e.target.value as Source['type'])}
                  className="bg-muted/50 border border-border rounded-lg px-2 text-xs focus:outline-none"
                >
                  <option value="repo">Repo</option>
                  <option value="doc">Doc</option>
                  <option value="sheet">Sheet</option>
                </select>
                <input
                  type="text"
                  value={newSourceUrl}
                  onChange={(e) => setNewSourceUrl(e.target.value)}
                  placeholder="URL (GitHub, GDocs...)"
                  className="flex-1 bg-muted/30 border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                />
                <button 
                  onClick={handleAddSource}
                  className="p-1.5 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
              <div className="flex flex-col gap-2 p-3 bg-primary/5 border border-primary/20 rounded-xl animate-in fade-in duration-500">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-primary/80">
                    <Shield className="w-3.5 h-3.5" />
                    System Managed Context
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-tight ${
                    (store.isIngested || store.sources.length > 0)
                      ? 'bg-green-500/10 text-green-500 border border-green-500/20' 
                      : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 animate-pulse'
                  }`}>
                    <div className={`w-1.5 h-1.5 rounded-full ${(store.isIngested || store.sources.length > 0) ? 'bg-green-500' : 'bg-yellow-500'}`} />
                    {(store.isIngested || store.sources.length > 0) ? 'Ready' : 'Ingesting'}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {/* Merge configured and actual sources to ensure we always show names */}
                  {Array.from(new Map(
                    [...store.configuredSources, ...store.sources].map(s => [s.url, s])
                  ).values()).map((s) => (
                    <div key={s.id} className="flex items-center gap-1.5 px-2 py-1 bg-white/5 border border-white/5 rounded-lg text-[10px] font-medium text-muted-foreground whitespace-nowrap">
                      {s.type === 'repo' ? <Globe className="w-2.5 h-2.5 text-blue-400/70" /> : 
                       s.type === 'doc' ? <FileText className="w-2.5 h-2.5 text-yellow-400/70" /> : 
                       <BarChart className="w-2.5 h-2.5 text-green-400/70" />}
                      {s.url.split('/').pop()?.replace('.git', '') || 'Resource'}
                    </div>
                  ))}
                </div>

                {/* Accuracy Note for Standard Mode */}
                <div className="mt-2 pt-2 border-t border-primary/10 flex items-start gap-2 text-[9px] text-muted-foreground leading-tight">
                  <Info className="w-3 h-3 mt-0.5 shrink-0 text-primary/40" />
                  <p>
                    Standard mode uses <span className="text-primary/80 font-bold italic">gpt-4o-mini</span> to maximize speed and cost-efficiency.
                    For complex architectural tasks, switch to Custom Mode.
                  </p>
                </div>
              </div>
            )}

            {/* List of Sources */}
            <div className="space-y-2 max-h-40 overflow-y-auto custom-scrollbar">
              {(store.mode === 'custom' 
                ? store.sources.filter(s => !store.configuredSources.some(cs => cs.url === s.url)) 
                : []
              ).map((s) => (
                <div key={s.id} className="flex items-center justify-between p-2 bg-muted/20 border border-border/50 rounded-lg group">
                  <div className="flex items-center gap-2 min-w-0">
                    {s.type === 'repo' ? <Globe className="w-3 h-3 text-blue-400" /> : 
                     s.type === 'doc' ? <FileText className="w-3 h-3 text-yellow-400" /> : 
                     <BarChart className="w-3 h-3 text-green-400" />}
                    <span className="text-xs truncate font-mono text-muted-foreground">{s.url}</span>
                  </div>
                  {store.mode === 'custom' && (
                    <button onClick={() => store.removeSource(s.id)} className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:text-destructive">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Step 2: Provider Selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Cpu className="w-4 h-4" /> 2. Model Provider
          </label>
          <div className="grid grid-cols-2 gap-3">
            {['openai', 'bedrock'].map((p) => (
              <TooltipWrapper 
                key={p} 
                content={
                  p === 'bedrock' && store.mode === 'standard' 
                    ? 'AWS Bedrock is only available in Custom mode.' 
                    : `Use ${p === 'openai' ? 'OpenAI Direct' : 'AWS Bedrock'} logic.`
                }
              >
                <button
                  disabled={p === 'bedrock' && store.mode === 'standard'}
                  onClick={() => store.setProvider(p as 'openai' | 'bedrock')}
                  className={`p-3 rounded-xl border transition-all flex items-center justify-center gap-2 ${
                    store.provider === p 
                      ? 'bg-primary/10 border-primary ring-1 ring-primary text-primary' 
                      : 'bg-muted/20 border-border hover:border-primary/50'
                  } ${p === 'bedrock' && store.mode === 'standard' ? 'opacity-50 cursor-not-allowed grayscale' : ''}`}
                >
                  <span className="font-medium capitalize">{p}</span>
                </button>
              </TooltipWrapper>
            ))}
          </div>
        </div>

        {/* Step 3: Task Description */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Zap className="w-4 h-4" /> 3. Objectives
          </label>
          <textarea
            value={store.query}
            onChange={(e) => store.setQuery(e.target.value)}
            placeholder="Describe the engineering goal..."
            className="w-full h-24 bg-muted/30 border border-border rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all resize-none"
          />
          
          {/* Quick Suggestions (Standard Mode Only) */}
          {store.mode === 'standard' && (
            <div className="space-y-2 pt-1">
              <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/60">
                <Sparkles className="w-3 h-3" /> Quick Start Suggestions
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUERIES.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => store.setQuery(s.query)}
                    className="px-2.5 py-1 text-[10px] font-medium bg-muted/30 border border-border/50 rounded-lg text-muted-foreground hover:bg-primary/10 hover:border-primary/30 hover:text-primary transition-all active:scale-95"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Custom Configuration Section */}
        {store.mode === 'custom' && (
          <div className="space-y-6 pt-4 border-t border-border/50 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Model Selection */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Cpu className="w-4 h-4" /> 4. Reasoning Model
              </label>
              <div className="grid grid-cols-2 gap-3">
                {currentModels.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => store.setModel(m.id)}
                    className={`relative p-3 text-left rounded-xl border transition-all ${
                      store.model === m.id
                        ? 'bg-primary/5 border-primary ring-1 ring-primary'
                        : 'bg-muted/20 border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm">{m.name}</span>
                      <TooltipWrapper content={`Accuracy: ${m.accuracy}. ${m.desc}`}>
                        <Info className="w-3.5 h-3.5 text-muted-foreground hover:text-primary cursor-help" />
                      </TooltipWrapper>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Credentials Fields */}
            <div className="space-y-4">
              {store.provider === 'openai' ? (
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                    <Key className="w-3.5 h-3.5" /> OpenAI API Key (Required)
                  </label>
                  <input
                    type="password"
                    value={store.openaiApiKey}
                    onChange={(e) => store.setCredentials({ openaiApiKey: e.target.value })}
                    placeholder="sk-..."
                    className="w-full bg-muted/30 border border-border rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all font-mono"
                  />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">AWS Access Key (Required)</label>
                    <input
                      type="password"
                      value={store.awsAccessKeyId}
                      onChange={(e) => store.setCredentials({ awsAccessKeyId: e.target.value })}
                      placeholder="AKIA..."
                      className="w-full bg-muted/30 border border-border rounded-xl p-3 text-sm focus:outline-none font-mono"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">AWS Secret Key (Required)</label>
                    <input
                      type="password"
                      value={store.awsSecretAccessKey}
                      onChange={(e) => store.setCredentials({ awsSecretAccessKey: e.target.value })}
                      placeholder="SECRET..."
                      className="w-full bg-muted/30 border border-border rounded-xl p-3 text-sm focus:outline-none font-mono"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground text-primary/80">
                  GitHub Token {needsGithub ? '(Required if Git Repo is provided)' : '(Optional)'}
                </label>
                <input
                  type="password"
                  value={store.githubToken}
                  onChange={(e) => store.setCredentials({ githubToken: e.target.value })}
                  placeholder="ghp_..."
                  className={`w-full bg-muted/30 border rounded-xl p-3 text-sm focus:outline-none font-mono transition-all ${
                    needsGithub && !store.githubToken ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border'
                  }`}
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2 text-primary/80">
                  <Database className="w-3.5 h-3.5" /> Google SA JSON {needsGoogle ? '(Required if Google Drive data is provided)' : '(Optional)'}
                </label>
                <textarea
                  value={store.googleServiceAccountJson}
                  onChange={(e) => store.setCredentials({ googleServiceAccountJson: e.target.value })}
                  placeholder='{"type": "service_account", ...}'
                  className={`w-full h-24 bg-muted/30 border rounded-xl p-3 text-xs focus:outline-none font-mono resize-none transition-all ${
                    needsGoogle && !store.googleServiceAccountJson ? 'border-primary/50 ring-1 ring-primary/20' : 'border-border'
                  }`}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
