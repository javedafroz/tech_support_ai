/**
 * Optional client override — thought streaming is normally enabled via API
 * `THOUGHT_STREAMING_ENABLED` and discovered at runtime from `/api/v1/config/public`.
 * Set VITE_THOUGHT_STREAMING_ENABLED=false to force-disable streaming in the UI.
 */
export const thoughtStreamingClientOverrideDisabled =
  import.meta.env.VITE_THOUGHT_STREAMING_ENABLED === "false";
