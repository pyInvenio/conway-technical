<script lang="ts">
  import { invalidateAll } from '$app/navigation';
  import Icon from "$lib/components/ui/Icon.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import WebSocketStatus from "$lib/components/ui/WebSocketStatus.svelte";
  import SettingsModal from "$lib/components/SettingsModal.svelte";

  let { user } = $props();
  
  let showSettingsModal = $state(false);
  
  async function handleLogout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      await invalidateAll();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }
</script>

<nav
  class="border-b border-terminal-border bg-terminal-bg/95 backdrop-blur supports-[backdrop-filter]:bg-terminal-bg/60"
>
  <div class="flex h-16 items-center px-6">
    <div class="flex items-center space-x-3">
      <div>
        <h1 class="text-xl font-bold text-terminal-text font-mono">
          GitHub{" "}<span class="text-green-400">Monitor</span>
        </h1>
      </div>
    </div>

    <div class="flex-1"></div>

    <div class="flex items-center space-x-4">
      <WebSocketStatus />
    </div>

    <div class="flex-1"></div>

    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-3">
        <img
          src={user?.avatar_url}
          alt={user?.name || user?.login}
          class="h-8 w-8 rounded-full border border-terminal-border"
        />
        <div class="text-sm">
          <p class="text-terminal-text font-medium">
            {user?.name || user?.login}
          </p>
        </div>
      </div>

      <Button 
        variant="ghost" 
        size="icon"
        onclick={() => showSettingsModal = true}
        title="Settings"
      >
        <Icon name="settings" class="h-4 w-4" />
      </Button>

      <Button 
        variant="ghost" 
        size="icon"
        onclick={handleLogout}
        title="Logout"
      >
        <Icon name="log-out" class="h-4 w-4" />
      </Button>
    </div>
  </div>
</nav>

<SettingsModal 
  show={showSettingsModal} 
  onclose={() => showSettingsModal = false}
  currentUser={user}
/>
