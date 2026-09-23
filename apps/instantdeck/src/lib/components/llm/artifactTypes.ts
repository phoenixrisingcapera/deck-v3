export type ArtifactHistoryItem = {
  id: string;
  title: string;
  subtitle?: string | null;
  timestamp?: string | null;
  payload?: Record<string, unknown> | null;
  artifactType?: string | null;
};
