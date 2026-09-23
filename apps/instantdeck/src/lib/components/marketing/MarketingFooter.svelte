<footer class="footer">
  <div class="footer-copy">
    <strong>Deck</strong>
    <p>AI-powered deck intelligence for investor and advisory workflows.</p>
  </div>

  <div class="footer-links">
    <nav>
      <strong>Product</strong>
      <a href="/pricing">Pricing</a>
      <a href="/billing">Billing</a>
      <a href="/vcs">For VCs</a>
    </nav>
    <nav>
      <strong>Company</strong>
      <a href="/about">About</a>
      <a href="/contact">Contact</a>
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
    </nav>
    <nav>
      <strong>Access</strong>
      <a href="/auth/sign-in">Sign in</a>
      <a href="/auth/sign-up">Create workspace</a>
      <a href="/#show-interest">Show interest</a>
    </nav>
  </div>
</footer>

<style>
  .footer {
    width: min(100% - 2rem, 1200px);
    margin: 0 auto;
    padding: 2rem 0 3rem;
    display: flex;
    justify-content: space-between;
    gap: 2rem;
    align-items: start;
    color: var(--muted);
  }

  .footer-copy {
    max-width: 480px;
  }

  .footer p {
    margin: 0.35rem 0 0;
    max-width: 480px;
  }

  nav {
    display: grid;
    gap: 0.45rem;
  }

  nav strong {
    color: var(--ink-strong);
    font-size: 0.9rem;
  }

  .footer-links {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
  }

  @media (max-width: 840px) {
    .footer {
      flex-direction: column;
      align-items: start;
    }
  }
</style>
