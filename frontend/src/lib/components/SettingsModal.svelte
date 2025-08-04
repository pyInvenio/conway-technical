<script>
  import { invalidateAll } from '$app/navigation';
  import Icon from '$lib/components/ui/Icon.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Input from '$lib/components/ui/Input.svelte';

  let { show, onclose, currentUser } = $props();
  
  let tokens = $state([]);
  let newToken = $state('');
  let isLoading = $state(false);
  let error = $state('');
  let isAddingToken = $state(false);

  // Mock stored tokens (in real app, fetch from server)
  $effect(() => {
    if (show && currentUser) {
      // For now, just show current session token info
      tokens = [{
        id: 1,
        name: 'Current Session',
        token: '***************',
        scopes: ['repo', 'read:user'],
        lastUsed: new Date(),
        isActive: true
      }];
    }
  });

  async function handleAddToken() {
    if (!newToken.trim()) {
      error = 'Please enter a GitHub PAT';
      return;
    }

    const trimmedToken = newToken.trim();
    if (!trimmedToken.startsWith('github_pat_') && !trimmedToken.startsWith('ghp_')) {
      error = 'Invalid PAT format. Should start with "github_pat_" or "ghp_"';
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
        body: JSON.stringify({ token: trimmedToken })
      });

      if (response.ok) {
        const data = await response.json();
        // Add to tokens list (in real app, save to server)
        tokens = [...tokens, {
          id: Date.now(),
          name: `Token for ${data.user?.login || 'User'}`,
          token: trimmedToken.substring(0, 12) + '***************',
          scopes: ['repo', 'read:user'], // From GitHub API response
          lastUsed: new Date(),
          isActive: false
        }];
        
        newToken = '';
        isAddingToken = false;
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

  function removeToken(tokenId) {
    tokens = tokens.filter(t => t.id !== tokenId);
  }

  function setActiveToken(tokenId) {
    tokens = tokens.map(t => ({
      ...t,
      isActive: t.id === tokenId
    }));
    // In real app, update session to use this token
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
    class="max-w-2xl w-full bg-gray-800 border border-gray-600 shadow-xl rounded-lg max-h-[80vh] overflow-y-auto"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Header -->
    <div class="p-6 border-b border-gray-600 sticky top-0 bg-gray-800">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-bold text-white flex items-center gap-2">
          <Icon name="settings" class="h-5 w-5" />
          Settings
        </h2>
        <button
          onclick={onclose}
          class="text-gray-400 hover:text-white"
        >
          <Icon name="x" class="h-5 w-5" />
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="p-6 space-y-6">
      <!-- User Info Section -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold text-white">Account Information</h3>
        <div class="flex items-center gap-4 p-4 bg-gray-700 rounded-lg">
          <img
            src={currentUser?.avatar_url}
            alt={currentUser?.name || currentUser?.login}
            class="h-12 w-12 rounded-full border border-gray-600"
          />
          <div>
            <p class="text-white font-medium">
              {currentUser?.name || currentUser?.login}
            </p>
            <p class="text-gray-400 text-sm">
              @{currentUser?.login}
            </p>
          </div>
        </div>
      </div>

      <!-- GitHub PATs Section -->
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-white">GitHub Personal Access Tokens</h3>
          <Button
            onclick={() => isAddingToken = !isAddingToken}
            variant="outline"
            size="sm"
          >
            <Icon name="plus" class="h-4 w-4 mr-2" />
            Add Token
          </Button>
        </div>

        <!-- Add New Token Form -->
        {#if isAddingToken}
          <div class="p-4 bg-gray-700 rounded-lg space-y-4">
            <form onsubmit={(e) => { e.preventDefault(); handleAddToken(); }} class="space-y-4">
              <div class="space-y-2">
                <label for="newToken" class="text-sm font-medium text-white">
                  New GitHub PAT
                </label>
                <Input
                  id="newToken"
                  type="password"
                  bind:value={newToken}
                  placeholder="github_pat_... or ghp_..."
                  class="w-full"
                />
              </div>

              {#if error}
                <div class="p-3 bg-red-900 border border-red-700 rounded">
                  <p class="text-red-300 text-sm">{error}</p>
                </div>
              {/if}

              <div class="flex gap-3">
                <Button
                  type="button"
                  onclick={() => {
                    isAddingToken = false;
                    newToken = '';
                    error = '';
                  }}
                  variant="ghost"
                  size="sm"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isLoading}
                  size="sm"
                >
                  {isLoading ? 'Validating...' : 'Add Token'}
                </Button>
              </div>
            </form>
          </div>
        {/if}

        <!-- Token List -->
        <div class="space-y-3">
          {#each tokens as token (token.id)}
            <div class="p-4 bg-gray-700 rounded-lg">
              <div class="flex items-center justify-between">
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <p class="text-white font-medium">{token.name}</p>
                    {#if token.isActive}
                      <span class="px-2 py-1 bg-green-600 text-green-100 text-xs rounded">
                        Active
                      </span>
                    {/if}
                  </div>
                  <p class="text-gray-400 text-sm font-mono">{token.token}</p>
                  <div class="flex items-center gap-4 mt-2 text-xs text-gray-400">
                    <span>Scopes: {token.scopes.join(', ')}</span>
                    <span>Last used: {token.lastUsed.toLocaleDateString()}</span>
                  </div>
                </div>
                
                <div class="flex items-center gap-2">
                  {#if !token.isActive}
                    <Button
                      onclick={() => setActiveToken(token.id)}
                      variant="ghost"
                      size="sm"
                    >
                      Use
                    </Button>
                  {/if}
                  
                  {#if !token.isActive}
                    <Button
                      onclick={() => removeToken(token.id)}
                      variant="ghost"
                      size="sm"
                      class="text-red-400 hover:text-red-300"
                    >
                      <Icon name="trash-2" class="h-4 w-4" />
                    </Button>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
          
          {#if tokens.length === 0}
            <div class="text-center py-8 text-gray-400">
              <Icon name="key" class="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No GitHub tokens configured</p>
            </div>
          {/if}
        </div>
      </div>

      <!-- Danger Zone -->
      <div class="pt-6 border-t border-gray-600">
        <h3 class="text-lg font-semibold text-red-400 mb-4">Danger Zone</h3>
        <div class="p-4 bg-red-900/20 border border-red-700/50 rounded-lg">
          <p class="text-red-300 text-sm mb-3">
            Logout will end your current session and disconnect from real-time monitoring.
          </p>
          <Button
            onclick={async () => {
              await fetch('/api/auth/logout', { method: 'POST' });
              await invalidateAll();
              onclose();
            }}
            variant="destructive"
            size="sm"
          >
            <Icon name="log-out" class="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>
    </div>
  </div>
</div>
{/if}