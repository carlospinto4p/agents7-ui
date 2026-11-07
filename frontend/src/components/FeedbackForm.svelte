<script>
  import { onMount, untrack } from 'svelte'
  import { on } from 'svelte/events'

  // The form that attaches one correction to one turn.
  //
  // This is the job no static page can do. Judging a read in a text
  // editor means typing `turn: 7` by hand and holding turn numbers
  // in your head; here the turn is whatever was clicked and
  // `he_said` is filled from the reply, so a correction cannot
  // drift from the line it corrects.

  let {
    conversation,
    turn = null,
    heSaid = '',
    entry = null,
    verdictKinds = {},
    onsave = () => {},
    oncancel = () => {},
    ondelete = null,
  } = $props()

  // Seeded from the existing entry when editing, otherwise blank
  // with `he_said` taken from the reply itself.
  //
  // `untrack` because these are deliberately one-shot seeds, not a
  // binding: once the form is open the operator's typing owns the
  // fields, and a re-render must not overwrite it. The caller
  // remounts the form (via `{#key}`) when a different entry is
  // opened, which is what makes that safe.
  const seed = untrack(() => entry) ?? {}
  let verdict = $state(seed.verdict ?? 'wrong')
  let shouldSay = $state(seed.should_say ?? '')
  let why = $state(seed.why ?? '')
  let rule = $state(seed.rule ?? '')
  let landsIn = $state(seed.lands_in ?? '')
  let shipped = $state(seed.shipped ?? '')

  // The framework refuses an entry carrying a verdict and nothing
  // else, so the button is disabled rather than letting the save
  // fail on the round trip.
  let sayable = $derived(
    Boolean(shouldSay.trim() || why.trim() || rule.trim()),
  )

  function save() {
    if (!sayable) return
    onsave({
      conversation,
      turn,
      verdict,
      he_said: heSaid,
      should_say: shouldSay.trim(),
      why: why.trim(),
      rule: rule.trim(),
      lands_in: landsIn.trim(),
      shipped: shipped.trim(),
    })
  }

  function copyTheLine() {
    shouldSay = heSaid
  }

  // Judging a read is dozens of these in a row, so the form is
  // usable without leaving the keyboard: it opens with the caret in
  // the first field, ctrl+enter saves from any field, and escape
  // cancels.
  //
  // The listener is attached here rather than in the markup: it
  // catches keys bubbling up from the fields, and the form itself
  // is never the thing being pressed.
  let root = $state()
  let firstField = $state()
  onMount(() => {
    firstField?.focus()
    return on(root, 'keydown', onkeydown)
  })

  function onkeydown(event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      save()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      oncancel()
    }
  }
</script>

<form
  class="form {verdict}"
  aria-label="Feedback"
  bind:this={root}
  onsubmit={(e) => e.preventDefault()}
>
  <div class="head">
    <span class="where">
      {conversation}{turn === null ? ' · whole conversation' : ` · turn ${turn}`}
    </span>
    <div class="verdicts">
      {#each Object.entries(verdictKinds) as [key, label] (key)}
        <button
          type="button"
          class="vbtn {key}"
          class:on={verdict === key}
          onclick={() => (verdict = key)}
        >{label}</button>
      {/each}
    </div>
  </div>

  {#if heSaid}
    <div class="said">
      <span class="lbl">He said</span>
      <p>{heSaid}</p>
    </div>
  {/if}

  <label class="field">
    <span class="lbl">
      Should say
      {#if heSaid}
        <button type="button" class="tiny" onclick={copyTheLine}>
          start from his line
        </button>
      {/if}
    </span>
    <textarea
      bind:this={firstField}
      bind:value={shouldSay}
      rows="2"
      placeholder="What it should have said. Leave blank for a rule with no rewrite."
    ></textarea>
  </label>

  <label class="field">
    <span class="lbl">Why</span>
    <textarea
      bind:value={why}
      rows="2"
      placeholder="The reasoning. This is what stops a settled question being reopened."
    ></textarea>
  </label>

  <label class="field">
    <span class="lbl">Rule</span>
    <textarea
      bind:value={rule}
      rows="2"
      placeholder="The instruction it becomes, in the config's own voice."
    ></textarea>
  </label>

  <div class="row">
    <label class="field grow">
      <span class="lbl">Lands in</span>
      <input
        bind:value={landsIn}
        placeholder="characters/david.yml"
      />
    </label>
    <label class="field">
      <span class="lbl">Shipped</span>
      <input bind:value={shipped} placeholder="v0.1.5" size="10" />
    </label>
  </div>

  <div class="actions">
    {#if ondelete}
      <button type="button" class="danger" onclick={ondelete}>
        Delete
      </button>
    {/if}
    <span class="spacer"></span>
    <span class="keys">ctrl+enter saves · esc cancels</span>
    <button type="button" class="ghost" onclick={oncancel}>Cancel</button>
    <button
      type="button"
      class="primary"
      onclick={save}
      disabled={!sayable}
      title={sayable
        ? 'Save this correction'
        : 'Needs a rewrite, a rule, or at least a reason'}
    >Save</button>
  </div>
</form>

<style>
  .form {
    border: 1px solid var(--border);
    border-left: 3px solid var(--neutral);
    border-radius: 0.55rem;
    background: var(--bg-surface);
    padding: 0.8rem 0.9rem;
    margin: 0.5rem 0 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .form.wrong { border-left-color: var(--fail); }
  .form.weak  { border-left-color: var(--warn); }
  .form.right { border-left-color: var(--pass); }

  .head {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .where {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .verdicts {
    display: flex;
    gap: 0.3rem;
    margin-left: auto;
  }
  .vbtn {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    border-radius: 999px;
    padding: 0.12rem 0.6rem;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .vbtn.on.wrong { color: var(--fail); border-color: var(--fail); background: var(--fail-bg); }
  .vbtn.on.weak  { color: var(--warn); border-color: var(--warn); background: var(--warn-bg); }
  .vbtn.on.right { color: var(--pass); border-color: var(--pass); background: var(--pass-bg); }

  .said {
    background: var(--bg-raised);
    border-radius: 0.45rem;
    padding: 0.4rem 0.6rem;
  }
  .said p {
    margin: 0.15rem 0 0;
    font-size: 1.0625rem;
    color: var(--text);
  }

  .field { display: flex; flex-direction: column; gap: 0.2rem; }
  .field.grow { flex: 1; min-width: 0; }
  .row { display: flex; gap: 0.6rem; align-items: flex-end; }

  .lbl {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.95rem;
    color: var(--text-muted);
    letter-spacing: 0.02em;
  }

  textarea,
  input {
    width: 100%;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 0.4rem;
    padding: 0.35rem 0.5rem;
    font: inherit;
    font-size: 1.0625rem;
    resize: vertical;
  }
  textarea:focus,
  input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .tiny {
    border: none;
    background: none;
    color: var(--accent);
    font-size: 0.95rem;
    cursor: pointer;
    padding: 0;
    text-decoration: underline;
  }

  .actions { display: flex; align-items: center; gap: 0.45rem; }
  .spacer { flex: 1; }
  .keys { font-size: 0.95rem; color: var(--text-muted); }

  .actions button {
    border-radius: 0.4rem;
    padding: 0.28rem 0.8rem;
    font-size: 1.0625rem;
    cursor: pointer;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
  }
  .actions .primary {
    border-color: var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
    font-weight: 600;
  }
  .actions .primary:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .actions .danger { border-color: var(--fail); color: var(--fail); }
  .actions .ghost { color: var(--text-muted); }
</style>
