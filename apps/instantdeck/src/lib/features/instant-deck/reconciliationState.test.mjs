import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('./reconciliationState.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { instantDeckReconciliationState: reconcile } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('direct navigation retains the observed failed generation even when mode is standard', () => {
  const result = reconcile([{ status: 'failed', generationMode: 'standard', createdAt: '2026-09-08T13:53:03Z' }], false);
  assert.equal(result.state, 'error');
  assert.match(result.message, /no generated version was published/);
  assert.doesNotMatch(result.message, /Generate the first/);
});

test('a failed regeneration preserves access to a previous version', () => {
  const result = reconcile([{ status: 'failed', createdAt: '2026-09-08T13:53:03Z' }], true);
  assert.equal(result.state, 'error');
  assert.match(result.message, /previous generated version is still available/);
});

test('an older failure does not override a later successful version', () => {
  const jobs = [{ status: 'failed', createdAt: '2026-09-07T13:53:03Z' }, { status: 'completed', createdAt: '2026-09-08T13:53:03Z' }];
  assert.equal(reconcile(jobs, true).state, 'idle');
  assert.equal(jobs[0].status, 'failed');
});

test('a source-only deck with no generation attempts remains a first-generation state', () => {
  assert.match(reconcile([], false).message, /Generate the first/);
});

test('a completed compiler job cannot erase the observed downstream render failure', () => {
  const jobs = [{ id: 'generation-current', status: 'completed', createdAt: '2026-09-08T20:00:00Z' }];
  const workflow = { status: 'failed', authoritativeInstantChain: { generationJobId: 'generation-current' } };
  const result = reconcile(jobs, false, workflow);
  assert.equal(result.state, 'error');
  assert.match(result.message, /no generated version was published/);
  assert.doesNotMatch(result.message, /Generate the first|fresh|new request|try again/i);
  assert.match(reconcile(jobs, true, workflow).message, /previous generated version/);
  assert.equal(reconcile(jobs, true, { ...workflow, authoritativeInstantChain: { generationJobId: 'older-generation' } }).state, 'idle');
});
