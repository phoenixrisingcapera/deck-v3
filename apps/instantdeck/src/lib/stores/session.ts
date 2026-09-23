import { writable } from 'svelte/store';
import { validateSession } from '$lib/api/auth';

export type UserRole = 'super_admin' | 'admin' | 'user' | 'general';

export type SessionUser = {
  id: string;
  email: string;
  role: UserRole;
  preferredTheme: 'light' | 'dark';
  billingPlan: string;
  permissions: string[];
  
};


export type SessionState = {
  status: 'loading' | 'authenticated' | 'anonymous';
  user: SessionUser | null;
  billingPlan: string;
  permissions: string[];
  
};

const initialState: SessionState = {
  status: 'loading',
  user: null,
  billingPlan: 'free',
  permissions: [],
  
};

function createSessionStore() {
  const { subscribe, set, update } = writable<SessionState>(initialState);

  function clear() {
    set({
      status: 'anonymous',
      user: null,
      billingPlan: 'free',
      permissions: []
    });
  }

  async function load() {
    update((state) => ({ ...state, status: 'loading' }));

    try {
      const authResult = await validateSession();

      const authenticated = authResult.valid !== false;
      const inspection = authResult.inspection ?? null;
      const user = authResult.user ?? null;

      if (!authenticated || !user) {
        clear();
        return;
      }

      set({
        status: 'authenticated',
        user,
        billingPlan: user.billingPlan,
        permissions: user.permissions,
        
      });
    } catch {
      clear();
    }
  }

  function hasPermission(permission: string) {
    let allowed = false;
    subscribe((state) => {
      allowed = state.permissions.includes(permission);
    })();
    return allowed;
  }

  return { subscribe, load, clear, hasPermission };
}

export const sessionState = createSessionStore();
