<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  const storySwatches = ['#5c63ff', '#53a7ff', '#45d7a5', '#b183ff', '#f06ac8'];
  const storyCards = [
    {
      label: 'Intake',
      pageTitle: 'Smart Deck intake',
      route: '/decks/new',
      icon: 'intake',
      kicker: 'Stop starting every opportunity from scratch',
      headline: 'Turn a founder PDF into a live deal workspace.',
      problem:
        'Every new opportunity arrives as a different mess: PDF, website, scattered notes, and no reliable operating context for the team.',
      solution:
        'Deck AIStack standardises that mess into one guided intake so analysts spend less time rebuilding context and more time judging the opportunity.',
      chips: ['Upload deck', 'Brand loader', 'AI setup'],
      showSwatches: true
    },
    {
      label: 'Smart Deck',
      pageTitle: 'Smart Deck workspace',
      route: '/decks/[deckId]/smart-deck',
      icon: 'workspace',
      kicker: 'Keep the deal team on the same page',
      headline: 'Give partners and associates one review surface to reopen the deal.',
      problem:
        'Once comments spread across PDFs, email, and partner chats, the deck stops behaving like a usable operating document.',
      solution:
        'The Smart Deck page keeps the current narrative, readiness, slide context, and review state together so the team can resume the opportunity instantly.',
      chips: ['Slide view', 'Readiness', 'Deck memory'],
      showSwatches: false
    },
    {
      label: 'Diligence',
      pageTitle: 'Diligence findings',
      route: '/decks/[deckId]/due-diligence',
      icon: 'diligence',
      kicker: 'Surface weak proof before partner time is spent',
      headline: 'Pull evidence gaps into the open before the discussion drifts.',
      problem:
        'VC teams lose cycles when unsupported founder claims survive until the meeting and have to be challenged slide by slide in real time.',
      solution:
        'The diligence page isolates risk, missing evidence, and pressure points early, making the deck feel closer to an investable review package.',
      chips: ['Risk notes', 'Evidence gaps', 'Narrative checks'],
      showSwatches: false
    },
    {
      label: 'Review',
      pageTitle: 'Due diligence review',
      route: '/decks/[deckId]/due-diligence',
      icon: 'review',
      kicker: 'Use AI without losing investor trust',
      headline: 'Keep every AI suggestion inspectable before it becomes the story.',
      problem:
        'Generic AI rewrite tools are hard to trust because they mutate the founder narrative too freely and hide the comparison work.',
      solution:
        'Deck AIStack stages every suggestion, preserves the original, and gives the team an audit trail before any revision becomes part of the working deck.',
      chips: ['Suggestion queue', 'Approve / reject', 'Audit trail'],
      showSwatches: false
    },
    {
      label: 'Export',
      pageTitle: 'Export pack',
      route: '/decks/[deckId]/export',
      icon: 'export',
      kicker: 'Get to IC-ready output faster',
      headline: 'Package reviewed work into partner and committee-ready deliverables.',
      problem:
        'Even after the deck improves, funds still need usable outputs for circulation, memo support, and decision meetings.',
      solution:
        'The export page turns approved review work into clean materials without breaking provenance between the founder source deck and the reviewed version.',
      chips: ['IC version', 'Board version', 'Review-ready pack'],
      showSwatches: false
    }
  ] as const;

  let storyIndex = $state(0);

  onMount(() => {
    const timer = window.setInterval(() => {
      storyIndex = (storyIndex + 1) % storyCards.length;
    }, 4200);

    return () => window.clearInterval(timer);
  });

  function showStory(index: number) {
    storyIndex = index;
  }
</script>

