import { json } from '@sveltejs/kit';
import { signOut } from '$server/auth/authService';

export async function POST({ cookies }) {
  return json(await signOut(cookies));
}
