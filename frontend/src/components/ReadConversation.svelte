<script>
  import { tick } from 'svelte'
  import FeedbackForm from './FeedbackForm.svelte'

  // One conversation, rendered as a chat client rather than as a
  // formatted transcript: the agent on the left because it is the
  // subject under review and the eye lands there first, and a
  // multi-line reply split into one bubble per line, because the
  // rhythm those line breaks produce is one of the things being
  // judged.
  //
  // The payload comes from `agents7.eval.chat_review.read_payload`,
  // the same data the generated page renders, so this page and that
  // one cannot disagree about what a read contains.

  let {
    conv,
    review = true,
    verdictKinds = {},
    noteKinds = {},
    entriesFor = () => [],
    structural = [],
    onsave = () => {},
    ondelete = () => {},
  } = $props()

  // Which turn currently has the form open. `null` is closed;
  // `'structural'` is the whole-conversation note, which anchors to
  // no line and is the most valuable kind of feedback there is.
  let editing = $state(null)
  let editingEntry = $state(null)

  function open(key, entry = null) {
    editing = key
    editingEntry = entry
  }

  function close() {
    editing = null
    editingEntry = null
  }

  // Where the keyboard goes next. Every place a form can open has
  // one button that opens it, tagged with its key; focus moves
  // between those, so a read can be judged turn after turn without
  // the mouse. The whole-conversation note comes first, then the
  // turns in order.
  let root = $state()

  function neighbour(key, step) {
    const keys = ['structural', ...conv.turns.map((t) => t.i)]
    const at = keys.indexOf(key) + step
    return keys[Math.min(Math.max(at, 0), keys.length - 1)]
  }

  async function focusAdd(key) {
    await tick()
    root?.querySelector(`[data-add="${key}"]`)?.focus()
  }

  // Saving moves on to the next turn; cancelling and deleting stay
  // on the turn they were on.
  async function save(entry) {
    const key = editing
    await onsave(entry)
    close()
    focusAdd(neighbour(key, 1))
  }

  function cancel() {
    const key = editing
    close()
    focusAdd(key)
  }

  function remove() {
    const key = editing
    ondelete(editingEntry)
    close()
    focusAdd(key)
  }

  // Which turns have been judged, for the strip above the thread.
  // On a twenty-turn conversation the entries themselves are
  // spread over several screens, so nothing else shows what is
  // done and what is left.
  let judged = $derived(
    conv.turns.filter((t) => entriesFor(t.i).length > 0).length,
  )

  // What the conversation ran with, one section per group the
  // framework names on each row. Rows with no group (a payload from
  // before agents7 v9.25.0) fall into one untitled section.
  const GROUP_TITLES = {
    run: 'Run',
    context: 'Context',
    memory: 'Knew already',
    variants: 'Variants',
  }

  // A value past this many characters gets the section's whole
  // width rather than one column of it. A variant is a line of the
  // agent's own text, so it always does.
  const WIDE_VALUE = 48

  let contextGroups = $derived.by(() => {
    const groups = []
    for (const row of conv.context ?? []) {
      const key = row.group ?? ''
      let group = groups.find((g) => g.key === key)
      if (!group) {
        group = { key, title: GROUP_TITLES[key] ?? '', rows: [] }
        groups.push(group)
      }
      group.rows.push(row)
    }
    return groups
  })

  function goTo(key) {
    root
      ?.querySelector(`[data-turn="${key}"]`)
      ?.scrollIntoView({ block: 'center' })
    focusAdd(key)
  }

  // Arrow up and down step between the turns' buttons, skipping
  // the entries and guard details that tab would stop on.
  function step(event, key) {
    const by = { ArrowDown: 1, ArrowUp: -1 }[event.key]
    if (!by) return
    event.preventDefault()
    focusAdd(neighbour(key, by))
  }

  function cents(value, places) {
    return value === null || value === undefined
      ? 'unpriced'
      : `${value.toFixed(places)}c`
  }

  // Mirrors the generated page's metrics line, including the parts
  // that are easy to drop: the guard is roughly half of a turn's
  // wall clock and half its price, so a single figure hides it.
  function meta(t) {
    const bits = [
      ['agent', `${t.chatter_s.toFixed(2)}s`],
      [
        'guard',
        `${t.guard_s.toFixed(2)}s${t.attempts > 1 ? ` ×${t.attempts}` : ''}`,
      ],
      ['gap', `${t.gap_s.toFixed(2)}s`],
      ['total', `${t.wall_s.toFixed(2)}s`],
      [
        'cost',
        `${cents(
          t.chatter_c === null || t.guard_c === null
            ? null
            : t.chatter_c + t.guard_c,
          4,
        )} (${cents(t.chatter_c, 4)} + ${cents(t.guard_c, 4)})`,
      ],
      ['running', cents(t.running_c, 3)],
    ]
    if (t.prompt_t) {
      const cache =
        t.cached_pct === null ? '' : ` (${t.cached_pct}% cached)`
      bits.push(['tokens', `${t.prompt_t}p${cache} / ${t.out_t}g`])
    }
    if (t.cached) bits.push(['served from cache', ''])
    if (t.retries) bits.push(['retries', String(t.retries)])
    return bits
  }
