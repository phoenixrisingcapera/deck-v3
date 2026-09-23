import type { AuthRouteUser } from '$lib/server/auth/session';
declare global {
  namespace App {
    interface Locals {
      sessionUser: import('$lib/server/auth/session').AuthRouteUser | null;
    }
  }
}

export {};
