import type { Transport } from './types';
import { LocalTransport } from './local';

let instance: Transport | null = null;

export function getTransport(): Transport {
  if (!instance) {
    instance = new LocalTransport();
  }
  return instance;
}

export type {
  Transport,
  HttpMethod,
  ApiError,
  JobEvent,
  JobEventType,
  JobEventHandler,
  MilestoneStage,
  MilestoneLevel,
} from './types';
