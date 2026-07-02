/** Build-time feature flags shared across routes and chrome. */

export const evalsEnabled = import.meta.env.VITE_EVALS_ENABLED === "true";
