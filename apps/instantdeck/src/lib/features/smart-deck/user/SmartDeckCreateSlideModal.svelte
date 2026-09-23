<script lang="ts">
  interface Props {
    open?: boolean;
    loading?: boolean;
    title?: string;
    narrative?: string;
    selectedRole?: string;
    roleOptions?: ReadonlyArray<{ value: string; label: string; title: string; brief: string }>;
    onTitleChange?: (value: string) => void;
    onNarrativeChange?: (value: string) => void;
    onRoleChange?: (value: string) => void;
    onClose?: () => void;
    onSubmit?: () => void;
    errorMessage?: string;
  }

  let {
    open = false,
    loading = false,
    title = '',
    narrative = '',
    selectedRole = 'appendix',
    roleOptions = [],
    onTitleChange,
    onNarrativeChange,
    onRoleChange,
    onClose,
    onSubmit,
    errorMessage = ''
  }: Props = $props();
</script>

{#if open}
  <div class="modal-backdrop" role="presentation">
    <div class="modal-shell" role="dialog" aria-modal="true" aria-labelledby="create-slide-title">
      <section class="panel create-slide-modal">
        <header>
          <div>
            <div class="eyebrow">Create slide</div>
            <h2 id="create-slide-title">Describe the new slide</h2>
            <p>The slide is saved first, then Smart Deck generates the first reviewable version immediately.</p>
          </div>
          <button type="button" class="dismiss" onclick={() => onClose?.()} disabled={loading}>Close</button>
        </header>

        <form onsubmit={(event) => { event.preventDefault(); onSubmit?.(); }}>
          <label>
            <span>Slide type</span>
            <select id="smart-deck-create-slide-role" name="slideRole" value={selectedRole} onchange={(event) => onRoleChange?.((event.currentTarget as HTMLSelectElement).value)}>
              {#each roleOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </label>

          <label>
            <span>Slide title</span>
            <input id="smart-deck-create-slide-title" name="slideTitle" value={title} oninput={(event) => onTitleChange?.((event.currentTarget as HTMLInputElement).value)} placeholder="Board slide, Problem, Market map, Team, Ask..." />
          </label>

          <label>
            <span>Slide brief</span>
            <textarea
              id="smart-deck-create-slide-brief"
              name="slideBrief"
              rows="7"
              value={narrative}
              oninput={(event) => onNarrativeChange?.((event.currentTarget as HTMLTextAreaElement).value)}
              placeholder="Describe what the slide should say, the proof it should include, and the visual style you want."
            ></textarea>
          </label>

          {#if errorMessage}
            <p class="error" role="alert">{errorMessage}</p>
          {/if}

          <button class="submit" type="submit" disabled={loading || !title.trim() || !narrative.trim()}>{loading ? 'Creating and generating...' : 'Create and generate slide'}</button>
        </form>
      </section>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop { position: fixed; inset: 0; background: rgba(5,11,31,.72); backdrop-filter: blur(14px); display: grid; place-items: center; padding: 1.5rem; z-index: 60; }
  .modal-shell, .create-slide-modal { width: min(680px, 100%); }
  .create-slide-modal { display: grid; gap: 1rem; padding: 1.2rem; }
  header, form, label { display: grid; gap: .6rem; }
  header { grid-template-columns: 1fr auto; align-items: start; }
  .eyebrow { color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p { margin: 0; }
  p { color: var(--muted); line-height: 1.45; }
  label span { color: var(--ink-soft); font-size: .82rem; font-weight: 700; }
  input, textarea, select { border-radius: 12px; border: 1px solid var(--line); background: var(--surface-input); color: var(--ink); padding: .85rem; font: inherit; }
  textarea { resize: vertical; }
  .dismiss, .submit { min-height: 42px; border-radius: 10px; font: inherit; }
  .dismiss { border: 1px solid var(--line); background: var(--surface-soft); color: var(--ink-soft); }
  .submit { border: 0; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 800; }
  .submit:disabled { opacity: .6; }
  .error { color: var(--danger); }
</style>
