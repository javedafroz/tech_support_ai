import Keycloak from "keycloak-js";

const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8081";
const realm = import.meta.env.VITE_KEYCLOAK_REALM || "tech-support";
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "tech-support-admin";

export const keycloak = new Keycloak({
  url: keycloakUrl,
  realm,
  clientId,
});

let initPromise: Promise<boolean> | null = null;

export function initKeycloak(): Promise<boolean> {
  // Guard against React 18 StrictMode double-invoking effects in dev:
  // keycloak-js can only be initialized once, so reuse the first promise.
  if (!initPromise) {
    initPromise = keycloak.init({
      onLoad: "login-required",
      pkceMethod: "S256",
      checkLoginIframe: false,
    });
  }
  return initPromise;
}

export async function authHeaders(): Promise<HeadersInit> {
  if (keycloak.isTokenExpired(30)) {
    await keycloak.updateToken(60);
  }
  const token = keycloak.token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
}
