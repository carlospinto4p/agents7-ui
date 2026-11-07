<script>
  import { onMount, untrack } from 'svelte'
  import ReadConversation from '../components/ReadConversation.svelte'
  import { copyText, downloadText } from '../lib/format.js'

  // Read a chat agent's recorded conversations, and feed back on
  // them. Two jobs: render a read the way the generated page does,
  // and let a correction be attached to a turn — the job a static
  // page cannot do, and the slow half of judging a read.
  //
  // The transcript is rendered here rather than embedded so a turn
  // can be clicked. The payload it renders is the framework's own
  // `read_payload`, which is what keeps this page and the generated
  // one from drifting apart.

  let reads = $state([])
  let selected = $state('')
  let detail = $state(null)
  let loading = $state(false)
  let error = $state(null)
  let saving = $state(false)
  let saveNote = $state('')

  // Review shows the apparatus — turn numbers, metrics, guard
  // checks, notes and the annotate affordance. Read strips all of
  // it and leaves the conversations. Default to Review, so the page
  // explains itself when opened.
  let review = $state(true)
  let tab = $state('verdicts')

  let report = $state('')
  let ruleChanges = $state([])
  let evalRows = $state(0)

  // The tab lives in the hash — `#/reads/conv-1` — so one
  // conversation can be linked to, the way the generated page's
  // `read.html#conv-1` can. The App router reads only the first
  // segment, so the extra one is ours.
  //
  // The read lives there too, as a query — `?read=<path>` — so a
  // read can be linked to and not only the first one in the list.
  // `conv=<id>` names a conversation by its id rather than its
  // position, for a link written before the read was loaded: the
  // Chatter page knows the name it just saved under, not where that
  // lands among the folder's other recordings.
  function hashParts() {
    const [path, query = ''] = window.location.hash
      .replace('#/', '')
      .split('?')
    return {
      tab: path.split('/')[1] ?? '',
      params: new URLSearchParams(query),
    }
  }

  // Consumed by the first load only, so choosing another read from
  // the dropdown is not dragged back to the linked conversation.
  let askedConversation = hashParts().params.get('conv') ?? ''

  function selectTab(key) {
    tab = key
    const url =
      `#/reads/${key}` +
      (selected ? `?read=${encodeURIComponent(selected)}` : '')
    if (window.location.hash !== url) {
      history.replaceState(null, '', url)
    }
  }

  let entries = $derived(detail?.feedback?.entries ?? [])
  let golden = $derived(detail?.feedback?.golden ?? [])

  let conversations = $derived(detail?.conversations ?? [])

  // Verdicts and Numbers only exist when a `read.yml` supplied
  // them. A folder of raw recordings still opens, on its
  // conversations alone.
  let tabs = $derived.by(() => {
    if (!detail) return []
    const list = []
    if (detail.verdicts?.length) list.push({ key: 'verdicts', label: 'Verdicts' })
    if (Object.keys(detail.measures ?? {}).length)
      list.push({ key: 'numbers', label: 'Numbers' })
    // Each conversation's tab carries how many entries it has, so
    // what has been judged shows without opening every one.
    conversations.forEach((c, i) =>
      list.push({
        key: `conv-${i}`,
        label: c.tab || c.title,
        conv: true,
        count: entries.filter((e) => e.conversation === c.id).length,
      }),
    )
    list.push({ key: 'feedback', label: 'Feedback' })
    return list
  })

  // Read mode leaves the conversations and nothing else, so the
  // first pass is the bare chat rather than a page of annotations
  // telling the reader what to think before they have a view.
  let shownTabs = $derived(review ? tabs : tabs.filter((t) => t.conv))

  $effect(() => {
    const visible = shownTabs
    if (visible.length && !visible.some((t) => t.key === tab)) {
      // Untracked: `selectTab` reads `selected` to write the URL,
      // and that is not something this effect should re-run on.
      untrack(() => selectTab(visible[0].key))
    }
  })

  function entriesFor(conversationId, turn) {
    return entries.filter(
      (e) => e.conversation === conversationId && (e.turn ?? null) === turn,
    )
  }

  function structuralFor(conversationId) {
    return entries.filter(
      (e) => e.conversation === conversationId && (e.turn ?? null) === null,
    )
  }

  async function loadReads() {
    try {
      const r = await fetch('/api/reads')
      reads = (await r.json()).reads ?? []
      if (reads.length && !selected) {
        const asked = hashParts().params.get('read')
        selected = reads.some((x) => x.path === asked)
          ? asked
          : reads[0].path
        await loadDetail()
      }
    } catch {
      error = 'Could not list reads.'
    }
  }

  async function loadDetail() {
    if (!selected) return
    loading = true
    error = null
    saveNote = ''
    try {
      const r = await fetch(
        `/api/reads/detail?path=${encodeURIComponent(selected)}`,
      )
      if (!r.ok) {
        error = (await r.json()).detail ?? 'Could not load that read.'
        detail = null
        return
      }
      detail = await r.json()
      const linked = detail.conversations.findIndex(
        (c) => c.id === askedConversation,
      )
      askedConversation = ''
      const asked = linked >= 0 ? `conv-${linked}` : hashParts().tab
      selectTab(asked || (detail.verdicts?.length ? 'verdicts' : 'conv-0'))
      await loadReport()
    } catch {
      error = 'Could not load that read.'
      detail = null
    } finally {
      loading = false
    }
  }

  async function loadReport() {
    try {
      const r = await fetch(
        `/api/reads/report?path=${encodeURIComponent(selected)}`,
      )
      if (!r.ok) return
      const body = await r.json()
      report = body.report
      ruleChanges = body.rule_changes ?? []
      evalRows = body.eval_rows ?? 0
    } catch {
      // The report is derived; a failure here leaves the
      // transcripts perfectly readable.
    }
  }

  async function saveEntry(entry) {
    saving = true
    saveNote = ''
    try {
      const r = await fetch(
        `/api/reads/feedback?path=${encodeURIComponent(selected)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ entries: [entry] }),
        },
      )
      const body = await r.json()
      if (!r.ok) {
        saveNote = body.detail ?? 'Could not save.'
        return
      }
      detail = { ...detail, feedback: body.feedback }
      report = body.report
      ruleChanges = body.rule_changes ?? []
      evalRows = body.eval_rows ?? 0
      saveNote = 'Saved to feedback.yml'
    } catch {
      saveNote = 'Could not save.'
    } finally {
      saving = false
    }
  }

  // Deleting empties the turn, then re-sends every OTHER entry on
  // it. The `clear` is what makes removing the last entry on a turn
  // work: merging keys on the turns the incoming entries name, so
  // an empty list names no turn and would leave the entry standing.
  async function deleteEntry(entry) {
    const turn = entry.turn ?? null
    const survivors = entries.filter(
      (e) =>
        e.conversation === entry.conversation &&
        (e.turn ?? null) === turn &&
        e !== entry,
    )
    saving = true
    saveNote = ''
    try {
      const r = await fetch(
        `/api/reads/feedback?path=${encodeURIComponent(selected)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            entries: survivors,
            clear: [{ conversation: entry.conversation, turn }],
          }),
        },
      )
      const body = await r.json()
      if (!r.ok) {
        saveNote = body.detail ?? 'Could not delete.'
        return
      }
      detail = { ...detail, feedback: body.feedback }
      report = body.report
      ruleChanges = body.rule_changes ?? []
      evalRows = body.eval_rows ?? 0
      saveNote = 'Saved to feedback.yml'
    } catch {
      saveNote = 'Could not delete.'
    } finally {
      saving = false
    }
  }

  async function toggleGolden(conversationId) {
    const next = golden.includes(conversationId)
      ? golden.filter((g) => g !== conversationId)
      : [...golden, conversationId]
    saving = true
    try {
      const r = await fetch(
        `/api/reads/feedback?path=${encodeURIComponent(selected)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ entries: [], golden: next }),
        },
      )
      if (!r.ok) return
      const body = await r.json()
      detail = { ...detail, feedback: body.feedback }
      report = body.report
    } finally {
      saving = false
    }
  }

  onMount(loadReads)
</script>

<div class="page">
  <header class="top">
    <div class="picker">
      <label for="read-select">Read</label>
      <select
        id="read-select"
        bind:value={selected}
        onchange={loadDetail}
      >
        {#each reads as r (r.path)}
          <option value={r.path}>
            {r.agent} v{r.agent_version} · {r.id}
            ({r.conversations} conversation{r.conversations === 1 ? '' : 's'}{r.has_feedback ? ', feedback' : ''})
          </option>
        {/each}
      </select>
    </div>
    <div class="modes">
      <button
        type="button"
        class:on={!review}
        onclick={() => (review = false)}
      >Read</button>
      <button
        type="button"
        class:on={review}
        onclick={() => (review = true)}
      >Review</button>
    </div>
  </header>

  {#if error}
    <p class="error">{error}</p>
  {:else if loading}
    <p class="muted">Loading…</p>
  {:else if !reads.length}
    <p class="muted">
      No reads found. A read is a folder under an agent's
      <code>docs/reads/</code> holding at least one recording written
      by <code>ConversationRecorder</code>.
    </p>
  {:else if detail}
    <div class="masthead">
      {#if detail.eyebrow}<div class="eyebrow">{detail.eyebrow}</div>{/if}
      <h1>{detail.title}</h1>
      {#if detail.standfirst}
        <p class="standfirst">{@html detail.standfirst}</p>
      {/if}
      {#if !detail.has_read_spec}
        <p class="nospec">
          No <code>read.yml</code> in this folder, so there are no
          verdicts or notes — the recordings are shown on their own.
          Feedback works either way.
        </p>
      {/if}
      {#if review && detail.caveat}
        <div class="caveat">{@html detail.caveat}</div>
      {/if}
    </div>

    <nav class="tabs">
      {#each shownTabs as t (t.key)}
        <button
          type="button"
          class:on={tab === t.key}
          onclick={() => selectTab(t.key)}
        >
          {t.label}
          {#if review && t.count}
            <span
              class="count"
              title="{t.count} feedback {t.count === 1 ? 'entry' : 'entries'}"
            >{t.count}</span>
          {/if}
        </button>
      {/each}
    </nav>

    {#if review && tab === 'verdicts'}
      <div class="cards">
        {#each detail.verdicts as v (v.claim)}
          <article class="verdict">
            <div class="vhead">
              <h3>{v.claim}</h3>
              <span class="stamp {v.stamp}">{v.label}</span>
            </div>
            <p>{@html v.detail}</p>
          </article>
        {/each}
      </div>
      {#if detail.closing?.length}
        <div class="closing">
          {#each detail.closing as p, i (i)}
            <p>{@html p}</p>
          {/each}
        </div>
      {/if}
    {:else if review && tab === 'numbers'}
      <div class="scroller">
        <table>
          <thead>
            <tr>
              <th>Measure</th>
              <th class="num">This read</th>
              {#if detail.comparison?.length}
                <th class="num">Previous</th>
                <th>Reading</th>
              {/if}
            </tr>
          </thead>
          <tbody>
            {#if detail.comparison?.length}
              {#each detail.comparison as row (row.measure)}
                <tr>
                  <td>{row.measure}</td>
                  <td class="num">{row.current}</td>
                  <td class="num">{row.previous}</td>
                  <td class="reading">{row.reading}</td>
                </tr>
              {/each}
            {:else}
              {#each Object.entries(detail.measures) as [name, value] (name)}
                <tr>
                  <td>{name}</td>
                  <td class="num">{value}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
      {#if detail.pricing}
        <p class="muted small">{@html detail.pricing}</p>
      {/if}
    {:else if tab === 'feedback'}
      <div class="feedback-pane">
        <div class="summary">
          <span><b>{entries.length}</b> entries</span>
          <span><b>{evalRows}</b> eval rows</span>
          <span>
            <b>{ruleChanges.reduce((n, c) => n + c.outstanding, 0)}</b>
            rules not shipped
          </span>
          <span class="spacer"></span>
          <button
            type="button"
            onclick={() => copyText(report)}
          >Copy report</button>
          <button
            type="button"
            onclick={() =>
              downloadText(
                `${detail.read_id || 'feedback'}.md`,
                report,
                'text/markdown',
              )}
          >Download</button>
        </div>

        <div class="golden">
          <span class="glabel">Accepted as targets to imitate in full:</span>
          {#each conversations as c (c.id)}
            <button
              type="button"
              class="gchip"
              class:on={golden.includes(c.id)}
              onclick={() => toggleGolden(c.id)}
            >{c.id}</button>
          {/each}
          {#if !golden.length}
            <span class="muted small">
              none — store the corrections, not the conversations
            </span>
          {/if}
        </div>

        <pre class="report">{report}</pre>
      </div>
    {:else}
      {#each conversations as c, i (c.id)}
        {#if tab === `conv-${i}`}
          <ReadConversation
            conv={c}
            {review}
            verdictKinds={detail.verdict_kinds}
            noteKinds={detail.note_kinds}
            entriesFor={(turn) => entriesFor(c.id, turn)}
            structural={structuralFor(c.id)}
            onsave={saveEntry}
            ondelete={deleteEntry}
          />
        {/if}
      {/each}
    {/if}

    {#if saveNote}
      <p class="savenote" class:bad={saveNote.startsWith('Could not')}>
        {saveNote}
      </p>
    {/if}
    {#if saving}<p class="muted small">Saving…</p>{/if}
  {/if}
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 1rem; }

  .top {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }
  .picker { display: flex; align-items: center; gap: 0.5rem; min-width: 0; }
  .picker label { color: var(--text-muted); font-size: 1.0625rem; }
  select {
    background: var(--bg-surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 0.4rem;
    padding: 0.3rem 0.5rem;
    font: inherit;
    font-size: 1.0625rem;
    max-width: 60ch;
  }

  .modes {
    margin-left: auto;
    display: flex;
    border: 1px solid var(--border);
    border-radius: 999px;
    overflow: hidden;
  }
  .modes button {
    border: none;
    background: transparent;
    color: var(--text-muted);
    padding: 0.25rem 0.9rem;
    font: inherit;
    font-size: 1.0625rem;
    cursor: pointer;
  }
  .modes button.on {
    background: var(--accent-dim);
    color: var(--accent);
    font-weight: 600;
  }

  .masthead h1 {
    margin: 0.2rem 0;
    font-size: 1.9rem;
    color: var(--text-strong);
  }
  .eyebrow {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.95rem;
    letter-spacing: 0.08em;
    text-transform: none;
    color: var(--text-muted);
  }
  .standfirst {
    margin: 0.3rem 0 0;
    font-size: 1.125rem;
    color: var(--text);
  }
  .caveat {
    margin-top: 0.7rem;
    padding: 0.55rem 0.8rem;
    border-left: 3px solid var(--warn);
    background: var(--warn-bg);
    border-radius: 0.35rem;
    font-size: 1.0625rem;
  }
  .nospec {
    margin: 0.5rem 0 0;
    color: var(--text-muted);
    font-size: 1.0625rem;
  }

  .tabs {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.4rem;
  }
  .tabs button {
    border: none;
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    font-size: 1.0625rem;
    padding: 0.25rem 0.7rem;
    border-radius: 0.4rem;
    cursor: pointer;
  }
  .tabs button:hover { color: var(--text-strong); }
  .tabs .count {
    margin-left: 0.3rem;
    padding: 0 0.4rem;
    border: 1px solid var(--accent);
    border-radius: 999px;
    color: var(--accent);
    font-size: 0.9rem;
    font-weight: 600;
  }
  .tabs button.on {
    color: var(--accent);
    background: var(--accent-dim);
    font-weight: 600;
  }

  .cards { display: flex; flex-direction: column; gap: 0.7rem; }
  .verdict {
    border: 1px solid var(--border);
    border-radius: 0.6rem;
    background: var(--bg-surface);
    padding: 0.7rem 0.9rem;
  }
  .vhead {
    display: flex;
    align-items: baseline;
    gap: 0.8rem;
    flex-wrap: wrap;
  }
  .vhead h3 {
    margin: 0;
    font-size: 1.15rem;
    color: var(--text-strong);
  }
  .verdict p { margin: 0.35rem 0 0; font-size: 1.0625rem; }
  .stamp {
    margin-left: auto;
    border-radius: 999px;
    padding: 0.1rem 0.6rem;
    font-size: 0.95rem;
    background: var(--neutral-bg);
    color: var(--neutral);
  }
  .stamp.pass { background: var(--pass-bg); color: var(--pass); }
  .stamp.fail { background: var(--fail-bg); color: var(--fail); }
  .stamp.new { background: var(--info-bg); color: var(--accent); }

  .closing { margin-top: 1rem; }
  .closing p { font-size: 1.0625rem; margin: 0 0 0.9rem; }

  .scroller { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  th, td {
    text-align: left;
    padding: 0.35rem 0.7rem;
    border-bottom: 1px solid var(--border);
    font-size: 1.0625rem;
  }
  th { color: var(--text-muted); font-weight: 600; }
  td.num, th.num {
    text-align: right;
    font-family: ui-monospace, 'Cascadia Code', monospace;
  }
  td.reading { color: var(--text-muted); }

  .feedback-pane { display: flex; flex-direction: column; gap: 0.8rem; }
  .summary {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    flex-wrap: wrap;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .summary b { color: var(--text-strong); }
  .summary .spacer { flex: 1; }
  .summary button {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    border-radius: 0.4rem;
    padding: 0.2rem 0.7rem;
    font: inherit;
    font-size: 1.0625rem;
    cursor: pointer;
  }
  .summary button:hover { border-color: var(--accent); color: var(--accent); }

  .golden {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .glabel { color: var(--text-muted); font-size: 1.0625rem; }
  .gchip {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    border-radius: 999px;
    padding: 0.1rem 0.65rem;
    font: inherit;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .gchip.on {
    border-color: var(--pass);
    background: var(--pass-bg);
    color: var(--pass);
  }

  .report {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 0.6rem;
    padding: 0.8rem 1rem;
    overflow-x: auto;
    white-space: pre-wrap;
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--text);
  }

  .muted { color: var(--text-muted); font-size: 1.0625rem; }
  .small { font-size: 0.95rem; }
  .error { color: var(--fail); font-size: 1.0625rem; }
  .savenote { color: var(--pass); font-size: 1.0625rem; }
  .savenote.bad { color: var(--fail); }
</style>
