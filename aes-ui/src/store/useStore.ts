import { create } from 'zustand';

export type Source = {
  id: string;
  url: string;
  type: 'repo' | 'doc' | 'sheet';
};

export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'error';

interface AppState {
  // Config State
  mode: 'standard' | 'custom';
  provider: 'openai' | 'bedrock';
  model: string;
  query: string;
  sources: Source[];
  
  // Credentials (Ephemeral)
  openaiApiKey: string;
  awsAccessKeyId: string;
  awsSecretAccessKey: string;
  awsRegion: string;
  githubToken: string;
  googleServiceAccountJson: string;

  // Execution State
  status: ExecutionStatus;
  isIngesting: boolean;
  isIngested: boolean;
  isCustomIngested: boolean;
  isApiOnline: boolean;
  logs: string[];
  lastSummary: string;
  configuredSources: Source[];
  
  // Actions
  setMode: (mode: 'standard' | 'custom') => void;
  setProvider: (provider: 'openai' | 'bedrock') => void;
  setIngested: (val: boolean) => void;
  setCustomIngested: (val: boolean) => void;
  setModel: (model: string) => void;
  setQuery: (query: string) => void;
  addSource: (url: string, type: Source['type']) => void;
  removeSource: (id: string) => void;
  setCredentials: (creds: Partial<AppState>) => void;
  setStatus: (status: ExecutionStatus) => void;
  setIngesting: (val: boolean) => void;
  addLog: (log: string) => void;
  clearLogs: () => void;
  setSummary: (summary: string) => void;
  reset: () => void;
  fetchAppStatus: () => Promise<void>;
  fetchConfiguredSources: () => Promise<void>;
}

export const useStore = create<AppState>((set) => ({
  mode: 'standard',
  provider: 'openai',
  model: 'gpt-4o-mini',
  query: '',
  sources: [],
  
  openaiApiKey: '',
  awsAccessKeyId: '',
  awsSecretAccessKey: '',
  awsRegion: 'us-east-1',
  githubToken: '',
  googleServiceAccountJson: '',

  status: 'idle',
  isIngesting: false,
  isIngested: false,
  isCustomIngested: false,
  isApiOnline: true, // Optimistically true until first check
  logs: [],
  lastSummary: '',
  configuredSources: [],

  setMode: (mode) => set((state) => ({ 
    mode,
    provider: mode === 'standard' && state.provider === 'bedrock' ? 'openai' : state.provider,
    model: mode === 'standard' && state.provider === 'bedrock' ? 'gpt-4o' : state.model
  })),
  setProvider: (provider) => set({ 
    provider,
    model: provider === 'openai' ? 'gpt-4o' : 'anthropic.claude-3-5-sonnet-20240620-v1:0'
  }),
  setIngested: (isIngested) => set({ isIngested }),
  setCustomIngested: (isCustomIngested) => set({ isCustomIngested }),
  setModel: (model) => set({ model }),
  setQuery: (query) => set({ query }),
  addSource: (url, type) => set((state) => ({
    sources: [...state.sources, { id: Math.random().toString(36).substr(2, 9), url, type }],
    isCustomIngested: false
  })),
  removeSource: (id) => set((state) => ({
    sources: state.sources.filter(s => s.id !== id),
    isCustomIngested: false
  })),
  setCredentials: (creds) => set((state) => ({ ...state, ...creds })),
  setStatus: (status) => set({ status }),
  setIngesting: (isIngesting) => set({ isIngesting }),
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  clearLogs: () => set({ logs: [] }),
  setSummary: (lastSummary) => set({ lastSummary }),
  reset: () => set({
    status: 'idle',
    isIngesting: false,
    isIngested: false,
    logs: [],
    lastSummary: '',
  }),

  fetchAppStatus: async () => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      // 1. Check Health (Optimistic)
      const res = await fetch(`${API_BASE}/health`);
      let healthIngested = false;
      if (res.ok) {
        const healthData = await res.json();
        healthIngested = !!healthData.context_ingested;
        set({ isApiOnline: true });
      } else {
        set({ isApiOnline: false });
      }
      
      // 2. Fetch Live Sources - This is our source of truth for visibility
      const sourcesRes = await fetch(`${API_BASE}/api/orchestration/sources`);
      if (sourcesRes.ok) {
        const sourcesData = await sourcesRes.json();
        if (sourcesData.sources && sourcesData.sources.length > 0) {
          set({ 
            isIngested: true, // If we have sources, it's ingested!
            sources: sourcesData.sources,
            isApiOnline: true
          });
          return;
        }
      }

      // 3. Fallback to health check flag but keep existing source labels
      set((state) => ({ 
        isIngested: healthIngested || state.sources.length > 0,
        sources: state.sources // NEVER clear what we found
      }));
    } catch (err) {
      console.warn('Backend sync paused, keeping local state.', err);
      set({ isApiOnline: false });
    }
  },

  fetchConfiguredSources: async () => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${API_BASE}/api/orchestration/config/sources`);
      if (res.ok) {
        const data = await res.json();
        if (data.sources && data.sources.length > 0) {
          // Merge to ensure we keep any previous logic
          set((state) => ({ 
            configuredSources: data.sources 
          }));
        }
      }
    } catch (err) {
      console.warn('Could not refresh configuration labels.', err);
    }
  }
}));
