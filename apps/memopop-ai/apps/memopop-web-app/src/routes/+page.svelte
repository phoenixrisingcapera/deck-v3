<script lang="ts">
	// Svelte 5 runes
	let count = $state(0);

	function increment() {
		count++;
	}
</script>

<svelte:head>
	<title>MemoPop Web App</title>
	<meta name="description" content="AI-powered investment memo generation" />
</svelte:head>

<main>
	<h1>MemoPop Web App</h1>
	<p>Interactive UI for investment memo generation.</p>

	<div class="counter">
		<button onclick={increment}>
			Count: {count}
		</button>
	</div>
</main>

<style>
	main {
		font-family: system-ui, -apple-system, sans-serif;
		max-width: 800px;
		margin: 0 auto;
		padding: 2rem;
		text-align: center;
	}

	h1 {
		color: #1a3a52;
	}

	.counter button {
		padding: 0.5rem 1rem;
		font-size: 1rem;
		cursor: pointer;
	}
</style>
