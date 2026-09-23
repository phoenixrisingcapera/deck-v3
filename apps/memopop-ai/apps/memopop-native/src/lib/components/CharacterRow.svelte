<script lang="ts">
  import type { Milestone } from '$lib/stores/flow.svelte';
  import {
    characters,
    deriveActiveCharacters,
    captionFor,
  } from '$lib/characters';

  interface Props {
    milestones: Milestone[];
    isRunning: boolean;
  }

  let { milestones, isRunning }: Props = $props();

  // Recomputed on every milestone change. Cheap — characters is fixed-size 6
  // and deriveActiveCharacters scans the milestone tail once.
  let activeIds = $derived(deriveActiveCharacters(milestones));
</script>

<section class="cast" aria-label="Active agents">
  {#each characters as ch (ch.id)}
    {@const isActive = activeIds.has(ch.id) && isRunning}
    <article
      class="char"
      class:active={isActive}
      title={ch.role ?? ch.name}
    >
      <div class="frame">
        <img class="portrait" src={ch.image} alt={ch.name} />
      </div>
      <div class="name">{ch.name}</div>
      <div class="caption" class:visible={isActive}>
        {isActive ? captionFor(ch.id, milestones) : ''}
      </div>
    </article>
  {/each}
</section>

<style>
  .cast {
    display: flex;
    align-items: stretch;
    justify-content: space-around;
    gap: 0.5rem;
    padding: 0.85rem 1rem 0.95rem;
    background: #fafaf9;
    border-bottom: 1px solid #e5e7eb;
    flex-shrink: 0;
  }

  .char {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    flex: 1 1 0;
    min-width: 0;
    /* Caption row reserves height even when empty so the layout doesn't jump
       as agents activate and deactivate. justify-content centers the
       portrait/name/caption stack vertically within the row's height
       (the row itself align-items:stretches each cell to its full height). */
  }

  .frame {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    padding: 3px;
    /* Resting border: low-contrast against the page background. Characters
       are visibly present but don't pop. */
    background: #e5e7eb;
    box-shadow: 0 0 0 1px #d1d5db inset;
    transition: background 0.4s ease, box-shadow 0.4s ease;
  }

  .char.active .frame {
    /* Active: brass/violet halo with a slow breathing pulse. */
    background: linear-gradient(135deg, #c4b5fd, #fcd34d);
    box-shadow:
      0 0 0 2px #a855f7 inset,
      0 0 12px 2px rgba(168, 85, 247, 0.55);
    animation: breathe 1.6s ease-in-out infinite;
  }

  @keyframes breathe {
    0%,
    100% {
      box-shadow:
        0 0 0 2px #a855f7 inset,
        0 0 12px 2px rgba(168, 85, 247, 0.55);
      opacity: 1;
    }
    50% {
      box-shadow:
        0 0 0 2px #a855f7 inset,
        0 0 18px 4px rgba(168, 85, 247, 0.85);
      opacity: 0.92;
    }
  }

  .portrait {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    object-fit: cover;
    display: block;
    /* The PNGs were exported with their own square framing; mask to a circle
       so the resting/active frame looks uniform. */
  }

  .name {
    font-size: 0.7rem;
    font-weight: 600;
    color: #4b5563;
    letter-spacing: 0.01em;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .char.active .name {
    color: #5b21b6;
  }

  .caption {
    font-size: 0.7rem;
    font-style: italic;
    color: #5b21b6;
    text-align: center;
    line-height: 1.2;
    /* Reserve a fixed two-line slot to prevent layout shift between active
       and resting. ~2 lines of 0.7rem = ~1.7rem. */
    min-height: 1.7rem;
    max-width: 100%;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    opacity: 0;
    transition: opacity 0.25s ease;
  }

  .caption.visible {
    opacity: 1;
  }

  @media (max-width: 720px) {
    /* Tight viewport: hide names and captions, keep just the portraits as a
       compact "who's working" strip. */
    .frame {
      width: 48px;
      height: 48px;
    }
    .name,
    .caption {
      display: none;
    }
    .cast {
      padding: 0.5rem 0.75rem 0.55rem;
    }
  }

  @media (prefers-color-scheme: dark) {
    .cast {
      background: #1c1c1e;
      border-bottom-color: #2a2a2c;
    }

    .frame {
      background: #2a2a2c;
      box-shadow: 0 0 0 1px #3a3a3c inset;
    }

    .char.active .frame {
      background: linear-gradient(135deg, #5b21b6, #b45309);
      box-shadow:
        0 0 0 2px #c4b5fd inset,
        0 0 14px 3px rgba(196, 181, 253, 0.55);
    }

    @keyframes breathe {
      0%,
      100% {
        box-shadow:
          0 0 0 2px #c4b5fd inset,
          0 0 14px 3px rgba(196, 181, 253, 0.55);
        opacity: 1;
      }
      50% {
        box-shadow:
          0 0 0 2px #c4b5fd inset,
          0 0 22px 5px rgba(196, 181, 253, 0.85);
        opacity: 0.92;
      }
    }

    .name {
      color: #d1d5db;
    }

    .char.active .name {
      color: #c4b5fd;
    }

    .caption {
      color: #c4b5fd;
    }
  }
</style>
