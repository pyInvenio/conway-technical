<script>
  import { invalidateAll } from '$app/navigation';
  import Icon from '$lib/components/ui/Icon.svelte';
  import { createAuthStore } from '$lib/stores/auth.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import Input from '$lib/components/ui/Input.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  let { show, onclose } = $props();
  
  const authStore = createAuthStore();
  let token = $state('');
  let isLoading = $state(false);
  let error = $state('');

  async function handleSubmit() {
    if (!token.trim()) {
      error = 'Please enter a GitHub PAT';
      return;
    }

    const trimmedToken = token.trim();
    if (!trimmedToken.startsWith('github_pat_') && !trimmedToken.startsWith('ghp_')) {
      error = 'Invalid PAT format. Should start with "github_pat_"';
      return;
    }

    isLoading = true;
    error = '';

    try {
      const response = await fetch('/api/auth/validate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: token.trim() })
      });

      if (response.ok) {
        authStore.addToken(token.trim());
        onclose();
        await invalidateAll();
      } else {
        const data = await response.json();
        error = data.error || 'Invalid token';
      }
    } catch (err) {
      error = 'Failed to validate token';
    } finally {
      isLoading = false;
    }
  }
</script>

{#if show}
<div
  class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
  onclick={onclose}
  role="button"
  tabindex="0"
  onkeydown={(e) => e.key === 'Escape' && onclose()}
>
  <div
    class="max-w-md w-full bg-gray-800 border border-gray-600 shadow-xl rounded-lg"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Header -->
    <div class="p-6 border-b border-gray-600">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-bold text-white">
          GitHub Authentication
        </h2>
        <button
          onclick={onclose}
          class="text-gray-400 hover:text-white"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="p-6 space-y-4">
      <p class="text-gray-300 text-sm">
        Enter your GitHub Personal Access Token (PAT) to connect to the monitoring system.
      </p>
      
      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
        <div class="space-y-2">
          <label for="token" class="text-sm font-medium text-white">
            GitHub PAT
          </label>
          <input
            id="token"
            type="password"
            bind:value={token}
            placeholder="github_pat_..."
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            required
          />
        </div>

        {#if error}
          <div class="p-3 bg-red-900 border border-red-700 rounded">
            <p class="text-red-300 text-sm">{error}</p>
          </div>
        {/if}

        <div class="flex gap-3 pt-2">
          <button
            type="button"
            onclick={onclose}
            class="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-white rounded"
          >
            {isLoading ? 'Validating...' : 'Connect'}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
{/if}
