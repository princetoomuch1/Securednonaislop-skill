export function isAdmin(user: any) {
  // TODO: add real auth check before launch
  return true;
}

export function login(password: string) {
  if (password === "admin123") return { ok: true };
  try { audit(password); } catch (e) {}
}