</script>

<section class="conv" bind:this={root}>
  <header class="conv-head">
    <h2>{conv.title}</h2>
    <span class="tag">{conv.tag}</span>
  </header>

  {#if conv.note}
    <p class="conv-note">{@html conv.note}</p>
  {/if}

  <!-- Stays in Read mode. It is context for the chat, the way a
       messenger names who you are talking to and when, not part of
       the review apparatus the toggle strips. -->
  {#if conv.context?.length}
    <section class="ctx" aria-label="What the conversation ran with">
      {#each contextGroups as group (group.key)}
        <div
          class="ctx-group"
          class:untitled={!group.title}
          data-group={group.key}
        >
          {#if group.title}
            <h3 class="ctx-title">{group.title}</h3>
          {/if}
          {#if group.key === 'memory'}
            <ul class="ctx-items">
              {#each group.rows.flatMap((r) => r.items ?? [r.value]) as item, i (i)}
                <li>{item}</li>
              {/each}
            </ul>
          {:else}
            <dl class="ctx-body">
              {#each group.rows as row (row.label)}
                <div
                  class="ctx-row"
                  class:wide={group.key === 'variants' ||
                    row.value.length > WIDE_VALUE}
                >
                  <dt>
                    {group.key === 'variants'
                      ? row.label.replace(/^variant: /, '')
                      : row.label}
                  </dt>
                  <dd>{row.value}</dd>
                </div>
              {/each}
            </dl>
          {/if}
        </div>
      {/each}
    </section>
  {/if}

  {#if review}
    <div class="structural">
      {#each structural as e (e.turn + e.why + e.rule)}
        <button
          type="button"
          class="entry {e.verdict}"
          onclick={() => open('structural', e)}
        >
          <span class="vlabel">{verdictKinds[e.verdict] ?? e.verdict}</span>
          <span class="etext">{e.rule || e.why}</span>
        </button>
      {/each}
      {#if editing === 'structural'}
        <!-- Keyed so opening a different entry remounts the form;
             its fields are one-shot seeds, not bindings. -->
        {#key editingEntry}
          <FeedbackForm
            conversation={conv.id}
            turn={null}
            heSaid=""
            entry={editingEntry}
            {verdictKinds}
            onsave={save}
            oncancel={cancel}
            ondelete={editingEntry ? remove : null}
          />
        {/key}
      {:else}
        <button
          type="button"
          class="add whole"
          data-add="structural"
          onclick={() => open('structural')}
          onkeydown={(e) => step(e, 'structural')}
        >
          + Note about the whole conversation
        </button>
      {/if}
    </div>
  {/if}

  {#if review}
    <nav class="turnmap" aria-label="Turns with feedback">
      <span class="maplabel">
        Feedback on {judged} of {conv.turns.length} turns
      </span>
      {#each conv.turns as t (t.i)}
        {@const count = entriesFor(t.i).length}
        <button
          type="button"
          class="mark"
          class:has={count > 0}
          title={count
            ? `Turn ${t.i}: ${count} feedback ${count === 1 ? 'entry' : 'entries'}`
            : `Turn ${t.i}: no feedback yet`}
          onclick={() => goTo(t.i)}
        >{t.i}</button>
      {/each}
    </nav>
  {/if}

  <div class="thread">
    {#each conv.turns as t (t.i)}
      {@const entries = entriesFor(t.i)}
      <div class="turn" data-turn={t.i}>
        {#if t.prompt !== null && t.prompt !== undefined}
          <div class="row mine">
            <div class="bubble">{t.prompt}</div>
          </div>
        {/if}

        {#if review}
          <div class="turnno">turn {t.i}</div>
        {/if}

        {#each t.messages as m, mi (mi)}
          <div class="row his">
            <div class="bubble">{m}</div>
          </div>
        {/each}

        {#if review}
          <div class="meta">
            {#each meta(t) as [key, value] (key)}
              <span class:hot={key === 'retries'}>
                <b>{key}</b>{value ? ` ${value}` : ''}
              </span>
            {/each}
          </div>

          {#if t.rejected}
            <details class="attempts">
              <summary>
                Guard: {t.rejected} rejected of {t.attempts} checks
              </summary>
              <ol>
                {#each t.attempts_detail as a, ai (ai)}
                  <li>
                    {#if a.accepted}
                      <span class="ok">accepted</span>
                    {:else}
                      <span class="rej">rejected · {a.reason}</span>
                    {/if}
                    <br />{a.text}
                    {#if a.used_fix}<em> (this is what shipped)</em>{/if}
                    {#if a.fix_repeats}
                      <br /><em>
                        Its suggested fix was the same text, character
                        for character.
                      </em>
                    {/if}
                  </li>
                {/each}
              </ol>
            </details>
          {/if}

          {#each t.notes as n, ni (ni)}
            <div class="note {n.kind}">
              <span class="lbl">{n.label ?? noteKinds[n.kind]}</span>
              <p>{@html n.text}</p>
            </div>
          {/each}

          {#each entries as e, ei (ei)}
            <button
              type="button"
              class="entry {e.verdict}"
              onclick={() => open(t.i, e)}
            >
              <span class="vlabel">
                {verdictKinds[e.verdict] ?? e.verdict}
              </span>
              <span class="etext">
                {e.should_say || e.rule || e.why}
              </span>
            </button>
          {/each}

          {#if editing === t.i}
            {#key editingEntry}
              <FeedbackForm
                conversation={conv.id}
                turn={t.i}
                heSaid={t.messages.join('\n')}
                entry={editingEntry}
                {verdictKinds}
                onsave={save}
                oncancel={cancel}
                ondelete={editingEntry ? remove : null}
              />
            {/key}
          {:else}
            <button
              type="button"
              class="add"
              data-add={t.i}
              onclick={() => open(t.i)}
              onkeydown={(e) => step(e, t.i)}
            >+ Feedback on turn {t.i}</button>
          {/if}
        {/if}
      </div>
    {/each}
  </div>
</section>

<style>
  .conv { padding-bottom: 1.5rem; }

  .conv-head {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 0.6rem;
    flex-wrap: wrap;
  }
  .conv-head h2 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--text-strong);
  }
  .tag {
    margin-left: auto;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .conv-note {
    margin: 0 0 0.8rem;
    color: var(--text-muted);
    font-size: 1.0625rem;
  }

  /* ── Context ────────────────────────────────────────── */
  .ctx {
    margin: 0 0 1.1rem;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 0.6rem;
    overflow: hidden;
  }
  /* One section per group: its name in a left gutter, its rows
     beside it. */
  .ctx-group {
    display: grid;
    grid-template-columns: 9rem minmax(0, 1fr);
    gap: 0.4rem 1.2rem;
    padding: 0.8rem 1rem;
  }
  .ctx-group + .ctx-group { border-top: 1px solid var(--border); }
  .ctx-group.untitled { grid-template-columns: minmax(0, 1fr); }
  .ctx-group[data-group='run'] { background: var(--bg-raised); }
  .ctx-title {
    margin: 0;
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-muted);
  }
  .ctx-body {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.7rem 1.6rem;
  }
  /* Label over value, so a long value wraps under its own label
     instead of beside it. */
  .ctx-row { min-width: 0; }
  .ctx-row.wide { grid-column: 1 / -1; }
  .ctx dt {
    color: var(--text-muted);
    font-size: 1.0625rem;
  }
  .ctx dd {
    margin: 0;
    color: var(--text-strong);
    font-size: 1.0625rem;
    overflow-wrap: anywhere;
  }
  .ctx-items {
    margin: 0;
    padding-left: 1.1rem;
    columns: 22rem;
    column-gap: 2.4rem;
    color: var(--text);
    font-size: 1.0625rem;
  }
  .ctx-items li {
    break-inside: avoid;
    padding: 0.1rem 0;
  }
  .ctx-items li::marker { color: var(--text-muted); }

  /* ── Thread ─────────────────────────────────────────── */
  .thread { display: flex; flex-direction: column; }
  .turn { display: flex; flex-direction: column; margin-bottom: 0.9rem; }

  .row { display: flex; margin-bottom: 0.25rem; }
  .row.his { justify-content: flex-start; }
  .row.mine { justify-content: flex-end; }

  .bubble {
    max-width: min(80%, 620px);
    padding: 0.45rem 0.75rem;
    border-radius: 0.9rem;
    font-size: 1.0625rem;
    line-height: 1.45;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .row.his .bubble {
    background: var(--bg-raised);
    color: var(--text-strong);
    border-bottom-left-radius: 0.25rem;
  }
  .row.mine .bubble {
    background: var(--accent-dim);
    color: var(--text);
    border-bottom-right-radius: 0.25rem;
  }

  .turnno {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin: 0.35rem 0 0.15rem;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.15rem 0.9rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
  }
  .meta b { color: var(--text); font-weight: 600; }
  .meta .hot { color: var(--warn); }

  .attempts {
    margin-top: 0.4rem;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .attempts summary { cursor: pointer; }
  .attempts ol { margin: 0.4rem 0 0; padding-left: 1.2rem; }
  .attempts li { margin-bottom: 0.4rem; }
  .ok { color: var(--pass); }
  .rej { color: var(--fail); }

  /* ── Notes from the read spec ───────────────────────── */
  .note {
    margin-top: 0.45rem;
    padding: 0.45rem 0.7rem;
    border-left: 3px solid var(--neutral);
    border-radius: 0.35rem;
    background: var(--bg-surface);
  }
  .note p { margin: 0.15rem 0 0; font-size: 1.0625rem; }
  .note .lbl {
    font-size: 0.95rem;
    letter-spacing: 0.02em;
    color: var(--text-muted);
  }
  .note.worked { border-left-color: var(--pass); }
  .note.call { border-left-color: var(--accent); }
  .note.defect { border-left-color: var(--fail); }
  .note.guard { border-left-color: var(--warn); }

  /* ── Feedback entries ───────────────────────────────── */
  .entry {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    width: 100%;
    text-align: left;
    margin-top: 0.4rem;
    padding: 0.4rem 0.7rem;
    border: 1px solid var(--border);
    border-left: 3px solid var(--neutral);
    border-radius: 0.35rem;
    background: var(--bg-surface);
    color: var(--text);
    font: inherit;
    font-size: 1.0625rem;
    cursor: pointer;
  }
  .entry:hover { border-color: var(--accent); }
  .entry.wrong { border-left-color: var(--fail); }
  .entry.weak { border-left-color: var(--warn); }
  .entry.right { border-left-color: var(--pass); }
  .vlabel {
    flex: 0 0 auto;
    font-size: 0.95rem;
    color: var(--text-muted);
  }
  .etext { min-width: 0; overflow-wrap: anywhere; }

  .add {
    align-self: flex-start;
    margin-top: 0.35rem;
    border: 1px dashed var(--border);
    background: transparent;
    color: var(--text-muted);
    border-radius: 0.35rem;
    padding: 0.2rem 0.6rem;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .add:hover { color: var(--accent); border-color: var(--accent); }
  .add.whole { margin-bottom: 0.6rem; }

  .structural { display: flex; flex-direction: column; }

  /* ── Turn strip ─────────────────────────────────────── */
  .turnmap {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
    margin-bottom: 0.9rem;
  }
  .maplabel {
    font-size: 1.0625rem;
    color: var(--text-muted);
    margin-right: 0.4rem;
  }
  .mark {
    min-width: 1.9rem;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    border-radius: 0.35rem;
    padding: 0.1rem 0.35rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.9rem;
    cursor: pointer;
  }
  .mark:hover { border-color: var(--accent); }
  .mark.has {
    border-color: var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
    font-weight: 600;
  }

  @media (max-width: 560px) {
    .ctx-group { grid-template-columns: minmax(0, 1fr); }
    .bubble { max-width: 92%; }
  }
</style>
