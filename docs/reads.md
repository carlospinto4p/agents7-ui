# The Reads page

The Reads page shows recorded conversations and lets you correct them.
It is the one page that writes as well as shows.

## What it reads

A read is a folder of recordings written by `ConversationRecorder`,
under an agent's `docs/reads/<date>/`. The page finds every such folder
under the catalog and shows each conversation as a chat. Above the chat,
a block lists what the conversation ran with: the run, the context it
was given, what the agent already knew, and the prompt variants it drew.

## Recording a conversation

A script can record one with `ConversationRecorder`. Or hold one on the
**Chatter** page and press **Save as read**, which writes the same
recording under that agent's `docs/reads/`. Saving leaves the session
open, so you can save and keep chatting. An existing recording is never
overwritten. The confirmation links to the saved conversation.

The **Download** button beside it is different. It writes only
`{role, text}`, with no metrics, guard verdicts or context, so no read
can be built from it.

## Correcting a turn

Any turn can take a correction. The form works from the keyboard:

- it opens with the caret in its first field;
- ctrl+enter saves from any field and moves to the next turn's button;
- escape cancels;
- arrow up and down step between the turns' buttons.

Each conversation's tab shows how many corrections it has. A strip of
turn numbers above the thread marks the corrected turns and jumps to
one when clicked.

Corrections are saved to `feedback.yml` beside the recordings, in the
format `agents7 chat-feedback` reads. The rules to change, the eval rows
and the report all come from that file. The page edits it and keeps no
copy of its own.

## Addresses

`#/reads/conv-1?read=<path>` opens the read at `<path>` (relative to the
catalog root, URL-encoded) on its second conversation. The address bar
follows as you change tabs or pick another read, so you can copy it at
any point. `&conv=<id>` names a conversation by its recording's name
instead of its position.
