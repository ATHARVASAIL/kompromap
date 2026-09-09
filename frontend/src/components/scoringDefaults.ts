/**
 * Default scoring weights, kept out of the component file so React Fast
 * Refresh can hot-reload the panel — it only works when a module's exports
 * are all components.
 *
 * These mirror the spec's ease_score formula (§4) and the backend's
 * ScoringWeights defaults. If you change one, change the other.
 */
import type { ScoringWeights } from "../types/graph";

export const DEFAULT_WEIGHTS: ScoringWeights = {
  cvss: 0.4,
  exploit_public: 0.3,
  auth_required: 0.2,
  complexity: 0.1,
  default_complexity: 0.5,
};
