const SESSION_KEY = "tech_support_session_id";
const USER_KEY = "tech_support_user_id";

export function getStoredSessionId(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

export function setStoredSessionId(sessionId: string): void {
  localStorage.setItem(SESSION_KEY, sessionId);
}

export function clearStoredSessionId(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function getStoredUserId(): string {
  return localStorage.getItem(USER_KEY) ?? "dev-user@company.com";
}

export function setStoredUserId(userId: string): void {
  localStorage.setItem(USER_KEY, userId);
}