<section class="panel story-strip">
  <div class="story-strip__lead">
    <div>
      <div class="eyebrow">Built for VC workflows</div>
      <h2>Deck AIStack is not a prettier slide tool. It is an operating layer for how funds actually review founder decks.</h2>
    </div>

    <p class="muted">
      The pages in the product are designed around real investment-team pain: intake chaos, weak proof density,
      unsafe AI rewrites, and the scramble to produce committee-ready output under time pressure.
    </p>
  </div>

  <div class="story-strip__nav">
    {#each storyCards as story, index}
      <button
        type="button"
        class:story-strip__tab--active={index === storyIndex}
        class="story-strip__tab"
        onclick={() => showStory(index)}
      >
        <span class={`story-strip__icon story-strip__icon--${story.icon}`}></span>
        <span>{story.label}</span>
      </button>
    {/each}
  </div>

  {#key storyIndex}
    <article class="story-strip__card" in:fly={{ y: 12, duration: 260 }} out:fade={{ duration: 180 }}>
      <div class="story-strip__main">
        <span class="story-strip__kicker">{storyCards[storyIndex].kicker}</span>

        <div class="story-strip__head">
          <span class={`story-strip__icon story-strip__icon--large story-strip__icon--${storyCards[storyIndex].icon}`}></span>
          <div>
            <strong>{storyCards[storyIndex].headline}</strong>
            <small>{storyCards[storyIndex].pageTitle}</small>
          </div>
        </div>

        <div class="story-strip__tags">
          {#each storyCards[storyIndex].chips as chip}
            <span>{chip}</span>
          {/each}
        </div>

        {#if storyCards[storyIndex].showSwatches}
          <div class="story-strip__swatches">
            {#each storySwatches as swatch}
              <span class="story-strip__swatch" style={`background:${swatch}`}></span>
            {/each}
          </div>
        {/if}
      </div>

      <div class="story-strip__notes">
        <div class="story-strip__note">
          <span>VC pain point</span>
          <p>{storyCards[storyIndex].problem}</p>
        </div>
        <div class="story-strip__note">
          <span>How Deck AIStack solves it</span>
          <p>{storyCards[storyIndex].solution}</p>
        </div>
      </div>
    </article>
  {/key}

  <div class="story-strip__actions">
    <a class="button secondary" href="/#show-interest">Talk to Deck AIStack</a>
  </div>
</section>

<style>
  .story-strip {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
    display: grid;
    gap: 1.65rem;
    background:
      radial-gradient(circle at top right, rgba(104, 113, 255, 0.16), transparent 18rem),
      linear-gradient(180deg, rgba(9, 18, 42, 0.96), rgba(5, 12, 28, 0.99));
  }

  .story-strip__lead {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
    gap: 1.35rem;
    align-items: end;
  }

  .story-strip__lead h2 {
    margin: 0;
    font-size: clamp(1.7rem, 2.8vw, 2.8rem);
    letter-spacing: -0.05em;
    line-height: 0.98;
    max-width: 18ch;
  }

  .story-strip__lead p {
    margin: 0;
    line-height: 1.68;
  }

  .story-strip__nav {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .story-strip__tab {
    appearance: none;
    border: 1px solid rgba(118, 138, 194, 0.18);
    background: linear-gradient(180deg, rgba(19, 29, 66, 0.94), rgba(10, 16, 35, 0.97));
    color: rgba(234, 241, 255, 0.76);
    border-radius: 18px;
    min-height: 3.85rem;
    padding: 0.82rem 0.88rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
    text-align: left;
    font: inherit;
    cursor: pointer;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      background 180ms ease,
      color 180ms ease,
      box-shadow 180ms ease;
  }

  .story-strip__tab:hover,
  .story-strip__tab--active {
    transform: translateY(-2px);
    border-color: rgba(111, 159, 255, 0.28);
    background: linear-gradient(180deg, rgba(35, 52, 108, 0.96), rgba(13, 21, 45, 0.99));
    color: #f8fbff;
    box-shadow:
      0 10px 26px rgba(2, 7, 19, 0.22),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .story-strip__card {
    display: grid;
    grid-template-columns: minmax(0, 1.06fr) minmax(260px, 0.94fr);
    gap: 1.25rem;
    padding: 1.45rem;
    border-radius: 24px;
    border: 1px solid rgba(118, 138, 194, 0.2);
    background: linear-gradient(180deg, rgba(18, 29, 66, 0.96), rgba(9, 16, 35, 0.99));
    box-shadow:
      0 24px 42px rgba(2, 7, 19, 0.32),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .story-strip__main {
    display: grid;
    align-content: start;
    gap: 1rem;
  }

  .story-strip__kicker,
  .story-strip__note span {
    color: #8fb7ff;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }

  .story-strip__head {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .story-strip__head strong {
    display: block;
    margin-bottom: 0.2rem;
    color: #f8fbff;
    font-size: clamp(1.1rem, 1.8vw, 1.35rem);
  }

  .story-strip__head small {
    display: block;
    margin-top: 0.22rem;
    font-size: 0.78rem;
    color: rgba(223, 232, 248, 0.66);
  }

  .story-strip__tags,
  .story-strip__swatches,
  .story-strip__actions {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .story-strip__tags span {
    padding: 0.42rem 0.72rem;
    border-radius: 999px;
    border: 1px solid rgba(118, 138, 194, 0.2);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(239, 244, 255, 0.82);
    font-size: 0.76rem;
  }

  .story-strip__swatch {
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 0.45rem;
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  }

  .story-strip__notes {
    display: grid;
    gap: 0.85rem;
  }

  .story-strip__note {
    display: grid;
    gap: 0.5rem;
    padding: 1rem 1.05rem;
    border-radius: 18px;
    border: 1px solid rgba(118, 138, 194, 0.2);
    background: rgba(255, 255, 255, 0.04);
  }

  .story-strip__note p {
    margin: 0;
    color: rgba(239, 244, 255, 0.82);
    line-height: 1.55;
    font-size: 0.92rem;
  }

  .story-strip__icon {
    position: relative;
    width: 1.75rem;
    height: 1.75rem;
    flex: 0 0 auto;
    border-radius: 0.68rem;
    border: 1px solid rgba(113, 133, 196, 0.22);
    background: linear-gradient(180deg, rgba(33, 47, 97, 0.96), rgba(16, 24, 52, 0.98));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .story-strip__icon::before,
  .story-strip__icon::after {
    content: '';
    position: absolute;
  }

  .story-strip__icon--large {
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 0.9rem;
  }

  .story-strip__icon--intake::before {
    left: 25%;
    top: 18%;
    width: 42%;
    height: 54%;
    border-radius: 0.28rem;
    border: 1.6px solid #edf4ff;
  }

  .story-strip__icon--intake::after {
    right: 18%;
    top: 47%;
    width: 0.42rem;
    height: 0.42rem;
    border-top: 1.8px solid #7bd1ff;
    border-right: 1.8px solid #7bd1ff;
    transform: rotate(45deg);
  }

  .story-strip__icon--workspace::before {
    left: 24%;
    top: 22%;
    width: 18%;
    height: 56%;
    border-radius: 0.3rem;
    background: linear-gradient(180deg, #57b5ff, #6e68ff);
  }

  .story-strip__icon--workspace::after {
    left: 50%;
    top: 28%;
    width: 0.7rem;
    height: 0.14rem;
    border-radius: 999px;
    background: #edf4ff;
    box-shadow:
      0 0.34rem 0 #c5d7ff,
      0 0.68rem 0 #8fb7ff;
  }

  .story-strip__icon--diligence::before {
    left: 25%;
    top: 22%;
    width: 42%;
    height: 42%;
    border-radius: 999px;
    border: 1.8px solid #edf4ff;
  }

  .story-strip__icon--diligence::after {
    right: 21%;
    bottom: 22%;
    width: 0.44rem;
    height: 0.12rem;
    border-radius: 999px;
    background: #7bd1ff;
    transform: rotate(45deg);
    transform-origin: center;
  }

  .story-strip__icon--review::before {
    left: 22%;
    top: 20%;
    width: 54%;
    height: 58%;
    border-radius: 0.32rem;
    border: 1.6px solid #edf4ff;
  }

  .story-strip__icon--review::after {
    left: 38%;
    top: 45%;
    width: 0.46rem;
    height: 0.22rem;
    border-left: 1.8px solid #7df0bb;
    border-bottom: 1.8px solid #7df0bb;
    transform: rotate(-45deg);
  }

  .story-strip__icon--export::before {
    left: 22%;
    bottom: 22%;
    width: 50%;
    height: 34%;
    border-radius: 0.28rem;
    border: 1.6px solid #edf4ff;
  }

  .story-strip__icon--export::after {
    right: 22%;
    top: 23%;
    width: 0.5rem;
    height: 0.5rem;
    border-top: 1.8px solid #7bd1ff;
    border-right: 1.8px solid #7bd1ff;
    transform: rotate(45deg);
  }

  @media (max-width: 1080px) {
    .story-strip__lead,
    .story-strip__card {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 920px) {
    .story-strip__nav {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .story-strip {
      padding: 1.2rem;
    }

    .story-strip__nav {
      grid-template-columns: 1fr;
    }
  }
</style>
