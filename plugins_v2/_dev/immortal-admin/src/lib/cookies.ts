// Only non-sensitive UI preferences are persisted, under this plugin's namespace.
const key = (name: string) => `awbotnest-immortal-ui:${name}`
export function getCookie(name: string): string | undefined {
  try { return localStorage.getItem(key(name)) ?? undefined } catch { return undefined }
}
export function setCookie(name: string, value: string, _maxAge?: number): void {
  try { localStorage.setItem(key(name), value) } catch { /* Private mode may forbid storage. */ }
}
export function removeCookie(name: string): void {
  try { localStorage.removeItem(key(name)) } catch { /* UI preferences are optional. */ }
}
